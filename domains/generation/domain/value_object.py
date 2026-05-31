"""
Generation Domain — Value Object
=================================

文案生成领域的值对象集合。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class Topic:
    """文案主题（值对象）。"""

    value: str

    def __post_init__(self):
        if not self.value or not self.value.strip():
            raise ValueError("Topic cannot be empty")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Audience:
    """目标受众（值对象）。"""

    value: str = "港宝家长"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Prompt:
    """提示词（值对象）。"""

    system: str
    user: str

    def __post_init__(self):
        if not self.system or not self.system.strip():
            raise ValueError("System prompt cannot be empty")
        if not self.user or not self.user.strip():
            raise ValueError("User prompt cannot be empty")

    @property
    def total_length(self) -> int:
        return len(self.system) + len(self.user)


@dataclass(frozen=True)
class QualityIssue:
    """质量问题条目（值对象）。"""

    category: str
    level: str  # error, warning, info
    message: str
    suggestion: str = ""

    def __post_init__(self):
        if self.level not in ("error", "warning", "info"):
            raise ValueError(f"Invalid level: {self.level}")


@dataclass
class QualityReport:
    """质量检查报告（值对象）。"""

    issues: List[QualityIssue] = field(default_factory=list)

    def is_passed(self, strict_mode: bool = False) -> bool:
        if not self.issues:
            return True
        if strict_mode:
            return False
        return all(i.level != "error" for i in self.issues)

    def add_issue(self, issue: QualityIssue) -> None:
        self.issues.append(issue)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.level == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.level == "warning")


@dataclass(frozen=True)
class GenerationParams:
    """生成参数（值对象）。"""

    topic: str
    audience: str = "港宝家长"
    core_data: str = ""
    policy_points: str = ""
    hidden_path: str = ""
    call_to_action: str = ""
    sample_ref: str = ""
    extra_requirements: str = ""
    scene: str = ""
