"""Prompt 执行器 —— 统一 LLM 调用入口。

职责：
  1. 接收 PromptExecutionContext，调用底层 LLM SDK。
  2. 支持同步生成与流式生成。
  3. 返回标准化的 PromptResult / PromptChunk。
  4. 不处理 HTTP 转换，不处理业务编排。
"""

import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, Optional


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

    内部委托给 ``vcw_copywriter.generator.CopywriterGenerator``
    （``ModelRouter`` 已弃用，不再使用）。
    """

    def __init__(self, llm_config: Dict[str, object]) -> None:
        self._llm_config = llm_config
        self._generator: Optional[Any] = None

    def _get_generator(self, ctx: PromptExecutionContext):
        """获取或创建 CopywriterGenerator 实例，并按 ctx 更新参数。"""
        from vcw_copywriter.generator import CopywriterGenerator

        if self._generator is None:
            config: Dict[str, object] = dict(self._llm_config)
            if ctx.model:
                config["model"] = ctx.model
            config.setdefault("temperature", ctx.temperature)
            config.setdefault("max_tokens", ctx.max_tokens)
            self._generator = CopywriterGenerator(config)
        else:
            if ctx.model:
                self._generator.model = ctx.model
            self._generator.temperature = ctx.temperature
            self._generator.max_tokens = ctx.max_tokens
        return self._generator

    def execute(self, ctx: PromptExecutionContext) -> PromptResult:
        t0 = time.perf_counter()
        try:
            gen = self._get_generator(ctx)
            success, content, meta = gen.generate(ctx.system_prompt, ctx.user_prompt)
        except Exception as exc:
            return PromptResult(
                success=False,
                content="",
                meta=str(exc),
                latency_ms=(time.perf_counter() - t0) * 1000,
            )

        latency_ms = (time.perf_counter() - t0) * 1000

        # 从 meta 字符串解析 token 用量
        token_usage: Optional[Dict[str, int]] = None
        if meta:
            m = re.search(r"消耗tokens:\s*(\d+)", meta)
            if m:
                token_usage = {"total_tokens": int(m.group(1))}

        return PromptResult(
            success=success,
            content=content,
            meta=meta,
            latency_ms=latency_ms,
            token_usage=token_usage,
        )

    def execute_stream(self, ctx: PromptExecutionContext) -> Iterator[PromptChunk]:
        try:
            gen = self._get_generator(ctx)
            for text in gen.generate_stream(ctx.system_prompt, ctx.user_prompt):
                yield PromptChunk(text=text)
            yield PromptChunk(text="", is_done=True)
        except Exception as exc:
            yield PromptChunk(text=f"[错误] {exc}", is_error=True, is_done=True)
