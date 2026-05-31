"""
文案生成 API（API v1 Blueprint）
"""
from flask import Blueprint, request, Response, stream_with_context

from app.core.container import get_service
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


@bp.route("/generate/stream")
def generate_stream():
    """SSE 流式生成文案（EventSource 只支持 GET）"""
    req_data = request.args.to_dict()
    topic = req_data.get("topic", "").strip()

    if not topic:
        def error_stream():
            yield "data: [错误] 主题不能为空\n\n"
        return Response(error_stream(), mimetype="text/event-stream")

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
def generate_async():
    """创建异步生成任务"""
    handler = get_service("generation_handler")
    req_data = request.get_json() or request.form.to_dict()

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
def generate_batch_async():
    """创建异步批量生成任务"""
    handler = get_service("generation_handler")
    payload = request.get_json() or request.form.to_dict()
    req_data = payload.get("req_data") or payload
    angles = payload.get("angles", [])

    # 支持 angles 从 form 或 JSON 传递
    if isinstance(angles, str):
        angles = [a.strip() for a in angles.split(",") if a.strip()]

    if not angles and "angles" in request.form:
        angles = request.form.getlist("angles")

    try:
        batch_id = handler.handle_submit_async_batch(
            SubmitAsyncBatchCommand(req_data=req_data, angles=angles)
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
