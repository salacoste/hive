"""Credential CRUD routes."""

import asyncio
import logging
import os
import re
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from aiohttp import web
from pydantic import SecretStr

from framework.credentials.models import CredentialKey, CredentialObject
from framework.credentials.store import CredentialStore
from framework.server.app import APP_KEY_CREDENTIAL_STORE, validate_agent_path

logger = logging.getLogger(__name__)

READINESS_BUNDLES: dict[str, dict[str, list[str]]] = {
    "local_pro_stack": {
        "required": [
            "BRAVE_SEARCH_API_KEY",
            "GITHUB_TOKEN",
            "TELEGRAM_BOT_TOKEN",
            "GOOGLE_ACCESS_TOKEN",
            "REDIS_URL",
            "DATABASE_URL",
        ],
        "optional": [
            "GOOGLE_MAPS_API_KEY",
            "GOOGLE_SEARCH_CONSOLE_TOKEN",
            "GOOGLE_APPLICATION_CREDENTIALS",
        ],
    }
}


def _get_store(request: web.Request) -> CredentialStore:
    return request.app[APP_KEY_CREDENTIAL_STORE]


def _credential_to_dict(cred: CredentialObject) -> dict:
    """Serialize a CredentialObject to JSON — never include secret values."""
    return {
        "credential_id": cred.id,
        "credential_type": str(cred.credential_type),
        "key_names": list(cred.keys.keys()),
        "created_at": cred.created_at.isoformat() if cred.created_at else None,
        "updated_at": cred.updated_at.isoformat() if cred.updated_at else None,
    }


def _normalize_provider_name(raw: str | None, fallback: str) -> str:
    text = (raw or fallback or "unknown").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    if not text:
        return "unknown"
    head = text.split("_", 1)[0]
    if head == "google":
        return "google"
    return head


def _credential_available(store: CredentialStore, cred_name: str, spec) -> bool:
    # Environment wins for speed and compatibility with scripts.
    if spec.env_var and os.environ.get(spec.env_var):
        return True

    cred_id = spec.credential_id or cred_name
    try:
        cred_obj = store.get_credential(cred_id, refresh_if_needed=False)
    except Exception:
        cred_obj = None
    if cred_obj is not None:
        try:
            if spec.credential_key and cred_obj.get_key(spec.credential_key):
                return True
        except Exception:
            pass
        return bool(store.get(cred_id))
    return False


def _env_var_available(store: CredentialStore, env_var: str, specs: dict[str, Any]) -> bool:
    if os.environ.get(env_var):
        return True
    for cred_name, spec in specs.items():
        if spec.env_var != env_var:
            continue
        if _credential_available(store, cred_name, spec):
            return True
    return False


async def handle_list_credentials(request: web.Request) -> web.Response:
    """GET /api/credentials — list all credential metadata (no secrets)."""
    store = _get_store(request)
    cred_ids = store.list_credentials()
    credentials = []
    for cid in cred_ids:
        cred = store.get_credential(cid, refresh_if_needed=False)
        if cred:
            credentials.append(_credential_to_dict(cred))
    return web.json_response({"credentials": credentials})


async def handle_get_credential(request: web.Request) -> web.Response:
    """GET /api/credentials/{credential_id} — get single credential metadata."""
    credential_id = request.match_info["credential_id"]
    store = _get_store(request)
    cred = store.get_credential(credential_id, refresh_if_needed=False)
    if cred is None:
        return web.json_response({"error": f"Credential '{credential_id}' not found"}, status=404)
    return web.json_response(_credential_to_dict(cred))


async def handle_save_credential(request: web.Request) -> web.Response:
    """POST /api/credentials — store a credential.

    Body: {"credential_id": "...", "keys": {"key_name": "value", ...}}
    """
    body = await request.json()

    credential_id = body.get("credential_id")
    keys = body.get("keys")

    if not credential_id or not keys or not isinstance(keys, dict):
        return web.json_response({"error": "credential_id and keys are required"}, status=400)

    # ADEN_API_KEY is stored in the encrypted store via key_storage module
    if credential_id == "aden_api_key":
        key = keys.get("api_key", "").strip()
        if not key:
            return web.json_response({"error": "api_key is required"}, status=400)

        from framework.credentials.key_storage import save_aden_api_key

        save_aden_api_key(key)

        # Immediately sync OAuth tokens from Aden (runs in executor because
        # _presync_aden_tokens makes blocking HTTP calls to the Aden server).
        try:
            from aden_tools.credentials import CREDENTIAL_SPECS

            from framework.credentials.validation import _presync_aden_tokens

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, _presync_aden_tokens, CREDENTIAL_SPECS)
        except Exception as exc:
            logger.warning("Aden token sync after key save failed: %s", exc)

        return web.json_response({"saved": "aden_api_key"}, status=201)

    store = _get_store(request)
    cred = CredentialObject(
        id=credential_id,
        keys={k: CredentialKey(name=k, value=SecretStr(v)) for k, v in keys.items()},
    )
    store.save_credential(cred)
    return web.json_response({"saved": credential_id}, status=201)


