"""
Prompt Registry —— Prompt 版本化管理中心
------------------------------------------
- 内存式注册表，支持多版本存储
- 按 ID + 版本精确检索，或按 ID 取最新版本
- 按类型筛选、按场景标签筛选
- 线程安全（GIL 保障，无显式锁）
"""
from typing import Any, Dict, List, Optional, Callable
from .schemas import PromptSpec, PromptVersion


class PromptRegistry:
    """
    Prompt 注册表

    存储结构：{prompt_id: [PromptSpec(v1), PromptSpec(v2), ...]}
    每个 ID 下的版本按从小到大排序。
    """

    def __init__(self):
        self._store: Dict[str, List[PromptSpec]] = {}
        self._index_by_type: Dict[str, List[str]] = {
            "system": [], "user": [], "scene": [],
            "style": [], "sample": [], "section": [], "composite": [],
        }

    # ------------------------------------------------------------------
    # 注册
    # ------------------------------------------------------------------
    def register(self, spec: PromptSpec) -> None:
        """注册一个 PromptSpec；同一 ID + 同一版本覆盖"""
        pid = spec.id
        if pid not in self._store:
            self._store[pid] = []
            self._index_by_type[spec.type].append(pid)

        versions = self._store[pid]
        # 查找同版本并覆盖
        for i, existing in enumerate(versions):
            if existing.version == spec.version:
                versions[i] = spec
                return
        # 新版本：插入并排序
        versions.append(spec)
        versions.sort(key=lambda s: s.version)

    def register_many(self, specs: List[PromptSpec]) -> None:
        """批量注册"""
        for spec in specs:
            self.register(spec)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    def get(
        self,
        prompt_id: str,
        version: Optional[str] = None,
        predicate: Optional[Callable[[PromptSpec], bool]] = None,
    ) -> Optional[PromptSpec]:
        """
        获取 PromptSpec

        Args:
            prompt_id: Prompt 唯一 ID
            version: 指定版本号（如 "1.2.0"），None 则取最新版本
            predicate: 额外过滤条件
        """
        versions = self._store.get(prompt_id)
        if not versions:
            return None

        candidates = versions[:]
        if version:
            target = PromptVersion.parse(version)
            candidates = [c for c in candidates if c.version == target]
        if predicate:
            candidates = [c for c in candidates if predicate(c)]

        if not candidates:
            return None
        # 取版本最高者
        return max(candidates, key=lambda c: c.version)

    def get_or_raise(self, prompt_id: str, version: Optional[str] = None) -> PromptSpec:
        """同 get，但找不到时抛出 KeyError"""
        spec = self.get(prompt_id, version=version)
        if spec is None:
            raise KeyError(f"Prompt not found: id={prompt_id}, version={version}")
        return spec

    def list_versions(self, prompt_id: str) -> List[PromptVersion]:
        """列出某 ID 的所有版本号（从小到大）"""
        return [s.version for s in self._store.get(prompt_id, [])]

    def list_ids(self, prompt_type: Optional[str] = None) -> List[str]:
        """列出所有注册的 Prompt ID，可按类型过滤"""
        if prompt_type:
            return self._index_by_type.get(prompt_type, [])[:]
        return list(self._store.keys())

    def list_by_type(self, prompt_type: str) -> List[PromptSpec]:
        """按类型列出所有 Prompt（每个 ID 取最新版本）"""
        result = []
        for pid in self._index_by_type.get(prompt_type, []):
            latest = self.get(pid)
            if latest:
                result.append(latest)
        return result

    def list_by_scene(self, scene: str) -> List[PromptSpec]:
        """按兼容场景标签列出所有 Prompt（每个 ID 取最新版本）"""
        result = []
        for pid, versions in self._store.items():
            latest = versions[-1] if versions else None
            if latest and scene in latest.metadata.compatible_scenes:
                result.append(latest)
        return result

    def resolve_dependencies(
        self,
        prompt_id: str,
        version: Optional[str] = None,
        _visited: Optional[set] = None,
    ) -> List[PromptSpec]:
        """
        解析 Prompt 的依赖树，返回拓扑排序后的列表（含自身）

        用于 composite Prompt：自动拉取其依赖的所有子 Prompt。
        """
        if _visited is None:
            _visited = set()

        spec = self.get_or_raise(prompt_id, version=version)
        if spec.full_id in _visited:
            return []
        _visited.add(spec.full_id)

        result = []
        for dep_id in spec.dependencies:
            # 依赖可带版本限定，如 "style:tone@1.0.0"
            dep_version = None
            if "@" in dep_id:
                dep_id, dep_version = dep_id.rsplit("@", 1)
            result.extend(self.resolve_dependencies(dep_id, dep_version, _visited))

        result.append(spec)
        return result

    # ------------------------------------------------------------------
    # 统计 / 元信息
    # ------------------------------------------------------------------
    def stats(self) -> Dict[str, Any]:
        """返回注册表统计信息"""
        return {
            "total_ids": len(self._store),
            "total_versions": sum(len(vs) for vs in self._store.values()),
            "by_type": {
                t: len(self._index_by_type[t])
                for t in self._index_by_type
            },
        }

    def __len__(self) -> int:
        return sum(len(vs) for vs in self._store.values())

    def __contains__(self, prompt_id: str) -> bool:
        return prompt_id in self._store
