"""
热点 API（API v1 Blueprint）
"""
from flask import Blueprint, request

from app.core.container import get_service
from app.api.v1.common import success_response, error_response
from domains.trend.application import (
    DisableSchedulerCommand,
    EnableSchedulerCommand,
    GetFreshHotspotsQuery,
    GetSchedulerStatusQuery,
    TriggerSchedulerCommand,
)
from services.scheduler_service import SchedulerError

bp = Blueprint("api_v1_trends", __name__)


@bp.route("/trends/fresh")
def api_trends_fresh():
    """API：获取最新热点（用于首页展示）"""
    handler = get_service("trend_handler")
    fresh = handler.handle_get_fresh_hotspots(GetFreshHotspotsQuery(limit=5))
    return success_response({
        "count": len(fresh),
        "trends": fresh,
    })


@bp.route("/trends/scheduler/status")
def scheduler_status():
    """获取定时爬取调度器状态"""
    handler = get_service("trend_handler")
    return success_response(
        {"status": handler.handle_get_scheduler_status(GetSchedulerStatusQuery())}
    )


@bp.route("/trends/scheduler/toggle", methods=["POST"])
def scheduler_toggle():
    """启用/禁用定时爬取"""
    handler = get_service("trend_handler")
    data = request.get_json() or {}
    enabled = data.get("enabled", False)
    interval = data.get("interval_minutes", 60)

    try:
        if enabled:
            handler.handle_enable_scheduler(
                EnableSchedulerCommand(interval_minutes=interval)
            )
        else:
            handler.handle_disable_scheduler(DisableSchedulerCommand())
        return success_response({"enabled": enabled})
    except SchedulerError as e:
        return error_response(e.code or "SCHEDULER_TOGGLE_FAILED", e.message)
    except Exception as e:
        return error_response("SCHEDULER_TOGGLE_FAILED", str(e))


@bp.route("/trends/scheduler/trigger", methods=["POST"])
def scheduler_trigger():
    """立即手动触发爬取"""
    handler = get_service("trend_handler")
    try:
        result = handler.handle_trigger_scheduler(TriggerSchedulerCommand())
        return success_response({"result": result})
    except SchedulerError as e:
        return error_response(e.code or "TRIGGER_FAILED", e.message)
    except Exception as e:
        return error_response("TRIGGER_FAILED", str(e))
