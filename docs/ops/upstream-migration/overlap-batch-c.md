# Overlap Batch C (Tools/MCP Compatibility)

Date: 2026-04-18

## Scope

Tools/MCP overlap integration for upstream landing:

1. `tools/Dockerfile`
2. `tools/coder_tools_server.py`
3. `tools/mcp_servers.json`
4. `tools/src/aden_tools/credentials/__init__.py`
5. `tools/src/aden_tools/tools/__init__.py`
6. `tools/src/aden_tools/tools/calendar_tool/calendar_tool.py`
7. `tools/src/aden_tools/tools/github_tool/github_tool.py`
8. `tools/src/aden_tools/tools/gmail_tool/gmail_tool.py`
9. `tools/src/aden_tools/tools/google_docs_tool/google_docs_tool.py`
10. `tools/src/aden_tools/tools/google_sheets_tool/google_sheets_tool.py`
11. `tools/src/gcu/__init__.py`
12. `tools/tests/test_coder_tools_server.py`
13. `tools/tests/tools/test_github_tool.py`

## Artifacts

1. Full export:
   - `docs/ops/upstream-migration/overlap-batch-c-latest.patch`
   - `docs/ops/upstream-migration/overlap-batch-c-latest.md`
2. Dependency bundle:
   - `docs/ops/upstream-migration/overlap-batch-c-dependency-bundle-latest.md`
3. Tools overlap bundle:
   - `docs/ops/upstream-migration/overlap-batch-c-bundle-latest.md`
4. Landing rehearsal:
   - `docs/ops/upstream-migration/overlap-batch-c-landing-rehearsal-latest.md`

## Scripts

1. `scripts/upstream_overlap_batch_c_export.sh`
2. `scripts/upstream_overlap_batch_c_dependency_bundle.sh`
3. `scripts/upstream_overlap_batch_c_bundle.sh`
4. `scripts/upstream_overlap_batch_c_landing_rehearsal.sh`
5. `scripts/upstream_overlap_batch_c_bundle_apply.sh`

## Current Finding

1. Deterministic overlap export is prepared for all 13 files.
2. Deterministic apply path is prepared via:
   - dependency bundle (`tools/src/*`, `tools/tests/*`, `scripts/mcp_health_summary.py`);
   - tools overlap bundle (13 scoped conflict files).
3. Landing rehearsal on clean `origin/main` clone passes static compatibility gates:
   - python compile for overlap files = `ok`;
   - `mcp_servers.json` parse = `ok`.
4. Live runtime compatibility/health gates pass in current workspace:
   - `tools/tests/test_coder_tools_server.py` = `ok`;
   - `tools/tests/tools/test_github_tool.py` = `ok`;
   - `scripts/mcp_health_summary.py` = `ok`;
   - `scripts/verify_access_stack.sh` = `ok`.

## Apply Step (landing branch only)

```bash
HIVE_UPSTREAM_LANDING_BRANCH=migration/upstream-wave3 \
./scripts/upstream_overlap_batch_c_bundle_apply.sh --check

HIVE_UPSTREAM_LANDING_BRANCH=migration/upstream-wave3 \
./scripts/upstream_overlap_batch_c_bundle_apply.sh --apply
```

Guardrails:

1. script exits if current branch is not `migration/upstream-wave3`;
2. script exits on dirty worktree unless `HIVE_UPSTREAM_ALLOW_DIRTY=true`.
