"""
记忆库管理路由（页面 Blueprint）
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.core.container import get_service

bp = Blueprint("pages_memory", __name__)


@bp.route("/memory")
def memory_page():
    """记忆库管理页面"""
    memory_bank = get_service("memory_bank")
    entries = memory_bank.get_recent_entries(limit=100)
    report = memory_bank.generate_report()
    return render_template("memory.html", entries=entries, report=report)


@bp.route("/memory/add", methods=["POST"])
def memory_add():
    """添加记忆条目"""
    memory_bank = get_service("memory_bank")
    topic = request.form.get("topic", "").strip()
    issue_description = request.form.get("issue_description", "").strip()
    issue_tags = request.form.get("issue_tags", "").strip().split()
    correction_plan = request.form.get("correction_plan", "").strip()
    original_text = request.form.get("original_text", "").strip()

    if not topic or not issue_description:
        flash("主题和问题描述不能为空", "error")
        return redirect(url_for("memory_page"))

    if not issue_tags:
        issue_tags = ["其他"]

    entry_id = memory_bank.add_entry(
        topic=topic,
        issue_description=issue_description,
        issue_tags=issue_tags,
        correction_plan=correction_plan,
        original_text=original_text,
    )
    flash(f"记忆条目已添加 (ID: {entry_id})", "success")
    return redirect(url_for("memory_page"))


@bp.route("/memory/mark/<entry_id>", methods=["POST"])
def memory_mark(entry_id):
    """标记记忆条目为已规避"""
    memory_bank = get_service("memory_bank")
    memory_bank.mark_avoided(entry_id)
    flash(f"条目 {entry_id} 已标记为已规避", "success")
    return redirect(url_for("memory_page"))


@bp.route("/memory/delete/<entry_id>", methods=["POST"])
def memory_delete(entry_id):
    """删除记忆条目"""
    memory_bank = get_service("memory_bank")
    try:
        ok = memory_bank.delete_entry(entry_id)
        if ok:
            flash(f"条目 {entry_id} 已删除", "success")
        else:
            flash(f"条目 {entry_id} 不存在", "warning")
    except Exception as e:
        flash(f"删除失败: {str(e)}", "error")
    return redirect(url_for("memory_page"))
