"""
迭代优化与记忆库模块 v2.0 — PostgreSQL Repository Pattern 适配器
对外接口完全一致，内部通过 MemoryRepository 操作 SQLAlchemy ORM。
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict

from .light_vector_search import LightVectorSearch


class MemoryBank:
    """文案记忆库 — Repository 适配器"""

    def __init__(self, db_path: str = "data/memory_db.json"):
        self.db_path = Path(db_path)
        from .db.session import init_db, get_session
        from .db.repositories.memory_repository import MemoryRepository
        init_db()
        self._repo = MemoryRepository(get_session())
        self._vector_search = LightVectorSearch()
        self.data = self._load()
        self._rebuild_vector_index()

    # ------------------ 加载 / 保存 ------------------

    def _load(self) -> Dict:
        # 优先从数据库加载
        entries = self._repo.get_recent_entries(limit=10000)
        if entries:
            result = {
                "entries": [e.to_dict() for e in entries],
                "topics_index": self._build_topics_index(entries),
            }
            return result

        # 数据库为空，从 JSON 回退
        if self.db_path.exists():
            with open(self.db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._sync_json_to_db(data)
            return data

        return {"entries": [], "topics_index": {}}

    def _save(self):
        from filelock import FileLock
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        lock = FileLock(str(self.db_path) + ".lock")
        with lock:
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        self._sync_to_db()

    def _sync_json_to_db(self, data: Dict):
        from .db.models import MemoryEntry
        for e_dict in data.get("entries", []):
            entry = MemoryEntry.from_dict(e_dict)
            self._repo.session.add(entry)
        self._repo.session.commit()
        print(f"[MemoryBank] JSON → 数据库迁移完成: {len(data.get('entries', []))} 条")

    def _sync_to_db(self):
        from .db.models import MemoryEntry
        from .scraper.utils import TimeParser
        existing = {e.id: e for e in self._repo.session.query(MemoryEntry).all()}
        current_ids = set()

        for e_dict in self.data.get("entries", []):
            eid = e_dict.get("id")
            current_ids.add(eid)
            if eid in existing:
                existing[eid].topic = e_dict.get("topic", "")
                existing[eid].issue_description = e_dict.get("issue_description", "")
                existing[eid].issue_tags = e_dict.get("issue_tags") or []
                existing[eid].correction_plan = e_dict.get("correction_plan", "")
                existing[eid].original_text = e_dict.get("original_text", "")
                existing[eid].is_avoided = bool(e_dict.get("is_avoided"))
                ca = e_dict.get("created_at", "")
                existing[eid].created_at = TimeParser.parse_datetime(ca) if ca else datetime.utcnow()
            else:
                entry = MemoryEntry.from_dict(e_dict)
                self._repo.session.add(entry)

        for eid, e_orm in existing.items():
            if eid not in current_ids:
                self._repo.session.delete(e_orm)

        self._repo.session.commit()

    def _build_topics_index(self, entries: List) -> Dict:
        idx: Dict[str, List[int]] = {}
        for e in entries:
            topic_key = e.topic.strip()
            if topic_key not in idx:
                idx[topic_key] = []
            idx[topic_key].append(e.id)
        return idx

    # ------------------ 业务方法 ------------------

    def add_entry(self, topic: str, issue_description: str, issue_tags: List[str],
                  correction_plan: str, original_text: str = "") -> str:
        entry_id = str(uuid.uuid4())[:8]
        entry = {
            "id": entry_id,
            "topic": topic,
            "issue_description": issue_description,
            "issue_tags": issue_tags or ["其他"],
            "correction_plan": correction_plan,
            "original_text": original_text,
            "created_at": datetime.now().isoformat(),
            "is_avoided": False,
        }
        self.data["entries"].append(entry)
        topic_key = topic.strip()
        if topic_key not in self.data["topics_index"]:
            self.data["topics_index"][topic_key] = []
        self.data["topics_index"][topic_key].append(entry_id)
        self._save()
        self._rebuild_vector_index()
        return entry_id

    def _rebuild_vector_index(self):
        docs = []
        for e in self.data["entries"]:
            text = f"{e.get('topic','')} {e.get('issue_description','')} {' '.join(e.get('issue_tags',[]))}"
            docs.append({"text": text, "entry": e})
        self._vector_search.build_index(docs, text_key="text")

    def get_entries_by_topic(self, topic: str, limit: int = 10) -> List[Dict]:
        topic_key = topic.strip()
        entry_ids = self.data["topics_index"].get(topic_key, [])
        entries = []
        for e in self.data["entries"]:
            if e["id"] in entry_ids:
                entries.append(e)
        if len(entries) < limit:
            seen_ids = {e["id"] for e in entries}
            vec_results = self._vector_search.search(topic, top_k=limit + 5)
            for doc, score in vec_results:
                entry = doc.get("entry")
                if entry and entry["id"] not in seen_ids:
                    entries.append(entry)
                    seen_ids.add(entry["id"])
                if len(entries) >= limit:
                    break
        entries.sort(key=lambda x: x["created_at"], reverse=True)
        return entries[:limit]

    def get_entries_by_tags(self, tags: List[str], limit: int = 10) -> List[Dict]:
        tag_set = set(tags)
        matched = []
        for e in self.data["entries"]:
            if tag_set & set(e.get("issue_tags", [])):
                matched.append(e)
        matched.sort(key=lambda x: x["created_at"], reverse=True)
        return matched[:limit]

    def get_recent_entries(self, limit: int = 20) -> List[Dict]:
        entries = sorted(self.data["entries"], key=lambda x: x["created_at"], reverse=True)
        return entries[:limit]

    def mark_avoided(self, entry_id: str):
        for e in self.data["entries"]:
            if e["id"] == entry_id:
                e["is_avoided"] = True
                break
        self._save()

    def format_memories_for_prompt(self, topic: str = "", tags: List[str] = None) -> str:
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
            status = "【已规避】" if e["is_avoided"] else "【待规避】"
            lines.append(f"[{i}] {status} 主题: {e['topic']} | 标签: {', '.join(e['issue_tags'])}")
            lines.append(f"    问题: {e['issue_description']}")
            lines.append(f"    修正: {e['correction_plan']}")
            if e["original_text"]:
                lines.append(f"    原文片段: {e['original_text'][:100]}...")
            lines.append("")
        return "\n".join(lines)

    def generate_report(self) -> str:
        total = len(self.data["entries"])
        avoided = sum(1 for e in self.data["entries"] if e["is_avoided"])
        tag_counts: Dict[str, int] = {}
        for e in self.data["entries"]:
            for t in e.get("issue_tags", []):
                tag_counts[t] = tag_counts.get(t, 0) + 1
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
        for topic, ids in self.data["topics_index"].items():
            lines.append(f"  - {topic}: {len(ids)}条")
        return "\n".join(lines)
