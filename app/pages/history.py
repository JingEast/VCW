"""
生成历史路由（页面 Blueprint）
"""
from flask import Blueprint, render_template

from app.core.container import get_service

bp = Blueprint("pages_history", __name__)


@bp.route("/history")
def history_page():
    """查看生成历史"""
    handler = get_service("generation_handler")
    files = handler.handle_list_recent_files(limit=9999)
    return render_template("history.html", files=files)
