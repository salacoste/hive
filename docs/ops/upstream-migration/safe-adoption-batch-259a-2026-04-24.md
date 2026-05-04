# Safe Upstream Adoption — Batch 259-A (Docs, non-destructive)

Date: 2026-04-24

## Scope

Apply low-risk docs deltas from `HEAD..upstream/main` without destructive deletion of local factory/ops documentation.

## Upstream docs delta snapshot

- total docs delta in upstream for this slice:
  - `100 files changed, +123 / -48381`
- dominant pattern:
  - mass deletions of local docs trees (`docs/autonomous-factory/**`, `docs/ops/**`, `ai-proxy-docs/**`).

Decision:
- treat mass-deletion patch as destructive for current branch;
- apply only additive/non-destructive docs subset.

## Applied files

1. `docs/releases/v0.10.3.md` (new)
2. `docs/releases/v0.10.4.md` (new)
3. `docs/skill-registry-prd.md` (updated to upstream content)

## Explicitly deferred in this batch

1. all `D` changes under:
   - `docs/autonomous-factory/**`
   - `docs/ops/**`
   - `ai-proxy-docs/**`
2. rationale:
   - these paths are active local operational artifacts for autonomous-factory rollout;
   - deleting them would drop local runbooks/backlog state and break current workflow continuity.

## Validation

1. file-level verification:
   - `git status --short -- docs/skill-registry-prd.md docs/releases/v0.10.3.md docs/releases/v0.10.4.md`
2. backlog consistency:
   - `uv run python scripts/validate_backlog_markdown.py`
   - `uv run python scripts/backlog_status.py --path docs/autonomous-factory/12-backlog-task-list.md`

---

## 259-D follow-up (Tools medium lane, additive-only)

Applied:

1. `tools/src/aden_tools/credentials/health_check.py`
   - added `PrometheusHealthChecker`
   - wired checker into `HEALTH_CHECKERS["prometheus"]`
2. `tools/tests/test_health_checks.py`
   - expected checker set updated with `prometheus`

Validation:

1. `./scripts/hive_ops_run.sh uv run --package tools pytest tools/tests/test_health_checks.py -q`
   - `40 passed`
2. `./scripts/hive_ops_run.sh uv run --package tools pytest tools/tests/integrations/test_registration.py -q`
   - `302 passed, 1 skipped`
3. `./scripts/hive_ops_run.sh uv run --package tools pytest tools/tests/integrations/test_spec_conformance.py -q`
   - `1394 passed, 2 skipped`
4. `./scripts/hive_ops_run.sh uv run --package tools pytest tools/tests/tools/test_github_tool.py -q`
   - `51 passed` (GitHub review/comment capabilities remain intact)

## 259-B / 259-C decision

Upstream delta for `scripts/**` and `.github/**` in `HEAD..upstream/main` is predominantly destructive
(mass file removals of local operational runbooks/automation). For this wave these lanes are marked
`deferred/no-adopt` to preserve active local autonomous-factory workflows.
