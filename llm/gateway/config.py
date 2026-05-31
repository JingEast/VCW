"""Gateway 全局配置。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class GatewayConfig:
    """LLM Gateway 运行时配置。

    所有字段均有默认值，支持渐进式启用中间件。
    """

    # ---- Provider 选择 ----
    default_provider: Optional[str] = None
    """未指定 provider 时的默认选择。"""

    # ---- Timeout ----
    request_timeout: float = 60.0
    """单次 LLM 请求超时（秒）。"""

    max_total_timeout: float = 300.0
    """含重试/fallback 的总超时上限（秒）。"""

    # ---- Retry ----
    max_retries: int = 3
    """单 provider 最大重试次数。"""

    retry_backoff_base: float = 1.0
    """指数退避基数（秒）。"""

    retry_max_delay: float = 60.0
    """退避上限（秒）。"""

    # ---- Fallback ----
    fallback_enabled: bool = False
    """是否启用自动 fallback。"""

    fallback_providers: List[str] = field(default_factory=list)
    """fallback provider 优先级列表。"""

    # ---- Cache ----
    cache_enabled: bool = False
    """是否启用响应缓存。"""

    cache_ttl_seconds: int = 3600
    """缓存有效期（秒）。"""

    # ---- Tracing ----
    tracing_enabled: bool = False
    """是否启用调用链路追踪。"""

    # ---- Metrics ----
    metrics_enabled: bool = False
    """是否启用指标采集。"""

    # ---- 透传字段 ----
    extra: Dict[str, Any] = field(default_factory=dict)
    """用户自定义扩展配置。"""
