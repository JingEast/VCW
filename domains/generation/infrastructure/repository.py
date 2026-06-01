"""Generation domain repository implementations (Adapter)."""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from domains.generation.domain.repository import (
    ICopyRepository,
    IMemoryRepository,
    ITaskRepository,
)


class CopyRepository(ICopyRepository):
    """文案文件系统持久化。"""

    def save(self, content: str, topic: str, meta: object, output_dir: str) -> str:
        import re

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_topic = re.sub(r"[^\w\u4e00-\u9fff]", "_", topic)[:30]
        filename = f"{timestamp}_{safe_topic}.md"
        filepath = output_path / filename

        header = f"""---
topic: {topic}
generated_at: {datetime.now().isoformat()}
meta: {meta}
---

"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(header + content)
        return str(filepath)

    def find_recent(self, limit: int, output_dir: str) -> List[Dict]:
        output_path = Path(output_dir)
        if not output_path.exists():
            return []
        files = sorted(
            output_path.glob("*.md"),
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )
        result = []
        for f in files[:limit]:
            stat = f.stat()
            topic = self._extract_topic(f)
            result.append({
                "name": f.name,
                "path": str(f),
                "size": f"{stat.st_size / 1024:.1f} KB",
                "time": datetime.fromtimestamp(stat.st_mtime).strftime(
                    "%Y-%m-%d %H:%M"
                ),
                "topic": topic or f.stem,
            })
        return result

    def get_stats(self, output_dir: str) -> Dict:
        stats = {"today": 0, "week": 0, "total": 0, "top_topics": []}
        output_path = Path(output_dir)
        if not output_path.exists():
            return stats

        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start.timestamp() - 7 * 24 * 3600
        topic_counts: Dict[str, int] = {}

        for f in output_path.glob("*.md"):
            try:
                stat = f.stat()
                mtime = stat.st_mtime
                if mtime >= today_start.timestamp():
                    stats["today"] += 1  # type: ignore[operator]
                if mtime >= week_start:
                    stats["week"] += 1  # type: ignore[operator]
                stats["total"] += 1  # type: ignore[operator]

                topic = self._extract_topic(f)
                if topic:
                    topic_counts[topic] = topic_counts.get(topic, 0) + 1
            except (OSError, UnicodeDecodeError, ValueError):
                pass

        stats["top_topics"] = sorted(
            topic_counts.items(), key=lambda x: x[1], reverse=True
        )[:5]
        return stats

    @staticmethod
    def _extract_topic(filepath: Path) -> str:
        try:
            with open(filepath, "r", encoding="utf-8") as fp:
                first_lines = fp.read(500)
                for line in first_lines.split("\n"):
                    if line.startswith("topic:"):
                        return line.replace("topic:", "").strip()
        except (OSError, UnicodeDecodeError, ValueError):
            pass
        return ""


class TaskRepository(ITaskRepository):
    """异步任务队列适配器。"""

    def __init__(self, task_queue):
        self._queue = task_queue

    def submit(self, task_type: str, worker_fn) -> str:
        return self._queue.submit(task_type, worker_fn)

    def get_status(self, task_id: str) -> Optional[Dict]:
        return self._queue.get_status(task_id)

    def cancel(self, task_id: str) -> bool:
        return self._queue.cancel(task_id)


class MemoryRepository(IMemoryRepository):
    """记忆库适配器。"""

    def __init__(self, memory_bank):
        self._bank = memory_bank

    def format_memories(self, topic: str) -> str:
        return self._bank.format_memories_for_prompt(topic=topic)

    def format_memories_for_prompt(self, topic: str = "") -> str:
        return self._bank.format_memories_for_prompt(topic=topic)
