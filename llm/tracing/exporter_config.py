"""OpenTelemetry Tracing Exporter 配置。

支持导出方式：
  - console: 输出到 stdout（调试）
  - otlp_http: OTLP HTTP 协议（Jaeger / Tempo / Collector）
  - otlp_grpc: OTLP gRPC 协议
  - jaeger_thrift: Jaeger Thrift（legacy）

环境变量：
  - OTEL_SERVICE_NAME: 服务名
  - OTEL_EXPORTER_OTLP_ENDPOINT: OTLP endpoint
  - OTEL_EXPORTER_OTLP_INSECURE: 是否禁用 TLS
  - OTEL_TRACING_EXPORTER: 导出器类型
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class TracingExporterConfig:
    """Tracing 导出器配置。"""

    service_name: str = "vcw-llm-gateway"
    """服务名称，出现在 Jaeger 服务列表中。"""

    exporter_type: str = "console"
    """导出器类型：console / otlp_http / otlp_grpc / jaeger_thrift"""

    endpoint: Optional[str] = None
    """导出端点 URL。None 时使用各导出器默认值。"""

    insecure: bool = True
    """OTLP 是否禁用 TLS（开发环境常用）。"""

    timeout: int = 10
    """导出超时（秒）。"""

    @classmethod
    def from_env(cls) -> TracingExporterConfig:
        """从环境变量读取配置。"""
        return cls(
            service_name=os.getenv("OTEL_SERVICE_NAME", "vcw-llm-gateway"),
            exporter_type=os.getenv("OTEL_TRACING_EXPORTER", "console"),
            endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or None,
            insecure=os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "true").lower() in ("1", "true", "yes"),
            timeout=int(os.getenv("OTEL_EXPORTER_OTLP_TIMEOUT", "10")),
        )

    def setup_tracer_provider(self) -> Any:
        """初始化并返回 TracerProvider。

        若 opentelemetry-sdk 未安装，返回 None。
        """
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        except ImportError:  # pragma: no cover
            return None

        resource = Resource.create({SERVICE_NAME: self.service_name})
        provider = TracerProvider(resource=resource)

        exporter = self._create_exporter()
        if exporter is not None:
            provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)
        return provider

    def _create_exporter(self) -> Optional[Any]:
        """根据 exporter_type 创建对应 Exporter。"""
        try:
            if self.exporter_type == "console":
                from opentelemetry.sdk.trace.export import ConsoleSpanExporter
                return ConsoleSpanExporter()

            if self.exporter_type in ("otlp_http", "otlp_grpc"):
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
                kwargs: dict[str, Any] = {"timeout": self.timeout}
                if self.endpoint:
                    kwargs["endpoint"] = self.endpoint
                return OTLPSpanExporter(**kwargs)

            if self.exporter_type == "jaeger_thrift":
                try:
                    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
                    je_kwargs: dict[str, Any] = {}
                    if self.endpoint:
                        je_kwargs["agent_host_name"] = self.endpoint
                    return JaegerExporter(**je_kwargs)
                except ImportError:
                    # fallback to OTLP if jaeger exporter not available
                    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
                    return OTLPSpanExporter()

        except ImportError:  # pragma: no cover
            pass

        return None