async def handle_delete_credential(request: web.Request) -> web.Response:
    """DELETE /api/credentials/{credential_id} — delete a credential."""
    credential_id = request.match_info["credential_id"]

    if credential_id == "aden_api_key":
        from framework.credentials.key_storage import delete_aden_api_key

        deleted = delete_aden_api_key()
        if not deleted:
            return web.json_response({"error": "Credential 'aden_api_key' not found"}, status=404)
        return web.json_response({"deleted": True})

    store = _get_store(request)
    deleted = store.delete_credential(credential_id)
    if not deleted:
        return web.json_response({"error": f"Credential '{credential_id}' not found"}, status=404)
    return web.json_response({"deleted": True})


async def handle_check_agent(request: web.Request) -> web.Response:
    """POST /api/credentials/check-agent — check and validate agent credentials.

    Uses the same ``validate_agent_credentials`` as agent startup:
    1. Presence — is the credential available (env, encrypted store, Aden)?
    2. Health check — does the credential actually work (lightweight HTTP call)?

    Body: {"agent_path": "...", "verify": true}
    """
    body = await request.json()
    agent_path = body.get("agent_path")
    verify = body.get("verify", True)

    if not agent_path:
        return web.json_response({"error": "agent_path is required"}, status=400)

    try:
        agent_path = str(validate_agent_path(agent_path))
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)

    try:
        from framework.credentials.setup import load_agent_nodes
        from framework.credentials.validation import (
            ensure_credential_key_env,
            validate_agent_credentials,
        )

        # Load env vars from shell config (same as runtime startup)
        ensure_credential_key_env()

        nodes = load_agent_nodes(agent_path)
        result = validate_agent_credentials(
            nodes, verify=verify, raise_on_error=False, force_refresh=True
        )

        # If any credential needs Aden, include ADEN_API_KEY as a first-class row
        if any(c.aden_supported for c in result.credentials):
            aden_key_status = {
                "credential_name": "Aden Platform",
                "credential_id": "aden_api_key",
                "env_var": "ADEN_API_KEY",
                "description": "API key from the Developers tab in Settings",
                "help_url": "https://hive.adenhq.com/",
                "tools": [],
                "node_types": [],
                "available": result.has_aden_key,
                "valid": None,
                "validation_message": None,
                "direct_api_key_supported": True,
                "aden_supported": True,  # renders with "Authorize" button to open Aden
                "credential_key": "api_key",
            }
            required = [aden_key_status] + [_status_to_dict(c) for c in result.credentials]
        else:
            required = [_status_to_dict(c) for c in result.credentials]

        return web.json_response(
            {
                "required": required,
                "has_aden_key": result.has_aden_key,
            }
        )
    except Exception as e:
        logger.exception(f"Error checking agent credentials: {e}")
        return web.json_response(
            {"error": "Internal server error while checking credentials"},
            status=500,
        )


