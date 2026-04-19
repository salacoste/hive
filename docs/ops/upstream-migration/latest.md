# Upstream Migration Snapshot (Latest)

- Baseline: `docs/ops/upstream-migration/baseline-2026-04-17.md`
- Detailed plan: `docs/autonomous-factory/21-upstream-migration-wave3-plan.md`
- Landing bootstrap: `docs/ops/upstream-migration/landing-branch-bootstrap.md`
- Landing probe evidence: `docs/ops/upstream-migration/landing-branch-probe-latest.md`
- Replay bundle guide: `docs/ops/upstream-migration/replay-bundle-wave3.md`
- Replay bundle manifest: `docs/ops/upstream-migration/replay-bundle-wave3-latest.md`
- Replay compatibility report: `docs/ops/upstream-migration/replay-bundle-wave3-compat-latest.md`
- Replay apply probe: `docs/ops/upstream-migration/replay-apply-probe-latest.md`
- Replay validation plan: `docs/ops/upstream-migration/replay-validation-wave3.md`
- Overlap batch A runbook: `docs/ops/upstream-migration/overlap-batch-a.md`
- Overlap batch A execution queue: `docs/ops/upstream-migration/overlap-batch-a-execution-queue.md`
- Overlap batch B runbook: `docs/ops/upstream-migration/overlap-batch-b.md`
- Overlap batch C runbook: `docs/ops/upstream-migration/overlap-batch-c.md`

Key facts:

- local is behind `origin/main` by `225` commits;
- upstream delta size is `649` changed entries;
- local/upstream overlap is `68` paths;
- unclassified decision coverage refreshed (April 18, 2026):
  - `covered_unclassified=634`;
  - `missing=0`;
  - `stale=0`;
  - tally: `already-absorbed=15`, `defer=619`, `merge-now=0`.
- landing branch bootstrap status (April 18, 2026):
  - local ref created: `migration/upstream-wave3` -> `origin/main`;
  - isolated probe checkout passed (`probe worktree dirty paths=0`).
- replay bundle status (April 18, 2026):
  - created wave3 control-plane bundle (36 paths, 0 missing);
  - bundle artifact:
    - `docs/ops/upstream-migration/replay-bundles/wave3-20260417-213932.tar.gz`;
  - checksum tracked in latest manifest.
  - compatibility report against `origin/main`:
    - `add=36`, `overlay=0`.
  - apply probe against `origin/main`:
    - changed paths after apply=`36`;
    - `modified/tracked=0`, `untracked=36`.
- overlap batch A status (April 18, 2026):
  - full export prepared (`overlap-batch-a-latest.patch`);
  - focus map + focus patch prepared;
  - focus probe (`git apply --check`) passes for focused runtime set (`changed paths=5`);
  - 3-way conflict probe passes (`unmerged files=0`);
  - file-by-file apply probe is green for:
    - `app.py`, `routes_execution.py`, `routes_sessions.py`, `session_manager.py`,
      `queen_orchestrator.py`, `routes_credentials.py`.
  - integration probe (`scripts/upstream_overlap_batch_a_integration_probe.sh`) added and executed:
    - baseline (`replay + focus patch`) fails with `ModuleNotFoundError: framework.runtime`;
    - deterministic dependency bundle created:
      - manifest: `docs/ops/upstream-migration/overlap-batch-a-dependency-bundle-latest.md`;
      - artifact: `docs/ops/upstream-migration/replay-bundles/wave3-batch-a-dependency-20260418-011208.tar.gz`;
      - includes: `runtime`, `graph`, `runner`, `model_routing.py`, `llm/fallback.py`,
        `routes_graphs.py`;
    - deterministic hotspots bundle created:
      - manifest: `docs/ops/upstream-migration/overlap-batch-a-hotspots-bundle-latest.md`;
      - artifact: `docs/ops/upstream-migration/replay-bundles/wave3-batch-a-hotspots-20260418-011209.tar.gz`;
      - includes 6 server hotspot files (`app/session_manager/routes_execution/routes_sessions/queen_orchestrator/routes_credentials`);
    - dependency closure formalized with mergeable runner fix:
      - `core/framework/runner/__init__.py` now lazy-loads runner exports
        (prevents graph/runner package init cycle);
    - overlay (`runtime + graph + runner + routes_graphs.py`) passes smoke + API health test;
    - landing rehearsal (`scripts/upstream_overlap_batch_a_landing_rehearsal.sh`) on clean clone:
      - applies replay + dependency + hotspots bundles;
      - gate report: `docs/ops/upstream-migration/overlap-batch-a-landing-rehearsal-latest.md`;
      - results: `test_api profile subset=ok`, `test_telegram_bridge=ok`,
        `test_queen_orchestrator=ok`.
    - guarded landing-branch apply helper added:
      - `scripts/upstream_overlap_batch_a_bundle_apply.sh` (`--check`/`--apply`).
    - landing integration snapshot recorded:
      - report: `docs/ops/upstream-migration/overlap-batch-a-landing-integration-latest.md`;
      - clean landing clone commit: `ff9b88b9a51071d4c5c3b2d82346c2bfb807080a`;
      - gate status: `test_api profile subset=ok`, `test_telegram_bridge=ok`,
        `test_queen_orchestrator=ok`, `test_control_plane_contract=ok`.
  - controlled landing-branch apply script prepared:
    - `scripts/upstream_overlap_batch_a_apply.sh` (`--check`/`--apply` with branch/worktree guards).
  - execution order and per-file test checkpoints documented in execution queue runbook.
