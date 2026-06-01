# VCW Microservice Readiness Report

**Task**: TASK-RV-MS-01  
**Date**: 2026-06-01  
**Scope**: docker orchestration, celery worker, service discovery, distributed stability

---

## 1. Quality Gates

| Gate | Result |
|------|--------|
| `pytest tests/` | ✅ **407 passed** (387 + 20 new distributed tests) |
| `pytest -n auto` | ✅ 407 passed (parallel) |
| `pytest --cov` | ✅ 55% total coverage |
| `ruff check .` | ✅ passed |
| `mypy .` | ✅ passed |

> **Note**: `docker compose up --build` and `celery -A worker inspect active` could not be executed live because Docker is not installed on this host. All validations below are based on configuration review, code analysis, and unit tests.

---

## 2. Docker Orchestration Review

### 2.1 Service Topology

```
redis     ┐
          ├→ web  (Flask + /health)
postgres  ┘    ├→ worker (Celery -c 2)
               └→ beat   (Celery beat)
```

### 2.2 Startup Order

| Service | Depends On | Condition | Status |
|---------|-----------|-----------|--------|
| web | redis, postgres | `service_healthy` | ✅ |
| worker | redis, postgres | `service_healthy` | ✅ |
| beat | redis, postgres | `service_healthy` | ✅ |

### 2.3 Healthchecks

| Service | Check | Interval | Timeout | Retries |
|---------|-------|----------|---------|---------|
| redis | `redis-cli ping` | 5s | 3s | 5 |
| postgres | `pg_isready -U vcw -d vcw` | 5s | 3s | 5 |
| web | HTTP GET /health | 10s | 5s | 5 |

### 2.4 Resource Limits (Added)

| Service | Memory Limit | Restart Policy |
|---------|-------------|----------------|
| redis | 512M | unless-stopped |
| postgres | 1G | unless-stopped |
| web | 512M | unless-stopped |
| worker | 1G | unless-stopped |
| beat | 256M | unless-stopped |

### 2.5 Volume Mounts

| Service | Mount | Risk |
|---------|-------|------|
| web | `.:/app` | ⚠️ Dev convenience; production should use `COPY` only |
| worker | `.:/app` | ⚠️ Same as above |
| beat | `.:/app` | ⚠️ Same as above |
| redis | `redis_data:/data` | ✅ Named volume |
| postgres | `postgres_data:/var/lib/postgresql/data` | ✅ Named volume |

### 2.6 Docker Orchestration Issues Found

| Issue | Severity | Fix Applied |
|-------|----------|-------------|
| Missing memory limits | 🔴 High | Added `deploy.resources.limits.memory` to all services |
| Missing restart policy | 🔴 High | Added `restart: unless-stopped` to all services |
| No log rotation | 🟡 Medium | Recommend adding `logging` driver config in production |

---

## 3. Celery Stability Report

### 3.1 Worker Configuration

| Setting | Value | Assessment |
|---------|-------|------------|
| `worker_prefetch_multiplier` | 1 | ✅ Fair scheduling, prevents starvation |
| `worker_max_tasks_per_child` | 1000 | ✅ Mitigates memory leaks |
| `task_time_limit` | 3600s | ✅ Hard limit 1 hour |
| `task_soft_time_limit` | 3300s | ✅ Soft limit 55 min, catchable |
| `result_expires` | 86400s | ✅ Results cleaned after 24h |
| `task_serializer` | json | ✅ Safe, no pickle |

### 3.2 Crash Recovery (Fixed)

| Setting | Before | After |
|---------|--------|-------|
| `task_acks_late` | ❌ Not set (default = False) | ✅ `True` |
| `task_reject_on_worker_lost` | ❌ Not set (default = False) | ✅ `True` |

**Impact**: Previously, tasks were acknowledged immediately upon receipt. If a worker crashed during execution, the task was lost. Now:
- Tasks are acked **after completion**
- If a worker dies mid-task, the task is **requeued** for another worker

### 3.3 Task Idempotency (Fixed)

| Task | Before | After |
|------|--------|-------|
| `generate_batch_task` | Subtask IDs = random `uuid.uuid4()[:12]` | Subtask IDs = deterministic `SHA256(batch_id:angle)[:12]` |
| `generate_batch_task` | DB job creation always inserted | `_create_job_if_not_exists` skips duplicates |

**Impact**: Retries or duplicate task submissions no longer create orphaned DB records or duplicate work.

### 3.4 Worker Process Init

- `@worker_process_init.connect` initializes DI container (`AppContainer`) per worker process
- All tasks resolve services via `interfaces.service_provider.get_service`
- This prevents `app -> domains -> services -> vcw_celery_tasks -> app` cycle

