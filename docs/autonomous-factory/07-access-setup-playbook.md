# 07. Access Setup Playbook (GitHub / DB / Google / Telegram)

This playbook is for local-first production setup where Hive runs in Docker and needs controlled access to external systems.

## 1) Principles

- Use per-integration credentials, not one global super-token.
- Keep credentials in `.env` (local only), never in git.
- Validate every credential before enabling autonomous runs.
- Default DB role is read-only; write access only via approval gate.

## 2) Required Environment Variables

Minimum for coding factory operations:

- `GITHUB_TOKEN`
- `TELEGRAM_BOT_TOKEN`
- `GOOGLE_ACCESS_TOKEN`
- `DATABASE_URL`
- `REDIS_URL`

Optional but recommended:

- `GOOGLE_APPLICATION_CREDENTIALS` (analytics/service-account flows)
- `GOOGLE_MAPS_API_KEY`, `GOOGLE_SEARCH_CONSOLE_TOKEN` (if those tools are used)

Use template: `.env.mcp.example`.

## 3) GitHub Access

### Token scopes (minimum)

- repository contents: read/write
- pull requests: read/write
- issues: read/write (optional)

### Validation

```bash
./scripts/verify_access_stack.sh
```

Success criteria:

- GitHub check returns `[OK] GitHub token valid`

## 4) Database Access

### Local docker defaults

- Postgres: `postgresql://hive:hive@postgres:5432/hive`
- Redis: `redis://redis:6379/0`

### Hardening model

- Create separate DB users:
  - `hive_ro`: read-only for analysis
  - `hive_rw`: controlled write for approved tasks
- Keep migrations out of autonomous default flow.

### Validation

```bash
./scripts/verify_access_stack.sh
```

Success criteria:

- `[OK] Redis reachable from hive-core`
- `[OK] Postgres reachable from hive-core`

## 5) Google Access

`GOOGLE_ACCESS_TOKEN` is used by current Google Workspace MCP tools (Docs/Sheets/Gmail/Calendar).

### Operational note

- Access token must be refreshed/rotated outside this repo (OAuth flow).
- Store only current token in `.env`.
- Recommended: configure full refresh flow with:
  - `GOOGLE_CLIENT_ID`
  - `GOOGLE_CLIENT_SECRET`
  - `GOOGLE_REFRESH_TOKEN`
  - `GOOGLE_ACCESS_TOKEN`

### Bootstrap and refresh commands

```bash
uv run python scripts/google_oauth_token_manager.py auth-url
uv run python scripts/google_oauth_token_manager.py exchange --code "<CODE_FROM_REDIRECT>"
./scripts/google_token_auto_refresh.sh
```

### Validation

```bash
./scripts/verify_access_stack.sh
```

Success criteria:

- `[OK] Google access token accepted`

## 6) Telegram Control Surface

Set:

- `TELEGRAM_BOT_TOKEN`

The bridge supports:

- slash command hints (`/start`, `/menu`, `/status`, `/sessions`, `/run`, `/stop`, `/cancel`, `/toggle`)
- compact reply keyboard and show/hide toggle
- inline buttons for ask-user flows

## 7) End-to-End Preflight

Run this before switching to autonomous mode:

```bash
./scripts/local_prod_checklist.sh
./scripts/verify_access_stack.sh
```

Gate to pass:

- all core containers healthy
- `/api/health` is OK
- required credentials present for selected tool bundle
- external integrations return successful validation
