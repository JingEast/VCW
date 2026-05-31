"""Prompt domain repository implementations (Adapter)."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict

from domains.prompt.domain.repository import (
    IKnowledgeRepository,
    IPromptTemplateRepository,
)


class PromptTemplateRepository(IPromptTemplateRepository):
    """Prompt 模板 JSON 文件持久化。"""

    def __init__(self, custom_path: str = "data/prompts_custom.json"):
        self._path = Path(custom_path)

    def save(self, system_prompt: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "saved_at": datetime.now().isoformat(),
                    "system_prompt": system_prompt,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

    def load(self) -> str:
        if not self._path.exists():
            return ""
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("system_prompt", "")
        except (OSError, json.JSONDecodeError):
            return ""


class KnowledgeRepository(IKnowledgeRepository):
    """知识库适配器。"""

    def get_resources(self) -> Dict:
        import vcw_copywriter.knowledge_base as kb

        return {
            "hk_student_sites": kb.HONG_KONG_STUDENT_WEBSITES,
            "transfer_sites": kb.SCHOOL_TRANSFER_WEBSITES,
            "dse_sites": kb.DSE_WEBSITES,
            "hk_student_keywords": kb.HONG_KONG_STUDENT_KEYWORDS,
            "transfer_keywords": kb.SCHOOL_TRANSFER_KEYWORDS,
            "dse_keywords": kb.DSE_KEYWORDS,
            "hk_student_workflow": kb.HONG_KONG_STUDENT_WORKFLOW,
            "transfer_workflow": kb.SCHOOL_TRANSFER_WORKFLOW,
            "dse_workflow": kb.DSE_WORKFLOW,
        }

    def format_for_prompt(self, scope: str) -> str:
        import vcw_copywriter.knowledge_base as kb

        return kb.format_for_prompt(scope)
