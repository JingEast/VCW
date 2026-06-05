# Blocker Inventory

Date: 2026-06-03
Total Blockers: 23

---

## Security Audit Blockers (10)

| ID | Severity | Source | Scope | Risk |
|----|----------|--------|-------|------|
| SEC-01 | 🔴 Critical | GO_LIVE_SECURITY_AUDIT.md | App bootstrap | SECRET_KEY not configured in production |
| SEC-02 | 🔴 Critical | GO_LIVE_SECURITY_AUDIT.md | App bootstrap | JWT_SECRET_KEY not configured in production |
| SEC-03 | 🔴 Critical | GO_LIVE_SECURITY_AUDIT.md | Flask app | JWT module not integrated into create_app |
| SEC-04 | 🔴 Critical | GO_LIVE_SECURITY_AUDIT.md | Flask app | Session auth not registered in create_app |
| SEC-05 | 🔴 Critical | GO_LIVE_SECURITY_AUDIT.md | Flask app | API auth middleware not registered |
| SEC-06 | 🔴 Critical | GO_LIVE_SECURITY_AUDIT.md | Database | RBAC not implemented (no user/role tables) |
| SEC-07 | 🔴 Critical | GO_LIVE_SECURITY_AUDIT.md | Flask app | CSRFProtect not integrated |
| SEC-08 | 🔴 Critical | GO_LIVE_SECURITY_AUDIT.md | Templates | CSRF tokens missing in all POST forms |
| SEC-09 | 🔴 Critical | GO_LIVE_SECURITY_AUDIT.md | API routes | 0 of 18 API routes require authentication |
| SEC-10 | 🔴 Critical | GO_LIVE_SECURITY_AUDIT.md | Page routes | 0 of 22 page routes require login |

## Test Audit Blockers (7)

| ID | Severity | Source | Scope | Risk |
|----|----------|--------|-------|------|
| TST-01 | 🔴 Critical | GO_LIVE_TEST_AUDIT.md | API layer | No API endpoint integration tests |
| TST-02 | 🔴 Critical | GO_LIVE_TEST_AUDIT.md | Auth layer | No authentication flow tests |
| TST-03 | 🟡 High | GO_LIVE_TEST_AUDIT.md | Worker layer | No Celery worker tests |
| TST-04 | 🟡 High | GO_LIVE_TEST_AUDIT.md | Security | No SQL injection security tests |
| TST-05 | 🟡 High | GO_LIVE_TEST_AUDIT.md | Security | No XSS payload security tests |
| TST-06 | 🟡 High | GO_LIVE_TEST_AUDIT.md | Security | No CSRF bypass security tests |
| TST-07 | 🟡 High | GO_LIVE_TEST_AUDIT.md | Coverage | Coverage < 50% (target 80%) |

## Operations Audit Blockers (2)

| ID | Severity | Source | Scope | Risk |
|----|----------|--------|-------|------|
| OPS-01 | 🔴 Critical | GO_LIVE_OPS_AUDIT.md | Database | No automated database backup strategy |
| OPS-02 | 🟡 High | GO_LIVE_OPS_AUDIT.md | Infrastructure | No documented disaster recovery plan |

## Release Audit Blockers (4)

| ID | Severity | Source | Scope | Risk |
|----|----------|--------|-------|------|
| REL-01 | 🔴 Critical | GO_LIVE_RELEASE_AUDIT.md | Git | Release tag v0.0.1 not pushed to remote |
| REL-02 | 🔴 Critical | GO_LIVE_RELEASE_AUDIT.md | GitHub | GitHub Secrets status unknown |
| REL-03 | 🔴 Critical | GO_LIVE_RELEASE_AUDIT.md | GitHub | GitHub Environments not configured |
| REL-04 | 🟢 Closed | GO_LIVE_RELEASE_AUDIT.md | GitHub | Branch protection rules not verified → observable via CI + local script |
