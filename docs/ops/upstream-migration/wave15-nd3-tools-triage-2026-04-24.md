# Wave 15 — ND-3 Tools Lane Triage

Date: 2026-04-24
Status: ND-3A/ND-3B/ND-3C/ND-3D/ND-3E executed (tools lane complete)

## Source artifact

- `docs/ops/upstream-migration/wave15-nd3-tools-inventory-2026-04-24.json`

## ND-3 summary (`HEAD..upstream/main`, `tools/`)

- total files: `29`
- by status:
  - `M=22`
  - `A=5`
  - `D=2`
- local parity vs upstream:
  - byte-equal: `3`
  - divergent: `22`
  - local missing while upstream adds: `2`

## Lane split

1. ND-3A `prometheus observability` (bounded candidate)
   - target files:
     - `tools/src/aden_tools/credentials/health_check.py`
     - `tools/src/aden_tools/credentials/prometheus.py`
     - `tools/src/aden_tools/tools/__init__.py`
     - `tools/src/aden_tools/tools/prometheus_tool/README.md`
     - `tools/src/aden_tools/tools/prometheus_tool/__init__.py`
     - `tools/src/aden_tools/tools/prometheus_tool/prometheus_tool.py`
     - `tools/tests/test_health_checks.py`
     - `tools/tests/tools/test_prometheus_tool.py`
2. ND-3B `gcu/browser runtime`
   - `tools/src/gcu/**` + `tools/tests/test_browser_tools_comprehensive.py`
3. ND-3C `productivity providers`
   - `calendar/github/gmail/google_docs/google_sheets` tool paths and tests.
4. ND-3D `tools runtime packaging`
   - `tools/Dockerfile`, `tools/coder_tools_server.py`, `tools/mcp_servers.json`,
     `tools/tests/test_coder_tools_server.py`.
5. ND-3E `deletions policy`
   - upstream deleted:
     - `tools/src/aden_tools/tools/google_auth.py`
     - `tools/tests/tools/test_google_auth.py`

## ND-3A probe

Artifacts:

- `docs/ops/upstream-migration/wave15-nd3a-prometheus.patch`
- `docs/ops/upstream-migration/wave15-nd3a-prometheus-probe-2026-04-24.json`
- `docs/ops/upstream-migration/wave15-nd3a-prometheus-reconcile-2026-04-24.json`

Result:

- `git apply --check` failed (`exit_code=1`).
- reasons:
  - pre-existing local files for some upstream `A` paths;
  - divergent hunks in:
    - `tools/src/aden_tools/credentials/health_check.py`
    - `tools/src/aden_tools/tools/__init__.py`
    - `tools/tests/test_health_checks.py`

Decision:

- ND-3A should be executed through explicit per-file reconcile/merge flow.
- blind patch apply is not safe in this lane.
- reconcile table is prepared (`8` files): `2` divergent hunks,
  `2` local pre-existing divergent adds, `2` missing local upstream adds,
  `2` already-equal carry-as-is files.

Execution update:

- ND-3A reconcile executed and validated:
  - `docs/ops/upstream-migration/wave15-nd3a-execution-2026-04-24.json`
  - full gate: `ok=7 failed=0`.
- ND-3B probe and replay plan prepared:
  - `docs/ops/upstream-migration/wave15-nd3b-gcu.patch`
  - `docs/ops/upstream-migration/wave15-nd3b-gcu-probe-2026-04-24.json`
  - `docs/ops/upstream-migration/wave15-nd3b-gcu-replay-plan-2026-04-24.md`
- ND-3B replay executed and validated:
  - `docs/ops/upstream-migration/wave15-nd3b-execution-2026-04-24.json`
  - full gate: `ok=7 failed=0`.
- ND-3C probe and replay plan prepared:
  - `docs/ops/upstream-migration/wave15-nd3c-productivity.patch`
  - `docs/ops/upstream-migration/wave15-nd3c-productivity-probe-2026-04-24.json`
  - `docs/ops/upstream-migration/wave15-nd3c-productivity-replay-plan-2026-04-24.md`
- ND-3C replay executed and validated:
  - `docs/ops/upstream-migration/wave15-nd3c-execution-2026-04-24.json`
  - full gate: `ok=7 failed=0`.
- ND-3D probe and replay plan prepared:
  - `docs/ops/upstream-migration/wave15-nd3d-runtime.patch`
  - `docs/ops/upstream-migration/wave15-nd3d-runtime-probe-2026-04-24.json`
  - `docs/ops/upstream-migration/wave15-nd3d-runtime-replay-plan-2026-04-24.md`
  - `docs/ops/upstream-migration/wave15-nd3d-runtime-reconcile-2026-04-24.json`
  - probe status: reconcile required (`coder_tools_server.py` hunk mismatch).
- ND-3D reconcile executed and validated:
  - `docs/ops/upstream-migration/wave15-nd3d-execution-2026-04-24.json`
  - full gate: `ok=7 failed=0`.
- ND-3E deletions policy executed:
  - removed upstream-deleted legacy files:
    - `tools/src/aden_tools/tools/google_auth.py`
    - `tools/tests/tools/test_google_auth.py`
  - reference scan returned empty:
    - `rg -n "google_auth|get_google_access_token_from_env_or_file" tools/src tools/tests`
  - full gate passed: `ok=7 failed=0`.
- next lane:
  - ND-4 core/frontend + core/framework bounded triage.
