"""
精修编辑器路由（页面 Blueprint）
"""
import urllib.parse
from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.core.container import get_service
from domains.editor.application import UpdateDraftCommand
from services.editor_service import EditorError

bp = Blueprint("pages_editor", __name__)


@bp.route("/editor")
def editor_page():
    """精修编辑器"""
    handler = get_service("editor_handler")

    content = request.args.get("content", "")
    topic = request.args.get("topic", "未命名文案")
    angle = request.args.get("angle", "")
    draft_id = request.args.get("draft_id", "")

    try:
        content = urllib.parse.unquote(content)
        topic = urllib.parse.unquote(topic)
        angle = urllib.parse.unquote(angle)
    except (UnicodeDecodeError, ValueError):
        pass

    try:
        draft = handler.handle_load_or_create_draft(content, topic, angle, draft_id)
        return render_template(
            "editor.html",
            content=draft.edited if draft.edited else draft.original,
            original=draft.original,
            topic=draft.topic,
            draft_id=draft.draft_id,
        )
    except EditorError as e:
        flash(e.message, "error")
        return redirect(url_for("index"))


@bp.route("/editor/save", methods=["POST"])
def editor_save():
    """保存精修版"""
    handler = get_service("editor_handler")

    try:
        result = handler.handle_update_draft(
            UpdateDraftCommand(
                draft_id=request.form.get("draft_id", "").strip(),
                edited_content=request.form.get("content", "").strip(),
                edit_note=request.form.get("edit_note", "").strip(),
                finalize=request.form.get("finalize", "") == "true",
            )
        )

        if result.finalize:
            flash("已标记为最终版本", "success")
        else:
            flash("精修版已保存", "success")

        return redirect(url_for("editor_page", draft_id=result.draft_id))
    except EditorError as e:
        flash(e.message, "error")
        if e.code == "MISSING_DRAFT_ID":
            return redirect(url_for("batch_page"))
        draft_id = request.form.get("draft_id", "").strip()
        return redirect(url_for("editor_page", draft_id=draft_id))
