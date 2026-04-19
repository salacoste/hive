# 06. MCP Server Bundle (Local-First Production)

## Objective

Define the exact MCP server set for your local autonomous development factory, with phased rollout and credential gating.

This plan is based on the servers and tools present in this repository.

## Ground Truth in This Repo

- `hive-tools` server exists (`tools/mcp_server.py`) and registers the full Aden toolset.
- `coder-tools` server exists (`tools/coder_tools_server.py`) and is used by queen for coding/build workflows.
- `gcu-tools` server exists (`tools/src/gcu/server.py`) and provides browser automation tools.
- `files-tools` server exists (`tools/files_server.py`) as a minimal file server.

## Recommended Server Set

## Tier 0 (Required)

1. `coder-tools`
- Purpose: queen coding operations, code edits, command execution, agent scaffolding.
- Why required: core build/debug loop depends on it.
- Current usage in repo: queen default MCP config already points to `coder-tools`.

2. `hive-tools`
- Purpose: business/system integrations and general tools:
  - web search/scrape
  - GitHub tools
  - Telegram tools
  - Google Workspace tools (Docs/Sheets/Gmail/Calendar)
  - Redis/Postgres tools
- Why required: this is your primary integration plane for automation tasks.

## Tier 1 (Strongly Recommended)

3. `gcu-tools`
- Purpose: browser automation for authenticated web flows and hard scraping/login tasks.
- Why recommended: `web_scrape` is enough for simple pages, but not for dynamic/authenticated UI flows.

## Tier 2 (Required by Your Current Policy)

4. `files-tools`
- Purpose: minimal file operations server.
- Notes: overlaps with parts of `coder-tools`, but kept enabled to satisfy the explicit "all 4 MCP servers enabled" operating policy.

## Not in Repo as Standalone MCP (Important)

- Dedicated Google Drive file-level MCP tools are not present as standalone tools in this repo.
- Current Google support is Docs/Sheets/Gmail/Calendar (plus Maps/Search Console/Analytics via separate credentials).
- If full Drive file operations are required, add a dedicated gdrive MCP server or implement one.

## Baseline Credentials for Your Target Stack

For your stated local stack (web search + scraping + telegram + github + google + redis/postgres), baseline variables are:

- `BRAVE_SEARCH_API_KEY`
- `GITHUB_TOKEN`
- `TELEGRAM_BOT_TOKEN`
- `GOOGLE_ACCESS_TOKEN`
- `GOOGLE_MAPS_API_KEY` (optional but useful for maps tools)
- `GOOGLE_SEARCH_CONSOLE_TOKEN` (optional)
- `GOOGLE_APPLICATION_CREDENTIALS` (for GA/BigQuery-related tools)
- `REDIS_URL`
- `DATABASE_URL`

Additional useful search/research keys:

- `EXA_API_KEY`
- `SERPAPI_API_KEY`
- `GOOGLE_API_KEY`
- `GOOGLE_CSE_ID`

## Suggested `mcp_servers.json` Profiles

Use flat dict format (no `mcpServers` wrapper).

### Worker Agents (default)

```json
{
  "hive-tools": {
    "transport": "stdio",
    "command": "uv",
    "args": ["run", "python", "mcp_server.py", "--stdio"],
    "cwd": "../../../tools",
    "description": "Primary integration server"
  },
  "gcu-tools": {
    "transport": "stdio",
    "command": "uv",
    "args": ["run", "python", "-m", "gcu.server", "--stdio"],
    "cwd": "../../../tools",
    "description": "Browser automation for dynamic/authenticated web tasks"
  }
}
```

### Queen Agent

Enable all four servers in queen config:
- `coder-tools`
- `hive-tools`
- `gcu-tools`
- `files-tools`

## Rollout Order (Local)

1. Keep `coder-tools` + `hive-tools` as baseline.
2. Add `gcu-tools` for browser-heavy flows.
3. Add `files-tools` to satisfy full 4-server policy.
4. Validate credentials with:
   - `uv run python scripts/audit_mcp_credentials.py --bundle local_pro_stack`
   - `uv run python scripts/audit_mcp_credentials.py --tools web_search web_scrape github_create_issue telegram_send_message google_docs_get_document google_sheets_get_values gmail_list_messages calendar_list_events`
5. Run smoke workflows:
   - web search + scrape
   - GitHub issue/PR read+write
   - Telegram send
   - Google Docs/Sheets read
   - Redis and Postgres connectivity

## Operational Rules

- Enable only servers needed by the specific agent to keep tool surface small.
- Separate queen (coding plane) from workers (integration plane).
- Apply least-privilege tokens:
  - GitHub token scopes limited to required repos/actions
  - Google OAuth token only with required scopes
  - DB credentials read-only by default
- Re-audit keys before each major rollout or after credential rotation.
