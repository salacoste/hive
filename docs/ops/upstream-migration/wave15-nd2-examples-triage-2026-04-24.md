# Wave 15 — ND-2 Examples/Templates Triage

Date: 2026-04-24
Status: ND-2A and ND-2B executed (gate green)

## Source artifact

- `docs/ops/upstream-migration/wave15-nd2-examples-inventory-2026-04-24.json`

## ND-2 summary (`HEAD..upstream/main`)

- total files: `15`
- config-only files: `12` (low risk)
- code-bearing template files: `3` (medium risk)

## First bounded candidate

Candidate ID: `ND-2A-config-only`

Scope (12 files):

- `examples/templates/competitive_intel_agent/mcp_servers.json`
- `examples/templates/deep_research_agent/mcp_servers.json`
- `examples/templates/email_inbox_management/mcp_servers.json`
- `examples/templates/email_reply_agent/mcp_servers.json`
- `examples/templates/job_hunter/mcp_servers.json`
- `examples/templates/local_business_extractor/mcp_servers.json`
- `examples/templates/meeting_scheduler/mcp_servers.json`
- `examples/templates/sdr_agent/mcp_servers.json`
- `examples/templates/tech_news_reporter/mcp_servers.json`
- `examples/templates/twitter_news_agent/mcp_servers.json`
- `examples/templates/vulnerability_assessment/mcp_registry.json`
- `examples/templates/vulnerability_assessment/mcp_servers.json`

Reason:

- configuration-only template updates are the lowest-risk sub-lane inside ND-2.

## Deferred within ND-2 (code-bearing)

- `examples/templates/deep_research_agent/agent.py`
- `examples/templates/deep_research_agent/nodes/__init__.py`
- `examples/templates/meeting_scheduler/nodes/__init__.py`

These should be replayed as a separate bounded sub-lane after ND-2A is
evaluated.

## ND-2A probe

Artifacts:

- `docs/ops/upstream-migration/wave15-nd2a-config-only.patch`
- `docs/ops/upstream-migration/wave15-nd2a-config-probe-2026-04-24.json`

Result:

- `git apply --check` passed for `ND-2A-config-only` (`exit_code=0`).

Implication:

- ND-2A is technically ready for bounded replay (subject to operator approval
  and mandatory post-apply gates).

Execution update:

- ND-2A replay executed and validated with full gate pass (`ok=7 failed=0`);
- evidence:
  - `docs/ops/upstream-migration/wave15-nd2a-execution-2026-04-24.json`.
- ND-2B replay executed and validated with full gate pass (`ok=7 failed=0`);
- evidence:
  - `docs/ops/upstream-migration/wave15-nd2b-execution-2026-04-24.json`.
- ND-2 lane status:
  - completed; next active lane moved to ND-3 (`tools`).
