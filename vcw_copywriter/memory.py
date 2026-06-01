"""
迭代优化与记忆库模块 v3.0 — PostgreSQL 唯一真相源

对外接口完全一致，内部不再持有进程内 self.data，
所有读写均通过 MemoryRepository 直达 PostgreSQL。
"""

from pathlib import Path
from typing import List, Dict

from .light_vector_search import LightVectorSearch


class MemoryBank:
    """文案记忆库 — PostgreSQL 持久化适配器

    关键约束：
      - 不持有 self.data（消除进程内状态漂移）。
      - 所有读取均通过 MemoryRepository 查询数据库。
      - 重启后数据自然存在于 PostgreSQL 中。
      - 多 worker 共享同一数据库，数据一致。
    """

    def __init__(self, db_path: str = "data/memory_db.json") -> None:
        """初始化记忆库。

        Args:
            db_path: 保留参数用于向后兼容（不再作为数据存储路径）。
        """
        self._db_path = Path(db_path)
        from .db.session import init_db, get_session
        from .db.repositories.memory_repository import MemoryRepository

        init_db()
        self._repo = MemoryRepository(get_session())
        self._vector_search = LightVectorSearch()
        self._rebuild_vector_index()

    # ------------------ 内部辅助 ------------------

    def _rebuild_vector_index(self) -> None:
        """基于数据库最新数据重建轻量向量索引。"""
        entries = self._repo.get_recent_entries(limit=10000)
        docs: List[Dict] = []
        for e in entries:
            text = f"{e.topic} {e.issue_description} {' '.join(e.issue_tags or [])}"
            docs.append({"text": text, "entry": e.to_dict()})
        self._vector_search.build_index(docs, text_key="text")

    # ------------------ 业务方法 ------------------

    def add_entry(
        self,
        topic: str,
        issue_description: str,
        issue_tags: List[str],
        correction_plan: str,
        original_text: str = "",
    ) -> str:
        """添加记忆条目并持久化到 PostgreSQL。"""
        entry = self._repo.add_entry(
            topic=topic,
            issue_description=issue_description,
            issue_tags=issue_tags,
            correction_plan=correction_plan,
            original_text=original_text,
        )
        self._rebuild_vector_index()
        return str(entry.id)

    def get_entries_by_topic(self, topic: str, limit: int = 10) -> List[Dict]:
        """按主题查询记忆条目，结果不足时 fallback 到向量相似度检索。"""
        orm_entries = self._repo.get_entries_by_topic(topic, limit)
        result = [e.to_dict() for e in orm_entries]

        if len(result) < limit:
            seen_ids = {e["id"] for e in result}
            vec_results = self._vector_search.search(topic, top_k=limit + 5)
            for doc, score in vec_results:
                entry = doc.get("entry")
                if entry and entry["id"] not in seen_ids:
                    result.append(entry)
                    seen_ids.add(entry["id"])
                if len(result) >= limit:
                    break

        result.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return result[:limit]

    def get_entries_by_tags(self, tags: List[str], limit: int = 10) -> List[Dict]:
        """按标签查询记忆条目。"""
        orm_entries = self._repo.get_entries_by_tags(tags, limit)
        return [e.to_dict() for e in orm_entries]

    def get_recent_entries(self, limit: int = 20) -> List[Dict]:
        """获取最近的记忆条目。"""
        orm_entries = self._repo.get_recent_entries(limit)
        return [e.to_dict() for e in orm_entries]

    def mark_avoided(self, entry_id: str) -> bool:
        """标记条目为已规避。"""
        return self._repo.mark_avoided(entry_id)

    def delete_entry(self, entry_id: str) -> bool:
        """删除指定条目。"""
        ok = self._repo.delete(entry_id)
        if ok:
            self._rebuild_vector_index()
        return ok

    def get_entry_count(self) -> int:
        """获取总条目数。"""
        return self._repo.count()

    def get_pending_count(self) -> int:
        """获取待规避条目数。"""
        return self._repo.count_pending()

    def format_memories_for_prompt(self, topic: str = "", tags: List[str] = None) -> str:
        """格式化记忆文本，供 prompt 拼接使用。"""
        if topic:
            entries = self.get_entries_by_topic(topic, limit=10)
        elif tags:
            entries = self.get_entries_by_tags(tags, limit=10)
        else:
            entries = self.get_recent_entries(limit=10)

        if not entries:
            return "【暂无历史修改意见】"

        lines = ["=== 历史修改意见与记忆（请务必规避以下问题） ===\n"]
        for i, e in enumerate(entries, 1):
            status = "【已规避】" if e.get("is_avoided") else "【待规避】"
            lines.append(
                f"[{i}] {status} 主题: {e.get('topic', '')} | "
                f"标签: {', '.join(e.get('issue_tags', []))}"
            )
            lines.append(f"    问题: {e.get('issue_description', '')}")
            lines.append(f"    修正: {e.get('correction_plan', '')}")
            if e.get("original_text"):
                lines.append(f"    原文片段: {e['original_text'][:100]}...")
            lines.append("")

        return "\n".join(lines)

    def generate_report(self) -> str:
        """生成记忆库统计报告。"""
        return self._repo.generate_report()
