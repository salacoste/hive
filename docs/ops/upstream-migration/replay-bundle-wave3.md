# Replay Bundle (Wave 3)

Date: 2026-04-18

## Purpose

Provide a deterministic replay package for local factory control-plane modules that must be ported onto the upstream landing branch.

## Script

- `scripts/upstream_replay_bundle.sh`
- `scripts/upstream_replay_compat_report.sh`
- `scripts/upstream_replay_apply_probe.sh`

## Create Bundle

```bash
./scripts/upstream_replay_bundle.sh --create
```

Artifacts:

1. Bundle archive:
   - `docs/ops/upstream-migration/replay-bundles/wave3-<timestamp>.tar.gz`
2. Latest manifest:
   - `docs/ops/upstream-migration/replay-bundle-wave3-latest.md`

## Dry Run

```bash
./scripts/upstream_replay_bundle.sh --dry-run
```

Dry-run writes a manifest only (no tarball), useful to validate path coverage before replay.

## Compatibility Report

```bash
./scripts/upstream_replay_compat_report.sh
```

Artifact:

- `docs/ops/upstream-migration/replay-bundle-wave3-compat-latest.md`

The report classifies each bundled path against `origin/main` as:

- `add` (path does not exist on upstream target);
- `overlay` (path exists and requires merge/reconcile).

## Apply Probe (isolated clone)

```bash
./scripts/upstream_replay_apply_probe.sh
```

Artifact:

- `docs/ops/upstream-migration/replay-apply-probe-latest.md`

This probe applies the bundle in a temporary clean clone on top of `origin/main` and captures resulting `git status --short` without touching the current working branch.
