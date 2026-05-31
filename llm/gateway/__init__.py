"""LLM Gateway 统一入口。

LLMGateway 是所有 LLM 调用的唯一入口，负责：
  1. Provider 选择（Registry 查询）
  2. Tracing 注入（前置/后置）
  3. Metrics 采集（token/latency/success rate）
  4. Cache 读写（命中则短路返回）
  5. Fallback 编排（主 provider 失败时切换备用）

使用示例：
    from llm.gateway import LLMGateway, ProviderRegistry, GatewayConfig
    from llm.adapter import OpenAIAdapter

    registry = ProviderRegistry()
    registry.register("kimi", OpenAIAdapter(api_key="..."))

    gateway = LLMGateway(config=GatewayConfig(), registry=registry)
    resp = gateway.generate(LLMPrompt(user="你好"), provider="kimi")
"""

from .config import GatewayConfig
from .core import LLMGateway
from .registry import ProviderRegistry

__all__ = [
    "GatewayConfig",
    "LLMGateway",
    "ProviderRegistry",
]
