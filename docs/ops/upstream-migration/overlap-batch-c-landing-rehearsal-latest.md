# Overlap Batch C Landing Rehearsal Snapshot

- Generated: 2026-04-18T02:20:46Z
- Target ref: origin/main
- Target SHA: 3c2161aad540610ae88c2c2d4b20ced82ca2d35d
- Landing branch: migration/upstream-wave3
- Replay bundle: `docs/ops/upstream-migration/replay-bundles/wave3-20260417-213932.tar.gz`
- Dependency bundle: `docs/ops/upstream-migration/replay-bundles/wave3-batch-c-dependency-20260418-021530.tar.gz`
- Tools bundle: `docs/ops/upstream-migration/replay-bundles/wave3-batch-c-tools-20260418-021531.tar.gz`
- Changed paths after apply: `227`

## Gate Results

### Clean clone (origin/main + bundles)

- `python compile overlap files`: `ok`
- `mcp_servers.json parse`: `ok`

### Live runtime (current workspace)

- `tools/tests/test_coder_tools_server.py`: `ok`
- `tools/tests/tools/test_github_tool.py`: `ok`
- `scripts/mcp_health_summary.py`: `ok`
- `scripts/verify_access_stack.sh`: `ok`

## Working Tree Snapshot (clean clone)

```
 M tools/Dockerfile
 M tools/coder_tools_server.py
 M tools/mcp_servers.json
 M tools/pyproject.toml
 M tools/src/aden_tools/credentials/__init__.py
 M tools/src/aden_tools/credentials/cloudflare.py
 M tools/src/aden_tools/credentials/discord.py
 M tools/src/aden_tools/credentials/docker_hub.py
 M tools/src/aden_tools/credentials/email.py
 M tools/src/aden_tools/credentials/health_check.py
 M tools/src/aden_tools/credentials/huggingface.py
 M tools/src/aden_tools/credentials/intercom.py
 M tools/src/aden_tools/credentials/pipedrive.py
 M tools/src/aden_tools/credentials/plaid.py
 M tools/src/aden_tools/credentials/postgres.py
 M tools/src/aden_tools/credentials/shell_config.py
 M tools/src/aden_tools/credentials/store_adapter.py
 M tools/src/aden_tools/file_ops.py
 M tools/src/aden_tools/hashline.py
 M tools/src/aden_tools/tools/__init__.py
 M tools/src/aden_tools/tools/apify_tool/apify_tool.py
 M tools/src/aden_tools/tools/apollo_tool/apollo_tool.py
 M tools/src/aden_tools/tools/asana_tool/asana_tool.py
 M tools/src/aden_tools/tools/attio_tool/attio_tool.py
 M tools/src/aden_tools/tools/aws_s3_tool/aws_s3_tool.py
 M tools/src/aden_tools/tools/azure_sql_tool/azure_sql_tool.py
 M tools/src/aden_tools/tools/bigquery_tool/bigquery_tool.py
 M tools/src/aden_tools/tools/brevo_tool/brevo_tool.py
 M tools/src/aden_tools/tools/calcom_tool/calcom_tool.py
 M tools/src/aden_tools/tools/calendar_tool/calendar_tool.py
 M tools/src/aden_tools/tools/cloudflare_tool/cloudflare_tool.py
 M tools/src/aden_tools/tools/cloudinary_tool/cloudinary_tool.py
 M tools/src/aden_tools/tools/csv_tool/csv_tool.py
 M tools/src/aden_tools/tools/databricks_tool/databricks_mcp_tool.py
 M tools/src/aden_tools/tools/databricks_tool/databricks_tool.py
 M tools/src/aden_tools/tools/discord_tool/discord_tool.py
 M tools/src/aden_tools/tools/dns_security_scanner/dns_security_scanner.py
 M tools/src/aden_tools/tools/docker_hub_tool/docker_hub_tool.py
 M tools/src/aden_tools/tools/email_tool/email_tool.py
 M tools/src/aden_tools/tools/exa_search_tool/exa_search_tool.py
 M tools/src/aden_tools/tools/excel_tool/excel_tool.py
 M tools/src/aden_tools/tools/file_system_toolkits/command_sanitizer.py
 M tools/src/aden_tools/tools/file_system_toolkits/data_tools/data_tools.py
 M tools/src/aden_tools/tools/file_system_toolkits/execute_command_tool/execute_command_tool.py
 M tools/src/aden_tools/tools/file_system_toolkits/hashline_edit/hashline_edit.py
 M tools/src/aden_tools/tools/file_system_toolkits/security.py
 M tools/src/aden_tools/tools/github_tool/github_tool.py
 M tools/src/aden_tools/tools/gitlab_tool/gitlab_tool.py
 M tools/src/aden_tools/tools/gmail_tool/gmail_tool.py
 M tools/src/aden_tools/tools/google_analytics_tool/google_analytics_tool.py
 M tools/src/aden_tools/tools/google_docs_tool/google_docs_tool.py
 M tools/src/aden_tools/tools/google_docs_tool/tests/test_google_docs_tool.py
 M tools/src/aden_tools/tools/google_search_console_tool/google_search_console_tool.py
 M tools/src/aden_tools/tools/google_sheets_tool/google_sheets_tool.py
 M tools/src/aden_tools/tools/google_sheets_tool/tests/test_google_sheets_integration.py
 M tools/src/aden_tools/tools/google_sheets_tool/tests/test_google_sheets_tool.py
 M tools/src/aden_tools/tools/greenhouse_tool/greenhouse_tool.py
 M tools/src/aden_tools/tools/http_headers_scanner/http_headers_scanner.py
 M tools/src/aden_tools/tools/hubspot_tool/hubspot_tool.py
 M tools/src/aden_tools/tools/hubspot_tool/tests/test_hubspot_tool.py
 M tools/src/aden_tools/tools/huggingface_tool/huggingface_tool.py
 M tools/src/aden_tools/tools/intercom_tool/intercom_tool.py
 M tools/src/aden_tools/tools/intercom_tool/tests/test_intercom_tool.py
 M tools/src/aden_tools/tools/jira_tool/jira_tool.py
 M tools/src/aden_tools/tools/linear_tool/linear_tool.py
 M tools/src/aden_tools/tools/linear_tool/tests/test_linear_tool.py
 M tools/src/aden_tools/tools/mattermost_tool/mattermost_tool.py
 M tools/src/aden_tools/tools/microsoft_graph_tool/microsoft_graph_tool.py
 M tools/src/aden_tools/tools/mssql_tool/mssql_tool.py
 M tools/src/aden_tools/tools/n8n_tool/n8n_tool.py
 M tools/src/aden_tools/tools/notion_tool/notion_tool.py
 M tools/src/aden_tools/tools/pdf_read_tool/pdf_read_tool.py
 M tools/src/aden_tools/tools/plaid_tool/plaid_tool.py
 M tools/src/aden_tools/tools/port_scanner/port_scanner.py
 M tools/src/aden_tools/tools/postgres_tool/postgres_tool.py
 M tools/src/aden_tools/tools/pushover_tool/pushover_tool.py
 M tools/src/aden_tools/tools/pushover_tool/tests/test_pushover_tool.py
 M tools/src/aden_tools/tools/quickbooks_tool/quickbooks_tool.py
 M tools/src/aden_tools/tools/salesforce_tool/salesforce_tool.py
 M tools/src/aden_tools/tools/serpapi_tool/serpapi_tool.py
 M tools/src/aden_tools/tools/slack_tool/slack_tool.py
 M tools/src/aden_tools/tools/snowflake_tool/snowflake_tool.py
 M tools/src/aden_tools/tools/ssl_tls_scanner/ssl_tls_scanner.py
 M tools/src/aden_tools/tools/stripe_tool/stripe_tool.py
 M tools/src/aden_tools/tools/subdomain_enumerator/subdomain_enumerator.py
 M tools/src/aden_tools/tools/tech_stack_detector/tech_stack_detector.py
 M tools/src/aden_tools/tools/telegram_tool/telegram_tool.py
 M tools/src/aden_tools/tools/trello_tool/trello_tool.py
 M tools/src/aden_tools/tools/twilio_tool/twilio_tool.py
 M tools/src/aden_tools/tools/vercel_tool/vercel_tool.py
 M tools/src/aden_tools/tools/vision_tool/vision_tool.py
 M tools/src/aden_tools/tools/web_scrape_tool/web_scrape_tool.py
 M tools/src/aden_tools/tools/yahoo_finance_tool/yahoo_finance_tool.py
 M tools/src/aden_tools/tools/youtube_tool/youtube_tool.py
 M tools/src/aden_tools/tools/youtube_transcript_tool/youtube_transcript_tool.py
 M tools/src/aden_tools/tools/zoho_crm_tool/tests/test_zoho_crm_tool.py
 M tools/src/aden_tools/tools/zoho_crm_tool/zoho_crm_tool.py
 M tools/src/aden_tools/tools/zoom_tool/zoom_tool.py
 M tools/src/aden_tools/utils/env_helpers.py
 M tools/src/gcu/__init__.py
 M tools/src/gcu/browser/__init__.py
 M tools/src/gcu/browser/bridge.py
 M tools/src/gcu/browser/refs.py
 M tools/src/gcu/browser/session.py
 M tools/src/gcu/browser/tools/advanced.py
 M tools/src/gcu/browser/tools/inspection.py
 M tools/src/gcu/browser/tools/interactions.py
 M tools/src/gcu/browser/tools/lifecycle.py
 M tools/src/gcu/browser/tools/navigation.py
 M tools/src/gcu/browser/tools/tabs.py
 M tools/src/gcu/server.py
 M tools/tests/conftest.py
 M tools/tests/integrations/test_input_validation.py
 M tools/tests/integrations/test_registration.py
 M tools/tests/integrations/test_spec_conformance.py
 M tools/tests/test_browser_tools_comprehensive.py
 M tools/tests/test_coder_tools_server.py
 M tools/tests/test_command_sanitizer.py
 M tools/tests/test_credential_registry.py
 M tools/tests/test_credentials.py
 M tools/tests/test_health_checks.py
 M tools/tests/test_live_health_checks.py
 M tools/tests/test_refs.py
 M tools/tests/test_screenshot_normalization.py
 M tools/tests/test_x_page_load_repro.py
 M tools/tests/tools/test_airtable_tool.py
 M tools/tests/tools/test_apollo_tool.py
 M tools/tests/tools/test_arxiv_tool.py
 M tools/tests/tools/test_asana_tool.py
 M tools/tests/tools/test_attio_tool.py
 M tools/tests/tools/test_aws_s3_tool.py
 M tools/tests/tools/test_azure_sql_tool.py
 M tools/tests/tools/test_bigquery_tool.py
 M tools/tests/tools/test_calcom_tool.py
 M tools/tests/tools/test_calendar_tool.py
 M tools/tests/tools/test_cloudflare.py
 M tools/tests/tools/test_cloudinary_tool.py
 M tools/tests/tools/test_confluence_tool.py
 M tools/tests/tools/test_csv_tool.py
 M tools/tests/tools/test_databricks_tool.py
 M tools/tests/tools/test_dns_security_scanner.py
 M tools/tests/tools/test_email_tool.py
 M tools/tests/tools/test_file_ops.py
 M tools/tests/tools/test_file_ops_hashline.py
 M tools/tests/tools/test_file_system_toolkits.py
 M tools/tests/tools/test_freshdesk_tool.py
 M tools/tests/tools/test_github_tool.py
 M tools/tests/tools/test_gitlab_tool.py
 M tools/tests/tools/test_gmail_tool.py
 M tools/tests/tools/test_google_analytics_tool.py
 M tools/tests/tools/test_google_docs_tool.py
 M tools/tests/tools/test_google_maps_tool.py
 M tools/tests/tools/test_google_search_console_tool.py
 M tools/tests/tools/test_google_sheets_tool.py
 M tools/tests/tools/test_hashline_edit.py
 M tools/tests/tools/test_hubspot_tool.py
 M tools/tests/tools/test_huggingface_tool.py
 M tools/tests/tools/test_intercom_tool.py
 M tools/tests/tools/test_jira_tool.py
 M tools/tests/tools/test_kafka_tool.py
 M tools/tests/tools/test_linear_tool.py
 M tools/tests/tools/test_lusha_tool.py
 M tools/tests/tools/test_mattermost_tool.py
 M tools/tests/tools/test_microsoft_graph_tool.py
 M tools/tests/tools/test_mongodb_tool.py
 M tools/tests/tools/test_notion_tool.py
 M tools/tests/tools/test_pagerduty_tool.py
 M tools/tests/tools/test_pinecone_tool.py
 M tools/tests/tools/test_powerbi_tool.py
 M tools/tests/tools/test_quickbooks_tool.py
 M tools/tests/tools/test_razorpay_tool.py
 M tools/tests/tools/test_redshift_tool.py
 M tools/tests/tools/test_salesforce_tool.py
 M tools/tests/tools/test_security.py
 M tools/tests/tools/test_shopify_tool.py
 M tools/tests/tools/test_slack_tool.py
 M tools/tests/tools/test_ssl_tls_scanner.py
 M tools/tests/tools/test_stripe_tool.py
 M tools/tests/tools/test_supabase_tool.py
 M tools/tests/tools/test_telegram_tool.py
 M tools/tests/tools/test_tines_tool.py
 M tools/tests/tools/test_twilio_tool.py
 M tools/tests/tools/test_vercel_tool.py
 M tools/tests/tools/test_vision_tool.py
 M tools/tests/tools/test_wandb_tool.py
 M tools/tests/tools/test_web_scrape_tool.py
 M tools/tests/tools/test_zendesk_tool.py
 M tools/tests/tools/test_zoho_crm_tool.py
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
?? core/frontend/src/api/projects.ts
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
?? scripts/mcp_health_summary.py
?? scripts/verify_access_stack.sh
?? tools/src/aden_tools/tools/google_auth.py
?? tools/tests/tools/test_google_auth.py
```
