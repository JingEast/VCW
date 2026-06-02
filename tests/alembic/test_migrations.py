"""
Alembic 迁移治理测试

覆盖：
- 迁移链线性（无分支）
- upgrade / downgrade 可逆
- 最新迁移后 schema 与模型一致
"""

import os
import tempfile

import pytest
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory


@pytest.fixture(scope="module")
def alembic_cfg():
    """返回 Alembic Config，使用临时文件数据库（避免 :memory: 连接隔离问题）。"""
    # 创建临时数据库文件
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db_url = f"sqlite:///{db_path}"
    os.environ["DATABASE_URL"] = db_url

    cfg = Config("alembic.ini")
    yield cfg

    # 清理
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture(scope="module")
def script_dir(alembic_cfg):
    """返回 Alembic ScriptDirectory。"""
    return ScriptDirectory.from_config(alembic_cfg)


class TestMigrationChain:
    """迁移链完整性测试。"""

    def test_single_head(self, script_dir):
        """必须只有一个 head（无线性分支）。"""
        heads = list(script_dir.get_heads())
        assert len(heads) == 1, f"Expected 1 head, got {len(heads)}: {heads}"

    def test_revisions_are_linear(self, script_dir):
        """所有 revision 必须形成一条单链，无 merge/branch。"""
        heads = list(script_dir.get_heads())
        assert len(heads) == 1
        head_rev = script_dir.get_revision(heads[0])
        visited = set()
        current = head_rev
        while current is not None:
            assert current.revision not in visited, "Circular dependency detected"
            visited.add(current.revision)
            down = current.down_revision
            if isinstance(down, tuple):
                assert len(down) == 1, f"Branch detected at {down}"
                down = down[0]
            current = script_dir.get_revision(down) if down else None


class TestMigrationReversibility:
    """迁移可逆性测试。"""

    def test_full_upgrade_downgrade(self, alembic_cfg):
        """从 base 到 head 再回退到 base 必须成功。"""
        command.upgrade(alembic_cfg, "head")
        command.downgrade(alembic_cfg, "base")

    def test_each_revision_downgradable(self, alembic_cfg, script_dir):
        """逐个 revision 降级并恢复。"""
        command.upgrade(alembic_cfg, "head")
        # 获取所有 revision ID（从 head 到 base）
        all_revs = []
        current = script_dir.get_revision(script_dir.get_heads()[0])
        while current is not None:
            all_revs.append(current.revision)
            down = current.down_revision
            if isinstance(down, tuple):
                down = down[0] if down else None
            current = script_dir.get_revision(down) if down else None

        # 从 base 后第一个开始逐个 down + up
        for rev_id in reversed(all_revs[:-1]):
            down_target = script_dir.get_revision(rev_id).down_revision
            if isinstance(down_target, tuple):
                down_target = down_target[0] if down_target else "base"
            elif down_target is None:
                down_target = "base"
            command.downgrade(alembic_cfg, down_target)
            command.upgrade(alembic_cfg, "head")

    def test_schema_consistency_after_upgrade(self, alembic_cfg):
        """升级到 head 后，schema 必须与模型一致（零 drift）。"""
        command.upgrade(alembic_cfg, "head")
        command.check(alembic_cfg)
