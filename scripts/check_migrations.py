#!/usr/bin/env python3
"""
Alembic 迁移一致性检查脚本。

用途：
  1. 应用所有迁移到目标数据库（alembic upgrade head）
  2. 检查当前模型与数据库 schema 是否存在差异（alembic check）
  3. 可选：生成差异报告

退出码：
  0 — 迁移与模型一致
  1 — 发现未提交的 schema 变更（需要生成新迁移）
  2 — 运行时错误

环境变量：
  DATABASE_URL — 数据库连接地址（默认 sqlite:///data/vcw.db）
"""

from __future__ import annotations

import os
import subprocess
import sys


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    print(f"[check-migrations] {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True, text=True)


def main() -> int:
    db_url = os.getenv("DATABASE_URL", "sqlite:///data/vcw.db")
    os.environ.setdefault("DATABASE_URL", db_url)

    # 1. 升级至最新迁移
    print("[check-migrations] Step 1/2: alembic upgrade head")
    result = _run([sys.executable, "-m", "alembic", "upgrade", "head"])
    if result.returncode != 0:
        print(f"[check-migrations] ERROR: upgrade failed\n{result.stderr}", file=sys.stderr)
        return 2
    print("[check-migrations] upgrade head: OK")

    # 2. 检查模型与数据库的差异
    print("[check-migrations] Step 2/2: alembic check")
    result = _run([sys.executable, "-m", "alembic", "check"])

    if result.returncode == 0:
        print("[check-migrations] Schema and models are in sync")
        return 0

    # Alembic check 返回非零说明有差异
    print("[check-migrations] FAILED: Schema drift detected!")
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    print("[check-migrations] Hint: run 'alembic revision --autogenerate -m \"your message\"'")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
