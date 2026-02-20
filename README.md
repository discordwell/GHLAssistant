# MaxLevel

MaxLevel is a modular GoHighLevel replacement platform with:

- `src/maxlevel`: GHL API/automation CLI + SDK
- `crm`: multi-tenant CRM app
- `workflows`: workflow builder and execution engine
- `hiring_tool`: hiring pipeline app
- `dashboard`: unified metrics/activity dashboard

## Quick Start (Local)

1. Create environment and install:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,crm,workflows,dashboard,hiring]"
```

2. Configure env:

```bash
cp .env.example .env
```

For production-hardening defaults, start from:

```bash
cp .env.production.example .env
```

3. Run services:

```bash
uvicorn crm.app:app --port 8020
uvicorn hiring_tool.app:app --port 8021
uvicorn workflows.app:app --port 8022
uvicorn dashboard.app:app --port 8023
```

## Database Migrations

Run migrations before starting production services:

```bash
alembic -c crm/alembic.ini upgrade head
alembic -c workflows/alembic.ini upgrade head
```

Notes:
- CRM and Workflows use Alembic for production schema management.
- Workflows only auto-creates tables for SQLite local-dev mode.

## Production-Like Local Deployment

Use Docker Compose:

```bash
docker compose up --build
```

Services:

- CRM: [http://localhost:8020](http://localhost:8020)
- Hiring: [http://localhost:8021](http://localhost:8021)
- Workflows: [http://localhost:8022](http://localhost:8022)
- Dashboard: [http://localhost:8023](http://localhost:8023)

## Security Hardening Controls

### Workflows

- `WF_WEBHOOK_SIGNING_SECRET`: HMAC verification for inbound workflow webhooks
- `WF_WEBHOOK_API_KEY`: API-key auth fallback for webhooks
- `WF_CHAT_API_KEY`: API-key auth for `/chat/send`
- `WF_WEBHOOK_ASYNC_DISPATCH=true`: queue webhook triggers instead of running inline
- `WF_SECURITY_FAIL_CLOSED=true` (or `WF_ENVIRONMENT=production`): reject insecure webhook/chat configs
- `WF_AUTH_ENABLED=true`: enable session auth + RBAC middleware

### CRM

- `CRM_WEBHOOKS_VERIFY_TWILIO_SIGNATURE=true`: validate Twilio callback signatures
- `CRM_SENDGRID_INBOUND_TOKEN`: require token for SendGrid inbound endpoint
- `CRM_TENANT_AUTH_REQUIRED=true`: require tenant token on `/loc/{slug}/...` routes
- `CRM_TENANT_ACCESS_TOKENS=slug:token,...`: per-tenant access tokens
- `CRM_SECURITY_FAIL_CLOSED=true` (or `CRM_ENVIRONMENT=production`): reject insecure webhook configs
- `CRM_AUTH_ENABLED=true`: enable session auth + RBAC middleware
- Form anti-spam:
  - `CRM_FORM_RATE_LIMIT_*`
  - honeypot field via `CRM_FORM_HONEYPOT_FIELD`

### Dashboard

- `DASH_AUTH_ENABLED=true`: enable session auth + RBAC middleware

Auth bootstrap credentials are currently environment-driven (`*_AUTH_BOOTSTRAP_*`) as a skeleton; replace with a real user store/IdP before GA.

## Health/Readiness Endpoints

- CRM: `/health`, `/ready`
- Workflows: `/health`, `/ready`
- Hiring: `/health`, `/ready`
- Dashboard: `/health`, `/ready`

## Testing

Run the full suite:

```bash
pytest tests crm/tests workflows/tests dashboard/tests hiring_tool/tests
```

CI workflow is included at `.github/workflows/ci.yml`.

## Notes

- Workflow dispatch claiming uses PostgreSQL `FOR UPDATE SKIP LOCKED` when available for safer multi-worker processing.
- SQLite/dev mode falls back to best-effort queue claiming.
