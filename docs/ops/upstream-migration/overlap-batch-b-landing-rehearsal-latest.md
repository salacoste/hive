# Overlap Batch B Landing Rehearsal Snapshot

- Generated: 2026-04-18T02:01:34Z
- Target ref: origin/main
- Target SHA: 3c2161aad540610ae88c2c2d4b20ced82ca2d35d
- Landing branch: migration/upstream-wave3
- Replay bundle: `docs/ops/upstream-migration/replay-bundles/wave3-20260417-213932.tar.gz`
- Dependency bundle: `docs/ops/upstream-migration/replay-bundles/wave3-batch-b-dependency-20260418-020126.tar.gz`
- Frontend bundle: `docs/ops/upstream-migration/replay-bundles/wave3-batch-b-frontend-20260418-020126.tar.gz`
- Changed paths after apply: `60`

## Gate Results

- `npm ci`: `ok`
- `operator TS smoke`: `ok`
- `npm run test -- src/lib/chat-helpers.test.ts`: `ok`
- `npm run build` (full frontend, informational): `failed`

## Working Tree Snapshot

```
 M core/frontend/src/api/agents.ts
 M core/frontend/src/api/client.ts
 M core/frontend/src/api/credentials.ts
 M core/frontend/src/api/execution.ts
 M core/frontend/src/api/logs.ts
 M core/frontend/src/api/sessions.ts
 M core/frontend/src/api/types.ts
 M core/frontend/src/components/ChatPanel.tsx
 M core/frontend/src/components/MultiQuestionWidget.tsx
 M core/frontend/src/components/ParallelSubagentBubble.tsx
 M core/frontend/src/components/QuestionWidget.tsx
 M core/frontend/src/lib/chat-helpers.test.ts
 M core/frontend/src/lib/chat-helpers.ts
 M core/frontend/src/lib/graphUtils.ts
?? core/framework/server/autonomous_pipeline.py
?? core/framework/server/project_execution.py
?? core/framework/server/project_metrics.py
?? core/framework/server/project_onboarding.py
?? core/framework/server/project_policy.py
?? core/framework/server/project_retention.py
?? core/framework/server/project_store.py
?? core/framework/server/project_templates.py
?? core/framework/server/project_toolchain.py
?? core/framework/server/routes_autonomous.py
?? core/framework/server/routes_projects.py
?? core/framework/server/telegram_bridge.py
?? core/frontend/src/api/autonomous.ts
?? core/frontend/src/api/graphs.ts
?? core/frontend/src/api/projects.ts
?? core/frontend/src/components/DraftGraph.tsx
?? core/frontend/src/components/HistorySidebar.tsx
?? core/frontend/src/components/NodeDetailPanel.tsx
?? core/frontend/src/components/TopBar.tsx
?? core/frontend/src/lib/graph-converter.test.ts
?? core/frontend/src/lib/graph-converter.ts
?? core/frontend/src/lib/tab-persistence.ts
?? core/frontend/src/pages/my-agents.tsx
?? core/frontend/src/pages/workspace.tsx
?? docs/LOCAL_PROD_RUNBOOK.md
?? docs/autonomous-factory/
?? scripts/acceptance_gate_presets.sh
?? scripts/acceptance_gate_presets_smoke.sh
?? scripts/acceptance_ops_summary.py
?? scripts/acceptance_report_artifact.py
?? scripts/acceptance_report_digest.py
?? scripts/acceptance_report_hygiene.py
?? scripts/acceptance_report_regression_guard.py
?? scripts/acceptance_scheduler_snapshot.sh
?? scripts/acceptance_toolchain_self_check.sh
?? scripts/acceptance_toolchain_self_check_deep.sh
?? scripts/acceptance_weekly_maintenance.sh
?? scripts/autonomous_acceptance_gate.sh
?? scripts/autonomous_delivery_e2e_smoke.py
?? scripts/autonomous_loop_tick.sh
?? scripts/autonomous_operator_profile.sh
?? scripts/autonomous_ops_drill.sh
?? scripts/autonomous_ops_health_check.sh
?? scripts/autonomous_remediate_stale_runs.sh
?? scripts/autonomous_scheduler_daemon.py
?? scripts/verify_access_stack.sh
```

## frontend_full_build error excerpt

