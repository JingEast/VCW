"""Prompt domain application handlers."""

from typing import Dict, Tuple

from .commands import PreviewPromptsCommand, SaveSystemTemplateCommand
from .queries import (
    BuildPromptsQuery,
    GetModelStatusQuery,
    GetResourcesContextQuery,
    GetTemplateContextQuery,
)


class PromptHandler:
    """Orchestrates prompt use cases."""

    def __init__(self, prompt_service):
        self._svc = prompt_service

    def handle_save_system_template(self, command: SaveSystemTemplateCommand) -> None:
        self._svc.save_system_template(command.system_prompt)

    def handle_preview(self, command: PreviewPromptsCommand) -> Dict:
        return self._svc.preview(command.data)

    def handle_get_template_context(self, query: GetTemplateContextQuery) -> Dict:
        return self._svc.get_template_context()

    def handle_get_resources_context(self, query: GetResourcesContextQuery) -> Dict:
        return self._svc.get_resources_context()

    def handle_get_model_status(self, query: GetModelStatusQuery) -> Dict:
        return self._svc.get_model_status()

    def handle_build_prompts(self, query: BuildPromptsQuery) -> Tuple[str, str, str]:
        return self._svc.build_prompts(query.data)
