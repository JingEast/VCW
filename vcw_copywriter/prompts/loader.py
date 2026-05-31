"""
Prompt Loader —— 从文件系统加载 Prompt
----------------------------------------
支持 Markdown + YAML Frontmatter 格式：

---
id: scene:insertion
type: scene
version: 1.0.0
metadata:
  author: team
  description: 香港中小学插班场景 Prompt
  tags: [scene, insertion, primary]
  compatible_scenes: [香港中小学插班规划]
dependencies: []
variables: []
---

这里放 Prompt 的 Markdown 内容……

同时支持直接从 JSON 文件加载 PromptSpec 数组。
"""
import json
import re
from pathlib import Path
from typing import List, Optional, Union

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from .schemas import PromptSpec, PromptVersion, PromptMetadata
from .registry import PromptRegistry


# Frontmatter 正则：匹配 --- 包裹的 YAML/JSON 块
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


class PromptLoader:
    """
    Prompt 文件加载器

    从目录树递归加载所有 .md / .json / .yaml 文件，解析为 PromptSpec。
    """

    def __init__(self, search_paths: Optional[List[Union[str, Path]]] = None):
        """
        Args:
            search_paths: 搜索路径列表，默认包含内置 templates/ 目录
        """
        base_dir = Path(__file__).parent / "templates"
        self.search_paths = [base_dir]
        if search_paths:
            self.search_paths.extend([Path(p) for p in search_paths])

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------
    def load_all(self, registry: Optional[PromptRegistry] = None) -> PromptRegistry:
        """
        加载所有搜索路径下的 Prompt 文件，注册到 registry（或新建）。
        """
        if registry is None:
            registry = PromptRegistry()

        for sp in self.search_paths:
            if not sp.exists():
                continue
            for spec in self._scan_dir(sp):
                registry.register(spec)
        return registry

    def load_file(self, filepath: Union[str, Path]) -> Optional[PromptSpec]:
        """加载单个文件为 PromptSpec"""
        path = Path(filepath)
        if not path.exists():
            return None

        suffix = path.suffix.lower()
        if suffix == ".json":
            return self._load_json(path)
        if suffix in (".md", ".txt", ".markdown"):
            return self._load_markdown(path)
        if suffix in (".yaml", ".yml"):
            return self._load_yaml(path)
        return None

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------
    def _scan_dir(self, directory: Path) -> List[PromptSpec]:
        """递归扫描目录"""
        specs = []
        for ext in ("*.md", "*.txt", "*.json", "*.yaml", "*.yml"):
            for fp in directory.rglob(ext):
                spec = self.load_file(fp)
                if spec:
                    specs.append(spec)
        return specs

    def _load_markdown(self, path: Path) -> Optional[PromptSpec]:
        """解析 Markdown + Frontmatter"""
        text = path.read_text(encoding="utf-8")
        match = _FRONTMATTER_RE.match(text)
        if not match:
            # 无 Frontmatter：尝试从文件名推断元信息
            return self._infer_from_content(path, text)

        fm_text, body = match.groups()
        frontmatter = self._parse_frontmatter(fm_text)
        if not frontmatter:
            return None

        return self._build_spec(frontmatter, body.strip(), source=str(path))

    def _load_json(self, path: Path) -> Optional[PromptSpec]:
        """加载单个 JSON PromptSpec"""
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            # 如果 JSON 是数组，取第一个
            data = data[0] if data else {}
        if not data.get("id"):
            return None
        return PromptSpec.from_dict(data)

    def _load_yaml(self, path: Path) -> Optional[PromptSpec]:
        """加载单个 YAML PromptSpec"""
        if not HAS_YAML:
            return None
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            data = data[0] if data else {}
        if not data or not data.get("id"):
            return None
        return PromptSpec.from_dict(data)

    def _parse_frontmatter(self, text: str) -> Optional[dict]:
        """解析 Frontmatter 字符串为 dict"""
        if HAS_YAML:
            try:
                return yaml.safe_load(text) or {}
            except (ValueError, TypeError):
                pass
        # Fallback：尝试 JSON
        try:
            return json.loads(text)
        except (ValueError, TypeError):
            return None

    def _infer_from_content(self, path: Path, text: str) -> Optional[PromptSpec]:
        """
        无 Frontmatter 时的推断逻辑：
        从目录结构和文件名推断 id / type / version
        """
        # 路径：.../templates/{type}/{name}_v{N}.md
        rel = path.relative_to(Path(__file__).parent / "templates")
        parts = rel.parts
        if len(parts) >= 2:
            ptype = parts[0]  # system / scene / style / sample / sections
            name = path.stem  # 去掉后缀
            # 尝试提取版本号 _v1, _v1.0, _v1.0.0
            version_match = re.search(r"_v(\d+(?:\.\d+)*)$", name)
            if version_match:
                version_str = version_match.group(1)
                name = name[:version_match.start()]
            else:
                version_str = "1.0.0"
            pid = f"{ptype}:{name}"
            return PromptSpec(
                id=pid,
                type=ptype if ptype in {
                    "system", "user", "scene", "style", "sample", "section", "composite"
                } else "section",
                version=PromptVersion.parse(version_str),
                content=text.strip(),
                metadata=PromptMetadata(
                    description=f"Auto-inferred from {rel}",
                    tags=[ptype, name],
                ),
            )
        return None

    def _build_spec(
        self, frontmatter: dict, body: str, source: str
    ) -> Optional[PromptSpec]:
        """从 Frontmatter dict + body 构建 PromptSpec"""
        pid = frontmatter.get("id")
        if not pid:
            return None

        ptype = frontmatter.get("type", "section")
        version_str = frontmatter.get("version", "1.0.0")

        meta = frontmatter.get("metadata", {})
        metadata = PromptMetadata.from_dict(meta)
        if not metadata.description:
            metadata.description = f"Loaded from {source}"

        return PromptSpec(
            id=pid,
            type=ptype,
            version=PromptVersion.parse(version_str),
            content=body,
            metadata=metadata,
            dependencies=frontmatter.get("dependencies", []),
            variables=frontmatter.get("variables", []),
        )


# ----------------------------------------------------------------------
# 便捷函数
# ----------------------------------------------------------------------
def load_default_registry(
    extra_paths: Optional[List[Union[str, Path]]] = None,
) -> PromptRegistry:
    """
    加载默认 Prompt Registry：
    1. 先加载内置 defaults（代码内联）
    2. 再扫描 templates/ 目录
    3. 最后加载用户自定义路径
    """
    from .defaults import register_defaults

    registry = PromptRegistry()
    register_defaults(registry)

    loader = PromptLoader(search_paths=extra_paths)
    loader.load_all(registry)

    return registry
