# Hive Local Production Runbook

## Autonomous Factory Docs

For full platform design and rollout (multi-stack coding factory), use:

- `docs/autonomous-factory/README.md`
- `docs/autonomous-factory/01-target-architecture.md`
- `docs/autonomous-factory/02-access-and-security.md`
- `docs/autonomous-factory/03-onboarding-repositories.md`
- `docs/autonomous-factory/04-operations-runbook.md`
- `docs/autonomous-factory/05-rollout-plan.md`
- `docs/autonomous-factory/06-mcp-server-bundle.md`
- `docs/autonomous-factory/07-access-setup-playbook.md`
- `docs/autonomous-factory/20-multi-project-autonomy-blueprint.md`
- `docs/autonomous-factory/templates/repo-automation-manifest.yaml`
- `docs/ops/acceptance-automation-map.md`

## 1) Configure secrets

1. Copy required entries from `.env.mcp.example` into `.env` and fill values.
2. Keep `.env` local-only (do not commit).
3. Ensure core model keys exist:
   - `ANTHROPIC_API_KEY`
   - `GEMINI_API_KEY`
   - `ZAI_API_KEY`
   - `OPENAI_API_KEY`
   - Optional bases: `*_API_BASE`

### Telegram (MCP tools)

Set in `.env`:

```bash
TELEGRAM_BOT_TOKEN=...
```

Quick token validation from the running container:

```bash
docker compose exec -T hive-core sh -lc 'uv run python - <<\"PY\"
import json, os, urllib.request
token=os.environ.get("TELEGRAM_BOT_TOKEN","")
url=f"https://api.telegram.org/bot{token}/getMe"
with urllib.request.urlopen(url, timeout=20) as r:
    data=json.loads(r.read().decode("utf-8"))
print("ok=", data.get("ok"))
print("username=", data.get("result", {}).get("username"))
PY'
```

Get chat IDs (after sending at least one message to your bot):

```bash
docker compose exec -T hive-core sh -lc 'uv run python - <<\"PY\"
import json, os, urllib.request
token=os.environ.get("TELEGRAM_BOT_TOKEN","")
url=f"https://api.telegram.org/bot{token}/getUpdates"
with urllib.request.urlopen(url, timeout=20) as r:
    data=json.loads(r.read().decode("utf-8"))
ids=[]
for u in data.get("result", []):
    msg=u.get("message") or u.get("edited_message") or {}
    chat=(msg.get("chat") or {})
    cid=chat.get("id")
    if cid is not None and cid not in ids:
        ids.append(cid)
print("chat_ids=", ids)
PY'
```

### Google OAuth (full setup + auto-refresh)

Required for stable Docs/Sheets/Gmail/Calendar:

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REFRESH_TOKEN`
- `GOOGLE_ACCESS_TOKEN` (auto-updated by refresh script)

Generate consent URL:

```bash
./scripts/hive_ops_run.sh uv run --no-project python scripts/google_oauth_token_manager.py auth-url
```

Exchange auth code to tokens:

```bash
./scripts/hive_ops_run.sh uv run --no-project python scripts/google_oauth_token_manager.py exchange --code "<CODE_FROM_REDIRECT>"
```

Manual refresh + apply to runtime:

```bash
./scripts/google_token_auto_refresh.sh
```

Optional (only when explicitly needed) recreate `hive-core` after refresh:

```bash
./scripts/google_token_auto_refresh.sh --recreate
```

Container-native automatic refresh (every 45 minutes) is enabled via
`google-token-refresher` service in `docker-compose.yml`.

Implementation note:

- `google-token-refresher` now runs from the same `hive-core` image
  (no host `./scripts` bind-mount dependency).
- inherited API healthcheck is disabled for this sidecar (it does not serve `:8787`);
  use `docker compose logs google-token-refresher` for runtime verification.
- refresher writes both:
  - access token: `/data/storage/secrets/google_access_token`
  - expiry metadata: `/data/storage/secrets/google_access_token.meta.json`
    (used by runtime auto-refresh/freshness checks).

Ensure it is running:

```bash
docker compose ps google-token-refresher
docker compose logs --tail=80 google-token-refresher
```

Run Google MCP smoke checks:

```bash
# Read-only checks (calendar + gmail)
./scripts/hive_ops_run.sh uv run --no-project python scripts/google_mcp_smoke_test.py --dotenv .env

# Full checks (includes doc/sheet creation)
./scripts/hive_ops_run.sh uv run --no-project python scripts/google_mcp_smoke_test.py --dotenv .env --write
```

Google token freshness thresholds for health checks (`scripts/mcp_health_summary.py`):

- `HIVE_GOOGLE_TOKEN_WARN_TTL_SECONDS` (default `900`)
- `HIVE_GOOGLE_TOKEN_CRITICAL_TTL_SECONDS` (default `120`)

When token freshness enters `critical`, Google check is marked degraded even if token is still technically valid.

Consecutive refresh-failure alerting (`google-token-refresher`):

- `GOOGLE_REFRESH_ALERT_ENABLED` (default `1`)
- `GOOGLE_REFRESH_ALERT_FAILURE_THRESHOLD` (default `3`)
- `GOOGLE_REFRESH_ALERT_COOLDOWN_SECONDS` (default `3600`)
- `GOOGLE_REFRESH_ALERT_CHAT_IDS` (comma-separated Telegram chat ids)
- `HIVE_TELEGRAM_TEST_CHAT_ID` (single fallback chat id for container smoke tests)

State file:

- `/data/storage/secrets/google_refresh_state.json`
  - tracks `consecutive_failures`, `total_failures`, `last_success_at`,
    `last_failure_at`, `last_alert_at`, `last_error`.

Rotation / re-auth SOP:

- `docs/ops/google-oauth-rotation-runbook.md`

Google canary artifacts:

- `docs/ops/google-canary/latest.json`
- `docs/ops/google-canary/latest.md`

Run one canary cycle manually:

```bash
./scripts/hive_ops_run.sh uv run --no-project python scripts/google_mcp_canary.py --dotenv .env
```

Container-only baseline:

- do not rely on host `launchd/cron`;
- run canary manually from container (command above) or wire it into container scheduler policy.

Discover Telegram chat id(s) for refresh alerts:

```bash
./scripts/hive_ops_run.sh uv run --no-project python scripts/telegram_chat_id_probe.py --dotenv .env --attempts 3 --timeout 10
# auto-write GOOGLE_REFRESH_ALERT_CHAT_IDS + HIVE_TELEGRAM_TEST_CHAT_ID when found
./scripts/hive_ops_run.sh uv run --no-project python scripts/telegram_chat_id_probe.py --dotenv .env --attempts 3 --timeout 10 --write-alert-env
```

## 2) Audit credentials

Priority integrations:

```bash
./scripts/hive_ops_run.sh uv run --no-project python scripts/audit_mcp_credentials.py --priority
```

Target stack (web search + scrape + telegram + github + google + redis/postgres):

```bash
./scripts/hive_ops_run.sh uv run --no-project python scripts/audit_mcp_credentials.py --bundle local_pro_stack
```

All credential specs:

```bash
./scripts/hive_ops_run.sh uv run --no-project python scripts/audit_mcp_credentials.py
```

Per-tool check:

```bash
./scripts/hive_ops_run.sh uv run --no-project python scripts/audit_mcp_credentials.py --tools web_search github_create_issue
```

Requested stack check:

```bash
./scripts/hive_ops_run.sh uv run --no-project python scripts/audit_mcp_credentials.py \
  --tools web_search web_scrape github_create_issue telegram_send_message \
          google_docs_get_document google_sheets_get_values \
          gmail_list_messages calendar_list_events
