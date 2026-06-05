# 可观测性体系设计

## 三大支柱

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   Metrics   │  │    Logs     │  │   Traces    │
├─────────────┤  ├─────────────┤  ├─────────────┤
│ Prometheus  │  │  JSON Logs  │  │  TraceId    │
│ Grafana     │  │  Structured │  │  X-Trace-Id │
│ Alerts      │  │  Correlated │  │  Jaeger     │
└─────────────┘  └─────────────┘  └─────────────┘
```

## 指标体系

| 指标类型 | 示例 | 采集方式 |
|----------|------|----------|
| 业务指标 | 生成成功数、失败数 | 代码埋点 |
| 性能指标 | 请求延迟、DB 查询时间 | 中间件 |
| 资源指标 | CPU、内存、连接池 | Prometheus |
| 错误指标 | 5xx 数、异常类型 | 错误处理器 |

## 关键监控面板 (Grafana)

1. **系统概览**: RPS、Latency、Error Rate、饱和度
2. **业务监控**: 生成量、模型调用次数、成本
3. **数据库**: 连接池、慢查询、锁等待
4. **缓存**: 命中率、Eviction 率
5. **队列**: Celery 任务堆积、Worker 状态

## 告警规则

| 条件 | 级别 | 通知方式 |
|------|------|----------|
| Error Rate > 1% | P1 | 邮件 + Slack |
| P99 Latency > 2s | P2 | Slack |
| DB Pool > 80% | P1 | 邮件 + Slack |
| Celery Queue > 100 | P2 | Slack |
| Disk > 85% | P1 | 邮件 |

## 日志关联

所有日志必须包含:
- `trace_id` — 跨服务追踪
- `request_id` — 单次请求标识
- `user_id` — 操作人
- `timestamp` — ISO 8601
