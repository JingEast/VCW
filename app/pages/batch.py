"""
批量文案生成路由（页面 Blueprint）
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.core.container import get_service
from domains.generation.application import GenerateBatchCommand
from services.generation_service import GenerationError

bp = Blueprint("pages_batch", __name__)


@bp.route("/batch")
def batch_page():
    """批量生成页面"""
    return render_template("batch.html", results=None, topic="")


@bp.route("/batch/generate", methods=["POST"])
def batch_generate():
    """执行批量生成"""
    handler = get_service("generation_handler")
    req_data = {k: v for k, v in request.form.items()}
    topic = req_data.get("topic", "").strip()
    angles = request.form.getlist("angles")

    if not topic:
        flash("主题不能为空", "error")
        return redirect(url_for("batch_page"))

    if not angles:
        angles = ["焦虑型", "数据型", "故事型"]

    try:
        results = handler.handle_generate_batch(
            GenerateBatchCommand(req_data=req_data, angles=angles)
        )
        return render_template(
            "batch.html",
            results=results,
            topic=topic,
            prefill_topic=topic,
            prefill_core_data=req_data.get("core_data", ""),
            prefill_policy_points=req_data.get("policy_points", ""),
            prefill_hidden_path=req_data.get("hidden_path", ""),
            prefill_call_to_action=req_data.get("call_to_action", ""),
        )
    except GenerationError as e:
        flash(e.message, "error")
        if e.code == "API_KEY_MISSING":
            return redirect(url_for("config_page"))
        return redirect(url_for("batch_page"))
    except Exception as e:
        flash(f"批量生成失败: {str(e)}", "error")
        return redirect(url_for("batch_page"))
