"""Prompt 执行器 —— 统一 LLM 调用入口。

职责：
  1. 接收 PromptExecutionContext，调用底层 LLM SDK。
  2. 支持同步生成与流式生成。
  3. 返回标准化的 PromptResult / PromptChunk。
  4. 不处理 HTTP 转换，不处理业务编排。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Iterator, Optional


@dataclass
class PromptExecutionContext:
    """单次 Prompt 执行的完整上下文。"""

    system_prompt: str = ""
    user_prompt: str = ""
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 2000
    metadata: Dict[str, object] = field(default_factory=dict)


@dataclass
class PromptResult:
    """同步执行结果。"""

    success: bool
    content: str = ""
    meta: str = ""
    latency_ms: float = 0.0
    token_usage: Optional[Dict[str, int]] = None


@dataclass
class PromptChunk:
    """流式生成的单个片段。"""

    text: str = ""
    is_done: bool = False
    is_error: bool = False
    meta: str = ""


class IPromptExecutor(ABC):
    """Prompt 执行器接口。"""

    @abstractmethod
    def execute(self, ctx: PromptExecutionContext) -> PromptResult:
        """同步执行 prompt，返回完整结果。"""

    @abstractmethod
    def execute_stream(self, ctx: PromptExecutionContext) -> Iterator[PromptChunk]:
        """流式执行 prompt，返回片段迭代器。"""


class PromptExecutor(IPromptExecutor):
    """默认 Prompt 执行器实现。

    内部委托给 vcw_copywriter 的 ModelRouter / CopywriterGenerator。
    """

    def __init__(self, llm_config: Dict[str, object]) -> None:
        self._llm_config = llm_config

    def execute(self, ctx: PromptExecutionContext) -> PromptResult:
        # TODO: integrate with ModelRouter / CopywriterGenerator
        raise NotImplementedError("execute() not yet implemented")

    def execute_stream(self, ctx: PromptExecutionContext) -> Iterator[PromptChunk]:
        # TODO: integrate with ModelRouter / CopywriterGenerator
        raise NotImplementedError("execute_stream() not yet implemented")
