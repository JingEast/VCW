"""
Prompt Registry Schema Definitions
----------------------------------
定义 Prompt 版本化系统的核心数据模型：
- PromptVersion: 语义化版本号 (major.minor.patch)
- PromptMetadata: 作者、标签、描述、兼容性等元信息
- PromptSpec: 单个 Prompt 的完整规格（ID、类型、版本、内容、依赖）
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any
from datetime import datetime


@dataclass(frozen=True)
class PromptVersion:
    """语义化版本号，支持比较和字符串化"""
    major: int = 1
    minor: int = 0
    patch: int = 0

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def __lt__(self, other: "PromptVersion") -> bool:
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __le__(self, other: "PromptVersion") -> bool:
        return (self.major, self.minor, self.patch) <= (other.major, other.minor, other.patch)

    def __gt__(self, other: "PromptVersion") -> bool:
        return (self.major, self.minor, self.patch) > (other.major, other.minor, other.patch)

    def __ge__(self, other: "PromptVersion") -> bool:
        return (self.major, self.minor, self.patch) >= (other.major, other.minor, other.patch)

    @classmethod
    def parse(cls, version_str: str) -> "PromptVersion":
        """从字符串解析版本号，如 '1.2.3'"""
        parts = version_str.strip().split(".")
        if len(parts) == 1:
            return cls(major=int(parts[0]))
        if len(parts) == 2:
            return cls(major=int(parts[0]), minor=int(parts[1]))
        return cls(major=int(parts[0]), minor=int(parts[1]), patch=int(parts[2]))


@dataclass
class PromptMetadata:
    """Prompt 元数据，描述性信息不参与组合逻辑"""
    author: str = ""
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    tags: List[str] = field(default_factory=list)
    # 兼容性：此 Prompt 适用于哪些场景 ID
    compatible_scenes: List[str] = field(default_factory=list)
    # 额外自定义字段
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "author": self.author,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tags": self.tags,
            "compatible_scenes": self.compatible_scenes,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PromptMetadata":
        return cls(
            author=d.get("author", ""),
            description=d.get("description", ""),
            created_at=d.get("created_at", datetime.now().isoformat()),
            updated_at=d.get("updated_at", datetime.now().isoformat()),
            tags=d.get("tags", []),
            compatible_scenes=d.get("compatible_scenes", []),
            extra=d.get("extra", {}),
        )


@dataclass
class PromptSpec:
    """
    Prompt 规格定义 —— Registry 中的最小存储单元

    Attributes:
        id: 唯一标识符，格式推荐为 "domain:name" 或 "type:name"
            例如："system:copywriting", "scene:insertion", "style:tone"
        type: Prompt 类型，决定其在组合中的角色
            system | user | scene | style | sample | section | composite
        version: 语义化版本号
        content: Prompt 文本内容
        metadata: 描述性元数据
        dependencies: 依赖的其他 Prompt ID 列表（用于组合时自动解析依赖树）
        variables: 内容中需要外部注入的变量名列表（用于校验）
    """
    id: str
    type: str  # system | user | scene | style | sample | section | composite
    version: PromptVersion
    content: str
    metadata: PromptMetadata = field(default_factory=PromptMetadata)
    dependencies: List[str] = field(default_factory=list)
    variables: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.type not in {
            "system", "user", "scene", "style", "sample", "section", "composite"
        }:
            raise ValueError(f"Invalid prompt type: {self.type}")

    @property
    def full_id(self) -> str:
        """带版本的完整标识符，如 system:copywriting@1.0.0"""
        return f"{self.id}@{self.version}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "version": str(self.version),
            "content": self.content,
            "metadata": self.metadata.to_dict(),
            "dependencies": self.dependencies,
            "variables": self.variables,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PromptSpec":
        return cls(
            id=d["id"],
            type=d["type"],
            version=PromptVersion.parse(d.get("version", "1.0.0")),
            content=d["content"],
            metadata=PromptMetadata.from_dict(d.get("metadata", {})),
            dependencies=d.get("dependencies", []),
            variables=d.get("variables", []),
        )
