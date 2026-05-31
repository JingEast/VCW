# Prompt Runtime

Prompt Runtime 是 VCW 的 Prompt 执行基础设施层，统一封装 LLM 调用的**执行、追踪、指标、缓存**四大能力。

## 目录结构

```
prompt_runtime/
├── __init__.py
├── prompt_executor.py    # Prompt 执行器（同步 + 流式）
├── prompt_trace.py       # Prompt 追踪器（调用链路记录）
├── prompt_metrics.py     # Prompt 指标收集器（性能统计）
├── prompt_cache.py       # Prompt 缓存（响应复用）
└── README.md
```

## 设计原则

1. **接口优先**：每个模块定义 `I` 前缀的抽象基类，便于测试替换和未来扩展（如 RedisCache、DBTracer）。
2. **零业务逻辑**：当前仅建立类结构，不实现复杂的 LLM 调用逻辑（`PromptExecutor` 标记为 TODO）。
3. **零外部依赖**：除 Python stdlib 外，不依赖 Flask、SQLAlchemy、OpenAI 等第三方库。
4. **可组合**：四个模块相互独立，可通过 DI 容器自由组合。

## 类关系图

```
┌──────────────────┐
│ PromptExecutionContext │
└────────┬─────────┘
         │
┌────────▼─────────┐     ┌──────────────────┐
│ IPromptExecutor  │────→│ PromptResult     │
│   execute()      │     │ (sync)           │
│   execute_stream()│    └──────────────────┘
└────────┬─────────┘     ┌──────────────────┐
         │               │ PromptChunk      │
┌────────▼─────────┐     │ (stream)         │
│ PromptExecutor   │     └──────────────────┘
└──────────────────┘

┌──────────────────┐
│ IPromptTracer    │
│   trace()        │
│   get_trace()    │
│   list_traces()  │
└────────┬─────────┘
┌────────▼─────────┐
│ PromptTracer     │
└──────────────────┘

┌──────────────────┐
│ IPromptMetrics   │
│   record()       │
│   get_metrics()  │
│   reset()        │
└────────┬─────────┘
┌────────▼─────────┐
│ PromptMetrics    │
│   Collector      │
└──────────────────┘

┌──────────────────┐
│ IPromptCache     │
│   get()          │
│   set()          │
│   invalidate()   │
│   clear()        │
└────────┬─────────┘
┌────────▼─────────┐
│ PromptCache      │
└──────────────────┘
```

## 使用示例（未来集成）

```python
from prompt_runtime import (
    PromptExecutor, PromptExecutionContext,
    PromptTracer, PromptMetricsCollector, PromptCache,
)

# 初始化（由 DI 容器注入）
executor = PromptExecutor(llm_config={...})
tracer = PromptTracer()
metrics = PromptMetricsCollector()
cache = PromptCache()

# 执行
ctx = PromptExecutionContext(
    system_prompt="你是一位资深文案编辑",
    user_prompt="写一篇关于DSE的文章",
    model="gpt-4o",
)
result = executor.execute(ctx)

# 记录
tracer.trace(PromptTraceRecord(...))
metrics.record(PromptCallInfo(latency_ms=result.latency_ms, ...))
```

## 演进路线

| 阶段 | 内容 |
|------|------|
| **当前** | 类结构 + 接口定义（内存实现） |
| **Phase 2** | `PromptExecutor` 接入 `ModelRouter` / `CopywriterGenerator` |
| **Phase 3** | `PromptCache` 替换为 Redis 实现 |
| **Phase 4** | `PromptTracer` 替换为持久化 DB 实现 |
| **Phase 5** | `PromptMetrics` 接入 Prometheus / Grafana |