```

## 3) Build and run locally

```bash
docker compose down --remove-orphans
docker compose up -d --build
```

Build performance notes:

- Dockerfile uses cache mounts for `npm` and `uv`, plus two-phase `uv sync`
  (dependencies first, workspace packages second).
- Playwright browsers are installed into shared path `/ms-playwright`
  (`PLAYWRIGHT_BROWSERS_PATH`) so non-root runtime (`hiveuser`) can launch Chromium.
- First clean build is still heavy; repeated builds are much faster when only code changes.
- For fastest edit loop, prefer `./scripts/hive_hot_sync.sh` instead of full rebuild.

Optional compiler/toolchain profiles (on demand):

- Build args are supported directly by `hive-core` image:
  - `HIVE_DOCKER_INSTALL_NODE=0|1`
  - `HIVE_DOCKER_INSTALL_GO=0|1`
  - `HIVE_DOCKER_INSTALL_RUST=0|1`
  - `HIVE_DOCKER_INSTALL_JAVA=0|1`
- This avoids baking every compiler into every local image by default.

Toolchain planning (dry-run):

```bash
# detect from local workspace path
./scripts/hive_ops_run.sh uv run --no-project python scripts/detect_project_toolchains.py \
  --workspace /path/to/repository

# or detect directly from remote GitHub repo
./scripts/hive_ops_run.sh uv run --no-project python scripts/detect_project_toolchains.py \
  --repository https://github.com/salacoste/mcp-n8n-workflow-builder
```

Apply toolchain profile with explicit confirmation token:

```bash
# 1) preview (prints required --confirm token, e.g. APPLY_NODE_6AA83D6E)
./scripts/apply_hive_toolchain_profile.sh \
  --repository https://github.com/salacoste/mcp-n8n-workflow-builder

# 2) apply only after explicit confirmation
./scripts/apply_hive_toolchain_profile.sh \
  --repository https://github.com/salacoste/mcp-n8n-workflow-builder \
  --apply --confirm APPLY_NODE_6AA83D6E
```

Safety contract:

- `apply_hive_toolchain_profile.sh` never rebuilds by default (dry-run first).
- Rebuild is executed only with `--apply` and exact `--confirm <token>`.

Fast local iteration (no rebuild on every code/config edit):

```bash
# Sync changed runtime files into running container and restart hive-core
./scripts/hive_hot_sync.sh

# Or sync specific files only
./scripts/hive_hot_sync.sh tools/mcp_server.py core/framework/agents/queen/mcp_servers.json
```

Why this mode:

- Avoids expensive full image rebuilds for small runtime changes.
- Keeps your current container image stable and only updates selected files.
- Useful for MCP config/server script iteration.

Container-only ops runner (fast repeatable checks on workspace bind mount):

```bash
# Generic pattern:
./scripts/hive_ops_run.sh <command...>

# Backlog / governance examples:
./scripts/hive_ops_run.sh uv run --no-project python scripts/validate_backlog_markdown.py
./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status.py --json
./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status_artifact.py
./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status_hygiene.py --keep 50 --yes

# Targeted test example:
./scripts/hive_ops_run.sh uv run pytest core/tests/test_queen_memory.py -q
```

Notes:

- `hive_ops_run.sh` uses `docker compose --profile ops run ... hive-ops` with persistent cache dirs:
  - `.cache/uv`
  - `.cache/uvproj`
- This avoids repeated heavy one-off `docker run` environment setup while keeping execution fully containerized.

One-shot setup:

```bash
./scripts/setup_local_pro.sh
```

Health checks:

```bash
docker compose ps
curl -sS http://localhost:${HIVE_CORE_PORT:-8787}/api/health
```

Infrastructure checks:

```bash
docker compose ps
docker compose exec -T hive-core sh -lc 'getent hosts redis postgres'
```

## 4) Validate model routing and fallback

Effective routing is configured in:

- `core/framework/model_routing.py`
- `~/.hive/configuration.json` (host and container)

Manual run examples:

```bash
# implementation profile: openai/gemini -> openai/glm fallback
./hive run exports/<agent> --input '{"ping":"pong"}' --model-profile implementation

# review profile: gpt-5.3-codex
./hive validate exports/<agent> --model-profile review_validation
```

## 5) Export full MCP inventory

```bash
./scripts/hive_ops_run.sh uv run --no-project python scripts/export_mcp_inventory.py
```

## 6) Autonomous Ops Status and Backups

Auto-next fallback policy (for autonomous review/validation orchestration):

```bash
# strict mode (default): auto-next returns explicit error on GitHub evaluate issues
export HIVE_AUTONOMOUS_AUTO_NEXT_FALLBACK=error

# deferred mode: auto-next returns 202 + manual action when GitHub evaluate is unavailable
export HIVE_AUTONOMOUS_AUTO_NEXT_FALLBACK=manual_pending
```

Autonomous pipeline observability snapshot:

```bash
curl -sS http://localhost:${HIVE_CORE_PORT:-8787}/api/autonomous/ops/status | jq .
# scoped to a single project
curl -sS "http://localhost:${HIVE_CORE_PORT:-8787}/api/autonomous/ops/status?project_id=default" | jq .
# include active run details
curl -sS "http://localhost:${HIVE_CORE_PORT:-8787}/api/autonomous/ops/status?project_id=default&include_runs=true" | jq .
```

Operator health check (threshold-based gate):

```bash
# profile-based defaults (local|dev|staging|prod); default is local
HIVE_AUTONOMOUS_HEALTH_PROFILE=local ./scripts/autonomous_ops_health_check.sh
HIVE_AUTONOMOUS_HEALTH_PROFILE=prod ./scripts/autonomous_ops_health_check.sh

# strict manual defaults: no stuck, no no-progress projects, loop must be fresh
./scripts/autonomous_ops_health_check.sh

# scoped to one project with custom limits
HIVE_AUTONOMOUS_HEALTH_PROJECT_ID=default \
HIVE_AUTONOMOUS_HEALTH_MAX_STUCK_RUNS=1 \
HIVE_AUTONOMOUS_HEALTH_MAX_NO_PROGRESS_PROJECTS=1 \
./scripts/autonomous_ops_health_check.sh
```

SLO policy and drill cadence are documented in:

- `docs/ops/autonomous-slo-policy.md`
- `docs/ops/phase-a-closure-checklist.md`
- `docs/ops/phase-b-closure-checklist.md`
- `docs/ops/phase-c-closure-checklist.md`
- `docs/ops/phase-d-closure-checklist.md`
- `docs/ops/phase-e-closure-checklist.md`
- `docs/ops/final-go-live-acceptance-pack.md`

Stale run remediation (safe default is dry-run):

```bash
# preview stale active runs (no writes)
./scripts/autonomous_remediate_stale_runs.sh

