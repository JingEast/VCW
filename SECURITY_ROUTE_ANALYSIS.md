# SECURITY_ROUTE_ANALYSIS.md

## Route Risk Assessment

Generated: 2026-06-03
Scope: All 40 registered routes in VCW Flask app

---

## 1. API Routes (/api/v1/*) — 18 routes

| Route | Method | Risk | Reason | Required Protection |
|-------|--------|------|--------|-------------------|
| /api/v1/generate/stream | GET | 🔴 Critical | Unauthenticated LLM stream can drain quota | JWT + Rate Limit |
| /api/v1/generate/async | POST | 🔴 Critical | Unauthenticated async generation | JWT + Rate Limit |
| /api/v1/generate/batch/async | POST | 🔴 Critical | Batch generation, high cost | JWT + Rate Limit |
| /api/v1/generate/status/<id> | GET | 🟡 Medium | Status polling, low risk | JWT |
| /api/v1/generate/cancel/<id> | POST | 🟡 Medium | Cancel operation | JWT |
| /api/v1/generate/batch/status/<id> | GET | 🟡 Medium | Batch status | JWT |
| /api/v1/generate/batch/cancel/<id> | POST | 🟡 Medium | Batch cancel | JWT |
| /api/v1/editor/de-ai | POST | 🟡 Medium | Content editing | JWT |
| /api/v1/prompts | POST | 🟡 Medium | Prompt modification | JWT + Admin |
| /api/v1/prompts/preview | POST | 🟢 Low | Preview only | JWT |
| /api/v1/trends/fresh | GET | 🟢 Low | Read-only data | JWT or Public |
| /api/v1/trends/scheduler/status | GET | 🟡 Medium | System status | JWT |
| /api/v1/trends/scheduler/toggle | POST | 🔴 Critical | Starts/stops scheduler | JWT + Admin |
| /api/v1/trends/scheduler/trigger | POST | 🔴 Critical | Manual trigger | JWT + Admin |
| /api/v1/model/status | GET | 🟢 Low | Model health | Public |
| /api/v1/prompts/check | POST | 🟢 Low | Prompt validation | JWT |
| /api/v1/files/preview/<path> | GET | 🟡 Medium | File access | JWT |
| /api/v1/generate/save-stream | POST | 🟡 Medium | Save generated content | JWT |

### API Risk Summary
- 🔴 Critical: 4 routes (unauthenticated LLM usage)
- 🟡 Medium: 9 routes
- 🟢 Low: 5 routes
- **Total unprotected**: 18/18 (100%)

---

## 2. Page Routes — 22 routes

| Route | Method | Risk | Reason | Required Protection |
|-------|--------|------|--------|-------------------|
| / | GET | 🟢 Low | Homepage | Public |
| /generate | POST | 🔴 Critical | Form-based generation | CSRF + Session |
| /batch | GET | 🟢 Low | Batch page | Session |
| /batch/generate | POST | 🔴 Critical | Batch form submit | CSRF + Session |
| /editor | GET | 🟢 Low | Editor page | Session |
| /editor/save | POST | 🟡 Medium | Save edits | CSRF + Session |
| /memory | GET | 🟢 Low | Memory page | Session |
| /memory/add | POST | 🟡 Medium | Add memory | CSRF + Session |
| /memory/mark/<id> | POST | 🟡 Medium | Mark memory | CSRF + Session |
| /memory/delete/<id> | POST | 🔴 Critical | Delete data | CSRF + Session |
| /prompts | GET | 🟢 Low | Prompts page | Session |
| /config | GET | 🟡 Medium | Config page | Session + Admin |
| /config/save | POST | 🔴 Critical | Save config | CSRF + Session + Admin |
| /history | GET | 🟢 Low | History page | Session |
| /resources | GET | 🟢 Low | Resources page | Session |
| /trends | GET | 🟢 Low | Trends page | Session |
| /trends/fetch | POST | 🟡 Medium | Fetch trends | CSRF + Session |
| /trend/select/<id> | POST | 🟡 Medium | Select trend | CSRF + Session |
| /trend/delete/<id> | POST | 🔴 Critical | Delete trend | CSRF + Session |
| /trend/add_manual | POST | 🟡 Medium | Add trend | CSRF + Session |
| /trend/delete_expired | POST | 🟡 Medium | Cleanup | CSRF + Session |
| /trend/archive_stale | POST | 🟡 Medium | Archive | CSRF + Session |

### Page Risk Summary
- 🔴 Critical: 4 routes (data modification without CSRF)
- 🟡 Medium: 9 routes
- 🟢 Low: 9 routes
- **Missing CSRF**: 11 POST routes

---

## 3. System Routes — 4 routes

| Route | Risk | Protection |
|-------|------|------------|
| /health | 🟢 Low | Public (monitoring) |
| /metrics | 🟢 Low | Public (monitoring) |
| /debug/profile | 🟡 Medium | Debug mode only (OK) |
| /debug/profile/clear | 🟡 Medium | Debug mode only (OK) |

---

## 4. Action Plan

### Immediate (P0)
1. Add JWT to ALL /api/v1/* routes except /model/status
2. Add CSRF tokens to ALL POST page forms
3. Add login_required to /config, /batch, /editor, /memory, /history

### Short-term (P1)
4. Add role-based access (admin/editor/viewer)
5. Add API rate limiting per user
6. Add audit logging for critical operations

### Long-term (P2)
7. Implement API key rotation
8. Add IP-based allowlisting for admin endpoints
