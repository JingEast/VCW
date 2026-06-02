"""
MemoryEntry Repository
记忆库数据访问层。
"""
from typing import Dict, List
from sqlalchemy.orm import Session

from .base import BaseRepository
from ..models import MemoryEntry
from app.core.cache import cached


class MemoryRepository(BaseRepository):
    """记忆库 Repository"""

    _CACHE_TTL = 300  # 5 分钟

    def __init__(self, session: Session):
        super().__init__(session, MemoryEntry)

    def _clear_read_caches(self) -> None:
        for method_name in ("get_entries_by_topic", "get_entries_by_tags", "get_recent_entries", "count_pending"):
            method = getattr(self, method_name, None)
            if method is not None:
                clear_fn = getattr(method, "cache_clear", None)
                if clear_fn is not None:
                    clear_fn()

    def add_entry(self, topic: str, issue_description: str, issue_tags: List[str],
                  correction_plan: str, original_text: str = "") -> MemoryEntry:
        import uuid
        entry = MemoryEntry(
            id=str(uuid.uuid4())[:8],
            topic=topic,
            issue_description=issue_description,
            issue_tags=issue_tags or ["其他"],
            correction_plan=correction_plan,
            original_text=original_text,
        )
        self.session.add(entry)
        self.session.commit()
        self.session.refresh(entry)
        self._clear_read_caches()
        return entry

    @cached(ttl_seconds=_CACHE_TTL, maxsize=32)
    def get_entries_by_topic(self, topic: str, limit: int = 10) -> List[MemoryEntry]:
        topic_key = topic.strip()
        entries = self.session.query(MemoryEntry).filter(
            MemoryEntry.topic == topic_key
        ).order_by(MemoryEntry.created_at.desc()).limit(limit).all()
        return entries

    @cached(ttl_seconds=_CACHE_TTL, maxsize=32)
    def get_entries_by_tags(self, tags: List[str], limit: int = 10) -> List[MemoryEntry]:
        # 候选集策略：先取最近 5*limit 条，再在 Python 中过滤
        # 避免全表加载（当 memory_entries 很大时）
        _CANDIDATE_MULT = 5
        candidate_limit = max(limit * _CANDIDATE_MULT, 50)
        entries = self.session.query(MemoryEntry).order_by(
            MemoryEntry.created_at.desc()
        ).limit(candidate_limit).all()
        tag_set = set(tags)
        matched = [e for e in entries if tag_set & set(e.issue_tags or [])]
        return matched[:limit]

    @cached(ttl_seconds=_CACHE_TTL, maxsize=16)
    def get_recent_entries(self, limit: int = 20) -> List[MemoryEntry]:
        return self.session.query(MemoryEntry).order_by(
            MemoryEntry.created_at.desc()
        ).limit(limit).all()

    def mark_avoided(self, entry_id: str) -> bool:
        entry = self.get_by_id(entry_id)
        if entry:
            entry.is_avoided = True
            self.session.commit()
            self._clear_read_caches()
            return True
        return False

    @cached(ttl_seconds=_CACHE_TTL, maxsize=4)
    def count_pending(self) -> int:
        return (
            self.session.query(MemoryEntry)
            .filter(MemoryEntry.is_avoided.is_(False))
            .count()
        )

    def generate_report(self) -> str:
        total = self.session.query(MemoryEntry).count()
        avoided = self.session.query(MemoryEntry).filter(MemoryEntry.is_avoided).count()

        # 标签统计（在 Python 中聚合，因为 issue_tags 是 JSON）
        entries = self.session.query(MemoryEntry).all()
        tag_counts: Dict[str, int] = {}
        topic_counts: Dict[str, int] = {}
        for e in entries:
            tags: List[str] = list(e.issue_tags or [])  # type: ignore[union-attr]
            for t in tags:
                tag_counts[t] = tag_counts.get(t, 0) + 1
            topic_counts[e.topic] = topic_counts.get(e.topic, 0) + 1  # type: ignore[index, call-overload]

        lines = [
            "=== 记忆库统计报告 ===",
            f"总条目数: {total}",
            f"已规避: {avoided} | 待规避: {total - avoided}",
            "",
            "问题类型分布:",
        ]
        for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  - {tag}: {count}条")

        lines.append("")
        lines.append("主题分布:")
        for topic, count in sorted(topic_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  - {topic}: {count}条")

        return "\n".join(lines)
