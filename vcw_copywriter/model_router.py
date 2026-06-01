"""
多模型智能路由模块（已弃用）。

.. deprecated::
    该模块已弃用，请直接使用 ``llm.gateway.llm_gateway.LLMGateway``。
    当前保留仅用于向后兼容，内部调用已全部委托给 LLMGateway。
"""

import time
import warnings
from typing import List, Dict, Optional, Tuple, Iterator
from dataclasses import dataclass


try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


@dataclass
class EndpointStatus:
    """Endpoint 健康状态"""
    name: str
    api_key: str
    base_url: str
    model: str
    priority: int = 0  # 数字越小优先级越高
    total_calls: int = 0
    success_calls: int = 0
    fail_calls: int = 0
    last_fail_time: Optional[float] = None
    last_error: str = ""
    disabled_until: float = 0  # 临时禁用直到此时间戳

    @property
    def is_available(self) -> bool:
        """检查当前是否可用"""
        if time.time() < self.disabled_until:
            return False
        # 如果连续失败3次以上，冷却30秒
        if self.fail_calls >= 3 and self.last_fail_time:
            if time.time() - self.last_fail_time < 30:
                return False
        return True

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 1.0
        return self.success_calls / self.total_calls

    def record_success(self):
        self.total_calls += 1
        self.success_calls += 1

    def record_fail(self, error: str):
        self.total_calls += 1
        self.fail_calls += 1
        self.last_fail_time = time.time()
        self.last_error = error
        # 连续失败过多，临时禁用
        if self.fail_calls >= 5:
            self.disabled_until = time.time() + 60


class ModelRouter:
    """
    多模型智能路由器（已弃用）。

    .. deprecated::
        请改用 ``llm.gateway.llm_gateway.LLMGateway``。
        当前保留仅用于向后兼容，内部调用已全部委托给 LLMGateway。
    """

    def __init__(self, config: Dict):
        warnings.warn(
            "ModelRouter 已弃用，请使用 llm.gateway.llm_gateway.LLMGateway",
            DeprecationWarning,
            stacklevel=2,
        )
        self.config = config
        self.endpoints: List[EndpointStatus] = []
        self._init_endpoints()
        self._current_idx = 0
        self._gateway = self._build_gateway()

    def _init_endpoints(self):
        """从配置初始化 endpoint 列表"""
        endpoints_cfg = self.config.get("endpoints", [])

        # 兼容旧配置（单 endpoint）
        if not endpoints_cfg and self.config.get("api_key"):
            endpoints_cfg = [{
                "name": "default",
                "api_key": self.config.get("api_key", ""),
                "base_url": self.config.get("base_url", ""),
                "model": self.config.get("model", "gpt-4o"),
                "priority": 0
            }]

        for i, cfg in enumerate(endpoints_cfg):
            ep = EndpointStatus(
                name=cfg.get("name", f"endpoint_{i}"),
                api_key=cfg.get("api_key", ""),
                base_url=cfg.get("base_url", ""),
                model=cfg.get("model", "gpt-4o"),
                priority=cfg.get("priority", i)
            )
            self.endpoints.append(ep)

        # 按优先级排序
        self.endpoints.sort(key=lambda e: e.priority)

    def get_available_endpoints(self) -> List[EndpointStatus]:
        """获取当前可用的 endpoint 列表（按优先级排序）"""
        return [ep for ep in self.endpoints if ep.is_available]

    def _create_client(self, endpoint: EndpointStatus):
        """为指定 endpoint 创建 OpenAI 客户端"""
        if not HAS_OPENAI:
            raise ImportError("未安装 openai 包")
        kwargs = {"api_key": endpoint.api_key}
        if endpoint.base_url:
            kwargs["base_url"] = endpoint.base_url
        return openai.OpenAI(**kwargs)  # type: ignore[arg-type]

    def _build_gateway(self):
        """基于当前配置构建 LLMGateway（内部委托）。"""
        from llm.gateway.llm_gateway import LLMGateway, ProviderRegistry, GatewayConfig
        from llm.adapter import create_adapter

        registry = ProviderRegistry()
        for ep in self.endpoints:
            adapter = create_adapter(
                ep.name,
                api_key=ep.api_key,
                base_url=ep.base_url or None,
                model=ep.model,
            )
            registry.register(ep.name, adapter)

        cfg = GatewayConfig(default_provider=self.endpoints[0].name if self.endpoints else None)
        return LLMGateway(config=cfg, registry=registry)

    def generate(self, system_prompt: str, user_prompt: str,
                 temperature: float = 0.7, max_tokens: int = 2000,
                 retry_count: int = 2, use_stream: bool = False) -> Tuple[bool, str, str]:
        """
        智能路由生成（非流式）— 已委托给 LLMGateway。

        Returns:
            (success, content, meta)
        """
        if use_stream:
            raise ValueError("流式模式请调用 generate_stream()")

        if self._gateway is not None and self._gateway.registry.list():
            try:
                response = self._gateway.complete(
                    prompt=user_prompt,
                    system=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                meta = (
                    f"模型: {response.model} | "
                    f"Provider: {response.provider} | "
                    f"Tokens: {response.usage.total_tokens}"
                )
                return True, response.content, meta
            except Exception as exc:
                return False, "", f"Gateway 调用失败: {exc}"

        # 兜底回退
        return False, "", "未配置可用端点"

    def generate_stream(self, system_prompt: str, user_prompt: str,
                        temperature: float = 0.7, max_tokens: int = 2000) -> Iterator[Tuple[bool, str, str]]:
        """
        流式生成 — 已委托给 LLMGateway。

        Yields:
            (is_meta, content, meta_info)
        """
        if self._gateway is not None and self._gateway.registry.list():
            messages: list[dict[str, str]] = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_prompt})

            meta_sent = False
            try:
                for chunk in self._gateway.generate_stream(
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ):
                    if not meta_sent:
                        yield True, f"model:{chunk.model}|endpoint:{chunk.provider}", ""
                        meta_sent = True
                    if chunk.content:
                        yield False, chunk.content, ""
                yield True, "done", ""
                return
            except Exception:
                pass

        yield False, "", "所有端点流式生成失败"

    def get_status(self) -> List[Dict]:
        """获取所有 endpoint 的状态报告"""
        return [{
            "name": ep.name,
            "model": ep.model,
            "priority": ep.priority,
            "available": ep.is_available,
            "total_calls": ep.total_calls,
            "success_rate": f"{ep.success_rate:.0%}",
            "last_error": ep.last_error[:100] if ep.last_error else "",
        } for ep in self.endpoints]
