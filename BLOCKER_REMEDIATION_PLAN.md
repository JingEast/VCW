# Blocker Remediation Plan

## P0 Remediation

### SEC-01: SECRET_KEY not configured
- **Solution**: Create `.env` with `SECRET_KEY=<random-64-char>`. Add validation in `create_app()`.
- **Files**: `.env`, `app/core/config_schema.py`
- **Rollback**: Delete `.env`, revert to `os.urandom()` fallback.

### SEC-02: JWT_SECRET_KEY not configured
- **Solution**: Add `JWT_SECRET_KEY` to `.env`. Update `app/auth/jwt_handler.py`.
- **Files**: `.env`, `app/auth/jwt_handler.py`
- **Rollback**: Remove `.env` key, revert to `SECRET_KEY` fallback.

### SEC-03: JWT module not integrated
- **Solution**: Call `init_jwt(app)` in `create_app()` after blueprint registration.
- **Files**: `app/__init__.py`
- **Rollback**: Comment out `init_jwt(app)` line.

### SEC-04: Session auth not registered
- **Solution**: Call `init_login_manager(app)` and `init_session_manager(app)` in `create_app()`.
- **Files**: `app/__init__.py`, `app/auth/session_handler.py`
- **Rollback**: Comment out init calls.

### SEC-05: API auth middleware not registered
- **Solution**: Call `register_auth_middleware(app)` in `create_app()`.
- **Files**: `app/__init__.py`, `app/middleware/auth_middleware.py`
- **Rollback**: Comment out middleware registration.

### SEC-06: RBAC not implemented
- **Solution**: Add `User`, `Role`, `UserRole` models. Create migration. Add `@require_role` decorator usage.
- **Files**: `vcw_copywriter/db/models.py`, `alembic/versions/`, `app/decorators/auth.py`
- **Rollback**: Drop migration, remove decorators.

### SEC-07: CSRFProtect not integrated
- **Solution**: Add `CSRFProtect(app)` in `create_app()`. Exempt API routes.
- **Files**: `app/__init__.py`
- **Rollback**: Remove `CSRFProtect` init.

### SEC-08: CSRF tokens missing
- **Solution**: Add `{{ csrf_token() }}` to all POST forms in templates.
- **Files**: `templates/*.html`
- **Rollback**: Revert template changes via git.

### SEC-09: 0 API routes require auth
- **Solution**: Add `@api_auth_required` or `@jwt_required()` to all non-public API routes.
- **Files**: `app/api/v1/*.py`
- **Rollback**: Revert decorator additions via git.

### SEC-10: 0 page routes require login
- **Solution**: Add `@page_auth_required` or `@login_required` to sensitive pages.
- **Files**: `app/pages/*.py`
- **Rollback**: Revert decorator additions via git.

### OPS-01: No automated backup
- **Solution**: Add `scripts/backup_db.sh` + cron/CI schedule for daily PostgreSQL dump.
- **Files**: `scripts/backup_db.sh`, `.github/workflows/backup.yml`
- **Rollback**: Remove script and workflow.

### REL-01: Tag not pushed
- **Solution**: `git push origin v0.0.1`
- **Files**: Git remote only
- **Rollback**: `git push --delete origin v0.0.1`

### REL-02: GitHub Secrets unknown
- **Solution**: Manually add `DOCKER_USERNAME`, `DOCKER_PASSWORD`, `CODECOV_TOKEN` in GitHub UI.
- **Files**: None (GitHub UI only)
- **Rollback**: Delete secrets in GitHub UI.

### REL-03: Environments not configured
- **Solution**: Create `staging` and `production` environments in GitHub UI with protection rules.
- **Files**: None (GitHub UI only)
- **Rollback**: Delete environments.

### REL-04: Branch protection not verified ✅ CLOSED
- **Solution**: Enable "Require pull request reviews" and "Require status checks" on `main`.
- **Automated verification**:
  - `scripts/check_branch_protection.sh` — local verification via GitHub API
  - `.github/workflows/ci.yml` — non-blocking `Check branch protection` step in `lint` job that emits `::warning::` if `main` lacks protection
- **Files**: `.github/workflows/ci.yml`, `scripts/check_branch_protection.sh`
- **Rollback**: Delete script; remove CI step.

## P1 Remediation

### TST-01: No API integration tests
- **Solution**: Create `tests/api/` with `test_generate.py`, `test_auth.py` using Flask `TestClient`.
- **Files**: `tests/api/*.py`
- **Rollback**: Delete test files.

### TST-02: No authentication flow tests
- **Solution**: Add login/logout/JWT refresh tests in `tests/api/test_auth.py`.
- **Files**: `tests/api/test_auth.py`
- **Rollback**: Delete test file.

### TST-03: No Celery worker tests
- **Solution**: Add `tests/worker/test_tasks.py` with `celery.contrib.testing`.
- **Files**: `tests/worker/*.py`
- **Rollback**: Delete test files.

### TST-07: Coverage < 50%
- **Solution**: Add unit tests for `app/core/`, `vcw_copywriter/` until 80%.
- **Files**: `tests/**/*.py`
- **Rollback**: Delete new test files.

## P2 Remediation

### TST-04~06: Security penetration tests
- **Solution**: Add `tests/security/` with SQL injection, XSS, CSRF payloads.
- **Files**: `tests/security/*.py`
- **Rollback**: Delete test files.

### OPS-02: No DR plan
- **Solution**: Write `docs/ops/DISASTER_RECOVERY.md` with RTO/RPO and step-by-step procedures.
- **Files**: `docs/ops/DISASTER_RECOVERY.md`
- **Rollback**: Delete document.
