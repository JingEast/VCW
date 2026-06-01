"""
首页与文案生成路由（页面 Blueprint）
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.core.container import get_service
from domains.generation.application import GenerateCopyCommand
from services.generation_service import GenerationError

bp = Blueprint("pages_main", __name__)


@bp.route("/")
def index():
    """首页 - 文案生成表单"""
    memory_bank = get_service("memory_bank")
    handler = get_service("generation_handler")

    recent_files = handler.handle_list_recent_files(limit=5)

    entry_count = memory_bank.get_entry_count()
    pending_count = memory_bank.get_pending_count()

    # 检查是否有从热点页面带过来的预填充参数
    prefill = {
        "topic": request.args.get("topic", ""),
        "core_data": request.args.get("core_data", ""),
        "policy_points": request.args.get("policy_points", ""),
        "hidden_path": request.args.get("hidden_path", ""),
        "call_to_action": request.args.get("call_to_action", ""),
        "scene": request.args.get("scene", ""),
    }

    # 数据看板统计
    stats = handler.handle_get_dashboard_stats()

    return render_template(
        "index.html",
        recent_files=recent_files,
        entry_count=entry_count,
        pending_count=pending_count,
        prefill=prefill,
        stats=stats,
    )


@bp.route("/generate", methods=["POST"])
def generate():
    """执行文案生成"""
    handler = get_service("generation_handler")
    try:
        result = handler.handle_generate_copy(
            GenerateCopyCommand(req_data=request.form.to_dict())
        )
        return render_template("result.html", **result)
    except GenerationError as e:
        flash(e.message, "error")
        if e.code == "API_KEY_MISSING":
            return redirect(url_for("config_page"))
        return redirect(url_for("index"))
    except ImportError as e:
        flash(f"依赖缺失: {e}", "error")
        return redirect(url_for("index"))
    except Exception as e:
        flash(f"发生错误: {str(e)}", "error")
        return redirect(url_for("index"))