### 3.5 Task Timeout & Retry

| Task | Max Retries | Retry Delay | Timeout |
|------|-------------|-------------|---------|
| `echo_task` | 3 | 60s | Default |
| `generate_copy_task` | 3 | 60s | Default |
| `generate_batch_task` | 3 | 60s | Default |
| `dead_letter_task` | 0 | N/A | Default |
| `health_check_task` | 0 | N/A | Default |

### 3.6 Queue Backlog Assessment

- **Broker**: Redis (single-node, in-memory)
- **Backend**: PostgreSQL (persistent)
- **Queue binding**: `celery,vcw`
- **No queue length monitoring**: Recommend adding Flower or custom metrics
- **No rate limiting**: Celery rate limits not configured

---

## 4. Distributed System Risks

### 4.1 Identified Risks

| Risk | Severity | Mitigation | Status |
|------|----------|------------|--------|
| Task duplication on retry | 🔴 High | Deterministic subtask IDs + `_create_job_if_not_exists` | ✅ Fixed |
| Worker crash loses tasks | 🔴 High | `task_acks_late=True` + `task_reject_on_worker_lost=True` | ✅ Fixed |
| Memory unbounded growth | 🟡 Medium | Memory limits in docker-compose + `worker_max_tasks_per_child` | ✅ Fixed |
| Container crash no restart | 🟡 Medium | `restart: unless-stopped` on all services | ✅ Fixed |
| No queue backlog monitoring | 🟡 Medium | Recommend Flower / Prometheus metrics | ⚠️ Pending |
| No log rotation | 🟡 Medium | Recommend JSON log driver + external collector | ⚠️ Pending |
| SQLite in dev / PG in prod | 🟡 Medium | `DATABASE_URL` env var switching | ⚠️ Acknowledged |
| Single Redis broker (SPOF) | 🟡 Medium | Recommend Redis Sentinel or RabbitMQ cluster for HA | ⚠️ Future |
| No task rate limiting | 🟢 Low | Not critical for current scale | ⚠️ Acknowledged |

### 4.2 Idempotency Matrix

| Operation | Idempotent? | Notes |
|-----------|-------------|-------|
| `generate_copy_task` (retry) | ⚠️ Partial | Content is regenerated; batch progress updated again. Acceptable for LLM generation. |
| `generate_batch_task` (retry) | ✅ Yes | Deterministic IDs prevent duplicate subtasks |
| `echo_task` | ✅ Yes | Pure function |
| `dead_letter_task` | ✅ Yes | Read-only scan |
| `_update_job_status` | ✅ Yes | SET operations are naturally idempotent |
| `_update_batch_progress` | ⚠️ Partial | Aggregation recalculated from all children; safe but not strictly idempotent |

---

## 5. Performance Bottlenecks

| Bottleneck | Location | Impact |
|------------|----------|--------|
| **Blocking LLM I/O** | `llm/adapter/*.py` | Each request blocks a thread; ~12 angles/sec throughput in eager mode |
| **SQLite file lock** | Dev only | Concurrent writes serialize |
| **Serial scraper** | `vcw_copywriter/batch_generator.py` | 1s sleep between batch items |
| **No connection pooling** | `urllib.request` in scraper | New connection per request |
| **Celery result backend** | PostgreSQL | Every task result writes to DB; high volume may strain DB |

---

## 6. Microservice Readiness Score

| Dimension | Score | Notes |
|-----------|-------|-------|
| Containerization | 8/10 | Dockerfile + compose ready; needs production volume strategy |
| Orchestration | 8/10 | Healthchecks + depends_on + resource limits added |
| Worker Resilience | 8/10 | acks_late + reject_on_worker_lost + retry + dead letter |
| Task Idempotency | 7/10 | Batch tasks fixed; generate_copy still regenerates on retry |
| Observability | 5/10 | Basic tracing exists; needs metrics exporter + queue monitoring |
| Service Discovery | 6/10 | Hardcoded service names (redis, postgres); no service mesh |
| Config Management | 7/10 | Env var based; `.env.example` provided |

**Overall Readiness: 7/10** — Ready for staging deployment; production requires queue monitoring, log aggregation, and HA broker.

---

## 7. Recommendations

1. **Add Flower** (`pip install flower`) for real-time Celery monitoring: `celery -A celery_app flower --port=5555`
2. **Add Prometheus metrics** for queue depth, worker count, task latency
3. **JSON logging** in production for centralized log aggregation
4. **Redis Sentinel** or **RabbitMQ cluster** for broker HA
5. **Separate result backend** from primary DB to avoid contention
6. **gunicorn** instead of Flask dev server: `gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app`
7. **Remove dev volume mounts** in production compose (`volumes: - .:/app`)