# apply remediation (terminalize stale runs as escalated)
HIVE_AUTONOMOUS_REMEDIATE_DRY_RUN=false \
HIVE_AUTONOMOUS_REMEDIATE_CONFIRM=true \
HIVE_AUTONOMOUS_REMEDIATE_ACTION=escalated \
HIVE_AUTONOMOUS_REMEDIATE_OLDER_THAN_SECONDS=1800 \
./scripts/autonomous_remediate_stale_runs.sh
```

Remediation API (for automation):

```bash
curl -sS -X POST http://localhost:${HIVE_CORE_PORT:-8787}/api/autonomous/ops/remediate-stale \
  -H 'Content-Type: application/json' \
  -d '{"dry_run":true,"project_id":"default","older_than_seconds":1800,"max_runs":100}' | jq .
```

Runtime parity check (container vs expected API contract):

```bash
./scripts/check_runtime_parity.sh
```

If parity check fails on `ops/status` contract fields (`alerts`, `loop`, `summary.include_runs`),
rebuild/redeploy `hive-core` from current repo state and rerun the check.

Full autonomous ops drill (recommended before/after prod changes):

```bash
# full drill (scoped to default project by default)
./scripts/autonomous_ops_drill.sh

# local/offline-friendly mode (skip API/loop smoke, keep backup+restore dry-run)
HIVE_AUTONOMOUS_DRILL_SKIP_NETWORK=true \
HIVE_AUTONOMOUS_DRILL_SKIP_LOOP_SMOKE=true \
./scripts/autonomous_ops_drill.sh

# custom project scope for loop smoke
HIVE_AUTONOMOUS_DRILL_PROJECT_IDS=default,my-project-id ./scripts/autonomous_ops_drill.sh
```

Acceptance gate scheduler (macOS launchd):

```bash
# install hourly acceptance gate (default 3600s)
./scripts/install_acceptance_gate_launchd.sh

# preset profiles
HIVE_ACCEPTANCE_PROFILE=balanced ./scripts/install_acceptance_gate_launchd.sh
HIVE_ACCEPTANCE_PROFILE=strict ./scripts/install_acceptance_gate_launchd.sh

# custom interval (seconds, >=300)
HIVE_ACCEPTANCE_GATE_INTERVAL=1800 ./scripts/install_acceptance_gate_launchd.sh

# strict historical policy in scheduler
HIVE_ACCEPTANCE_ENFORCE_HISTORY=true \
HIVE_ACCEPTANCE_HISTORY_MAX_FAIL=0 \
HIVE_ACCEPTANCE_HISTORY_MIN_PASS_RATE=1.0 \
./scripts/install_acceptance_gate_launchd.sh

# status / uninstall
./scripts/status_acceptance_gate_launchd.sh
./scripts/uninstall_acceptance_gate_launchd.sh
```

Acceptance gate scheduler (portable cron fallback):

```bash
# install hourly acceptance gate
./scripts/install_acceptance_gate_cron.sh

# preset profiles
HIVE_ACCEPTANCE_PROFILE=balanced ./scripts/install_acceptance_gate_cron.sh
HIVE_ACCEPTANCE_PROFILE=strict ./scripts/install_acceptance_gate_cron.sh

# custom cron expression
HIVE_ACCEPTANCE_GATE_CRON_EXPR="*/30 * * * *" ./scripts/install_acceptance_gate_cron.sh

# status / uninstall
./scripts/status_acceptance_gate_cron.sh
./scripts/uninstall_acceptance_gate_cron.sh
```

Docker-native scheduler sidecar (primary container-only mode):

```bash
# start scheduler container
docker compose up -d hive-scheduler

# live logs
docker compose logs -f hive-scheduler

# verify health
docker compose ps hive-scheduler

# stop scheduler container
docker compose stop hive-scheduler
```

Implementation note:

- `hive-scheduler` now runs from the same `hive-core` image
  (no host `./scripts` bind-mount dependency).

Key env knobs (`.env`):

- `HIVE_SCHEDULER_AUTONOMOUS_INTERVAL_SECONDS` (default `120`)
- `HIVE_SCHEDULER_MAX_STEPS_PER_PROJECT` (default `3`)
- `HIVE_SCHEDULER_PROJECT_IDS` (comma-separated, empty = all projects)
- `HIVE_SCHEDULER_SESSION_ID` (single session binding for all scheduler ticks)
- `HIVE_SCHEDULER_SESSION_ID_BY_PROJECT_JSON` (project->session map JSON, preferred)
- `HIVE_SCHEDULER_ACCEPTANCE_INTERVAL_SECONDS` (default `3600`)
- `HIVE_SCHEDULER_ACCEPTANCE_PROJECT_ID` (default `default`)
- `HIVE_SCHEDULER_STATE_PATH` (default `/tmp/hive_scheduler_state.json`)
- `HIVE_SCHEDULER_HEALTH_STALE_SECONDS` (default `180`)

Container-only portability baseline (recommended on every new machine):

```bash
# keep host schedulers disabled
./scripts/uninstall_autonomous_loop_launchd.sh || true
./scripts/uninstall_acceptance_gate_launchd.sh || true
./scripts/uninstall_acceptance_weekly_launchd.sh || true
./scripts/uninstall_autonomous_loop_cron.sh || true
./scripts/uninstall_acceptance_gate_cron.sh || true
./scripts/uninstall_acceptance_weekly_cron.sh || true

# run only docker scheduler
docker compose up -d hive-scheduler
```

Weekly maintenance scheduler (macOS launchd):

```bash
# install weekly cadence (default 604800s / 7 days)
./scripts/install_acceptance_weekly_launchd.sh

# custom cadence (>= 86400)
HIVE_ACCEPTANCE_WEEKLY_INTERVAL=172800 ./scripts/install_acceptance_weekly_launchd.sh

# status / uninstall
./scripts/status_acceptance_weekly_launchd.sh
./scripts/uninstall_acceptance_weekly_launchd.sh
```

Weekly maintenance scheduler (portable cron fallback):

```bash
# install weekly cadence (default: Monday 04:00)
./scripts/install_acceptance_weekly_cron.sh

# custom cron expression
HIVE_ACCEPTANCE_WEEKLY_CRON_EXPR="0 3 * * 0" ./scripts/install_acceptance_weekly_cron.sh

