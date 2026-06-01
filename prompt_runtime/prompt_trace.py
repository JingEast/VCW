"""Prompt 追踪器 —— 记录每次 LLM 调用的完整链路。

职责：
  1. 记录 request / response / latency / model / token 等关键信息。
  2. 支持 trace_id 生成与传播。
  3. 支持 JSON 格式日志输出。
  4. 支持按 trace_id 查询和分页列表。
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .prompt_executor import IPromptExecutor, PromptExecutionContext, PromptResult


@dataclass
class PromptTraceRequest:
    """Prompt 调用请求侧数据。"""

    system_prompt: str = ""
    user_prompt: str = ""
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 2000
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PromptTraceResponse:
    """Prompt 调用响应侧数据。"""

    success: bool = False
    content: str = ""
    meta: str = ""
    token_usage: Optional[Dict[str, int]] = None


@dataclass
class PromptTraceRecord:
    """单次 Prompt 调用的完整追踪记录。"""

    trace_id: str
    timestamp: str  # ISO-8601
    request: PromptTraceRequest
    response: PromptTraceResponse
    latency_ms: float
    model: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典（供 JSON 使用）。"""
        return asdict(self)

    def to_json(self) -> str:
        """序列化为 JSON 字符串。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


class IPromptTracer(ABC):
    """Prompt 追踪器接口。"""

    @abstractmethod
    def generate_trace_id(self) -> str:
        """生成全局唯一的 trace_id。"""

    @abstractmethod
    def trace(self, record: PromptTraceRecord) -> None:
        """记录一次追踪。"""

    @abstractmethod
    def get_trace(self, trace_id: str) -> Optional[PromptTraceRecord]:
        """根据 trace_id 查询单条记录。"""

    @abstractmethod
    def list_traces(self, limit: int = 100, offset: int = 0) -> List[PromptTraceRecord]:
        """分页查询追踪记录。"""

    @abstractmethod
    def export_json_logs(self, filepath: str) -> None:
        """将所有记录导出为 JSON Lines 文件。"""


class PromptTracer(IPromptTracer):
    """默认 Prompt 追踪器实现。

    特性：
      - 内存保存最近 N 条记录（默认 1000）。
      - 同时输出 JSON 格式日志到 logger。
      - 支持导出 JSON Lines 文件。
    """

    def __init__(self, max_records: int = 1000) -> None:
        self._records: List[PromptTraceRecord] = []
        self._max_records = max_records
        self._logger = logging.getLogger("prompt_runtime.trace")

    def generate_trace_id(self) -> str:
        return uuid.uuid4().hex

    def trace(self, record: PromptTraceRecord) -> None:
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records.pop(0)
        self._logger.info(record.to_json())

    def get_trace(self, trace_id: str) -> Optional[PromptTraceRecord]:
        for r in reversed(self._records):
            if r.trace_id == trace_id:
                return r
        return None

    def list_traces(self, limit: int = 100, offset: int = 0) -> List[PromptTraceRecord]:
        return self._records[-(offset + limit):][:limit]

    def export_json_logs(self, filepath: str) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            for r in self._records:
                f.write(r.to_json() + "\n")


class PromptTraceMiddleware:
    """Prompt Trace 中间件。

    包装 IPromptExecutor，在 execute / execute_stream 前后自动记录追踪。
    """

    def __init__(self, executor: IPromptExecutor, tracer: IPromptTracer) -> None:
        self._executor = executor
        self._tracer = tracer

    def execute(self, ctx: PromptExecutionContext) -> PromptResult:
        trace_id = self._tracer.generate_trace_id()
        start = time.perf_counter()
        error: Optional[str] = None
        result: Optional[PromptResult] = None

        try:
            result = self._executor.execute(ctx)
            return result
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            latency_ms = (time.perf_counter() - start) * 1000
            record = PromptTraceRecord(
                trace_id=trace_id,
                timestamp=datetime.now().isoformat(),
                request=PromptTraceRequest(
                    system_prompt=ctx.system_prompt,
                    user_prompt=ctx.user_prompt,
                    model=ctx.model,
                    temperature=ctx.temperature,
                    max_tokens=ctx.max_tokens,
                    extra=ctx.metadata,
                ),
                response=PromptTraceResponse(
                    success=result.success if result else False,
                    content=result.content if result else "",
                    meta=result.meta if result else "",
                    token_usage=result.token_usage if result else None,
                ),
                latency_ms=latency_ms,
                model=ctx.model,
                error=error,
            )
            self._tracer.trace(record)

    def execute_stream(self, ctx: PromptExecutionContext):
        trace_id = self._tracer.generate_trace_id()
        start = time.perf_counter()
        error: Optional[str] = None
        chunks: List[str] = []
        meta_parts: List[str] = []

        try:
            for chunk in self._executor.execute_stream(ctx):
                if chunk.is_error:
                    error = chunk.text
                if not chunk.is_done and not chunk.is_error:
                    chunks.append(chunk.text)
                if chunk.meta:
                    meta_parts.append(chunk.meta)
                yield chunk
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            latency_ms = (time.perf_counter() - start) * 1000
            content = "".join(chunks)
            record = PromptTraceRecord(
                trace_id=trace_id,
                timestamp=datetime.now().isoformat(),
                request=PromptTraceRequest(
                    system_prompt=ctx.system_prompt,
                    user_prompt=ctx.user_prompt,
                    model=ctx.model,
                    temperature=ctx.temperature,
                    max_tokens=ctx.max_tokens,
                    extra=ctx.metadata,
                ),
                response=PromptTraceResponse(
                    success=error is None,
                    content=content,
                    meta="".join(meta_parts),
                    token_usage=None,
                ),
                latency_ms=latency_ms,
                model=ctx.model,
                error=error,
            )
            self._tracer.trace(record)
