"""
EditorService 单元测试
验证草稿生命周期与 AI 优化逻辑，确保依赖注入（IGenerationServiceClient）正常工作。
"""
import pytest
from typing import Dict, List, Optional, Tuple

from domains.editor.application.dto import (
    DeAIOptimizeRequest,
    SaveDraftRequest,
    UpdateDraftRequest,
)
from services.editor_service import EditorService, EditorError
from domains.editor.domain.repository import IDraftRepository
from interfaces.generation_client import IGenerationServiceClient


class FakeDraftRepo(IDraftRepository):
    """伪草稿仓库，用于隔离测试。"""

    def __init__(self):
        self._drafts: Dict[str, Dict] = {}
        self._counter = 0

    def save(
        self, original_content: str, topic: str, source_filepath: str = "", meta: str = ""
    ) -> str:
        self._counter += 1
        draft_id = f"draft-{self._counter}"
        self._drafts[draft_id] = {
            "id": draft_id,
            "topic": topic,
            "status": "draft",
            "original": original_content,
            "edited": "",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
            "source_filepath": source_filepath,
            "meta": meta,
            "edit_history": [],
        }
        return draft_id

    def get(self, draft_id: str) -> Optional[Dict]:
        return self._drafts.get(draft_id)

    def list_all(self, status: Optional[str] = None) -> List[Dict]:
        drafts = list(self._drafts.values())
        if status:
            drafts = [d for d in drafts if d["status"] == status]
        return drafts

    def update_edited(self, draft_id: str, edited_content: str, edit_note: str) -> bool:
        draft = self._drafts.get(draft_id)
        if not draft:
            return False
        draft["edited"] = edited_content
        draft["edit_history"].append({"note": edit_note})
        return True

    def finalize(self, draft_id: str) -> bool:
        draft = self._drafts.get(draft_id)
        if not draft:
            return False
        draft["status"] = "finalized"
        return True

    def get_diff(self, draft_id: str) -> Tuple[str, str]:
        draft = self._drafts.get(draft_id)
        if not draft:
            return ("", "")
        return (draft["original"], draft["edited"])

    def build_de_ai_prompt(self, content: str) -> str:
        return f"去AI味优化：\n{content}"


class FakeGenerationClient(IGenerationServiceClient):
    """伪生成客户端。"""

    def __init__(self, response: Tuple[bool, str, str] = (True, "optimized", "ok")):
        self.calls: List[Tuple[str, str]] = []
        self._response = response

    def generate_text(self, system_prompt: str, user_prompt: str) -> Tuple[bool, str, str]:
        self.calls.append((system_prompt, user_prompt))
        return self._response


@pytest.fixture
def editor_service():
    repo = FakeDraftRepo()
    client = FakeGenerationClient()
    svc = EditorService(
        draft_repo=repo,
        config=None,
        generation_client=client,
        transaction_manager=None,
        permission_manager=None,
    )
    return svc, repo, client


def test_load_or_create_draft_load_existing(editor_service):
    svc, repo, _ = editor_service
    draft_id = repo.save(original_content="hello", topic="test")
    result = svc.load_or_create_draft(content="", topic="", angle="", draft_id=draft_id)
    assert result.draft_id == draft_id


def test_load_or_create_draft_create_new(editor_service):
    svc, repo, _ = editor_service
    result = svc.load_or_create_draft(content="hello", topic="test", angle="a", draft_id="")
    assert result.topic == "test_a"
    assert result.draft_id in repo._drafts


def test_load_or_create_draft_empty(editor_service):
    svc, _, _ = editor_service
    result = svc.load_or_create_draft(content="", topic="t", angle="", draft_id="")
    assert result.draft_id == ""
    assert result.topic == "t"


def test_save_draft_success(editor_service):
    svc, repo, _ = editor_service
    req = SaveDraftRequest(original_content="content", topic="topic")
    draft_id = svc.save_draft(req)
    assert draft_id in repo._drafts


def test_save_draft_empty_content(editor_service):
    svc, _, _ = editor_service
    with pytest.raises(EditorError) as exc_info:
        svc.save_draft(SaveDraftRequest(original_content="", topic="topic"))
    assert exc_info.value.code == "EMPTY_CONTENT"


def test_save_draft_empty_topic(editor_service):
    svc, _, _ = editor_service
    with pytest.raises(EditorError) as exc_info:
        svc.save_draft(SaveDraftRequest(original_content="content", topic=""))
    assert exc_info.value.code == "EMPTY_TOPIC"