```
.gate_frontend_full_build.stdout:5:src/components/QueenSessionSwitcher.tsx(3,15): error TS2305: Module '"@/api/types"' has no exported member 'HistorySession'.
.gate_frontend_full_build.stdout:6:src/components/SettingsModal.tsx(90,8): error TS2339: Property 'validateKey' does not exist on type '{ list: () => Promise<{ credentials: CredentialInfo[]; }>; get: (credentialId: string) => Promise<CredentialInfo>; save: (credentialId: string, keys: Record<...>) => Promise<...>; delete: (credentialId: string) => Promise<...>; checkAgent: (agentPath: string) => Promise<...>; readiness: (bundle?: string) => Promise<...'.
.gate_frontend_full_build.stdout:7:src/components/TriggerDetailPanel.tsx(54,27): error TS2339: Property 'deactivateTrigger' does not exist on type '{ create: (agentPath?: string | undefined, agentId?: string | undefined, model?: string | undefined, initialPrompt?: string | undefined, queenResumeFrom?: string | undefined, projectId?: string | undefined) => Promise<...>; ... 13 more ...; deleteHistory: (sessionId: string) => Promise<...>; }'.
.gate_frontend_full_build.stdout:8:src/components/TriggerDetailPanel.tsx(56,27): error TS2339: Property 'activateTrigger' does not exist on type '{ create: (agentPath?: string | undefined, agentId?: string | undefined, model?: string | undefined, initialPrompt?: string | undefined, queenResumeFrom?: string | undefined, projectId?: string | undefined) => Promise<...>; ... 13 more ...; deleteHistory: (sessionId: string) => Promise<...>; }'.
.gate_frontend_full_build.stdout:9:src/context/ColonyContext.tsx(145,24): error TS2339: Property 'queen_id' does not exist on type 'LiveSession'.
.gate_frontend_full_build.stdout:10:src/context/ColonyContext.tsx(153,31): error TS2339: Property 'queen_id' does not exist on type '{ session_id: string; cold: boolean; live: boolean; has_messages: boolean; created_at: number; agent_name?: string | null | undefined; agent_path?: string | null | undefined; project_id?: string | ... 1 more ... | undefined; } | { ...; }'.
.gate_frontend_full_build.stdout:12:src/context/ColonyContext.tsx(156,41): error TS2339: Property 'queen_id' does not exist on type '{ session_id: string; cold: boolean; live: boolean; has_messages: boolean; created_at: number; agent_name?: string | null | undefined; agent_path?: string | null | undefined; project_id?: string | ... 1 more ... | undefined; } | { ...; }'.
.gate_frontend_full_build.stdout:14:src/context/ColonyContext.tsx(165,16): error TS2339: Property 'queen_id' does not exist on type '{ session_id: string; cold: boolean; live: boolean; has_messages: boolean; created_at: number; agent_name?: string | null | undefined; agent_path?: string | null | undefined; project_id?: string | ... 1 more ... | undefined; } | { ...; }'.
.gate_frontend_full_build.stdout:16:src/context/ColonyContext.tsx(166,22): error TS2339: Property 'last_active_at' does not exist on type '{ session_id: string; cold: boolean; live: boolean; has_messages: boolean; created_at: number; agent_name?: string | null | undefined; agent_path?: string | null | undefined; project_id?: string | ... 1 more ... | undefined; } | { ...; }'.
.gate_frontend_full_build.stdout:18:src/context/ColonyContext.tsx(167,44): error TS2339: Property 'queen_id' does not exist on type '{ session_id: string; cold: boolean; live: boolean; has_messages: boolean; created_at: number; agent_name?: string | null | undefined; agent_path?: string | null | undefined; project_id?: string | ... 1 more ... | undefined; } | { ...; }'.
.gate_frontend_full_build.stdout:20:src/context/ColonyContext.tsx(168,68): error TS2339: Property 'queen_id' does not exist on type '{ session_id: string; cold: boolean; live: boolean; has_messages: boolean; created_at: number; agent_name?: string | null | undefined; agent_path?: string | null | undefined; project_id?: string | ... 1 more ... | undefined; } | { ...; }'.
.gate_frontend_full_build.stdout:22:src/context/ColonyContext.tsx(180,33): error TS2339: Property 'workers' does not exist on type 'DiscoverEntry'.
.gate_frontend_full_build.stdout:23:src/context/ColonyContext.tsx(201,28): error TS2339: Property 'queen_id' does not exist on type 'LiveSession'.
.gate_frontend_full_build.stdout:24:src/context/ColonyContext.tsx(202,25): error TS2339: Property 'queen_id' does not exist on type 'LiveSession'.
.gate_frontend_full_build.stdout:25:src/context/ColonyContext.tsx(248,34): error TS2339: Property 'queen_id' does not exist on type 'LiveSession'.
.gate_frontend_full_build.stdout:26:src/context/ColonyContext.tsx(248,57): error TS2339: Property 'queen_id' does not exist on type 'LiveSession'.
.gate_frontend_full_build.stdout:27:src/context/ColonyContext.tsx(268,15): error TS2339: Property 'deleteAgent' does not exist on type '{ discover: () => Promise<DiscoverResult>; }'.
.gate_frontend_full_build.stdout:28:src/pages/colony-chat.tsx(418,58): error TS2339: Property 'colony_name' does not exist on type 'LiveSession'.
.gate_frontend_full_build.stdout:29:src/pages/colony-chat.tsx(966,14): error TS2678: Type '"worker_colony_loaded"' is not comparable to type 'EventTypeName'.
.gate_frontend_full_build.stdout:30:src/pages/colony-chat.tsx(1277,13): error TS2322: Type '"running" | "planning" | "building" | "staging" | "independent"' is not assignable to type '"running" | "planning" | "building" | "staging" | undefined'.
.gate_frontend_full_build.stdout:32:src/pages/credentials.tsx(17,8): error TS2724: '"@/api/credentials"' has no exported member named 'CredentialSpec'. Did you mean 'credentialsApi'?
.gate_frontend_full_build.stdout:33:src/pages/credentials.tsx(18,8): error TS2305: Module '"@/api/credentials"' has no exported member 'CredentialAccount'.
.gate_frontend_full_build.stdout:34:src/pages/credentials.tsx(206,41): error TS2339: Property 'listSpecs' does not exist on type '{ list: () => Promise<{ credentials: CredentialInfo[]; }>; get: (credentialId: string) => Promise<CredentialInfo>; save: (credentialId: string, keys: Record<...>) => Promise<...>; delete: (credentialId: string) => Promise<...>; checkAgent: (agentPath: string) => Promise<...>; readiness: (bundle?: string) => Promise<...'.
.gate_frontend_full_build.stdout:35:src/pages/credentials.tsx(272,39): error TS7006: Parameter 'a' implicitly has an 'any' type.
.gate_frontend_full_build.stdout:36:src/pages/credentials.tsx(307,43): error TS2339: Property 'resync' does not exist on type '{ list: () => Promise<{ credentials: CredentialInfo[]; }>; get: (credentialId: string) => Promise<CredentialInfo>; save: (credentialId: string, keys: Record<...>) => Promise<...>; delete: (credentialId: string) => Promise<...>; checkAgent: (agentPath: string) => Promise<...>; readiness: (bundle?: string) => Promise<...'.
.gate_frontend_full_build.stdout:37:src/pages/credentials.tsx(313,39): error TS7006: Parameter 'a' implicitly has an 'any' type.
.gate_frontend_full_build.stdout:38:src/pages/credentials.tsx(395,23): error TS7006: Parameter 't' implicitly has an 'any' type.
.gate_frontend_full_build.stdout:39:src/pages/credentials.tsx(554,30): error TS7006: Parameter 'acct' implicitly has an 'any' type.
.gate_frontend_full_build.stdout:40:src/pages/queen-dm.tsx(13,27): error TS2305: Module '"@/api/types"' has no exported member 'HistorySession'.
.gate_frontend_full_build.stdout:41:src/pages/queen-dm.tsx(266,40): error TS2339: Property 'queen_id' does not exist on type '{ session_id: string; cold: boolean; live: boolean; has_messages: boolean; created_at: number; agent_name?: string | null | undefined; agent_path?: string | null | undefined; project_id?: string | ... 1 more ... | undefined; }'.
.gate_frontend_full_build.stdout:42:src/pages/queen-dm.tsx(288,41): error TS2339: Property 'colonySpawn' does not exist on type '{ trigger: (sessionId: string, entryPointId: string, inputData: Record<string, unknown>, sessionState?: Record<string, unknown> | undefined) => Promise<TriggerResult>; ... 6 more ...; goalProgress: (sessionId: string) => Promise<...>; }'.
.gate_frontend_full_build.stdout:43:src/pages/queen-dm.tsx(403,37): error TS2339: Property 'queued' does not exist on type 'ChatMessage'.
.gate_frontend_full_build.stdout:44:src/pages/queen-dm.tsx(404,39): error TS2339: Property 'queued' does not exist on type 'ChatMessage'.
.gate_frontend_full_build.stdout:45:src/pages/queen-dm.tsx(413,14): error TS2678: Type '"llm_turn_complete"' is not comparable to type 'EventTypeName'.
.gate_frontend_full_build.stdout:46:src/pages/queen-dm.tsx(532,14): error TS2678: Type '"colony_created"' is not comparable to type 'EventTypeName'.
.gate_frontend_full_build.stdout:47:src/pages/queen-dm.tsx(556,13): error TS2322: Type '"colony_link"' is not assignable to type '"system" | "agent" | "user" | "tool_status" | "worker_input_request" | "run_divider" | undefined'.
.gate_frontend_full_build.stdout:48:src/pages/queen-dm.tsx(732,9): error TS2353: Object literal may only specify known properties, and 'queued' does not exist in type 'ChatMessage'.
.gate_frontend_full_build.stdout:49:src/pages/queen-dm.tsx(781,33): error TS2339: Property 'queued' does not exist on type 'ChatMessage'.
.gate_frontend_full_build.stdout:50:src/pages/queen-dm.tsx(782,35): error TS2339: Property 'queued' does not exist on type 'ChatMessage'.
.gate_frontend_full_build.stdout:51:src/pages/queen-dm.tsx(814,11): error TS2322: Type '"running" | "planning" | "building" | "staging" | "independent"' is not assignable to type '"running" | "planning" | "building" | "staging" | undefined'.
```
