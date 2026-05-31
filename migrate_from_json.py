#!/usr/bin/env python3
"""
JSON → PostgreSQL / SQLite 迁移脚本

用法:
    python migrate_from_json.py

环境变量:
    DATABASE_URL=postgresql://user:pass@localhost/vcw
    不设置则默认使用 SQLite: sqlite:///data/vcw.db

迁移逻辑（幂等）：
    1. 若数据库已有数据，跳过该实体
    2. 若 JSON 文件存在，读取并写入数据库
    3. 写入完成后可选择保留或删除 JSON 文件
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def migrate_trends(json_path: str = "data/trend_db.json"):
    from vcw_copywriter.db.session import get_session, init_db
    from vcw_copywriter.db.models import Trend
    from vcw_copywriter.db.repositories.trend_repository import TrendRepository

    init_db()
    session = get_session()
    repo = TrendRepository(session)

    existing = repo.session.query(Trend).count()
    if existing > 0:
        print(f"[migrate] trends 表已有 {existing} 条数据，跳过迁移")
        session.close()
        return

    json_file = Path(json_path)
    if not json_file.exists():
        print(f"[migrate] {json_path} 不存在，跳过")
        session.close()
        return

    import json
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    count = 0
    for t_dict in data.get("trends", []):
        trend = Trend.from_dict(t_dict)
        trend.is_archived = False
        repo.session.add(trend)
        count += 1
    for t_dict in data.get("archived", []):
        trend = Trend.from_dict(t_dict)
        trend.is_archived = True
        repo.session.add(trend)
        count += 1

    repo.session.commit()
    session.close()
    print(f"[migrate] trends 迁移完成: {count} 条（活跃 {len(data.get('trends', []))} + 归档 {len(data.get('archived', []))}）")


def migrate_memory(json_path: str = "data/memory_db.json"):
    from vcw_copywriter.db.session import get_session, init_db
    from vcw_copywriter.db.models import MemoryEntry
    from vcw_copywriter.db.repositories.memory_repository import MemoryRepository

    init_db()
    session = get_session()
    repo = MemoryRepository(session)

    existing = repo.session.query(MemoryEntry).count()
    if existing > 0:
        print(f"[migrate] memory_entries 表已有 {existing} 条数据，跳过迁移")
        session.close()
        return

    json_file = Path(json_path)
    if not json_file.exists():
        print(f"[migrate] {json_path} 不存在，跳过")
        session.close()
        return

    import json
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    count = 0
    for e_dict in data.get("entries", []):
        entry = MemoryEntry.from_dict(e_dict)
        repo.session.add(entry)
        count += 1

    repo.session.commit()
    session.close()
    print(f"[migrate] memory_entries 迁移完成: {count} 条")


def migrate_jobs(sqlite_path: str = "data/task_queue.db"):
    """从旧 SQLite task_queue.db 迁移到 ORM 数据库"""
    from vcw_copywriter.db.session import get_session, init_db
    from vcw_copywriter.db.models import GenerationJob

    init_db()
    session = get_session()

    existing = session.query(GenerationJob).count()
    if existing > 0:
        print(f"[migrate] generation_jobs 表已有 {existing} 条数据，跳过迁移")
        session.close()
        return

    db_file = Path(sqlite_path)
    if not db_file.exists():
        print(f"[migrate] {sqlite_path} 不存在，跳过")
        session.close()
        return

    import sqlite3
    conn = sqlite3.connect(sqlite_path)
    rows = conn.execute(
        "SELECT id, type, status, progress, message, result, error, created_at, started_at, completed_at FROM tasks"
    ).fetchall()
    conn.close()

    count = 0
    for row in rows:
        job = GenerationJob.from_legacy_sqlite_row(row)
        session.add(job)
        count += 1

    session.commit()
    session.close()
    print(f"[migrate] generation_jobs 迁移完成: {count} 条")


def main():
    print("=" * 60)
    print("VCW JSON → PostgreSQL/SQLite 迁移工具")
    print("=" * 60)
    db_url = os.environ.get("DATABASE_URL", "sqlite:///data/vcw.db")
    print(f"目标数据库: {db_url}")
    print()

    migrate_trends()
    migrate_memory()
    migrate_jobs()

    print()
    print("=" * 60)
    print("迁移完成。后续应用启动时将自动从数据库加载数据。")
    print("JSON 文件已保留作为备份，可手动删除。")
    print("=" * 60)


if __name__ == "__main__":
    main()