def test_get_draft_success(editor_service):
    svc, repo, _ = editor_service
    draft_id = repo.save(original_content="c", topic="t")
    result = svc.get_draft(draft_id)
    assert result.draft_id == draft_id


def test_get_draft_missing_id(editor_service):
    svc, _, _ = editor_service
    with pytest.raises(EditorError) as exc_info:
        svc.get_draft("")
    assert exc_info.value.code == "MISSING_DRAFT_ID"


def test_get_draft_not_found(editor_service):
    svc, _, _ = editor_service
    with pytest.raises(EditorError) as exc_info:
        svc.get_draft("nonexistent")
    assert exc_info.value.code == "DRAFT_NOT_FOUND"


def test_list_drafts(editor_service):
    svc, repo, _ = editor_service
    repo.save(original_content="c1", topic="t1")
    repo.save(original_content="c2", topic="t2")
    result = svc.list_drafts()
    assert result.total == 2


def test_list_drafts_by_status(editor_service):
    svc, repo, _ = editor_service
    draft_id = repo.save(original_content="c", topic="t")
    repo._drafts[draft_id]["status"] = "finalized"
    result = svc.list_drafts(status="finalized")
    assert result.total == 1


def test_update_draft_success(editor_service):
    svc, repo, _ = editor_service
    draft_id = repo.save(original_content="c", topic="t")
    req = UpdateDraftRequest(draft_id=draft_id, edited_content="edited", edit_note="note")
    result = svc.update_draft(req)
    assert result.edited == "edited"


def test_update_draft_finalize(editor_service):
    svc, repo, _ = editor_service
    draft_id = repo.save(original_content="c", topic="t")
    req = UpdateDraftRequest(
        draft_id=draft_id, edited_content="e", edit_note="n", finalize=True
    )
    result = svc.update_draft(req)
    assert result.status == "finalized"


def test_update_draft_missing_id(editor_service):
    svc, _, _ = editor_service
    with pytest.raises(EditorError) as exc_info:
        svc.update_draft(UpdateDraftRequest(draft_id="", edited_content="e"))
    assert exc_info.value.code == "MISSING_DRAFT_ID"


def test_update_draft_not_found(editor_service):
    svc, _, _ = editor_service
    with pytest.raises(EditorError) as exc_info:
        svc.update_draft(UpdateDraftRequest(draft_id="x", edited_content="e"))
    assert exc_info.value.code == "UPDATE_FAILED"


def test_get_diff_success(editor_service):
    svc, repo, _ = editor_service
    draft_id = repo.save(original_content="orig", topic="t")
    repo.update_edited(draft_id, "edit", "note")
    result = svc.get_diff(draft_id)
    assert result.original == "orig"
    assert result.edited == "edit"


def test_get_diff_missing_id(editor_service):
    svc, _, _ = editor_service
    with pytest.raises(EditorError) as exc_info:
        svc.get_diff("")
    assert exc_info.value.code == "MISSING_DRAFT_ID"


def test_get_diff_not_found(editor_service):
    svc, _, _ = editor_service
    with pytest.raises(EditorError) as exc_info:
        svc.get_diff("nonexistent")
    assert exc_info.value.code == "DRAFT_NOT_FOUND"


def test_build_de_ai_prompt(editor_service):
    svc, _, _ = editor_service
    prompt = svc.build_de_ai_prompt("hello world")
    assert "hello world" in prompt


def test_build_de_ai_prompt_empty(editor_service):
    svc, _, _ = editor_service
    with pytest.raises(EditorError) as exc_info:
        svc.build_de_ai_prompt("")
    assert exc_info.value.code == "EMPTY_CONTENT"


def test_optimize_with_ai_success(editor_service):
    svc, _, client = editor_service
    result = svc.optimize_with_ai(DeAIOptimizeRequest(content="test"))
    assert result.success is True
    assert result.optimized == "optimized"
    assert len(client.calls) == 1


def test_optimize_with_ai_failure(editor_service):
    svc, _, client = editor_service
    client._response = (False, "", "rate limited")
    with pytest.raises(EditorError) as exc_info:
        svc.optimize_with_ai(DeAIOptimizeRequest(content="test"))
    assert exc_info.value.code == "GENERATION_FAILED"
    assert "rate limited" in str(exc_info.value)
