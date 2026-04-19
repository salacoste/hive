# Google OAuth Rotation and Re-Auth Runbook

## Scope

Runbook for rotating Google OAuth credentials used by Hive local deployment:

- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REFRESH_TOKEN`
- optional `GOOGLE_CLIENT_ID` migration

This procedure targets Docker runtime (`hive-core` + `google-token-refresher`) and minimizes downtime.

## Preconditions

- Repository root available locally.
- `.env` contains current Google OAuth settings.
- `hive-core` stack is running:

```bash
docker compose ps hive-core google-token-refresher
```

## Safety Snapshot

Create rollback snapshot before any changes:

```bash
cp .env ".env.backup.$(date +%Y%m%d-%H%M%S)"
```

Verify current health baseline:

```bash
./scripts/verify_access_stack.sh
docker compose exec -T hive-core uv run python scripts/mcp_health_summary.py --dotenv .env --since-minutes 20
```

## A) Client Secret Rotation (same client ID)

1. Open Google Cloud Console -> APIs & Services -> Credentials.
2. Select your OAuth client.
3. Create a new client secret (keep old one enabled until cutover validation passes).
4. Update `.env`:
   - `GOOGLE_CLIENT_SECRET=<new-secret>`
5. Trigger token refresh:

```bash
./scripts/google_token_auto_refresh.sh
```

6. Validate:

```bash
./scripts/verify_access_stack.sh
docker compose exec -T hive-core uv run python scripts/mcp_health_summary.py --dotenv .env --json | jq '.checks[] | select(.name=="google")'
```

7. If validation is green, disable/delete old client secret in Google Console.

## B) Refresh Token Rotation / Full Re-Auth

Use this flow when refresh starts failing (`invalid_grant`) or scopes changed.

1. Generate OAuth consent URL:

```bash
docker compose exec -T hive-core uv run python scripts/google_oauth_token_manager.py auth-url
```

2. Complete consent in browser.
3. From redirect URL copy `code=...`.
4. Exchange code to new tokens:

```bash
docker compose exec -T hive-core uv run python scripts/google_oauth_token_manager.py exchange --code "<CODE_FROM_REDIRECT>"
```

5. Apply refresh/runtime sync:

```bash
./scripts/google_token_auto_refresh.sh
```

6. Validate:

```bash
./scripts/verify_access_stack.sh
docker compose exec -T hive-core uv run python scripts/google_mcp_smoke_test.py --dotenv .env
```

7. Optional: revoke old refresh token/client secret after stable validation window.

## C) Client ID Migration

If moving to a new OAuth client:

1. Update `.env`:
   - `GOOGLE_CLIENT_ID=<new-id>`
   - `GOOGLE_CLIENT_SECRET=<new-secret>`
2. Execute full re-auth flow from section B to get a refresh token tied to new client ID.
3. Re-run all validations from section B.

## Failure Handling

If anything fails during rotation:

1. Restore previous env snapshot:

```bash
cp .env.backup.<timestamp> .env
```

2. Re-apply previous runtime token:

```bash
./scripts/google_token_auto_refresh.sh
docker compose up -d --force-recreate hive-core google-token-refresher
```

3. Re-check:

```bash
./scripts/verify_access_stack.sh
```

## Post-Rotation Checklist

- `google-token-refresher` logs show `refresh ok expires_in=...`.
- `docs/ops/google-canary/latest.json` is green on next scheduled run.
- `scripts/mcp_health_summary.py` Google check `ok=true` with `freshness.level=ok|warning`.
