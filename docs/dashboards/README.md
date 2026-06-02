# VCW Grafana Dashboards

## grafana-vcw.json

**用途**: 生产环境核心可观测性看板

**导入方式**:
1. Grafana UI → Dashboards → Import
2. 上传 `grafana-vcw.json` 或粘贴 JSON
3. 选择 Prometheus 数据源（变量 `${datasource}` 会自动匹配）

**面板说明**:

| 面板 | 指标 | 用途 |
|------|------|------|
| HTTP QPS by Status | `vcw_http_requests_total` | 按状态码观察流量与异常比例 |
| HTTP Latency p99 | `vcw_http_request_duration_seconds` | 发现延迟抖动与长尾请求 |
| Error Rate | `vcw_errors_total` | 聚合错误速率，触发告警基线 |
| Errors by Code | `vcw_errors_total` | 定位具体错误类型分布 |
| LLM Calls by Provider | `vcw_llm_calls_total` | 多模型路由负载与成功率 |
| LLM Latency p99 | `vcw_llm_request_duration_seconds` | LLM 供应商性能对比 |
| Celery Tasks by Status | `vcw_celery_tasks_total` | 任务队列吞吐与失败趋势 |
| Celery Success Rate | `vcw_celery_tasks_total` | 批量生成任务可靠性 |

**PromQL 速查**:

```promql
# HTTP QPS
sum by (status) (rate(vcw_http_requests_total[5m]))

# HTTP p99 延迟
vcw_http_request_duration_seconds{quantile="0.99"}

# 错误率
sum(rate(vcw_errors_total[5m]))

# LLM 调用速率
sum by (provider, status) (rate(vcw_llm_calls_total[5m]))

# Celery 成功率
sum(rate(vcw_celery_tasks_total{status="success"}[5m]))
  /
sum(rate(vcw_celery_tasks_total[5m]))
```

**兼容性**:
- Grafana >= 10.0
- Prometheus >= 2.40
- 无需安装额外插件

**数据源要求**:
- Prometheus 已配置抓取 `http://vcw-web:5000/metrics`
- scrape_interval <= 15s（推荐）
