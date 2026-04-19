# Telegram Operator Sign-off

- generated_at: `2026-04-19T19:19:48Z`
- operator: `ivan`
- scenario: `both`
- project_id: `default`
- overall_status: `pass`
- manual_status: `pass`
- machine_ok: `true`

## Machine Checks
- ✅ `telegram_bridge_status`: enabled=true poller_owner=true running=true startup_status=running
- ✅ `health_telegram_snapshot`: status=ok telegram_running=true startup_status=running
- ✅ `autonomous_ops_status`: status=ok include_runs=true projects_total=0 runs_total=0
- ✅ `remediate_stale_dry_run`: status=ok candidates_total=0 selected_total=0

## Manual Checklist
Run from Telegram and set manual_status=pass only after confirmation.
- [ ] Send /status: Correct project/session; no bridge/runtime errors
- [ ] Send /sessions: Active session list is rendered correctly
- [ ] Send plain text (for example: ping bridge): Bot response received; no duplicate side effects
- [ ] Run one bootstrap flow: Trace contains task_id, run_id, report endpoint, optional PR URL

## Notes
Manual Telegram smoke confirmed by operator (/status,/sessions,plain text,bootstrap flow); post-cutover runtime healthy.
