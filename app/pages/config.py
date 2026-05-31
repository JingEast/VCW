"""
配置管理路由（页面 Blueprint）
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.core.container import get_service

bp = Blueprint("pages_config", __name__)


@bp.route("/config")
def config_page():
    """配置页面"""
    config = get_service("config")
    cfg = config.data
    return render_template("config.html", config=cfg)


@bp.route("/config/save", methods=["POST"])
def config_save():
    """保存配置（支持多模型 Endpoint）"""
    config = get_service("config")
    config.set("llm", "api_key", value=request.form.get("api_key", "").strip())
    config.set("llm", "model", value=request.form.get("model", "gpt-4o").strip())
    config.set(
        "llm",
        "base_url",
        value=request.form.get("base_url", "https://api.openai.com/v1").strip(),
    )

    try:
        temperature = float(request.form.get("temperature", 0.7))
    except (ValueError, TypeError):
        flash("Temperature 必须为有效数字", "error")
        return redirect(url_for("config_page"))
    config.set("llm", "temperature", value=temperature)

    try:
        max_tokens = int(request.form.get("max_tokens", 2000))
    except (ValueError, TypeError):
        flash("Max Tokens 必须为有效整数", "error")
        return redirect(url_for("config_page"))
    config.set("llm", "max_tokens", value=max_tokens)

    config.set(
        "quality_check",
        "strict_mode",
        value=request.form.get("strict_mode") == "on",
    )

    ep_names = request.form.getlist("ep_name[]")
    ep_keys = request.form.getlist("ep_key[]")
    ep_urls = request.form.getlist("ep_url[]")
    ep_models = request.form.getlist("ep_model[]")
    ep_priorities = request.form.getlist("ep_priority[]")

    endpoints = []
    for i in range(len(ep_names)):
        if ep_names[i].strip():
            try:
                priority = int(ep_priorities[i]) if i < len(ep_priorities) and ep_priorities[i] else 0
            except (ValueError, TypeError):
                priority = 0
            endpoints.append({
                "name": ep_names[i].strip(),
                "api_key": ep_keys[i].strip() if i < len(ep_keys) else "",
                "base_url": ep_urls[i].strip() if i < len(ep_urls) else "",
                "model": ep_models[i].strip() if i < len(ep_models) else "",
                "priority": priority,
            })

    if endpoints:
        config.data["llm"]["endpoints"] = endpoints
    elif "endpoints" in config.data.get("llm", {}):
        del config.data["llm"]["endpoints"]

    config.save()
    flash("配置已保存", "success")
    return redirect(url_for("config_page"))