# status / uninstall
./scripts/status_acceptance_weekly_cron.sh
./scripts/uninstall_acceptance_weekly_cron.sh
```

Acceptance artifact lifecycle knobs:

- `HIVE_ACCEPTANCE_PROFILE` (`balanced` default, `strict` enables historical guard by default)
- `HIVE_ACCEPTANCE_REPORT_KEEP` (default `50`)
- `HIVE_ACCEPTANCE_REPORT_PRUNE_APPLY` (`false` by default, preview-only mode)
- `HIVE_ACCEPTANCE_DIGEST_DAYS` (default `7`)
- `HIVE_ACCEPTANCE_DIGEST_LIMIT` (default `20`)
- `HIVE_ACCEPTANCE_DIGEST_JSON_PATH` (default `docs/ops/acceptance-reports/digest-latest.json`)
- `HIVE_ACCEPTANCE_DIGEST_MD_PATH` (default `docs/ops/acceptance-reports/digest-latest.md`)
- `HIVE_ACCEPTANCE_ENFORCE_HISTORY` (`false` by default; set `true` to enforce historical thresholds in gate)
- `HIVE_ACCEPTANCE_HISTORY_MAX_FAIL` (default `0`)
- `HIVE_ACCEPTANCE_HISTORY_MIN_PASS_RATE` (default `1.0`)
- `HIVE_ACCEPTANCE_SUMMARY_JSON` (`false` default; `true` prints JSON summary in gate output)
- `HIVE_ACCEPTANCE_RUN_SELF_CHECK` (`false` default; `true` runs `acceptance_toolchain_self_check.sh` inside gate)
- `HIVE_ACCEPTANCE_RUN_DOCS_NAV_CHECK` (`false` default; `true` runs docs navigation check inside gate)
- `HIVE_ACCEPTANCE_RUN_PRESET_SMOKE` (`false` default; `true` runs preset smoke matrix inside gate)
- `HIVE_ACCEPTANCE_RUN_DELIVERY_E2E_SMOKE` (`false` default; `true` runs real/template autonomous delivery e2e smoke)

Acceptance gate toggles quick reference:

- `HIVE_ACCEPTANCE_SKIP_CHECKLIST=true`: skip heavy local checklist stage.
- `HIVE_ACCEPTANCE_SKIP_TELEGRAM=true`: skip Telegram bridge status probe.
- `HIVE_ACCEPTANCE_ENFORCE_HISTORY=true`: enable historical regression guard.
- `HIVE_ACCEPTANCE_SUMMARY_JSON=true`: output JSON summary snapshot.
- `HIVE_ACCEPTANCE_RUN_SELF_CHECK=true`: run full acceptance toolchain self-check first.
- `HIVE_ACCEPTANCE_RUN_DOCS_NAV_CHECK=true`: enforce docs navigation integrity in gate.
- `HIVE_ACCEPTANCE_RUN_PRESET_SMOKE=true`: run preset matrix smoke (`fast|strict|full`) in gate.
- `HIVE_ACCEPTANCE_RUN_DELIVERY_E2E_SMOKE=true`: run autonomous delivery e2e smoke (`real_repo` + `template_repo`).

Weekly trend digest:

```bash
./scripts/hive_ops_run.sh uv run --no-project python scripts/acceptance_report_digest.py --days 7 --limit 20

# optional artifact export
./scripts/hive_ops_run.sh uv run --no-project python scripts/acceptance_report_digest.py --days 7 --limit 20 \
  --out-json docs/ops/acceptance-reports/digest-latest.json \
  --out-md docs/ops/acceptance-reports/digest-latest.md

# optional strict history guard
./scripts/hive_ops_run.sh uv run --no-project python scripts/acceptance_report_regression_guard.py \
  --days 7 --max-fail 0 --min-pass-rate 1.0

# one-command weekly maintenance
./scripts/acceptance_weekly_maintenance.sh

# compact ops snapshot from latest artifacts
./scripts/hive_ops_run.sh uv run --no-project python scripts/acceptance_ops_summary.py
./scripts/hive_ops_run.sh uv run --no-project python scripts/acceptance_ops_summary.py --json

# scheduler state + recent logs snapshot
./scripts/acceptance_scheduler_snapshot.sh

# acceptance automation integrity check
./scripts/acceptance_toolchain_self_check.sh

# include preset matrix smoke in self-check
HIVE_ACCEPTANCE_SELF_CHECK_RUN_PRESET_SMOKE=true ./scripts/acceptance_toolchain_self_check.sh

# include live runtime parity check in self-check (requires running core API)
HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=true ./scripts/acceptance_toolchain_self_check.sh

# full deep self-check profile (preset smoke + runtime parity)
HIVE_ACCEPTANCE_SELF_CHECK_RUN_PRESET_SMOKE=true \
HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=true \
./scripts/acceptance_toolchain_self_check.sh

# same full deep profile via wrapper
./scripts/acceptance_toolchain_self_check_deep.sh

# note: self-check now auto-refreshes backlog status artifacts before drift check
# (equivalent to backlog_status_artifact + backlog_status_hygiene --keep 50)

# acceptance docs navigation consistency
./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_docs_navigation.py

# acceptance gate toggles sync sanity-check
./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_gate_toggles_sync.py

# acceptance preset contract sync sanity-check
./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_preset_contract_sync.py

# acceptance preset smoke determinism sanity-check
./scripts/check_acceptance_preset_smoke_determinism.sh

# acceptance guardrails sync sanity-check (self-check vs acceptance map)
./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_guardrails_sync.py

# acceptance runbook sanity command-set sync check
./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_runbook_sanity_sync.py

# acceptance self-check pytest bundle sync sanity-check
./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_self_check_test_bundle_sync.py

# acceptance guardrail marker-set sync sanity-check
./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_guardrail_marker_set_sync.py

# backlog status parser/validator consistency sanity-check
./scripts/hive_ops_run.sh uv run --no-project python scripts/check_backlog_status_consistency.py

# backlog status JSON contract sanity-check
./scripts/hive_ops_run.sh uv run --no-project python scripts/check_backlog_status_json_contract.py

# backlog status drift sanity-check (live status vs latest artifact)
./scripts/hive_ops_run.sh uv run --no-project python scripts/check_backlog_status_drift.py

# backlog status auto-refresh sequence (refresh latest + rebuild index + verify no drift)
./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status_artifact.py
./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status_hygiene.py --keep 50
./scripts/hive_ops_run.sh uv run --no-project python scripts/check_backlog_status_drift.py

# backlog status artifacts index sanity-check
./scripts/hive_ops_run.sh uv run --no-project python scripts/check_backlog_status_artifacts_index.py

