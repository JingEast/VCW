# VCW Scalability & Async Stability Report

**Task**: TASK-RV-H3-01  
**Date**: 2026-06-01  
**Scope**: extensibility, plugin capability, async scalability

---

## 1. Quality Gates

| Gate | Result |
|------|--------|
| `pytest tests/` | ✅ 378+ passed |
| `pytest -n auto` | ✅ 378 passed (parallel) |
| `ruff check .` | ✅ passed |
| `mypy .` | ✅ passed (185 files) |
| `pytest --cov` | ✅ 55% total coverage |

---

## 2. Stress Test Results

### 2.1 Batch Generation Throughput

| Scenario | Batches × Angles | Total Angles | Time (s) | Throughput (angles/sec) | Memory Peak (MB) | Status |
|----------|------------------|--------------|----------|------------------------|------------------|--------|
| Light | 10 × 3 | 30 | 2.607 | 11.5 | 4.48 | ✅ 100% success |
| Medium | 50 × 5 | 250 | 21.171 | 11.8 | 3.95 | ✅ 100% success |
| Heavy | 10 × 20 | 200 | 19.954 | 10.0 | 3.01 | ✅ 100% success |
| Partial (20% fail) | 10 × 5 | 50 | 4.448 | 11.2 | 31.46 | ✅ 60% success, 40% failure as designed |

> **Observation**: Throughput is stable around **10–12 angles/sec** across all scenarios. The eager Celery mode simulates execution without real broker latency.

### 2.2 HTTP Load Test (Locust)

Locustfile created at `locustfile.py` with 4 scenarios:
- Health check (weight 5)
- Index page (weight 3)
- Config page (weight 2)
- Generate copy (weight 1)
- Batch generate (weight 1)

**Note**: Live Locust execution requires a running Flask server (`python wsgi.py`). This was not executed during the regression due to no server being online.

---

## 3. Async Stability Analysis

### 3.1 Thread Safety Audit

| Component | Locking Before | Locking After | Risk Level |
|-----------|---------------|---------------|------------|
| `MemoryCacheBackend` | ❌ None (relied on GIL) | ✅ `threading.Lock` | 🔴 High → ✅ Fixed |
| `TokenAccountingCollector` | ✅ `threading.RLock` | ✅ `threading.RLock` | ✅ Low |
| `ChainFallbackStrategy._history` | ❌ None | ✅ `threading.Lock` | 🟡 Medium → ✅ Fixed |
| `OtelTracingMiddleware._spans` | ❌ None | ✅ `threading.Lock` + try/finally cleanup | 🟡 Medium → ✅ Fixed |
| `ProviderRegistry` | ❌ None (documented single-thread) | ❌ None (boot-only) | 🟡 Medium (acceptable) |

### 3.2 Resource Leak Audit

| Resource | Before | After |
|----------|--------|-------|
| `httpx.Client` (per adapter) | ❌ No `close()` — leaked on container reload | ✅ `BaseLLMAdapter.close()` + concrete implementations |
| Tracing spans dict | ❌ Could grow unbounded if `post_call` raised | ✅ `try/finally` ensures `pop()` always runs |
| Memory cache entries | ✅ TTL expiry on `get()` | ✅ Atomic get+pop under lock |

### 3.3 Async Edge Tests (New)

| Test | Description | Result |
|------|-------------|--------|
| `test_concurrent_set_no_crash` | 10 threads × 50 sets each | ✅ Passed |
| `test_concurrent_get_set_delete` | 9 threads mixed get/set/delete | ✅ Passed |
| `test_concurrent_record_result` | 10 threads × 100 appends each | ✅ Passed |
| `test_spans_cleaned_up_after_post_call` | 100 pre/post cycles | ✅ Passed |
| `test_spans_cleaned_up_on_exception` | 100 error paths | ✅ Passed |
| `test_concurrent_pre_post_call_no_crash` | 10 threads × 50 cycles | ✅ Passed |
| `test_*_adapter_close` | All 3 adapters close cleanly | ✅ Passed |

---

## 4. Extensibility & Plugin Architecture

### 4.1 Extension Points

