# 01. Target Architecture

## Objective

Provide a universal autonomous development platform for multiple stacks:

- Frontend-only repositories
- Backend-only repositories
- Fullstack repositories
- Polyglot mono-repos

## Core Components

1. Hive Core (orchestrator)
- Session management
- Planning and agent routing
- Telegram/Web control surface
- MCP integration hub

2. Workspace Runners (ephemeral execution plane)
- Per-task isolated runtime
- Git clone, code changes, local validation
- Artifact generation (logs, reports, patches)

3. GitHub Integration
- Branch creation
- Push and PR creation
- Review comment publishing
- CI status checks

4. Secrets and Identity
- Short-lived credentials
- Service-specific scoped tokens
- Secret rotation lifecycle

5. Observability and Audit
- Structured task logs
- Execution timeline and decisions
- Access and secret usage audit

## Runtime Topology

1. Task enters Hive Core
2. Hive selects target repository and stack profile
3. Hive allocates a runner image from pool
4. Runner clones repository and creates branch
5. Runner executes task workflow:
- plan
- implement
- validate
- summarize
6. Hive opens PR with evidence and logs
7. Merge via CI policy
8. Runner destroyed

## Runner Types (Minimum Set)

- `runner-node` for Node.js/TypeScript projects
- `runner-python` for Python projects
- `runner-go` for Go projects
- `runner-jvm` for Java/Kotlin projects
- `runner-rust` for Rust projects
- `runner-fullstack` for mixed toolchains

Each runner should be versioned and pinned.

## Task Lifecycle Contract

1. Intake
- source: issue, chat command, webhook
- required fields: repo, objective, acceptance criteria

2. Plan
- scope confirmation
- changed files forecast
- risk flags

3. Implementation
- branch naming standard
- idempotent command execution

4. Validation
- tests
- lint/type checks
- security scan

5. PR
- summary
- risks
- test evidence
- rollback notes

6. Closure
- task status finalization
- metrics update

## Non-Goals

- Direct edits to production servers
- Direct write access to production DB by default
- Global host filesystem access from runner