# backlog archive index consistency (no unknown timestamps, no stale refs)
./scripts/hive_ops_run.sh uv run --no-project python scripts/check_backlog_archive_index.py
```

Acceptance report artifacts index:

- `docs/ops/acceptance-reports/INDEX.md` (generated by `acceptance_report_hygiene.py`)

Rollout sequence (recommended):

1. Dry-run acceptance manually:
   - `HIVE_ACCEPTANCE_SKIP_CHECKLIST=true ./scripts/autonomous_acceptance_gate.sh`
2. Install scheduler:
   - `./scripts/install_acceptance_gate_launchd.sh`
3. Verify loaded status:
   - `./scripts/status_acceptance_gate_launchd.sh`
4. Monitor logs:
   - `tail -f .logs/acceptance-gate.out.log`
   - `tail -f .logs/acceptance-gate.err.log`
5. Keep acceptance report artifacts compact:
   - `./scripts/hive_ops_run.sh uv run --no-project python scripts/acceptance_report_hygiene.py --keep 50`
6. (Optional) enforce historical quality policy in scheduler:
   - reinstall with `HIVE_ACCEPTANCE_ENFORCE_HISTORY=true` and thresholds.

Troubleshooting:

- If status is `not-installed`, reinstall launchd plist.
- If scheduler runs but fails checks, run gate manually to isolate failing step.
- If Telegram status check fails intermittently, keep `HIVE_ACCEPTANCE_SKIP_TELEGRAM=true` for scheduler and investigate bridge ownership separately.
- If scheduler logs show `Operation not permitted` for `./scripts/*.sh` from launchd:
  - treat as host-level execution policy for current repo path,
  - prefer docker sidecar scheduler (`docker compose up -d hive-scheduler`),
  - keep launchd schedulers uninstalled (`./scripts/uninstall_*_launchd.sh`),
  - install cron fallback schedulers (`./scripts/install_acceptance_gate_cron.sh`, `./scripts/install_acceptance_weekly_cron.sh`, `./scripts/install_autonomous_loop_cron.sh`) or run manual gates.

Acceptance gate preset commands:

```bash
# fast local smoke
HIVE_ACCEPTANCE_SKIP_CHECKLIST=true \
HIVE_ACCEPTANCE_SKIP_TELEGRAM=true \
./scripts/autonomous_acceptance_gate.sh

# strict historical gate
HIVE_ACCEPTANCE_SKIP_CHECKLIST=true \
HIVE_ACCEPTANCE_ENFORCE_HISTORY=true \
HIVE_ACCEPTANCE_SUMMARY_JSON=true \
./scripts/autonomous_acceptance_gate.sh

# full strict + self-check + docs-nav
HIVE_ACCEPTANCE_SKIP_CHECKLIST=true \
HIVE_ACCEPTANCE_ENFORCE_HISTORY=true \
HIVE_ACCEPTANCE_SUMMARY_JSON=true \
HIVE_ACCEPTANCE_RUN_SELF_CHECK=true \
HIVE_ACCEPTANCE_RUN_DOCS_NAV_CHECK=true \
./scripts/autonomous_acceptance_gate.sh

# helper script wrappers
./scripts/acceptance_gate_presets.sh fast
./scripts/acceptance_gate_presets.sh strict
./scripts/acceptance_gate_presets.sh full
./scripts/acceptance_gate_presets.sh full-deep

# preview preset env without running gate
./scripts/acceptance_gate_presets.sh fast --print-env-only

# run preset against specific project scope
./scripts/acceptance_gate_presets.sh strict --project default

# one-command preset matrix smoke
./scripts/acceptance_gate_presets_smoke.sh

# run delivery e2e smoke inside acceptance gate (real + template scenarios)
HIVE_ACCEPTANCE_RUN_DELIVERY_E2E_SMOKE=true \
./scripts/autonomous_acceptance_gate.sh

# run delivery e2e smoke standalone
./scripts/hive_ops_run.sh \
  env HIVE_DELIVERY_E2E_BASE_URL=http://hive-core:${HIVE_CORE_PORT:-8787} \
  uv run --no-project python scripts/autonomous_delivery_e2e_smoke.py
```

Preset helper error behavior:

- Unknown preset mode (`./scripts/acceptance_gate_presets.sh unknown`) exits non-zero and prints usage.
- Missing project value (`./scripts/acceptance_gate_presets.sh fast --project`) exits non-zero with explicit `--project requires value`.

Run one autonomous pipeline run until terminal/wait (bounded server-side loop):

```bash
curl -sS -X POST \
  -H "Content-Type: application/json" \
  -d '{"max_steps":8}' \
  "http://localhost:${HIVE_CORE_PORT:-8787}/api/projects/default/autonomous/runs/<run_id>/run-until-terminal" | jq .
```

Dispatch and execute next backlog task in one server-side call:

```bash
curl -sS -X POST \
  -H "Content-Type: application/json" \
  -d '{"max_steps":8,"auto_start":true}' \
  "http://localhost:${HIVE_CORE_PORT:-8787}/api/projects/default/autonomous/execute-next" | jq .
```

Stuck-run alert threshold (seconds, default `1800`):

```bash
export HIVE_AUTONOMOUS_STUCK_RUN_SECONDS=1800
# early no-progress alert threshold (seconds, default 900)
export HIVE_AUTONOMOUS_NO_PROGRESS_SECONDS=900
# autonomous loop heartbeat stale threshold (seconds, default 600)
export HIVE_AUTONOMOUS_LOOP_STALE_SECONDS=600
# optional custom heartbeat state file path
export HIVE_AUTONOMOUS_LOOP_STATE_PATH=~/.hive/server/autonomous_loop_state.json
```

`/api/autonomous/ops/status` also returns:
- `alerts.stuck_runs_total`
- `alerts.stuck_runs[]` (`project_id`, `run_id`, `status`, `current_stage`, `stuck_for_seconds`)
- `alerts.no_progress_projects_total`
- `alerts.no_progress_projects[]` (`project_id`, `active_runs`, `max_no_progress_seconds`)
- `alerts.loop_stale`, `alerts.loop_stale_seconds`, `alerts.loop_stale_threshold_seconds`
- per-project `stuck_runs` and `max_stuck_for_seconds`
- per-project `active_runs` and `max_no_progress_seconds`
- `summary.project_filter` when `?project_id=<id>` is used
- `summary.include_runs` + top-level `active_runs[]` when `?include_runs=true`
- top-level `loop` (`state_path`, `state`, `stale`, `stale_seconds`, `stale_threshold_seconds`)

Web UI note: in `Auto` panel use `Refresh Ops` for independent loop-health refresh;
`loop_stale=true` is highlighted as warning for faster operator triage.
`Execution Snapshot` in the same panel shows last server-driven orchestration result/error.

Create backup of Hive state (`credentials`, `server`, `secrets`, `configuration.json`):

```bash
./scripts/backup_hive_state.sh
```

Optional custom paths:

```bash
HIVE_HOME=~/.hive HIVE_BACKUP_ROOT=~/.hive/backups ./scripts/backup_hive_state.sh
```

Safe restore drill (dry-run):

```bash
LATEST=$(ls -1t ~/.hive/backups/hive-state-*.tar.gz | head -n 1)
./scripts/restore_hive_state.sh --archive "$LATEST" --dry-run
```

Apply restore:

```bash
./scripts/restore_hive_state.sh --archive "$LATEST" --yes
```

Production MCP health summary (target stack):

```bash
./scripts/hive_ops_run.sh uv run --no-project python scripts/mcp_health_summary.py --dotenv .env --since-minutes 20
```

Autonomous loop tick (one-shot orchestration across projects):

```bash
./scripts/autonomous_loop_tick.sh
```

Each loop run updates heartbeat/state file (default `~/.hive/server/autonomous_loop_state.json`)
with `started_at/finished_at/updated_at`, `status`, and run `summary`.

By default script uses global backend orchestration endpoint
`POST /api/autonomous/loop/tick-all` and falls back to per-project tick if needed.
Set `HIVE_AUTONOMOUS_USE_TICK_ALL=false` to force legacy per-project mode.
Script now prefers `POST /api/autonomous/loop/run-cycle` (multi-step per project),
then falls back to `tick-all`, then per-project tick.

Optional cycle depth:

```bash
HIVE_AUTONOMOUS_MAX_STEPS_PER_PROJECT=5 ./scripts/autonomous_loop_tick.sh
```

Direct API call for multi-step cycle:

```bash
curl -sS -X POST http://localhost:${HIVE_CORE_PORT:-8787}/api/autonomous/loop/run-cycle \
  -H 'Content-Type: application/json' \
  -d '{"project_ids":["default"],"auto_start":true,"max_steps_per_project":3}' | jq .
```

`run-cycle` result includes operator-facing terminal markers:
- `terminal` (bool)
- `terminal_status` (`completed|failed|escalated`)
- `terminal_run_id`
- `pr_ready` (bool, from report `pr.ready`)
- `summary.outcomes` counters (e.g. `completed`, `failed`, `escalated`, `manual_deferred`, `idle`, `in_progress`)

Expected terminal states for autonomous delivery smoke:

- `completed`:
  - flow reached terminal success;
  - if GitHub PR stage exists, report may include `pr.url`.
- `failed`:
  - hard execution/review/validation failure;
  - required action: inspect run report + stage checks, then retry with fixed inputs.
- `escalated`:
  - policy/retry escalation boundary reached;
  - required action: operator intervention (policy/template/task refinement).
- `manual_deferred` (non-terminal orchestration outcome in cycle summary):
  - typically missing checks/token/context; run awaits operator decision/manual evaluate.

Quick troubleshooting matrix:

1. Symptom: onboarding not ready (`failed_checks` present).
   Action: fix workspace/repo binding and rerun `/onboard`.
2. Symptom: `execute-next` chooses another task.
   Action: reorder/close older todo tasks; run project backlog list and keep only intended top-priority task.
3. Symptom: `manual_deferred` in cycle/report.
   Action: provide missing GitHub context (`repository/ref/pr_url`) and run evaluate/auto-next again.
4. Symptom: stale `queued|in_progress` runs.
   Action: use `/api/autonomous/ops/status` + stale remediation dry-run/apply path.

In Web UI (`Auto` modal), use `Run Cycle` button and inspect `Run Cycle Summary` block
for the same counters and last-result outcome fields.

Compact report endpoint (ops/telegram-friendly):

```bash
curl -sS -X POST http://localhost:${HIVE_CORE_PORT:-8787}/api/autonomous/loop/run-cycle/report \
  -H 'Content-Type: application/json' \
  -d '{"project_ids":["default"],"auto_start":false,"max_steps_per_project":1}' | jq .
```

Telegram autonomous digest:

- Command: `/autodigest`
- Inline button: `🧭 Auto Digest` in `/status` panel
- Source: bridge calls `/api/autonomous/loop/run-cycle/report` and sends compact per-project summary.
- Proactive loop env:
  - `HIVE_TELEGRAM_AUTONOMOUS_DIGEST_ENABLED=1|0`
  - `HIVE_TELEGRAM_AUTONOMOUS_DIGEST_HOUR=0..23` (default `12`)
  - proactive send uses anti-noise filter and sends only when outcomes include
    `failed|escalated|manual_deferred`.

Optional scope (only selected projects):

```bash
HIVE_AUTONOMOUS_PROJECT_IDS="default,my-project-id" ./scripts/autonomous_loop_tick.sh
```

Cron example (every 2 minutes):

```bash
*/2 * * * * cd /path/to/hive && ./scripts/autonomous_loop_tick.sh >> ~/.hive/logs/autonomous-loop.log 2>&1
```

Managed cron wrapper (legacy fallback):

```bash
# install default cron cadence (*/2)
./scripts/install_autonomous_loop_cron.sh

