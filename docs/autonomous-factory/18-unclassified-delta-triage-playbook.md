# 18. Unclassified Delta Triage Playbook

Date: 2026-04-10

## Goal

Define deterministic handling for `other_unclassified` paths reported by `scripts/upstream_delta_status.py`.

## Inputs

1. `./scripts/upstream_sync_preflight.sh`
2. `uv run python scripts/upstream_delta_status.py --json`
3. `docs/ops/upstream-unclassified-decisions.json`
4. `uv run python scripts/check_unclassified_delta_decisions.py`

## Triage Rules

1. If a path is security/stability fix already integrated locally, mark as `already-absorbed` and do not re-merge blindly.
2. If a path affects session/runtime/telegram/autonomous contracts, route to a dedicated backlog item with targeted tests.
3. If a path is docs-only and low-risk, move it into Bucket A mapping and update contract sync.
4. If a path removes architecture used in local factory, mark as high-risk and gate behind architecture decision doc.

## Required Output Per Path

For each unclassified file, record:

- decision: `merge-now` | `defer` | `already-absorbed`
- rationale (1-2 lines)
- validation command(s)
- rollback note (if merge-now)

## Escalation Matrix

- `P0`: auth/credentials/security/runtime crash fixes
- `P1`: orchestration, session model, API contract, bridge behavior
- `P2`: docs/cosmetic/developer UX

## Merge Order For Unclassified Group

1. Security/stability patches first.
2. Runtime orchestration second.
3. API/front-end parity third.
4. Documentation and cleanup last.

## Guardrail

Never mix unclassified high-risk architectural removals with low-risk docs/tooling updates in one merge step.
