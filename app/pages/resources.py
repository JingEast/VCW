"""
业务资源库路由（页面 Blueprint）
"""
from flask import Blueprint, render_template

from app.core.container import get_service

bp = Blueprint("pages_resources", __name__)


@bp.route("/resources")
def resources_page():
    """业务资源库页面"""
    prompt_service = get_service("prompt_service")
    ctx = prompt_service.get_resources_context()
    return render_template("resources.html", **ctx)