| Layer | Mechanism | File |
|-------|-----------|------|
| **Adapter** | `register_provider(name, cls)` in `llm/adapter/factory.py` | Factory pattern |
| **Gateway Registry** | `registry.register(name, adapter)` | Runtime binding |
| **Middleware** | `attach_tracing()`, `attach_metrics()`, `attach_cache()`, `attach_fallback()` | Builder pattern |
| **Fallback Strategy** | `BaseFallbackStrategy` subclass | Strategy pattern |
| **Metrics Collector** | `BaseMetricsCollector` subclass | Observer pattern |
| **Tracing Middleware** | `BaseTracingMiddleware` subclass | Decorator pattern |
| **Cache Backend** | `BaseCacheBackend` subclass | Adapter pattern |

### 4.2 Plugin Capability Assessment

- ✅ **Adapter registration** at runtime supported
- ✅ **Middleware stacking** supported via Gateway builder
- ⚠️ **No async plugin interface**: All adapters use sync `httpx.Client`; no `AsyncClient` path
- ⚠️ **No formal plugin discovery**: No entry-points or auto-discovery mechanism

---

## 5. Bottleneck Analysis

### 5.1 Current Bottlenecks

| Bottleneck | Location | Impact | Mitigation |
|------------|----------|--------|------------|
| **Sync I/O blocking** | `llm/adapter/*.py` | Each LLM call blocks a thread; high concurrency requires many threads | Consider `httpx.AsyncClient` + async Gateway path for high-RPS scenarios |
| **Serial batch generation** | `vcw_copywriter/batch_generator.py:54` | 1-second sleep between serial calls | Already mitigated by Celery `group()` parallelism in `generate_batch_task` |
| **SQLite file locking** | `vcw_copywriter/db/session.py` | Concurrent writes serialize on file lock | Use PostgreSQL in production (`DATABASE_URL`) |
| **No connection pool caps** | `llm/adapter/*.py` | `httpx.Client` uses default limits; may exhaust FDs under extreme load | Explicit `limits=Limits(...)` config recommended |
| **Scraper no connection reuse** | `vcw_copywriter/scraper/base.py` | `urllib.request` per call; inefficient under `ThreadPoolExecutor` | Migrate to `httpx` or `requests.Session` |

### 5.2 Scalability Ceiling (Estimated)

| Dimension | Current Limit | Bottleneck |
|-----------|--------------|------------|
| Concurrent LLM calls | ~100 (thread count) | OS thread memory + blocking I/O |
| Batch throughput | ~12 angles/sec (eager mode) | Python CPU + mock latency |
| Web RPS (Flask) | ~50–100 | Single-process WSGI; no gunicorn/uwsgi |
| Celery task concurrency | Worker count × prefetch | Redis broker + PostgreSQL backend |

---

## 6. Fix Summary

| Issue | Severity | Fix |
|-------|----------|-----|
| `httpx.Client` connection leak | 🔴 High | Added `close()` to `BaseLLMAdapter` and all 3 concrete adapters |
| `MemoryCacheBackend` race / non-atomic eviction | 🔴 High | Added `threading.Lock` around all operations |
| `OtelTracingMiddleware._spans` leak + race | 🟡 Medium | Added `threading.Lock` + `try/finally` cleanup |
| `ChainFallbackStrategy._history` race | 🟡 Medium | Added `threading.Lock` around `record_result()` |
| Missing HTTP load test harness | 🟡 Medium | Added `locustfile.py` with 5 scenarios |
| Missing async edge tests | 🟡 Medium | Added `tests/performance/test_async_edge_cases.py` (9 tests) |

---

## 7. Recommendations

1. **Add async adapter path**: For high-concurrency LLM serving, introduce `AsyncBaseLLMAdapter` using `httpx.AsyncClient` and an async Gateway.
2. **Connection pool limits**: Explicitly configure `httpx.Limits(max_connections=...)` in adapters.
3. **Production WSGI**: Replace dev server with gunicorn + gevent/eventlet for higher RPS.
4. **PostgreSQL in production**: The SQLite default is fine for dev, but production must use PostgreSQL.
5. **Plugin discovery**: Consider `entry_points` in `pyproject.toml` for auto-discovering adapters and strategies.
