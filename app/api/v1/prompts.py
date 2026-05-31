"""
Prompt API（API v1 Blueprint）
"""
from flask import Blueprint, request

from app.core.container import get_service
from app.api.v1.common import success_response, error_response
from domains.prompt.application import PreviewPromptsCommand, SaveSystemTemplateCommand

bp = Blueprint("api_v1_prompts", __name__)


@bp.route("/prompts", methods=["POST"])
def prompts_save():
    """保存 Prompt 模板（保存到 data/prompts_custom.json）"""
    data = request.get_json() or {}
    system_prompt = data.get("system_prompt", "").strip()

    if not system_prompt:
        return error_response("EMPTY_PROMPT", "System Prompt 不能为空")

    try:
        handler = get_service("prompt_handler")
        handler.handle_save_system_template(
            SaveSystemTemplateCommand(system_prompt=system_prompt)
        )
        return success_response()
    except Exception as e:
        return error_response("SAVE_FAILED", str(e))


@bp.route("/prompts/preview", methods=["POST"])
def prompts_preview():
    """预览 Prompt 渲染效果"""
    data = request.get_json() or {}

    try:
        handler = get_service("prompt_handler")
        result = handler.handle_preview(PreviewPromptsCommand(data=data))
        return success_response(result)
    except Exception as e:
        return error_response("PREVIEW_FAILED", str(e))
