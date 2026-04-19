# 03. Repository Onboarding Standard

## Goal

Define one onboarding contract for any repository so Hive can execute tasks consistently across different stacks.

## Onboarding Checklist

1. Repository classification
- stack: node/python/go/jvm/rust/fullstack
- repo type: single repo or monorepo
- deployment target: dev/stage/prod

2. Automation manifest committed
- add `automation/hive.manifest.yaml` (template below)

3. CI prerequisites
- lint/test/build commands wired in CI
- branch protection enabled
- required checks configured

4. Access requirements documented
- secrets needed
- DB/service endpoints
- approval-required operations

5. Smoke command available
- one deterministic post-build command

## Required Repository Files

1. `automation/hive.manifest.yaml`
2. `README.md` with local run instructions
3. `CONTRIBUTING.md` or equivalent dev workflow
4. test and lint config files

## Required Manifest Fields

- `stack`
- `install`
- `lint`
- `typecheck` (or `none`)
- `test`
- `build`
- `smoke`
- `workdirs` (for monorepos)
- `policy` block (actions requiring approval)

Reference template:
[templates/repo-automation-manifest.yaml](./templates/repo-automation-manifest.yaml)

## Branch and PR Conventions

Branch naming:

- `hive/task-<ticket-or-ts>-<short-slug>`

PR title:

- `[Hive] <short objective>`

PR body must contain:

1. objective
2. changed files summary
3. validation evidence
4. risk notes
5. rollback plan

## Validation Contract

Every task should run in this order:

1. install
2. lint
3. typecheck (if enabled)
4. tests
5. build
6. smoke

If any step fails:

- stop pipeline
- attach logs
- return actionable error summary

## Multi-Repo / Fullstack Tasks

For fullstack features spanning multiple repos:

1. create parent task id
2. create child tasks per repo
3. track dependency graph (frontend waits for API contract)
4. open linked PRs
5. merge by dependency order

## Onboarding Exit Criteria

A repository is "factory-ready" when:

1. manifest exists and validated
2. autonomous dry-run task succeeds
3. PR opens with full evidence
4. no privileged action required for normal code tasks

