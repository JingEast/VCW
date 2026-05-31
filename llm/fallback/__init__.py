"""Fallback 策略。

当主 provider 失败时，按策略切换到备用 provider：
  - ChainFallback: 链式依次尝试
  - PriorityFallback: 按优先级选择健康节点
  - CircuitBreakerFallback: 熔断 + 降级
"""

from .base import BaseFallbackStrategy, FallbackResult

__all__ = [
    "BaseFallbackStrategy",
    "FallbackResult",
]
