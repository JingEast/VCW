"""
API 杂项路由（API v1 Blueprint）
存放零散的小型 API 端点。
"""
from flask import Blueprint, request

from app.core.container import get_service
from app.core.flask_cache import cache
from app.api.v1.common import success_response, error_response
from domains.editor.application import SaveDraftCommand
from domains.prompt.application import BuildPromptsQuery, GetModelStatusQuery

bp = Blueprint("api_v1_misc", __name__)


@bp.route("/generate/save-stream", methods=["POST"])
def save_stream():
    """保存流式生成的文案到精修库"""
    handler = get_service("editor_handler")
    data = request.get_json() or {}
    content = data.get("content", "").strip()
    topic = data.get("topic", "未命名文案").strip()
    meta = data.get("meta", "").strip()

    if not content:
        return error_response("EMPTY_CONTENT", "内容不能为空")

    try:
        draft_id = handler.handle_save_draft(
            SaveDraftCommand(
                original_content=content,
                topic=topic,
                source_filepath="",
                meta=meta,
            )
        )
        return success_response({"draft_id": draft_id})
    except Exception as e:
        return error_response("SAVE_FAILED", str(e))


@bp.route("/model/status")
@cache.cached(timeout=30, key_prefix="api_model_status")
def model_status():
    """查询模型端点健康状态"""
    try:
        handler = get_service("prompt_handler")
        result = handler.handle_get_model_status(GetModelStatusQuery())
        return success_response(result)
    except Exception as e:
        return error_response("STATUS_FAILED", str(e))


@bp.route("/prompts/check", methods=["POST"])
def check_prompt():
    """API：预览将要发送的提示词（用于调试）"""
    data = request.json or {}
    handler = get_service("prompt_handler")
    topic, system_prompt, user_prompt = handler.handle_build_prompts(
        BuildPromptsQuery(data=data)
    )

    return success_response({
        "system_prompt_length": len(system_prompt),
        "user_prompt_length": len(user_prompt),
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
    })


@bp.route("/files/preview/<path:filename>")
def preview_file(filename):
    """API：预览文件内容"""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            content = f.read()
        return success_response({"content": content})
    except Exception as e:
        return error_response("FILE_READ_ERROR", str(e))
