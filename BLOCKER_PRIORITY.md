# Blocker Priority Matrix

## P0 — Must Fix Before Go-Live (15)

| Rank | ID | Category | Rationale |
|------|-----|----------|-----------|
| 1 | SEC-01 | Secrets | Without SECRET_KEY, sessions are insecure |
| 2 | SEC-02 | Secrets | Without JWT_SECRET_KEY, tokens are forgeable |
| 3 | SEC-03 | Auth | JWT module exists but not wired into app |
| 4 | SEC-04 | Auth | Session auth exists but not wired into app |
| 5 | SEC-05 | Auth | API middleware exists but not registered |
| 6 | SEC-06 | Auth | No RBAC = no privilege separation |
| 7 | SEC-07 | Security | No CSRF = all POST forms vulnerable |
| 8 | SEC-08 | Security | Templates lack csrf_token() |
| 9 | SEC-09 | Auth | 100% API endpoints open to anyone |
| 10 | SEC-10 | Auth | 100% pages open to anyone |
| 11 | OPS-01 | Database | No backup = data loss risk |
| 12 | REL-01 | Release | Cannot deploy without pushed tag |
| 13 | REL-02 | Release | CI/CD cannot authenticate to Docker Hub |
| 14 | REL-03 | Release | CD cannot target staging/production |
| 15 | REL-04 | Release | main branch unprotected |

## P1 — Strongly Recommended (4)

| Rank | ID | Category | Rationale |
|------|-----|----------|-----------|
| 16 | TST-01 | Testing | No API tests = regression risk |
| 17 | TST-02 | Testing | No auth tests = auth bugs undetected |
| 18 | TST-03 | Testing | No worker tests = background job risk |
| 19 | TST-07 | Testing | Low coverage = unknown bug surface |

## P2 — Fix After Go-Live (4)

| Rank | ID | Category | Rationale |
|------|-----|----------|-----------|
| 20 | TST-04 | Testing | SQL injection tests can be added post-launch |
| 21 | TST-05 | Testing | XSS tests can be added post-launch |
| 22 | TST-06 | Testing | CSRF bypass tests can be added post-launch |
| 23 | OPS-02 | Infrastructure | DR plan needed but backup (P0) buys time |
