"""LLM Gateway — 统一大模型调用基础设施。

设计目标：
  1. 所有 LLM 调用统一入口（gateway/core.py::LLMGateway）
  2. Provider Adapter 模式，支持 OpenAI/Azure/Anthropic/Gemini 等
  3. 可插拔的 tracing、metrics、cache、fallback 中间件
  4. 向后兼容：现有 CopywriterGenerator / ModelRouter 不迁移

快速开始：
    from llm.gateway import LLMGateway, ProviderRegistry, GatewayConfig
    from llm.adapter import OpenAIAdapter

    registry = ProviderRegistry()
    registry.register("kimi", OpenAIAdapter(api_key="...", base_url="..."))

    gateway = LLMGateway(config=GatewayConfig(), registry=registry)
    response = gateway.chat(
        [{"role": "user", "content": "你好"}],
        provider="kimi"
    )
"""