# custom cron expression
HIVE_AUTONOMOUS_LOOP_CRON_EXPR="* * * * *" ./scripts/install_autonomous_loop_cron.sh

# status / uninstall
./scripts/status_autonomous_loop_cron.sh
./scripts/uninstall_autonomous_loop_cron.sh
```

Container-native alternative:

```bash
# autonomous ticks from scheduler sidecar
docker compose logs -f hive-scheduler
```

macOS launchd (persistent autonomous loop service):

```bash
# install (default interval 120s; override with HIVE_AUTONOMOUS_LOOP_INTERVAL)
./scripts/install_autonomous_loop_launchd.sh

# status
./scripts/status_autonomous_loop_launchd.sh

# uninstall
./scripts/uninstall_autonomous_loop_launchd.sh
```

If launchd reports `Operation not permitted` for `./scripts/autonomous_loop_tick.sh`,
use manual/cron loop mode until repo path is moved and launchd can execute script files.

Generated files:

- `docs/ops/mcp-tools-verified.txt`
- `docs/ops/mcp-tools-all.txt`
- `docs/ops/mcp-env-vars-all.txt`
- `docs/ops/mcp-tool-env-map.csv`

## 6) Google integrations available in this repo

- Available now: Google Docs, Google Sheets, Gmail, Google Calendar (via `GOOGLE_ACCESS_TOKEN`)
- Also available: Google Maps (`GOOGLE_MAPS_API_KEY`), Google Search Console (`GOOGLE_SEARCH_CONSOLE_TOKEN`), Google Analytics (`GOOGLE_APPLICATION_CREDENTIALS`)
- Direct Google Drive MCP tool is not present as a standalone tool in this repo.
  Google Docs tool uses Drive API endpoints internally for comments/export.
  If you need file-level drive operations, use OneDrive tools (`onedrive_*`) or add a dedicated gdrive tool.

## 7) Readiness gates (local production)

- `docker compose ps` shows `hive-core` as `healthy`
- `/api/health` returns `status=ok`
- Target agents pass `hive validate`
- Target flows pass `hive run` with intended model profiles
- Credential audit has no missing keys for integrations you actually use

## 8) One-command preflight and access verification

Run these before real autonomous workloads:

```bash
# container-only preflight pipeline
./scripts/hive_ops_preflight.sh

# optional explicit commands (same runner)
./scripts/hive_ops_run.sh uv run --no-project python scripts/validate_backlog_markdown.py
./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status.py --json
./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status_artifact.py
./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status_hygiene.py --keep 50 --yes
./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_archive_snapshot.py
./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_archive_hygiene.py
./scripts/hive_ops_run.sh uv run --no-project python scripts/acceptance_report_hygiene.py --keep 50

# host-side container reachability + credential stack checks
./scripts/local_prod_checklist.sh
./scripts/verify_access_stack.sh
HIVE_ACCEPTANCE_SKIP_CHECKLIST=true ./scripts/autonomous_acceptance_gate.sh
```

Operator profile wrapper (container-first):

```bash
# recommended daily baseline
./scripts/autonomous_operator_profile.sh --mode daily --project <project-id>

# extended deep validation profile
./scripts/autonomous_operator_profile.sh --mode deep --project <project-id>

