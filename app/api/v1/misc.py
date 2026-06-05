"""
API 杂项路由（API v1 Blueprint）
存放零散的小型 API 端点。
"""
from flask import Blueprint, request

import os

from app.core.container import get_service
from app.core.flask_cache import cache
from app.core.limiter import limiter
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
@limiter.limit("60 per minute")
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


# 允许预览的文件扩展名白名单
_SAFE_PREVIEW_EXTENSIONS = {".txt", ".md", ".json", ".yaml", ".yml", ".html", ".css", ".js"}
# 允许预览的根目录（相对项目根目录）
_SAFE_PREVIEW_DIRS = {"data", "templates", "static", "docs"}


@bp.route("/files/preview/<path:filename>")
@limiter.limit("30 per minute")
def preview_file(filename):
    """API：预览文件内容（受路径遍历保护）。"""
    # 1. 禁止绝对路径（同时支持 Unix / 和 Windows C:\ 格式）
    if os.path.isabs(filename) or __import__("re").match(r"^[A-Za-z]:[\\/]", filename):
        return error_response("INVALID_PATH", "Absolute paths are not allowed", status_code=400)
    # 2. 禁止路径遍历符号
    if ".." in filename or "~" in filename:
        return error_response("INVALID_PATH", "Path traversal is not allowed", status_code=400)
    # 3. 扩展名白名单
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _SAFE_PREVIEW_EXTENSIONS:
        return error_response("INVALID_FILE_TYPE", f"File type '{ext}' not allowed", status_code=400)
    # 4. 只允许特定根目录
    top_dir = filename.split("/")[0]
    if top_dir not in _SAFE_PREVIEW_DIRS:
        return error_response("INVALID_PATH", f"Directory '{top_dir}' not allowed", status_code=400)
    # 5. 解析为绝对路径并校验
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    target_path = os.path.abspath(os.path.join(base_dir, filename))
    allowed_roots = [os.path.abspath(os.path.join(base_dir, d)) for d in _SAFE_PREVIEW_DIRS]
    if not any(target_path.startswith(r + os.sep) for r in allowed_roots):
        return error_response("INVALID_PATH", "File outside allowed directories", status_code=400)
    # 6. 读取文件
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()
        # 限制返回内容大小（防止大文件导致内存问题）
        max_size = 1024 * 1024  # 1MB
        if len(content) > max_size:
            content = content[:max_size] + "\n[Truncated: file exceeds 1MB limit]"
        return success_response({"content": content})
    except FileNotFoundError:
        return error_response("FILE_NOT_FOUND", "File not found", status_code=404)
    except Exception as e:
        return error_response("FILE_READ_ERROR", str(e))
