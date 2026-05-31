import uuid
from flask import jsonify
from typing import Any, Optional


def _generate_trace_id() -> str:
    return uuid.uuid4().hex[:12]


def success_response(data: Any = None, meta: Optional[dict] = None):
    """统一成功响应格式"""
    return jsonify(
        {
            "success": True,
            "data": data,
            "error": None,
            "trace_id": None,
            "meta": meta or {},
        }
    )


def error_response(
    code: str,
    message: str,
    details: Optional[dict] = None,
    status_code: int = 400,
):
    """统一错误响应格式（带 trace_id）"""
    trace_id = _generate_trace_id()
    resp = jsonify(
        {
            "success": False,
            "data": None,
            "error": {"code": code, "message": message, "details": details},
            "trace_id": trace_id,
            "meta": {},
        }
    )
    resp.status_code = status_code
    return resp