- overlap batch B status (April 18, 2026):
  - deterministic export prepared:
    - `docs/ops/upstream-migration/overlap-batch-b-latest.patch`;
    - `docs/ops/upstream-migration/overlap-batch-b-latest.md` (numstat included).
  - deterministic dependency bundle prepared:
    - manifest: `docs/ops/upstream-migration/overlap-batch-b-dependency-bundle-latest.md`;
    - artifact:
      `docs/ops/upstream-migration/replay-bundles/wave3-batch-b-dependency-20260418-020126.tar.gz`.
  - deterministic frontend bundle prepared:
    - manifest: `docs/ops/upstream-migration/overlap-batch-b-bundle-latest.md`;
    - artifact:
      `docs/ops/upstream-migration/replay-bundles/wave3-batch-b-frontend-20260418-020126.tar.gz`.
  - landing rehearsal (`scripts/upstream_overlap_batch_b_landing_rehearsal.sh`) on clean clone:
    - report: `docs/ops/upstream-migration/overlap-batch-b-landing-rehearsal-latest.md`;
    - required gates: `npm ci=ok`, `operator TS smoke=ok`,
      `chat-helpers vitest=ok`;
    - full frontend build remains informational and currently `failed` due
      legacy out-of-scope pages (`queen-dm`, `colony-chat`, legacy credentials/config APIs).
  - guarded landing-branch apply helper prepared:
    - `scripts/upstream_overlap_batch_b_bundle_apply.sh` (`--check`/`--apply`).
- overlap batch C status (April 18, 2026):
  - deterministic export prepared:
    - `docs/ops/upstream-migration/overlap-batch-c-latest.patch`;
    - `docs/ops/upstream-migration/overlap-batch-c-latest.md` (numstat included).
  - deterministic dependency bundle prepared:
    - manifest: `docs/ops/upstream-migration/overlap-batch-c-dependency-bundle-latest.md`;
    - artifact:
      `docs/ops/upstream-migration/replay-bundles/wave3-batch-c-dependency-20260418-021530.tar.gz`.
  - deterministic tools bundle prepared:
    - manifest: `docs/ops/upstream-migration/overlap-batch-c-bundle-latest.md`;
    - artifact:
      `docs/ops/upstream-migration/replay-bundles/wave3-batch-c-tools-20260418-021531.tar.gz`.
  - landing rehearsal (`scripts/upstream_overlap_batch_c_landing_rehearsal.sh`) results:
    - report: `docs/ops/upstream-migration/overlap-batch-c-landing-rehearsal-latest.md`;
    - clean-clone gates: `python compile overlap files=ok`, `mcp_servers.json parse=ok`;
    - live runtime gates: `test_coder_tools_server=ok`,
      `test_github_tool=ok`, `mcp_health_summary=ok`, `verify_access_stack=ok`.
  - guarded landing-branch apply helper prepared:
    - `scripts/upstream_overlap_batch_c_bundle_apply.sh` (`--check`/`--apply`).
- full regression gate status (April 18, 2026):
  - executed and green in container-first runtime:
    - `./scripts/acceptance_toolchain_self_check.sh` = `ok`;
    - `./scripts/check_runtime_parity.sh` = `ok`;
    - `./scripts/local_prod_checklist.sh` = `ok`;
    - `uv run --package framework pytest core/framework/server/tests/test_api.py -q` =
      `176 passed`;
    - `uv run --package framework pytest core/framework/server/tests/test_telegram_bridge.py -q` =
      `28 passed`;
    - `uv run --no-project python scripts/autonomous_delivery_e2e_smoke.py` = `ok`.
  - ops summary confirms:
    - `stuck_runs_total=0`,
    - `no_progress_projects_total=0`,
    - `loop_stale=false`.
- cutover status (April 18, 2026):
  - runtime rebuild executed:
    - `docker compose up -d --build hive-core hive-scheduler` completed.
  - post-cutover checks are green:
    - `docker compose ps` -> services healthy;
    - `/api/health` -> `status=ok`;
    - `/api/telegram/bridge/status` -> `status=ok`;
    - `/api/autonomous/ops/status` -> `status=ok`.
  - Telegram operator sign-off artifact generated:
    - `docs/ops/telegram-signoff/latest.json`,
    - `docs/ops/telegram-signoff/latest.md`;
  - machine checks: `ok`, manual checklist: `pending`.
