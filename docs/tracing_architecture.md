# OpenTelemetry Tracing 架构

## 设计目标

1. **零侵入**：未安装 `opentelemetry` 时，系统正常运行，tracing 自动降级为 no-op。
2. **全链路覆盖**：从 HTTP 请求 → Gateway → Cache → Model Call → Retry → Fallback → Metrics，每个阶段均有 span。
3. **多后端支持**：Console（调试）、OTLP（Jaeger/Tempo/Collector）、Jaeger Thrift（legacy）。
4. **环境驱动**：通过环境变量即可切换 exporter，无需改代码。

---

## 架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                         HTTP Request (Flask)                        │
│                    trace_id 通过 Header 注入                          │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        LLMGateway.chat()                            │
│  Span: llm.request                                                  │
│  Attributes: llm.provider, llm.model, llm.user, llm.messages.count  │
│  Events:  cache.hit / cache.miss                                    │
└─────────────────────────────────────────────────────────────────────┘
                                  │
            ┌─────────────────────┼─────────────────────┐
            ▼                     ▼                     ▼
   ┌──────────────┐     ┌─────────────────┐    ┌──────────────┐
   │  Cache Get   │     │  Tracing pre    │    │  Fallback    │
   │  (optional)  │     │  (span start)   │    │  (optional)  │
   └──────────────┘     └─────────────────┘    └──────────────┘
            │                     │
            ▼                     ▼
   ┌─────────────────────────────────────────────────────────────┐
   │              Adapter.chat() with retry                      │
   │  Child Span: llm.model.call                                 │
   │  Attributes: llm.provider, llm.model                        │
   │  Events:     llm.retry (attempt, exception, wait_seconds)   │
   └─────────────────────────────────────────────────────────────┘
            │
            ▼
   ┌─────────────────────────────────────────────────────────────┐
   │              Fallback decide (if model fails)               │
   │  Child Span: llm.fallback                                   │
   │  Attributes: fallback.from_provider, fallback.to_provider   │
   │              fallback.reason                                │
   └─────────────────────────────────────────────────────────────┘
            │
            ▼
   ┌─────────────────────────────────────────────────────────────┐
   │              Tracing post + Metrics record                  │
   │  Span Status: OK / ERROR                                    │
   │  Attributes: llm.response.tokens.*, llm.latency_ms          │
   └─────────────────────────────────────────────────────────────┘
```

---

## Span 定义

### 1. `llm.request` —— Gateway 级 Span

由 `OtelTracingMiddleware` 在 `pre_call` / `post_call` 中创建与结束。

**Attributes:**
| Key | Type | 说明 |
|-----|------|------|
| `llm.provider` | string | provider 名称 |
| `llm.model` | string | 模型名称 |
| `llm.user` | string | 用户标识 |
| `llm.messages.count` | int | 消息数量 |
| `llm.temperature` | float | 温度参数（若有）|
| `llm.max_tokens` | int | max_tokens（若有）|
| `llm.latency_ms` | float | 端到端延迟 |
| `llm.response.tokens.prompt` | int | prompt tokens |
| `llm.response.tokens.completion` | int | completion tokens |
| `llm.response.tokens.total` | int | total tokens |

**Status:**
- `OK`：调用成功
- `ERROR`：调用失败（含 exception message）

### 2. `llm.model.call` —— 模型调用子 Span

由 `GatewayTracer.model_call_span()` 在 `gateway/core.py` 中创建。

**Attributes:**
| Key | Type | 说明 |
|-----|------|------|
| `llm.provider` | string | provider 名称 |
| `llm.model` | string | 模型名称 |

### 3. `llm.retry` —— 重试 Event

由 `retry.py` 中的 `_before_sleep_with_trace` 回调记录为 **Span Event**。

**Event Attributes:**
| Key | Type | 说明 |
|-----|------|------|
| `retry.attempt` | int | 当前重试次数 |
| `retry.max_attempts` | int | 最大重试次数 |
| `retry.exception` | string | 异常类型名 |
| `retry.wait_seconds` | float | 等待秒数 |

### 4. `llm.fallback` —— 降级 Event

由 `ChainFallbackStrategy._trace_fallback()` 记录为 **Span Event**。

**Event Attributes:**
| Key | Type | 说明 |
|-----|------|------|
| `fallback.from_provider` | string | 失败的 provider |
| `fallback.to_provider` | string | 降级到的 provider |
| `fallback.reason` | string | 降级原因 |
| `fallback.result` | string | success / exhausted |

---

## Exporter 配置

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OTEL_SERVICE_NAME` | `vcw-llm-gateway` | Jaeger 服务名 |
| `OTEL_TRACING_EXPORTER` | `console` | `console` / `otlp_http` / `otlp_grpc` / `jaeger_thrift` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `None` | OTLP endpoint，如 `http://localhost:4318` |
| `OTEL_EXPORTER_OTLP_INSECURE` | `true` | 禁用 TLS |
| `OTEL_EXPORTER_OTLP_TIMEOUT` | `10` | 导出超时（秒）|

### 快速启动（Console）

```python
from llm.tracing import OtelTracingMiddleware, TracingExporterConfig

config = TracingExporterConfig(exporter_type="console")
config.setup_tracer_provider()

gateway.attach_tracing(OtelTracingMiddleware())
```

### 快速启动（Jaeger + OTLP）

```bash
# 启动 Jaeger
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 4318:4318 \
  jaegertracing/all-in-one:latest

# 设置环境变量
export OTEL_TRACING_EXPORTER=otlp_http
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

```python
config = TracingExporterConfig.from_env()
config.setup_tracer_provider()
gateway.attach_tracing(OtelTracingMiddleware())
```

---

## 模块职责

| 模块 | 职责 |
|------|------|
| `llm/tracing/exporter_config.py` | TracingExporterConfig：解析环境变量、初始化 TracerProvider |
| `llm/tracing/otel_tracing.py` | OtelTracingMiddleware：Gateway 级 span；GatewayTracer：子 span 助手 |
| `llm/tracing/decorators.py` | `@trace_retry`、`@trace_fallback`：装饰器模式（独立使用）|
| `llm/tracing/log_tracing.py` | LogTracingMiddleware：基于 Python logging 的降级方案 |
| `llm/adapter/retry.py` | `_before_sleep_with_trace`：tenacity 回调注入 retry event |
| `llm/fallback/chain_strategy.py` | `_trace_fallback`：fallback 决策 event |
| `llm/gateway/core.py` | `GatewayTracer.model_call_span()`：包装 adapter.chat |

---

## 向后兼容

- 未安装 `opentelemetry-api/sdk/exporter` 时，所有 span 操作自动降级为 `_NoopSpan`，**零性能开销**。
- 已有的 `LogTracingMiddleware` 继续可用，与 `OtelTracingMiddleware` 可并存或独立使用。
- Gateway 的 `attach_tracing()` builder 模式不变。