async def handle_credentials_readiness(request: web.Request) -> web.Response:
    """GET /api/credentials/readiness — bundle-first credential readiness snapshot."""
    bundle_name = (request.query.get("bundle") or "local_pro_stack").strip()
    bundle = READINESS_BUNDLES.get(bundle_name)
    if bundle is None:
        return web.json_response(
            {
                "error": f"Unknown readiness bundle: {bundle_name}",
                "available_bundles": sorted(READINESS_BUNDLES.keys()),
            },
            status=400,
        )

    try:
        from aden_tools.credentials import CREDENTIAL_SPECS
        from framework.credentials.validation import ensure_credential_key_env

        ensure_credential_key_env()
    except Exception:
        return web.json_response(
            {"error": "Failed to load credential specs for readiness report"},
            status=500,
        )

    store = _get_store(request)
    required_vars = [str(v).strip() for v in bundle.get("required", []) if str(v).strip()]
    optional_vars = [str(v).strip() for v in bundle.get("optional", []) if str(v).strip()]

    required_rows = [
        {"env_var": env_var, "available": _env_var_available(store, env_var, CREDENTIAL_SPECS)}
        for env_var in required_vars
    ]
    optional_rows = [
        {"env_var": env_var, "available": _env_var_available(store, env_var, CREDENTIAL_SPECS)}
        for env_var in optional_vars
    ]

    missing_required = [row["env_var"] for row in required_rows if not row["available"]]
    missing_optional = [row["env_var"] for row in optional_rows if not row["available"]]

    provider_rows: dict[str, dict[str, Any]] = {}
    for cred_name, spec in CREDENTIAL_SPECS.items():
        env_var = str(spec.env_var or "").strip()
        if not env_var:
            continue
        provider_hint = spec.aden_provider_name or spec.credential_group or spec.credential_id
        provider = _normalize_provider_name(provider_hint, fallback=cred_name)
        row = provider_rows.setdefault(
            provider,
            {
                "provider": provider,
                "credentials_total": 0,
                "credentials_available": 0,
                "credentials_missing": 0,
                "env_vars": set(),
                "missing_env_vars": set(),
            },
        )
        if env_var in row["env_vars"]:
            continue
        row["env_vars"].add(env_var)
        row["credentials_total"] += 1
        available = _env_var_available(store, env_var, CREDENTIAL_SPECS)
        if available:
            row["credentials_available"] += 1
        else:
            row["credentials_missing"] += 1
            row["missing_env_vars"].add(env_var)

    providers = []
    for provider in sorted(provider_rows.keys()):
        row = provider_rows[provider]
        providers.append(
            {
                "provider": provider,
                "credentials_total": int(row["credentials_total"]),
                "credentials_available": int(row["credentials_available"]),
                "credentials_missing": int(row["credentials_missing"]),
                "env_vars": sorted(row["env_vars"]),
                "missing_env_vars": sorted(row["missing_env_vars"]),
            }
        )

    summary = {
        "ready": len(missing_required) == 0,
        "required_total": len(required_rows),
        "required_available": len(required_rows) - len(missing_required),
        "required_missing": len(missing_required),
        "optional_total": len(optional_rows),
        "optional_available": len(optional_rows) - len(missing_optional),
        "optional_missing": len(missing_optional),
    }
    return web.json_response(
        {
            "bundle": bundle_name,
            "required": required_rows,
            "optional": optional_rows,
            "missing": {"required": missing_required, "optional": missing_optional},
            "summary": summary,
            "providers": providers,
            "checked_at": datetime.now(UTC).isoformat(),
        }
    )


def _status_to_dict(c) -> dict:
    """Convert a CredentialStatus to the JSON dict expected by the frontend."""
    return {
        "credential_name": c.credential_name,
        "credential_id": c.credential_id,
        "env_var": c.env_var,
        "description": c.description,
        "help_url": c.help_url,
        "tools": c.tools,
        "node_types": c.node_types,
        "available": c.available,
        "direct_api_key_supported": c.direct_api_key_supported,
        "aden_supported": c.aden_supported,
        "credential_key": c.credential_key,
        "valid": c.valid,
        "validation_message": c.validation_message,
        "alternative_group": c.alternative_group,
    }


def _resolve_spec(credential_id: str, specs: dict[str, Any]) -> tuple[str, Any] | None:
    text = (credential_id or "").strip().lower()
    if not text:
        return None
    if text in specs:
        return text, specs[text]
    for name, spec in specs.items():
        if (spec.credential_id or name).strip().lower() == text:
            return name, spec
    return None


def _default_credential_name(credential_id: str) -> str:
    return credential_id.replace("_", " ").strip().title()


async def handle_list_specs(request: web.Request) -> web.Response:
    """GET /api/credentials/specs — list credential specs for UI."""
    try:
        from aden_tools.credentials import CREDENTIAL_SPECS
        from framework.credentials.key_storage import load_aden_api_key
        from framework.credentials.validation import ensure_credential_key_env

        ensure_credential_key_env()
        load_aden_api_key()
    except Exception:
        return web.json_response(
            {"error": "Failed to load credential specs"},
            status=500,
        )

    store = _get_store(request)
    specs_payload: list[dict[str, Any]] = []
    now_iso = datetime.now(UTC).isoformat()

    for cred_name, spec in sorted(
        CREDENTIAL_SPECS.items(),
        key=lambda kv: (kv[1].credential_id or kv[0]).lower(),
    ):
        cred_id = spec.credential_id or cred_name
        available = _credential_available(store, cred_name, spec)
        accounts: list[dict[str, Any]] = []

        # Local account projection: a stored credential or env var means this
        # provider is connected even without Aden OAuth state.
        if available:
            accounts.append(
                {
                    "provider": _normalize_provider_name(spec.aden_provider_name, cred_id),
                    "alias": "default",
                    "identity": {"connected_at": now_iso},
                    "source": "local",
                    "credential_id": cred_id,
                }
            )

        specs_payload.append(
            {
                "credential_name": _default_credential_name(cred_id),
                "credential_id": cred_id,
                "env_var": spec.env_var,
                "description": spec.description or "",
                "help_url": spec.help_url or "",
                "api_key_instructions": spec.api_key_instructions or "",
                "tools": list(spec.tools or []),
                "aden_supported": bool(spec.aden_supported),
                "direct_api_key_supported": bool(spec.direct_api_key_supported),
                "credential_key": spec.credential_key or "access_token",
                "credential_group": spec.credential_group or "",
                "available": bool(available),
                "accounts": accounts,
            }
        )

    return web.json_response(
        {
            "specs": specs_payload,
            "has_aden_key": bool(os.environ.get("ADEN_API_KEY")),
        }
    )


