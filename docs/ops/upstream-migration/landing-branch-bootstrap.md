# Landing Branch Bootstrap (Wave 3)

Date: 2026-04-18

## Purpose

Provide a deterministic, container-first bootstrap flow for creating a clean landing branch from upstream before replaying local factory modules.

## Script

- `scripts/upstream_landing_branch_bootstrap.sh`
- `scripts/upstream_landing_branch_probe.sh`

## Print-Only (default)

```bash
./scripts/upstream_landing_branch_bootstrap.sh
```

Output:

- prints base/target/landing refs;
- captures ahead/behind and dirty overlap;
- writes snapshot artifact:
  - `docs/ops/upstream-migration/landing-branch-bootstrap-latest.md`;
- prints exact apply command without switching branch.

## Apply (requires clean worktree)

```bash
HIVE_UPSTREAM_TARGET_REF=origin/main \
HIVE_UPSTREAM_BASE_BRANCH=main \
HIVE_UPSTREAM_LANDING_BRANCH=migration/upstream-wave3 \
./scripts/upstream_landing_branch_bootstrap.sh --apply
```

Apply mode runs:

1. `git fetch origin --prune`
2. `git checkout -B <landing-branch> <target-ref>`

Guardrail:

- apply mode exits with error if `git status --porcelain` is not empty.

## Probe Evidence (no branch switch in current workspace)

```bash
./scripts/upstream_landing_branch_probe.sh
```

What it does:

1. creates an isolated clean clone in a temp directory;
2. checks out `<landing-branch>` from `<target-ref>`;
3. verifies clean worktree in the probe clone;
4. writes evidence:
   - `docs/ops/upstream-migration/landing-branch-probe-latest.md`.
