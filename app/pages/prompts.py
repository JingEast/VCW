"""
Prompt 可视化编辑路由（页面 Blueprint）
"""
from flask import Blueprint, render_template

from app.core.container import get_service

bp = Blueprint("pages_prompts", __name__)


@bp.route("/prompts")
def prompts_page():
    """Prompt 模板编辑页面"""
    prompt_service = get_service("prompt_service")
    ctx = prompt_service.get_template_context()
    return render_template("prompts.html", **ctx)
