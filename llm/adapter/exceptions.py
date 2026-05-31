"""LLM Adapter 统一异常体系。

所有 provider 的原始异常在 adapter 层被翻译为以下统一异常，
供上层 Gateway 做 fallback / retry / metrics 决策。
"""


class LLMAdapterError(Exception):
    """LLM Adapter 根异常。"""

    def __init__(self, message: str, provider: str = "", code: str = "", details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.code = code
        self.details = details or {}


class LLMTimeoutError(LLMAdapterError):
    """请求超时（可重试）。"""

    pass


class LLMRateLimitError(LLMAdapterError):
    """速率限制（可重试）。"""

    pass


class LLMServiceUnavailableError(LLMAdapterError):
    """服务端不可用 / 5xx（可重试）。"""

    pass


class LLMAuthenticationError(LLMAdapterError):
    """认证失败（不可重试）。"""

    pass


class LLMContentFilterError(LLMAdapterError):
    """内容安全拦截（不可重试）。"""

    pass


class LLMBadRequestError(LLMAdapterError):
    """请求参数错误（不可重试）。"""

    pass


class LLMNotImplementedError(LLMAdapterError):
    """当前 provider 不支持该功能（不可重试）。"""

    pass
