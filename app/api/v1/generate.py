"""
文案生成 API（API v1 Blueprint）
"""
from flask import Blueprint, request, Response, stream_with_context

from app.core.container import get_service
from app.core.limiter import limiter
from app.api.v1.common import success_response, error_response
from domains.generation.application import (
    CancelAsyncBatchCommand,
    CancelAsyncCommand,
    GenerateStreamQuery,
    GetAsyncBatchStatusQuery,
    GetAsyncStatusQuery,
    SubmitAsyncBatchCommand,
    SubmitAsyncCommand,
)
from services.generation_service import GenerationError

bp = Blueprint("api_v1_generate", __name__)


# 输入长度限制常量
_MAX_TOPIC_LENGTH = 500
_MAX_AUDIENCE_LENGTH = 200
_MAX_STYLE_LENGTH = 100
_MAX_ANGLES_COUNT = 10
_MAX_ANGLE_LENGTH = 100


def _sanitize_topic(topic: str) -> str:
    """清理主题输入，限制长度并过滤控制字符。"""
    topic = topic.strip()
    if len(topic) > _MAX_TOPIC_LENGTH:
        topic = topic[:_MAX_TOPIC_LENGTH]
    # 过滤不可见控制字符（保留换行和制表符）
    topic = "".join(ch for ch in topic if ch == "\n" or ch == "\t" or ord(ch) >= 32)
    return topic


def _validate_generate_payload(data: dict) -> tuple[str | None, dict]:
    """校验生成请求的 payload，返回 (error_message, sanitized_data)。"""
    topic = _sanitize_topic(data.get("topic", ""))
    if not topic:
        return "主题不能为空", {}
    audience = data.get("audience", "").strip()
    if len(audience) > _MAX_AUDIENCE_LENGTH:
        audience = audience[:_MAX_AUDIENCE_LENGTH]
    style = data.get("style", "").strip()
    if len(style) > _MAX_STYLE_LENGTH:
        style = style[:_MAX_STYLE_LENGTH]
    return None, {"topic": topic, "audience": audience, "style": style}


@bp.route("/generate/stream")
@limiter.limit("20 per minute")
def generate_stream():
    """SSE 流式生成文案（EventSource 只支持 GET）"""
    req_data = request.args.to_dict()
    topic = _sanitize_topic(req_data.get("topic", ""))

    if not topic:
        def error_stream():
            yield "data: [错误] 主题不能为空\n\n"
        return Response(error_stream(), mimetype="text/event-stream")
    req_data["topic"] = topic

    handler = get_service("generation_handler")

    def event_stream():
        try:
            for event_type, payload in handler.handle_generate_stream(
                GenerateStreamQuery(req_data=req_data)
            ):
                if event_type == "meta":
                    yield f"event: meta\ndata: {payload}\n\n"
                elif event_type == "done":
                    yield f"event: done\ndata: {payload}\n\n"
                elif event_type == "error":
                    yield f"event: error\ndata: {payload}\n\n"
                    return
                else:  # content
                    safe_text = payload.replace("\n", "\\n").replace("\r", "")
                    yield f"event: content\ndata: {safe_text}\n\n"
        except Exception as e:
            yield f"event: error\ndata: [错误] {str(e)}\n\n"

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@bp.route("/generate/async", methods=["POST"])
@limiter.limit("10 per minute")
def generate_async():
    """创建异步生成任务"""
    handler = get_service("generation_handler")
    raw_data = request.get_json() or request.form.to_dict()
    err, req_data = _validate_generate_payload(raw_data)
    if err:
        return error_response("VALIDATION_ERROR", err, status_code=400)

    try:
        task_id = handler.handle_submit_async(SubmitAsyncCommand(req_data=req_data))
        return success_response({"task_id": task_id})
    except GenerationError as e:
        return error_response(e.code or "GENERATION_ERROR", e.message)
    except Exception as e:
        return error_response("INTERNAL_ERROR", str(e))


@bp.route("/generate/status/<task_id>")
def generate_status(task_id):
    """查询异步任务状态"""
    handler = get_service("generation_handler")
    try:
        status = handler.handle_get_async_status(GetAsyncStatusQuery(task_id=task_id))
        return success_response({"task": status})
    except GenerationError as e:
        return error_response(e.code or "TASK_NOT_FOUND", e.message, status_code=404)
    except Exception as e:
        return error_response("INTERNAL_ERROR", str(e))


@bp.route("/generate/cancel/<task_id>", methods=["POST"])
def generate_cancel(task_id):
    """取消异步任务"""
    handler = get_service("generation_handler")
    try:
        ok = handler.handle_cancel_async(CancelAsyncCommand(task_id=task_id))
        return success_response({"cancelled": ok})
    except Exception as e:
        return error_response("INTERNAL_ERROR", str(e))


# ------------------------------------------------------------------------------
# 批量异步任务
# ------------------------------------------------------------------------------

@bp.route("/generate/batch/async", methods=["POST"])
@limiter.limit("5 per minute")
def generate_batch_async():
    """创建异步批量生成任务"""
    handler = get_service("generation_handler")
    payload = request.get_json() or request.form.to_dict()
    req_data = payload.get("req_data") or payload

    err, sanitized = _validate_generate_payload(req_data)
    if err:
        return error_response("VALIDATION_ERROR", err, status_code=400)

    angles = payload.get("angles", [])
    # 支持 angles 从 form 或 JSON 传递
    if isinstance(angles, str):
        angles = [a.strip() for a in angles.split(",") if a.strip()]
    if not angles and "angles" in request.form:
        angles = request.form.getlist("angles")
    # 校验 angles 数量和长度
    if len(angles) > _MAX_ANGLES_COUNT:
        return error_response(
            "VALIDATION_ERROR",
            f"Angles count exceeds limit {_MAX_ANGLES_COUNT}",
            status_code=400,
        )
    for angle in angles:
        if len(angle) > _MAX_ANGLE_LENGTH:
            return error_response(
                "VALIDATION_ERROR",
                f"Angle length exceeds limit {_MAX_ANGLE_LENGTH}",
                status_code=400,
            )

    try:
        batch_id = handler.handle_submit_async_batch(
            SubmitAsyncBatchCommand(req_data=sanitized, angles=angles)
        )
        return success_response({"batch_id": batch_id})
    except GenerationError as e:
        return error_response(e.code or "GENERATION_ERROR", e.message)
    except Exception as e:
        return error_response("INTERNAL_ERROR", str(e))


@bp.route("/generate/batch/status/<batch_id>")
def generate_batch_status(batch_id):
    """查询异步批量任务状态"""
    handler = get_service("generation_handler")
    try:
        status = handler.handle_get_async_batch_status(
            GetAsyncBatchStatusQuery(batch_id=batch_id)
        )
        return success_response({"batch": status})
    except GenerationError as e:
        return error_response(e.code or "BATCH_NOT_FOUND", e.message, status_code=404)
    except Exception as e:
        return error_response("INTERNAL_ERROR", str(e))


@bp.route("/generate/batch/cancel/<batch_id>", methods=["POST"])
def generate_batch_cancel(batch_id):
    """取消异步批量任务"""
    handler = get_service("generation_handler")
    try:
        ok = handler.handle_cancel_async_batch(CancelAsyncBatchCommand(batch_id=batch_id))
        return success_response({"cancelled": ok})
    except GenerationError as e:
        return error_response(e.code or "BATCH_NOT_FOUND", e.message, status_code=404)
    except Exception as e:
        return error_response("INTERNAL_ERROR", str(e))
