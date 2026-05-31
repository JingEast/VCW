"""LLM 调用链路追踪中间件。

在 Gateway 调用前后注入追踪逻辑，支持：
  - OpenTelemetry（含 Jaeger/OTLP 导出）
  - 结构化日志（JSON）
  - 自定义 trace_id 传递
"""

from .base import BaseTracingMiddleware, TraceContext
from .exporter_config import TracingExporterConfig
from .log_tracing import LogTracingMiddleware
from .otel_tracing import GatewayTracer, OtelTracingMiddleware, _get_tracer

__all__ = [
    "BaseTracingMiddleware",
    "TraceContext",
    "LogTracingMiddleware",
    "OtelTracingMiddleware",
    "GatewayTracer",
    "TracingExporterConfig",
    "_get_tracer",
]
