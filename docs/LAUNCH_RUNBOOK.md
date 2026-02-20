# Launch Runbook

## 1. Preflight

1. Apply migrations:
   - `alembic -c crm/alembic.ini upgrade head`
   - `alembic -c workflows/alembic.ini upgrade head`
2. Bootstrap at least one owner explicitly:
   - `maxlevel auth bootstrap-owner --service crm --email owner@example.com --password '...strong...'`
   - `maxlevel auth bootstrap-owner --service workflows --email owner@example.com --password '...strong...'`
3. Verify health:
   - CRM: `/health`, `/ready`
   - Workflows: `/health`, `/ready`
   - Dashboard: `/health`, `/ready`

## 2. Staging Soak

Run all services in staging with production-like env and keep them running for at least 24h while executing:

1. Background synthetic checks:
   - login success/failure
   - forgot/reset password flow
   - invite + accept flow
   - session revoke-all flow
2. Watch:
   - process restarts
   - auth error rates
   - DB lock/contention
   - readiness flaps

## 3. Load Test

Use the auth load script to generate concurrent login traffic:

`python scripts/load_test_auth.py --base-url http://localhost:8020 --email owner@example.com --password '...strong...' --concurrency 20 --requests 500`

Suggested targets:

1. P95 login request latency < 300ms on staging hardware.
2. No 5xx responses under steady load.
3. Rate-limit behavior remains consistent under brute-force simulation.

## 4. Backup/Restore Drill

Perform at least one full restore rehearsal from fresh backups:

`bash scripts/backup_restore_drill.sh`

Success criteria:

1. Backup artifacts are created for CRM/workflows/hiring DBs.
2. Restored DBs can be opened and queried.
3. Row counts for critical auth tables are non-zero on restored copies where expected.

## 5. Go-Live Gate

Launch only when all are true:

1. Full test suite is green.
2. Migrations are applied in target environment.
3. Owner account exists and can log in.
4. Backup/restore drill passed within the last 7 days.
5. On-call + rollback plan is documented and acknowledged.
