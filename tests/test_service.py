"""
Service 层测试示例

测试策略：
  1. 每个测试使用独立的临时目录（tmp_path），避免文件系统污染。
  2. 对 datetime 进行 mock，获得确定性的 draft_id，便于断言。
  3. 不修改业务代码，通过构造函数注入 edit_dir 实现隔离。
"""

import json
from datetime import datetime
from unittest.mock import patch

import pytest

from vcw_copywriter.editor import EditorWorkflow


class TestEditorWorkflow:
    """测试 EditorWorkflow —— 精修工作流 Service"""

    @pytest.fixture
    def editor(self, tmp_path):
        """
        使用临时目录构造 EditorWorkflow，测试互不干扰。
        """
        return EditorWorkflow(edit_dir=str(tmp_path / "edited"))

    @pytest.fixture
    def fixed_now(self):
        """固定时间，用于确定性 draft_id"""
        return datetime(2026, 5, 29, 14, 30, 0)

    # ------------------------------------------------------------------
    # save_draft
    # ------------------------------------------------------------------
    def test_save_draft_creates_index_and_markdown(self, editor, tmp_path, fixed_now):
        """保存草稿后，index.json 和 .md 文件应同时存在"""
        with patch("vcw_copywriter.editor.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.strftime = datetime.strftime
            mock_dt.isoformat = datetime.isoformat

            draft_id = editor.save_draft(
                original_content="原始文案内容",
                topic="DSE保底路径",
                source_filepath="data/generated/test.md",
                meta="batch_id_001",
            )

        assert draft_id == "20260529_143000"

        # 验证 index.json
        index = json.loads(editor.index_path.read_text(encoding="utf-8"))
        assert len(index["versions"]) == 1
        assert index["versions"][0]["id"] == draft_id
        assert index["versions"][0]["topic"] == "DSE保底路径"
        assert index["versions"][0]["status"] == "draft"

        # 验证 markdown 文件已生成
        md_files = list(editor.edit_dir.glob("*.md"))
        assert len(md_files) == 1
        assert draft_id in md_files[0].name
        assert "DSE保底路径" in md_files[0].read_text(encoding="utf-8")

    def test_save_draft_default_meta(self, editor, fixed_now):
        """不传入 meta 时，meta 应为空字符串"""
        with patch("vcw_copywriter.editor.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.strftime = datetime.strftime
            mock_dt.isoformat = datetime.isoformat

            draft_id = editor.save_draft(
                original_content="内容",
                topic="测试主题",
            )

        draft = editor.get_draft(draft_id)
        assert draft["meta"] == ""

    # ------------------------------------------------------------------
    # get_draft / get_all_drafts
    # ------------------------------------------------------------------
    def test_get_draft_not_found(self, editor):
        """查询不存在的 draft_id 应返回 None"""
        assert editor.get_draft("nonexistent") is None

    def test_get_all_drafts_sorted_by_updated_at(self, editor, fixed_now):
        """多条草稿应按 updated_at 降序排列"""
        times = [
            fixed_now,
            fixed_now.replace(minute=31),
            fixed_now.replace(minute=32),
        ]

        for i, t in enumerate(times):
            with patch("vcw_copywriter.editor.datetime") as mock_dt:
                mock_dt.now.return_value = t
                mock_dt.strftime = datetime.strftime
                mock_dt.isoformat = datetime.isoformat
                editor.save_draft(original_content=f"内容{i}", topic=f"主题{i}")

        drafts = editor.get_all_drafts()
        assert len(drafts) == 3
        # 降序：最新的排在最前
        assert drafts[0]["topic"] == "主题2"
        assert drafts[2]["topic"] == "主题0"

    def test_get_all_drafts_filter_by_status(self, editor, fixed_now):
        """按 status 过滤草稿"""
        with patch("vcw_copywriter.editor.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.strftime = datetime.strftime
            mock_dt.isoformat = datetime.isoformat
            draft_id = editor.save_draft(original_content="内容", topic="主题")

        # 初始状态为 draft
        assert len(editor.get_all_drafts(status="draft")) == 1
        assert len(editor.get_all_drafts(status="final")) == 0

        editor.finalize(draft_id)
        assert len(editor.get_all_drafts(status="final")) == 1
        assert len(editor.get_all_drafts(status="draft")) == 0

    # ------------------------------------------------------------------
    # update_edited
    # ------------------------------------------------------------------
    def test_update_edited_records_history(self, editor, fixed_now):
        """更新精修内容应记录编辑历史并修改状态"""
        with patch("vcw_copywriter.editor.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.strftime = datetime.strftime
            mock_dt.isoformat = datetime.isoformat
            draft_id = editor.save_draft(original_content="原始文案", topic="主题")

        # 第一次编辑
        ok = editor.update_edited(
            draft_id=draft_id,
            edited_content="精修后的文案",
            edit_note="调整了语气",
        )
        assert ok is True

        draft = editor.get_draft(draft_id)
        assert draft["edited"] == "精修后的文案"
        assert draft["status"] == "edited"
        assert len(draft["edit_history"]) == 1
        assert draft["edit_history"][0]["note"] == "调整了语气"
        assert draft["edit_history"][0]["before_length"] == len("原始文案")
        assert draft["edit_history"][0]["after_length"] == len("精修后的文案")

    def test_update_edited_not_found(self, editor):
        """对不存在的 draft_id 更新应返回 False"""
        ok = editor.update_edited("no_such_id", "内容")
        assert ok is False

    # ------------------------------------------------------------------
    # finalize
    # ------------------------------------------------------------------
    def test_finalize_sets_status(self, editor, fixed_now):
        """finalize 应将草稿状态设为 final"""
        with patch("vcw_copywriter.editor.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.strftime = datetime.strftime
            mock_dt.isoformat = datetime.isoformat
            draft_id = editor.save_draft(original_content="内容", topic="主题")

        assert editor.get_draft(draft_id)["status"] == "draft"
        assert editor.finalize(draft_id) is True
        assert editor.get_draft(draft_id)["status"] == "final"

    def test_finalize_not_found(self, editor):
        """对不存在的 draft_id finalize 应返回 False"""
        assert editor.finalize("no_such_id") is False

    # ------------------------------------------------------------------
    # get_diff
    # ------------------------------------------------------------------
    def test_get_diff_returns_original_and_edited(self, editor, fixed_now):
        """get_diff 应返回 (original, edited) 元组"""
        with patch("vcw_copywriter.editor.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.strftime = datetime.strftime
            mock_dt.isoformat = datetime.isoformat
            draft_id = editor.save_draft(original_content="原始文案", topic="主题")

        editor.update_edited(draft_id, "精修文案", "note")
        original, edited = editor.get_diff(draft_id)
        assert original == "原始文案"
        assert edited == "精修文案"

    def test_get_diff_not_found(self, editor):
        """对不存在的 draft_id get_diff 应返回空字符串元组"""
        assert editor.get_diff("no_such_id") == ("", "")

    # ------------------------------------------------------------------
    # build_de_ai_prompt
    # ------------------------------------------------------------------
    def test_build_de_ai_prompt_contains_content(self, editor):
        """build_de_ai_prompt 应将内容注入模板"""
        content = "这是待优化的文案"
        prompt = editor.build_de_ai_prompt(content)
        assert content in prompt
        assert "去AI味" in prompt or "资深短视频文案编辑" in prompt

    def test_build_de_ai_prompt_idempotent(self, editor):
        """多次调用应各自独立，不修改模板本身"""
        p1 = editor.build_de_ai_prompt("文案A")
        p2 = editor.build_de_ai_prompt("文案B")
        assert "文案A" in p1
        assert "文案B" in p2
        assert "文案B" not in p1
        assert "文案A" not in p2
