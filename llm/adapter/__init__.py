"""LLM Provider Adapter 层。

将不同厂商的 LLM API 统一为 Gateway 可消费的接口。
已支持：
  - OpenAIAdapter（OpenAI / Kimi / DeepSeek / Azure / vLLM / Ollama）
  - AnthropicAdapter（Claude）
  - GeminiAdapter（Google Gemini）
"""

from .base import BaseLLMAdapter, HealthStatus, LLMResponse, TokenUsage
from .exceptions import (
    LLMAdapterError,
    LLMAuthenticationError,
    LLMBadRequestError,
    LLMContentFilterError,
    LLMNotImplementedError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)
from .factory import create_adapter, list_providers, register_provider
from .openai_adapter import OpenAIAdapter
from .anthropic_adapter import AnthropicAdapter
from .gemini_adapter import GeminiAdapter
from .retry import with_llm_retry, RETRYABLE_EXCEPTIONS

__all__ = [
    # base
    "BaseLLMAdapter",
    "HealthStatus",
    "LLMResponse",
    "TokenUsage",
    # exceptions
    "LLMAdapterError",
    "LLMAuthenticationError",
    "LLMBadRequestError",
    "LLMContentFilterError",
    "LLMNotImplementedError",
    "LLMRateLimitError",
    "LLMServiceUnavailableError",
    "LLMTimeoutError",
    # factory
    "create_adapter",
    "list_providers",
    "register_provider",
    # adapters
    "OpenAIAdapter",
    "AnthropicAdapter",
    "GeminiAdapter",
    # retry
    "with_llm_retry",
    "RETRYABLE_EXCEPTIONS",
]
