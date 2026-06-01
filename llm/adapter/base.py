"""Provider Adapter 抽象基类与数据模型。

所有具体 Adapter（OpenAI、Anthropic、Gemini…）必须继承
BaseLLMAdapter 并实现其抽象方法。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class HealthStatus(str, Enum):
    """适配器健康状态。"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TokenUsage:
    """Token 消耗统计。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class LLMResponse:
    """标准化 LLM 响应。"""

    content: str
    provider: str
    model: str
    usage: TokenUsage
    latency_ms: float
    meta: Dict[str, Any] = field(default_factory=dict)
    raw_response: Optional[Any] = None


class BaseLLMAdapter(ABC):
    """LLM Provider Adapter 抽象基类。

    子类只需关注如何将标准化参数翻译为厂商原生 API，
    以及如何将原生响应翻译为标准化 LLMResponse。
    Gateway 层负责 tracing、metrics、cache、fallback 的编排。

    Args:
        provider_name: provider 唯一标识。
        api_key: API 密钥。
        base_url: 自定义 base URL（可选）。
        model: 默认模型名称。
        timeout: HTTP 请求超时（秒）。
        max_retries: 最大重试次数。
        retry_backoff: 指数退避初始值（秒）。
    """

    def __init__(
        self,
        provider_name: str,
        *,
        api_key: str,
        base_url: Optional[str] = None,
        model: str = "",
        timeout: float = 60.0,
        max_retries: int = 3,
        retry_backoff: float = 1.0,
        **kwargs: Any,
    ) -> None:
        self.provider_name = provider_name
        self.api_key = api_key
        self.base_url = (base_url or "").rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.config = kwargs

    # ------------------------------------------------------------------
    # 抽象方法 —— 子类必须实现
    # ------------------------------------------------------------------

    @abstractmethod
    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> LLMResponse:
        """多轮对话生成。

        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}, ...]
            **kwargs: 透传参数（如 temperature、max_tokens、model_override）。

        Returns:
            标准化响应 LLMResponse。
        """
        ...

    @abstractmethod
    def embed(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        """文本嵌入（向量化）。

        Args:
            texts: 待嵌入文本列表。
            **kwargs: 透传参数（如 model_override、dimensions）。

        Returns:
            嵌入向量列表，每项为 float 列表。

        Raises:
            LLMNotImplementedError: 当前 provider 不支持 embedding。
        """
        ...

    @abstractmethod
    def health_check(self) -> HealthStatus:
        """健康检查。

        建议实现：发送极轻量请求（如 model list 或 1-token completion）
        根据响应时间与状态码判断状态。
        """
        ...

    # ------------------------------------------------------------------
    # 有默认实现 —— 子类可覆盖
    # ------------------------------------------------------------------

    def complete(self, prompt: str, system: Optional[str] = None, **kwargs: Any) -> LLMResponse:
        """单轮补全（complete 的默认实现：包装为单轮 chat）。

        子类若提供更高效的 native complete endpoint，可覆盖此方法。
        """
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, **kwargs)

    def generate_stream(self, messages: list[dict[str, str]], **kwargs: Any):
        """流式生成（占位，未来扩展）。"""
        raise NotImplementedError(f"{self.provider_name} 未实现 generate_stream")

    def list_models(self) -> List[str]:
        """返回当前账号可访问的模型列表。"""
        return []

    def close(self) -> None:
        """关闭底层连接资源（如 httpx.Client）。

        子类若持有可关闭资源，应覆盖此方法。
        """
        pass

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} "
            f"provider={self.provider_name} "
            f"model={self.model}>"
        )
