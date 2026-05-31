"""
编辑器 API（API v1 Blueprint）
"""
from flask import Blueprint, request

from app.core.container import get_service
from app.api.v1.common import success_response, error_response
from domains.editor.application import DeAIOptimizeCommand
from services.editor_service import EditorError

bp = Blueprint("api_v1_editor", __name__)


@bp.route("/editor/de-ai", methods=["POST"])
def api_de_ai():
    """API：一键去 AI 味优化"""
    handler = get_service("editor_handler")
    data = request.json or {}
    content = data.get("content", "")

    try:
        result = handler.handle_de_ai_optimize(DeAIOptimizeCommand(content=content))
        return success_response({"optimized": result.optimized})
    except EditorError as e:
        if e.code == "API_KEY_MISSING":
            return error_response(e.code, e.message)
        return error_response(e.code or "DE_AI_ERROR", e.message)
    except Exception as e:
        return error_response("DE_AI_ERROR", str(e))
