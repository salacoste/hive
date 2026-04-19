# 05. Rollout Plan

## Goal

Move from local assisted mode to a controlled autonomous factory in phases with explicit safety gates.

Acceptance gate and automation baseline for rollout:

- `../ops/acceptance-automation-map.md`
- `../LOCAL_PROD_RUNBOOK.md`

## Phase 0 - Foundation (Current Local Mode)

Outcomes:

- Hive Core stable
- Telegram/Web control surfaces operational
- baseline model routing and MCP integrations configured

Exit criteria:

- repeated local coding tasks complete successfully
- no unresolved runtime stability issues

## Phase 1 - Controlled Repo Automation

Outcomes:

- GitHub app integration enabled
- task -> branch -> PR automation live
- repository onboarding manifest enforced

Constraints:

- no auto-merge
- no infra or DB write actions

Exit criteria:

- 20+ successful PR tasks
- validation pass rate >= target threshold

## Phase 2 - Multi-Stack Scaling

Outcomes:

- runner pool by stack operational
- fullstack cross-repo task routing in place
- queue/scheduler and concurrency limits active

Constraints:

- high-risk actions still approval-gated

Exit criteria:

- mixed frontend/backend/fullstack workload stable
- queue backlog within SLO

## Phase 3 - Semi-Autonomous Production

Outcomes:

- automatic PR generation and CI feedback loop
- policy-based approvals integrated
- observability dashboards and alerting in place

Constraints:

- merge remains gated by required checks and reviewer policy

Exit criteria:

- incident response playbooks validated
- audit trail complete for all tasks

## Phase 4 - Autonomous Factory Mode

Outcomes:

- autonomous execution for low/medium-risk coding tasks
- automatic reruns for transient failures
- KPI-driven optimization and model/routing tuning

Constraints:

- permanent manual gate for high-risk classes

Exit criteria:

- sustained KPI targets for multiple release cycles

## Risk Register (Initial)

1. Over-privileged credentials
2. Non-deterministic task behavior
3. CI bottlenecks and queue saturation
4. Cross-repo dependency ordering failures
5. Incomplete audit trails

Each risk must have:

- owner
- mitigation
- detection signal
- runbook link

## Governance Cadence

Weekly:

- review KPIs and incidents
- update policy thresholds

Monthly:

- rotate secrets and access review
- disaster recovery drill

Quarterly:

- architecture review
- model routing and cost/performance rebalance
