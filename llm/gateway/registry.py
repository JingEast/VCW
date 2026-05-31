"""Provider Registry —— Adapter 注册与发现。"""

from __future__ import annotations

from typing import Dict, List, Optional

from llm.adapter.base import BaseLLMAdapter, HealthStatus


class ProviderRegistry:
    """Provider Adapter 注册表。

    线程安全假设：注册操作通常在应用启动时单线程完成，
    运行时查询（get/list）无锁即可。
    """

    def __init__(self) -> None:
        self._adapters: Dict[str, BaseLLMAdapter] = {}

    def register(self, name: str, adapter: BaseLLMAdapter) -> "ProviderRegistry":
        """注册一个 provider adapter，支持链式调用。

        Args:
            name: provider 唯一标识，如 "kimi", "deepseek", "azure-gpt4"。
            adapter: 继承 BaseLLMAdapter 的具体实现。

        Raises:
            ValueError: 同名 provider 已存在。
        """
        if name in self._adapters:
            raise ValueError(f"Provider '{name}' 已注册")
        self._adapters[name] = adapter
        return self

    def unregister(self, name: str) -> Optional[BaseLLMAdapter]:
        """注销 provider，返回被移除的 adapter（如存在）。"""
        return self._adapters.pop(name, None)

    def get(self, name: str) -> BaseLLMAdapter:
        """按名称获取 adapter。

        Raises:
            KeyError: provider 未注册。
        """
        try:
            return self._adapters[name]
        except KeyError as exc:
            raise KeyError(
                f"Provider '{name}' 未注册。已注册: {list(self._adapters.keys())}"
            ) from exc

    def list(self) -> List[str]:
        """返回所有已注册 provider 名称列表。"""
        return list(self._adapters.keys())

    def health_check_all(self) -> Dict[str, HealthStatus]:
        """对所有已注册 provider 执行健康检查。

        Returns:
            {provider_name: HealthStatus}
        """
        return {
            name: adapter.health_check()
            for name, adapter in self._adapters.items()
        }

    def __contains__(self, name: str) -> bool:
        return name in self._adapters

    def __repr__(self) -> str:
        return f"<ProviderRegistry providers={self.list()}>"
