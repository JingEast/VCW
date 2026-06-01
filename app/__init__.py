import os
import traceback
import uuid
from flask import Flask, jsonify, request


def create_app() -> Flask:
    """Flask Application Factory"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, "templates"),
        static_folder=os.path.join(base_dir, "static"),
        static_url_path="/static",
    )
    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key:
        import warnings
        warnings.warn(
            "SECRET_KEY environment variable is not set. "
            "Using a random key which will invalidate sessions across restarts. "
            "Please set SECRET_KEY in production.",
            RuntimeWarning,
            stacklevel=2,
        )
        secret_key = os.urandom(32).hex()
    app.config["SECRET_KEY"] = secret_key

    # 初始化应用容器（dependency-injector）
    from app.core.container import AppContainer, set_container

    container = AppContainer()
    app.container = container  # type: ignore[attr-defined]
    set_container(container)

    # 初始化日志与全局错误处理
    from app.core.logging_config import setup_logging

    setup_logging(app)
    _register_error_handlers(app)

    # ============================================================
    # 页面 Blueprints（无 url_prefix，保持原有 URL 路径）
    # ============================================================
    from app.pages import main as pages_main
    from app.pages import trends as pages_trends
    from app.pages import batch as pages_batch
    from app.pages import editor as pages_editor
    from app.pages import memory as pages_memory
    from app.pages import prompts as pages_prompts
    from app.pages import config as pages_config
    from app.pages import history as pages_history
    from app.pages import resources as pages_resources

    app.register_blueprint(pages_main.bp)
    app.register_blueprint(pages_trends.bp)
    app.register_blueprint(pages_batch.bp)
    app.register_blueprint(pages_editor.bp)
    app.register_blueprint(pages_memory.bp)
    app.register_blueprint(pages_prompts.bp)
    app.register_blueprint(pages_config.bp)
    app.register_blueprint(pages_history.bp)
    app.register_blueprint(pages_resources.bp)

    # ============================================================
    # API v1 Blueprints（统一前缀 /api/v1）
    # ============================================================
    from app.api.v1 import generate as api_generate
    from app.api.v1 import trends as api_trends
    from app.api.v1 import editor as api_editor
    from app.api.v1 import prompts as api_prompts
    from app.api.v1 import misc as api_misc

    app.register_blueprint(api_generate.bp, url_prefix="/api/v1")
    app.register_blueprint(api_trends.bp, url_prefix="/api/v1")
    app.register_blueprint(api_editor.bp, url_prefix="/api/v1")
    app.register_blueprint(api_prompts.bp, url_prefix="/api/v1")
    app.register_blueprint(api_misc.bp, url_prefix="/api/v1")

    # ============================================================
    # 健康检查端点（供 Docker / 负载均衡器使用）
    # ============================================================
    @app.route("/health")
    def health():
        from celery_app import health_check as celery_health
        celery_status = celery_health()
        return jsonify({
            "status": "ok" if celery_status["status"] == "ok" else "degraded",
            "celery": celery_status,
        }), 200 if celery_status["status"] == "ok" else 503

    # ============================================================
    # 兼容处理：裸端点名与 request.endpoint 修补
    # 确保模板中 url_for('index')、request.endpoint == 'index' 等继续有效
    # ============================================================
    _register_naked_endpoints(app)
    _patch_request_endpoint()

    return app


def _register_naked_endpoints(app: Flask) -> None:
    """
    为所有页面 Blueprint 端点注册裸名兼容。
    使模板中的 url_for('index')、url_for('trends_page') 等无需前缀即可工作。
    """
    naked_map: dict[str, str] = {}
    for rule in app.url_map.iter_rules():
        if "." not in rule.endpoint:
            continue
        bp_name, ep_name = rule.endpoint.split(".", 1)
        if not bp_name.startswith("pages_"):
            continue
        if ep_name not in naked_map:
            naked_map[ep_name] = rule.endpoint
        if ep_name not in app.view_functions:
            app.view_functions[ep_name] = app.view_functions[rule.endpoint]

    # 避免重复注册（如测试环境多次调用 create_app）
    if getattr(app, "_naked_endpoints_registered", False):  # type: ignore[attr-defined]
        return

    def naked_url_handler(error, endpoint, values):
        if endpoint in naked_map:
            from flask import url_for

            return url_for(naked_map[endpoint], **values)
        raise error

    app.url_build_error_handlers.append(naked_url_handler)
    app._naked_endpoints_registered = True  # type: ignore[attr-defined]


_request_endpoint_patched = False


def _patch_request_endpoint() -> None:
    """
    修补 request.endpoint，使 request.endpoint == 'index' 等判断在模板中正常工作。
    将 pages_main.index / api_v1_generate.stream 等转换为裸名。
    """
    global _request_endpoint_patched
    if _request_endpoint_patched:
        return

    from flask.wrappers import Request

    _original_fget = Request.endpoint.fget  # type: ignore[attr-defined]

    @property  # type: ignore[misc]
    def patched_endpoint(self):
        ep = _original_fget(self)
        if ep and "." in ep:
            bp_name = ep.split(".", 1)[0]
            if bp_name.startswith("pages_") or bp_name.startswith("api_v1_"):
                return ep.split(".", 1)[1]
        return ep

    Request.endpoint = patched_endpoint  # type: ignore[method-assign]
    _request_endpoint_patched = True


def _generate_trace_id() -> str:
    """生成 12 字符的十六进制 trace_id"""
    return uuid.uuid4().hex[:12]


def _register_error_handlers(app: Flask) -> None:
    """注册全局错误处理器，所有异常返回统一 JSON 格式并附带 trace_id"""

    @app.errorhandler(400)
    def bad_request(error):
        trace_id = _generate_trace_id()
        app.logger.warning(
            "BadRequest [%s] %s %s | %s",
            trace_id,
            request.method,
            request.url,
            getattr(error, "description", str(error)),
        )
        return jsonify({
            "success": False,
            "data": None,
            "error": {"code": "BAD_REQUEST", "message": getattr(error, "description", str(error)), "details": None},
            "trace_id": trace_id,
            "meta": {},
        }), 400

    @app.errorhandler(404)
    def not_found(error):
        trace_id = _generate_trace_id()
        app.logger.warning(
            "NotFound [%s] %s %s",
            trace_id,
            request.method,
            request.url,
        )
        return jsonify({
            "success": False,
            "data": None,
            "error": {"code": "NOT_FOUND", "message": "Not Found", "details": None},
            "trace_id": trace_id,
            "meta": {},
        }), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        trace_id = _generate_trace_id()
        app.logger.warning(
            "MethodNotAllowed [%s] %s %s",
            trace_id,
            request.method,
            request.url,
        )
        return jsonify({
            "success": False,
            "data": None,
            "error": {"code": "METHOD_NOT_ALLOWED", "message": "Method Not Allowed", "details": None},
            "trace_id": trace_id,
            "meta": {},
        }), 405

    @app.errorhandler(500)
    def internal_error(error):
        trace_id = _generate_trace_id()
        app.logger.error(
            "InternalError [%s] %s %s | %s\n%s",
            trace_id,
            request.method,
            request.url,
            str(error),
            traceback.format_exc(),
            exc_info=False,
        )
        return jsonify({
            "success": False,
            "data": None,
            "error": {"code": "INTERNAL_ERROR", "message": "Internal Server Error", "details": None},
            "trace_id": trace_id,
            "meta": {},
        }), 500

    @app.errorhandler(Exception)
    def unhandled_exception(error):
        trace_id = _generate_trace_id()
        app.logger.error(
            "UnhandledException [%s] endpoint=%s method=%s url=%s | %s\n%s",
            trace_id,
            request.endpoint,
            request.method,
            request.url,
            str(error),
            traceback.format_exc(),
            exc_info=False,
        )
        return jsonify({
            "success": False,
            "data": None,
            "error": {
                "code": "UNHANDLED_EXCEPTION",
                "message": str(error) if app.debug else "Internal Server Error",
                "details": None,
            },
            "trace_id": trace_id,
            "meta": {},
        }), 500
