# Phase C Closure Checklist (MCP Access + Credential Policy)

Source of truth: `docs/autonomous-factory/13-master-implementation-plan.md` -> `Phase C`.

## Exit Criteria

1. Required MCP stack checks are green (`github`, `google`, `web search/scrape`, `files-tools`).
2. Credential failures are explicit and actionable (no silent fail).
3. Token refresh/remediation flow is documented and reproducible.

## Command Checklist

```bash
# 1) required MCP stack health
uv run python scripts/mcp_health_summary.py --since-minutes 30

# 2) access stack check (tokens + redis/postgres/refresher)
./scripts/verify_access_stack.sh

# 3) credential audit visibility
uv run python scripts/audit_mcp_credentials.py

# 4) Google token remediation (when google check is non-200)
./scripts/google_token_auto_refresh.sh
```

## Latest Closure Evidence

Date: `2026-04-10` (local run)

- `mcp_health_summary.py --since-minutes 30`: `status: ok`, `ok: 5/5`.
- `verify_access_stack.sh`: `GitHub`, `Telegram`, `Google`, `Redis`, `Postgres`, `google-token-refresher` all `OK`.
- `google_token_auto_refresh.sh`: `Refresh success. expires_in=3599`.
- Runtime probe confirms files MCP registration:
  - session load via `examples/templates/deep_research_agent`,
  - logs include `Connected to MCP server 'files-tools'`,
  - logs include `Discovered 6 tools from 'files-tools'`.

## Notes

- `scripts/mcp_health_summary.py` exposes per-check `ok/code/detail` and global status.
- `scripts/verify_access_stack.sh` surfaces explicit `[OK]/[WARN]` outcomes for operator remediation.
- `scripts/audit_mcp_credentials.py` prints concrete set/missing env vars for MCP tools.