async def handle_resync_credentials(request: web.Request) -> web.Response:
    """POST /api/credentials/resync — best-effort sync of Aden-backed creds."""
    try:
        from aden_tools.credentials import CREDENTIAL_SPECS
        from framework.credentials.aden.client import AdenClientConfig, AdenCredentialClient
        from framework.credentials.key_storage import load_aden_api_key
        from framework.credentials.validation import _presync_aden_tokens, ensure_credential_key_env

        ensure_credential_key_env()
        load_aden_api_key()
    except Exception:
        return web.json_response(
            {"error": "Failed to initialize credential resync"},
            status=500,
        )

    if not os.environ.get("ADEN_API_KEY"):
        return web.json_response({"synced": False, "accounts_by_provider": {}})

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _presync_aden_tokens, CREDENTIAL_SPECS)
    except Exception as exc:
        logger.warning("Credential resync pre-sync failed: %s", exc)

    accounts_by_provider: dict[str, list[dict[str, Any]]] = defaultdict(list)
    client = AdenCredentialClient(
        AdenClientConfig(base_url=os.environ.get("ADEN_BASE_URL", "https://api.adenhq.com"))
    )
    try:
        integrations = client.list_integrations()
        for info in integrations:
            provider_key = _normalize_provider_name(info.provider, info.provider)
            base_account = {
                "provider": provider_key,
                "alias": info.alias or "default",
                "identity": {
                    "email": info.email or "",
                    "status": info.status or "",
                    "integration_id": info.integration_id or "",
                },
                "source": "aden",
                "credential_id": provider_key,
            }

            # Keep provider-native key.
            accounts_by_provider[provider_key].append(base_account)

            # Also map by matching credential_id so frontend lookups by
            # spec.credential_id resolve immediately.
            for cred_name, spec in CREDENTIAL_SPECS.items():
                cred_id = spec.credential_id or cred_name
                spec_provider_key = _normalize_provider_name(spec.aden_provider_name, cred_id)
                if spec_provider_key != provider_key:
                    continue
                mapped = dict(base_account)
                mapped["credential_id"] = cred_id
                accounts_by_provider[cred_id].append(mapped)
    finally:
        client.close()

    return web.json_response(
        {
            "synced": True,
            "accounts_by_provider": {k: v for k, v in sorted(accounts_by_provider.items())},
        }
    )


async def handle_validate_key(request: web.Request) -> web.Response:
    """POST /api/credentials/validate-key — lightweight API key validation."""
    body = await request.json()
    provider_id = str(body.get("provider_id") or "").strip()
    api_key = str(body.get("api_key") or "").strip()
    if not provider_id or not api_key:
        return web.json_response({"error": "provider_id and api_key are required"}, status=400)

    try:
        from aden_tools.credentials import CREDENTIAL_SPECS, check_credential_health
    except Exception:
        return web.json_response({"valid": None, "message": "Credential checker unavailable"})

    resolved = _resolve_spec(provider_id, CREDENTIAL_SPECS)
    if resolved is None:
        return web.json_response({"valid": None, "message": f"Unknown provider: {provider_id}"})

    cred_name, spec = resolved
    try:
        result = check_credential_health(
            cred_name,
            api_key,
            health_check_endpoint=spec.health_check_endpoint,
            health_check_method=spec.health_check_method,
        )
        return web.json_response({"valid": bool(result.valid), "message": result.message})
    except Exception as exc:
        logger.warning("Credential key validation failed for provider=%s: %s", provider_id, exc)
        return web.json_response({"valid": None, "message": f"Could not verify key: {exc}"})


def register_routes(app: web.Application) -> None:
    """Register credential routes on the application."""
    # Static routes must be registered BEFORE the {credential_id} wildcard.
    app.router.add_get("/api/credentials/specs", handle_list_specs)
    app.router.add_post("/api/credentials/resync", handle_resync_credentials)
    app.router.add_post("/api/credentials/validate-key", handle_validate_key)
    app.router.add_post("/api/credentials/check-agent", handle_check_agent)
    app.router.add_get("/api/credentials/readiness", handle_credentials_readiness)
    app.router.add_get("/api/credentials", handle_list_credentials)
    app.router.add_post("/api/credentials", handle_save_credential)
    app.router.add_get("/api/credentials/{credential_id}", handle_get_credential)
    app.router.add_delete("/api/credentials/{credential_id}", handle_delete_credential)
