# 02. Access and Security Model

## Security Baseline

Default policy:

- deny by default
- least privilege
- short-lived credentials
- explicit approval for high-impact actions

## Repository Access

Preferred model:

1. Hive uses GitHub App credentials
2. Runner clones repo per task
3. Runner pushes only to task branch
4. Merge through protected branch rules

Do not rely on unrestricted host bind mounts for production mode.

## GitHub Permissions (Recommended Minimum)

- `contents`: read/write
- `pull_requests`: read/write
- `issues`: read/write (optional)
- `checks`: read (optional)

Disallow admin-level scopes unless explicitly needed.

## Secret Management

Use one secret manager as source of truth:

- HashiCorp Vault
- AWS Secrets Manager
- GCP Secret Manager
- 1Password Connect

Rules:

1. No long-lived secrets in repo
2. No plaintext API keys in logs
3. Secret TTL and rotation schedule mandatory
4. Per-service tokens with narrow scopes

## Database Access

Default:

- read-only role for inspection and analysis

Escalated:

- migration role only in approved pipeline stage
- time-bound credentials

Never allow direct production write role from autonomous task execution by default.

## Service Access (Internal/External)

1. API access via gateway
2. Outbound egress allowlist
3. Per-service service account identity
4. Rate limits and retry budgets

## Approval Gates

Mandatory manual approval for:

- schema changes
- infrastructure changes
- production config changes
- credential scope increases
- destructive data operations

## Audit Requirements

Record for every autonomous task:

- who/what created task
- what repo and branch was modified
- what credentials were requested
- what external services were called
- which approvals were granted
- final outcome and artifacts

## Incident Controls

Required controls:

1. kill switch for all active runners
2. queue freeze mode
3. emergency secret revoke
4. branch protection override procedure with two-person approval