# safe preview profile (no gate execution)
./scripts/autonomous_operator_profile.sh --mode dry-run --project <project-id>
```

Profile modes:

- `daily`: `hive_ops_preflight` -> stale runs remediation (apply) ->
  acceptance `strict` preset -> ops summary JSON.
  - remediation is enabled by default:
    - `HIVE_OPERATOR_AUTO_REMEDIATE_STALE=true`
    - `HIVE_OPERATOR_REMEDIATE_ACTION=escalated` (override when needed)
  - uses operator-safe health overrides for local container runtime:
    - `HIVE_AUTONOMOUS_HEALTH_ALLOW_LOOP_STALE=true`
    - `HIVE_AUTONOMOUS_HEALTH_MAX_NO_PROGRESS_PROJECTS=1` (override via env if needed)
- `deep`: `hive_ops_preflight` -> deep self-check (`preset_smoke + runtime_parity`) ->
  optional stale runs remediation (apply) -> acceptance `full-deep` preset -> ops summary JSON.
  - optional remediation toggle (default disabled):
    - `HIVE_OPERATOR_DEEP_AUTO_REMEDIATE_STALE=false`
    - when enabled, uses `HIVE_OPERATOR_REMEDIATE_ACTION=escalated` (override when needed)
- `dry-run`: prints strict/full-deep acceptance env plans (`--print-env-only`) and current ops summary.

Project health profiles (operator-level abstraction):

- `prod` (default): `max_stuck_runs=0`, `max_no_progress_projects=1`, `allow_loop_stale=true`
- `strict`: `max_stuck_runs=0`, `max_no_progress_projects=0`, `allow_loop_stale=false`
- `relaxed`: `max_stuck_runs=2`, `max_no_progress_projects=2`, `allow_loop_stale=true`

CLI overrides (higher priority than env):

- `--remediate`: force remediation on for both daily and deep in this run.
- `--no-remediate`: force remediation off for both daily and deep in this run.
- `--no-remediation`: alias for `--no-remediate`.
- `--daily-remediate` / `--no-daily-remediate`: override only daily remediation.
- `--deep-remediate` / `--no-deep-remediate`: override only deep remediation.
- `--remediate-action <escalated|failed>`: force remediation action for this run
  (overrides `HIVE_OPERATOR_REMEDIATE_ACTION`).
- `--project-health-profile <prod|strict|relaxed>`: select health threshold profile for this run
  (overrides `HIVE_OPERATOR_PROJECT_HEALTH_PROFILE`).
- `--skip-preflight`: skip `hive_ops_preflight` step for fast ops-only run.
- `--skip-self-check`: skip deep self-check stage (`deep` mode only).
- `--ops-summary-only`: run only final ops summary (skip preflight/self-check/remediation/gate).
- `--acceptance-preset <fast|strict|full|full-deep>`: force acceptance preset used in gate
  (and dry-run preview when set), overriding mode defaults.
- `--acceptance-extra-args "<...>"`: pass extra args through to
  `scripts/acceptance_gate_presets.sh` (forwarded as `-- <args>`).

What they validate:

- backlog task/status structure and `Current Focus` consistency
- compact backlog execution summary (focus/in-progress/status counts)
- machine-readable backlog summary for automation hooks (`backlog_status.py --json`)
- backlog status artifacts (`docs/ops/backlog-status/latest.json` + timestamp snapshots)
- backlog status artifact hygiene/index refresh (`backlog_status_hygiene.py --keep 50`)
- container-network runtime parity check (`hive-core:8787`) via preflight
- container health, API health, and internal service DNS
- `local_pro_stack` credential bundle completeness
- token health for GitHub / Telegram / Google
- Google refresh flow presence (`GOOGLE_REFRESH_TOKEN`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`)
- Redis + Postgres reachability from `hive-core`
- one-command autonomous acceptance smoke (parity/health/remediation dry-run/telegram/report)

Backlog archive rotation policy:

- `docs/autonomous-factory/archive/ROTATION_POLICY.md`
- `docs/autonomous-factory/BACKLOG_COMPACTION_CHECKLIST.md`

Archive prune guardrails (safe by default):

```bash
# preview only (no delete)
./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_archive_hygiene.py --prune-keep 20

# apply delete only after reviewing preview
./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_archive_hygiene.py --prune-keep 20 --yes
```

Archive prune recovery:

```bash
# restore deleted snapshots/index from VCS
git restore docs/autonomous-factory/archive/backlog-done-snapshot-*.md docs/autonomous-factory/archive/INDEX.md

# rebuild index
./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_archive_hygiene.py
```

Backlog compaction cadence:

- End of each execution wave: run full checklist in
  `docs/autonomous-factory/BACKLOG_COMPACTION_CHECKLIST.md`.
- Weekly maintenance: rerun checklist even without wave closure.

Backlog status auto-refresh playbook:

1. Refresh status snapshot:
   - `./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status_artifact.py`
2. Rebuild index and apply hygiene preview:
   - `./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status_hygiene.py --keep 50`
3. Confirm no live/artifact drift:
   - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_backlog_status_drift.py`
4. Confirm index consistency:
   - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_backlog_status_artifacts_index.py`

Backlog status drift troubleshooting:

- If `check_backlog_status_drift.py` reports `live_vs_artifact_mismatch`:
  1. Run the auto-refresh sequence above.
  2. Re-check drift.
  3. If mismatch remains, inspect latest backlog edits and rerun:
     - `./scripts/hive_ops_run.sh uv run --no-project python scripts/validate_backlog_markdown.py`
     - `./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status.py --json`
     - `./scripts/hive_ops_run.sh uv run --no-project python scripts/acceptance_ops_summary.py --json`
- If drift reason is `missing_latest_artifact_status`, regenerate artifact first:
  - `./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status_artifact.py`
- If drift reason is `live_backlog_status_unavailable`, run:
  - `./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status.py --json`
  and inspect script/runtime errors before rerunning drift check.

Fast local rebuild mode (skip Playwright browser deps in image):

```bash
HIVE_DOCKER_INSTALL_PLAYWRIGHT=0 docker compose up -d --build hive-core
```

Use default/production build for full browser scraping capability:

```bash
HIVE_DOCKER_INSTALL_PLAYWRIGHT=1 docker compose up -d --build hive-core
```

Note: when Playwright install is skipped, browser-dependent scraping flows may be unavailable inside container.

## 8.1) Frontend Build Baseline (Workspace bundle)

Use this quick check after frontend changes:

```bash
cd core/frontend && npm run build
```

Current baseline (April 9, 2026):

- before chunk hardening: `index-*.js` was `612.10 kB` with Vite warning (`>500 kB`);
- after `manualChunks` split in `vite.config.ts`:
  - `index-*.js` is `223.81 kB`;
  - `vendor-*.js` is `387.46 kB`;
  - no chunk-size warning.

## 9) Telegram Bridge Live Smoke Checklist (E2E)

Use this to validate operator flow after deploy/restart.

Preconditions:

- `hive-core` is `healthy`
- bot token configured (`TELEGRAM_BOT_TOKEN`)
- at least one real chat has opened the bot (`/start`)

