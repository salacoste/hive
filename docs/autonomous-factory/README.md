# Hive Autonomous Development Factory

This documentation set defines the target operating model for running Hive as an autonomous software development platform across mixed stacks (frontend, backend, fullstack).

Use this as the single source of truth for implementation and operations.

## Documents

1. [01-target-architecture.md](./01-target-architecture.md)
2. [02-access-and-security.md](./02-access-and-security.md)
3. [03-onboarding-repositories.md](./03-onboarding-repositories.md)
4. [04-operations-runbook.md](./04-operations-runbook.md)
5. [05-rollout-plan.md](./05-rollout-plan.md)
6. [06-mcp-server-bundle.md](./06-mcp-server-bundle.md)
7. [07-access-setup-playbook.md](./07-access-setup-playbook.md)
8. [08-official-hive-docs-map.md](./08-official-hive-docs-map.md)
9. [09-autonomous-control-plane.md](./09-autonomous-control-plane.md)
10. [10-coding-factory-operating-model.md](./10-coding-factory-operating-model.md)
11. [11-project-scoped-sessions.md](./11-project-scoped-sessions.md)
12. [12-backlog-task-list.md](./12-backlog-task-list.md)
13. [13-master-implementation-plan.md](./13-master-implementation-plan.md)
14. [14-upstream-memory-reflection-compatibility-plan.md](./14-upstream-memory-reflection-compatibility-plan.md)
15. [15-upstream-sync-governance.md](./15-upstream-sync-governance.md)
16. [16-upstream-wave2-delta-inventory.md](./16-upstream-wave2-delta-inventory.md)
17. [17-memory-architecture-transition-decision.md](./17-memory-architecture-transition-decision.md)
18. [18-unclassified-delta-triage-playbook.md](./18-unclassified-delta-triage-playbook.md)
19. [19-unclassified-delta-decision-register.md](./19-unclassified-delta-decision-register.md)
20. [20-multi-project-autonomy-blueprint.md](./20-multi-project-autonomy-blueprint.md)
21. [21-upstream-migration-wave3-plan.md](./21-upstream-migration-wave3-plan.md)
22. [templates/repo-automation-manifest.yaml](./templates/repo-automation-manifest.yaml)
23. [templates/factory-policy.yaml](./templates/factory-policy.yaml)
24. [templates/task-brief.yaml](./templates/task-brief.yaml)
25. [templates/project-create.json](./templates/project-create.json)
26. [templates/project-onboarding.json](./templates/project-onboarding.json)
27. [templates/project-policy-binding.json](./templates/project-policy-binding.json)
28. [templates/project-execution-template.json](./templates/project-execution-template.json)
29. [templates/autonomous-backlog-task.json](./templates/autonomous-backlog-task.json)
30. [../ops/acceptance-automation-map.md](../ops/acceptance-automation-map.md)
31. [../ops/upstream-migration/latest.md](../ops/upstream-migration/latest.md)
32. [../ops/upstream-migration/landing-branch-bootstrap.md](../ops/upstream-migration/landing-branch-bootstrap.md)
33. [../ops/upstream-migration/replay-bundle-wave3.md](../ops/upstream-migration/replay-bundle-wave3.md)
34. [../ops/upstream-migration/replay-validation-wave3.md](../ops/upstream-migration/replay-validation-wave3.md)
35. [../ops/upstream-migration/overlap-batch-a.md](../ops/upstream-migration/overlap-batch-a.md)
36. [../ops/upstream-migration/overlap-batch-a-execution-queue.md](../ops/upstream-migration/overlap-batch-a-execution-queue.md)

## Scope

- Task intake and execution lifecycle
- Workspace model and repo access
- Security boundaries and secrets model
- GitHub/CI/CD/DB and service access patterns
- Production operations, incident handling, and recovery
- Rollout strategy from local mode to fully autonomous mode

## Design Principles

- One task -> one ephemeral workspace -> one branch -> one PR
- Least privilege by default for all tokens, roles, and network egress
- Human approval required for high-risk actions (schema, infra, production config)
- Deterministic validation gates before merge/deploy
- Full observability and auditability of autonomous actions
