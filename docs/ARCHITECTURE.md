# MaxLevel Architecture

## System Layout

MaxLevel is split into service-focused apps plus a shared CLI SDK:

- `src/maxlevel`: GHL API client + CLI workflows
- `crm`: contacts/pipelines/forms/conversations/campaigns/funnels
- `workflows`: visual workflow builder + execution engine
- `hiring_tool`: recruiting and candidate pipeline workflows
- `dashboard`: cross-service metrics and recent activity feed

## Data Model and Isolation

- CRM is location-oriented (`/loc/{slug}/...`) with tenant resolution in `crm/tenant/deps.py`.
- Tenant authorization can be enabled with per-slug tokens.
- Dashboard reads all service databases in read-only mode through `dashboard/database.py`.

## Workflow Execution

- Workflow webhook triggers are now dispatch-queued (`workflow_dispatch`) instead of inline request execution.
- A background dispatch worker (`workflows/worker.py`) claims pending jobs and runs them through `WorkflowRunner`.
- Dispatch status is queryable at `/webhooks/dispatches/{dispatch_id}`.
- Dispatch claiming uses PostgreSQL `FOR UPDATE SKIP LOCKED` when available for multi-worker-safe claiming.

## Security Controls

- Session auth + RBAC middleware is wired for CRM, Workflows, and Dashboard (role tiers: viewer, agent, manager, admin, owner).
- CRM and Workflows now persist auth users + invites in database tables (`auth_account`, `auth_invite`).
- CRM/Workflows auth now includes user lifecycle UI (`/auth/users`) for role and activation state updates.
- CRM/Workflows include authenticated self-service password rotation (`/auth/password`).
- CRM/Workflows treat bootstrap credentials as seed-only once DB auth callbacks are configured (no direct fallback bypass).
- User lifecycle updates enforce role hierarchy to prevent non-owner escalation and owner-account takeover by lower roles.
- Session auth is resolved against DB user state/role per request in CRM/Workflows so disable/demotion applies immediately.
- Auth form endpoints are brute-force throttled via `*_AUTH_RATE_LIMIT_*` controls.
- Auth form POSTs (including login + invite accept) require CSRF token validation.
- Auth login `next` redirects are sanitized to prevent open-redirect abuse.
- Auth events are appended to immutable-style `auth_event` audit logs (no update/delete paths exposed).
- Dashboard auth is resolved from persistent CRM auth accounts with no direct bootstrap fallback.
- Workflow webhooks:
  - HMAC signing (`WF_WEBHOOK_SIGNING_SECRET`)
  - API key fallback (`WF_WEBHOOK_API_KEY`)
- Workflow chat endpoint:
  - API key (`WF_CHAT_API_KEY`)
- Fail-closed mode:
  - `WF_SECURITY_FAIL_CLOSED=true` or `WF_ENVIRONMENT=production`
  - `CRM_SECURITY_FAIL_CLOSED=true` or `CRM_ENVIRONMENT=production`
- CRM webhook verification:
  - Twilio signature validation
  - SendGrid inbound token/basic auth validation
- Public form protection:
  - per-IP/form rate limiting
  - honeypot field and optional min-submit timing

Current auth supports DB-backed users/invites with bootstrap seeding for first admin. SSO/user lifecycle expansion can be layered on top.

## Availability

Each service exposes health and readiness checks:

- `/health`
- `/ready`

Dashboard aggregates dependent service health.

## Deployment

- `Dockerfile` builds all services from one image base.
- `docker-compose.yml` orchestrates CRM, workflows, hiring, and dashboard.
- `.github/workflows/ci.yml` runs the full test matrix on push and PR.

## Schema Management

- CRM migrations live under `crm/migrations` and run with `alembic -c crm/alembic.ini upgrade head`.
- Workflows migrations live under `workflows/migrations` and run with `alembic -c workflows/alembic.ini upgrade head`.
- Workflows queue schema (`workflow_dispatch`) is migration-managed in production; runtime table auto-creation is limited to SQLite local development.