Live monitor in terminal:

```bash
docker compose logs -f --since=2m hive-core | rg -n "Telegram bridge|received message|injected chat|sent telegram reply|ERROR|Traceback"
```

Smoke actions from Telegram:

1. Send `/status`
2. Send `/sessions`
3. Send plain text (for example: `ping bridge`)

Bootstrap preset smoke (autonomous delivery in one flow):

1. Existing repository mode:
   - `/bootstrap repo https://github.com/<owner>/<repo> --task <goal text>`
2. New repository mode:
   - `/bootstrap newrepo <name> owner=<org> visibility=private --task <goal text>`
3. Tap `✅ Run Bootstrap`.
4. Verify final trace message contains:
   - `project=...`
   - `task_id=...`
   - `run_id=...`
   - `report=/api/projects/<project>/autonomous/runs/<run>/report`
   - optional `pr=https://github.com/.../pull/...`

Expected signals:

- command updates are received by bridge
- plain text is injected into bound queen session
- bot returns a reply for each input
- no `ERROR`/`Traceback` during flow

Record template:

```text
Date/Time:
Operator:
Session/Project:

/status: PASS|FAIL
/sessions: PASS|FAIL
plain text: PASS|FAIL

Bridge logs clean (no ERROR/Traceback): YES|NO
Notes:
```

Telegram bridge single-consumer controls (polling mode):

```bash
# live status (owner/lock/running/error)
curl -sS http://localhost:${HIVE_CORE_PORT:-8787}/api/telegram/bridge/status | jq .

# same status is also embedded in global health
curl -sS http://localhost:${HIVE_CORE_PORT:-8787}/api/health | jq '.telegram_bridge'
```

Mode and ownership env knobs:

```bash
# polling bridge mode (default)
export HIVE_TELEGRAM_MODE=polling

# enforce one polling consumer with filesystem lock (default enabled)
export HIVE_TELEGRAM_SINGLE_CONSUMER=1
export HIVE_TELEGRAM_POLL_LOCK_PATH=~/.hive/server/telegram-poll.lock
```

Operator mode switching guide:

1. If Hive should own Telegram polling, keep `HIVE_TELEGRAM_BRIDGE_ENABLED=1` and `HIVE_TELEGRAM_MODE=polling`.
2. If another process owns bot updates, disable Hive polling with `HIVE_TELEGRAM_BRIDGE_ENABLED=0` to avoid poller conflicts.
3. After restart, verify ownership via `/api/telegram/bridge/status` (`poller_owner=true`, `running=true`).
4. In steady-state logs there should be no recurring `getUpdates ... Conflict` / `409` lines.

## 10) Telegram-First Autonomous Development (Operator Flow)

Use this section when you want to run autonomous development primarily from Telegram.

### Scenario A: Existing repository

1. Select/create target project:
   - `/projects`
   - `/project <id>`
2. Bind repository:
   - `/repo https://github.com/<owner>/<repo>`
3. Run onboarding:
   - `/onboard stack=<node|python|fullstack|go|rust|jvm> [template_id=<template>] [workspace_path=<path>]`
4. Start autonomous task:
   - `/bootstrap repo https://github.com/<owner>/<repo> --task <goal>`
   - tap `✅ Run Bootstrap`
5. Track delivery trace:
   - verify `task_id`, `run_id`, `report=/api/projects/.../report`, optional `pr=...`

### Scenario B: New repository

1. Select/create target project:
   - `/projects`
   - `/project <id>` (or `/newproject <name>`)
2. Create repository:
   - `/newrepo <name> owner=<org> visibility=private`
   - tap `✅ Create Repository`
3. Run bootstrap preset:
   - `/bootstrap newrepo <name> owner=<org> visibility=private --task <goal>`
   - tap `✅ Run Bootstrap`
4. Verify final trace and report endpoint.

### DB and Multi-Container apps

- Default production-safe strategy: **CI-first validation**.
- Agent prepares code + PR; GitHub Actions runs DB/compose integration tests.
- Use project execution policy for checks-based review/validation before merge.
- For local containerized integration tests inside runtime, use optional docker lane (`HIVE_AUTONOMOUS_DOCKER_LANE_ENABLED=1`) only when explicitly needed.

### Telegram-only run checklist

1. `/status` shows expected project/session and no bridge errors.
2. Onboarding result is explicit (`ready=true` or manual deferred with failed checks listed).
3. Bootstrap returns `run_id` and `report` endpoint.
4. If run is deferred/blocked, use:
   - `/autodigest`
   - `GET /api/autonomous/ops/status?project_id=<id>&include_runs=true`
5. Before merge, verify review/validation outcomes and required checks.

### Rollback and incident triage

1. Stop active run if needed:
   - `/stop`
   - `/cancel`
2. Inspect run health:
   - `curl -sS "http://localhost:${HIVE_CORE_PORT:-8787}/api/autonomous/ops/status?project_id=<id>&include_runs=true" | jq .`
3. Preview stale remediation:
   - `HIVE_AUTONOMOUS_REMEDIATE_PROJECT_ID=<id> HIVE_AUTONOMOUS_REMEDIATE_DRY_RUN=true ./scripts/autonomous_remediate_stale_runs.sh`
4. Apply remediation only with explicit confirmation settings.
5. Re-run onboarding/bootstrap after fix and confirm new `run_id` trace.

### Container-first validation bundle (terminal side)

Use this quick bundle to validate Telegram-first operator path from containerized runtime:

```bash
# 1) Telegram bridge ownership/running
curl -sS http://localhost:${HIVE_CORE_PORT:-8787}/api/telegram/bridge/status | jq .

# 2) Global health includes telegram bridge snapshot
curl -sS http://localhost:${HIVE_CORE_PORT:-8787}/api/health | jq '.telegram_bridge'

# 3) Autonomous ops visibility with active-runs shape
curl -sS "http://localhost:${HIVE_CORE_PORT:-8787}/api/autonomous/ops/status?include_runs=true" | jq .

# 4) Stale remediation preview for a project (safe dry-run)
HIVE_AUTONOMOUS_REMEDIATE_PROJECT_ID=<project_id> \
HIVE_AUTONOMOUS_REMEDIATE_DRY_RUN=true \
./scripts/autonomous_remediate_stale_runs.sh
```

Generate a sign-off artifact (JSON + Markdown):

```bash
./scripts/hive_ops_run.sh \
  env HIVE_BASE_URL=http://hive-core:${HIVE_CORE_PORT:-8787} \
  uv run --no-project python scripts/telegram_operator_signoff.py \
  --project-id <project_id> \
  --operator "<name>" \
  --manual-status pending
```

After manual Telegram checklist pass, finalize sign-off:

```bash
./scripts/hive_ops_run.sh \
  env HIVE_BASE_URL=http://hive-core:${HIVE_CORE_PORT:-8787} \
  uv run --no-project python scripts/telegram_operator_signoff.py \
  --project-id <project_id> \
  --operator "<name>" \
  --manual-status pass \
  --notes "Scenario A/B passed"
```
