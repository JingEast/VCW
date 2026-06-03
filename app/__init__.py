import logging
import os
import time
import traceback
import uuid
from flask import Flask, has_request_context, jsonify, request

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Flask Application Factory"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 加载并校验应用配置（必须在 Flask app 创建前执行）
    from app.core.config_schema import load_settings, validate_startup_config

    settings = load_settings()
    startup_warnings = validate_startup_config()
    for warning in startup_warnings:
        logger.warning("[STARTUP_CONFIG] %s", warning)
    logger.info(
        "[STARTUP_CONFIG] Configuration loaded: %s",
        settings.to_safe_dict(),
    )

    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, "templates"),
        static_folder=os.path.join(base_dir, "static"),
        static_url_path="/static",
    )
    app.config["SECRET_KEY"] = settings.secret_key or os.urandom(32).hex()
    app.config["SQLALCHEMY_DATABASE_URI"] = settings.database_url
    app.config["CORS_ORIGINS"] = settings.cors_origins

    # 初始化应用容器（dependency-injector）
    from app.core.container import AppContainer, set_container

    container = AppContainer()
    app.container = container  # type: ignore[attr-defined]
    set_container(container)

    # 初始化限流器（需在路由注册前初始化）
    from app.core.limiter import limiter

    limiter.init_app(app)
    # 测试环境禁用限流（避免测试请求被拦截）
    if app.config.get("TESTING"):
        limiter.enabled = False

    # 初始化日志与全局错误处理
    from app.core.logging_config import setup_logging

    setup_logging(app)
    _register_error_handlers(app)
    _register_trace_middleware(app)
    _register_metrics_middleware(app)
    _register_profiler(app)

    # 初始化 Flask-Caching
    _init_cache(app)

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
    # Auth Blueprints (register before auth init so routes exist)
    # ============================================================
    from app.pages.auth import bp as pages_auth_bp
    from app.api.v1.auth import bp as api_auth_bp

    app.register_blueprint(pages_auth_bp)
    app.register_blueprint(api_auth_bp, url_prefix="/api/v1")

    # ============================================================
    # JWT Authentication
    # ============================================================
    try:
        from app.auth.jwt_handler import init_jwt
        init_jwt(app)
    except ImportError as exc:
        app.logger.warning("JWT authentication disabled: %s", exc)

    # ============================================================
    # Session Authentication
    # ============================================================
    try:
        from app.auth.session_handler import init_login_manager
        from app.auth.session_manager import init_session_manager
        init_login_manager(app)
        init_session_manager(app)
    except ImportError as exc:
        app.logger.warning("Session authentication disabled: %s", exc)

    # ============================================================
    # API Auth Middleware
    # ============================================================
    try:
        from app.middleware.auth_middleware import register_auth_middleware
        register_auth_middleware(app)
    except ImportError as exc:
        app.logger.warning("API auth middleware disabled: %s", exc)

    # ============================================================
    # CSRF Protection
    # ============================================================
    # 测试环境禁用 CSRF（避免测试 POST 请求被拦截）
    if app.config.get("TESTING"):
        app.config["WTF_CSRF_ENABLED"] = False

    try:
        from flask_wtf.csrf import CSRFProtect
        csrf = CSRFProtect()
        csrf.init_app(app)
        # Exempt API endpoints (JWT or session authenticated)
        csrf.exempt(api_generate.bp)
        csrf.exempt(api_trends.bp)
        csrf.exempt(api_editor.bp)
        csrf.exempt(api_prompts.bp)
        csrf.exempt(api_misc.bp)
        csrf.exempt(api_auth_bp)
    except ImportError:
        app.logger.warning("flask-wtf not installed, CSRF protection disabled")

    # ============================================================
    # 健康检查端点（供 Docker / 负载均衡器使用）
    # ============================================================
    @app.route("/health")
    @limiter.limit("60 per minute")
    def health():
        from celery_app import health_check as celery_health
        celery_status = celery_health()
        return jsonify({
            "status": "ok" if celery_status["status"] == "ok" else "degraded",
            "celery": celery_status,
        }), 200 if celery_status["status"] == "ok" else 503

    # ============================================================
    # Prometheus 指标端点
    # ============================================================
    @app.route("/metrics")
    @limiter.limit("30 per minute")
    def metrics_endpoint():
        collector = getattr(app, "metrics", None)
        if collector is None:
            return "# no metrics collector\n", 200, {"Content-Type": "text/plain; version=0.0.4; charset=utf-8"}
        # Error correlation: 在 Prometheus 注释中声明 trace_id 关联方式
        prom_output = collector.to_prometheus()
        header = (
            "# Error Correlation: each error log line contains "
            "[error_code=<code> trace_id=<id>] for cross-reference\n"
            "# Dead letter tasks include trace_id in GenerationJob.result\n"
        )

        # DB connection pool metrics
        from vcw_copywriter.db.session import engine
        pool = engine.pool
        pool_size = getattr(pool, "size", lambda: 0)()
        pool_checked_in = getattr(pool, "checked_in", lambda: 0)()
        pool_checked_out = getattr(pool, "checked_out", lambda: 0)()
        pool_overflow = getattr(pool, "overflow", lambda: 0)()
        pool_metrics = (
            f"\n# DB connection pool\n"
            f"db_pool_size {pool_size}\n"
            f"db_pool_checked_in {pool_checked_in}\n"
            f"db_pool_checked_out {pool_checked_out}\n"
            f"db_pool_overflow {pool_overflow}\n"
        )

        return (
            header + prom_output + pool_metrics,
            200,
            {"Content-Type": "text/plain; version=0.0.4; charset=utf-8"},
        )

    # ============================================================
    # Profiling 端点
    # ============================================================
    @app.route("/debug/profile")
    def debug_profile():
        if not app.debug:
            return jsonify({"error": "profiling disabled"}), 403
        profiler = getattr(app, "profiler", None)
        if profiler is None:
            return jsonify({"error": "profiler not initialized"}), 500
        snapshot = profiler.snapshot()
        # 支持通过 query 参数动态过滤慢查询阈值
        try:
            threshold_ms = float(request.args.get("threshold_ms", profiler.slow_threshold_ms))
        except (ValueError, TypeError):
            threshold_ms = profiler.slow_threshold_ms
        if threshold_ms != profiler.slow_threshold_ms:
            snapshot["slow_queries"] = [
                {
                    "name": r.name,
                    "duration_ms": round(r.duration_ms, 2),
                    "meta": r.meta,
                }
                for r in profiler.slow_queries(threshold_ms)
            ]
            snapshot["slow_threshold_ms"] = round(threshold_ms, 2)
            snapshot["slow_count"] = len(snapshot["slow_queries"])
        return jsonify(snapshot)

    @app.route("/debug/profile/clear", methods=["POST"])
    def debug_profile_clear():
        if not app.debug:
            return jsonify({"error": "profiling disabled"}), 403
        profiler = getattr(app, "profiler", None)
        if profiler is not None:
            profiler.clear()
        return jsonify({"ok": True})

    # ============================================================
    # HTTP 传输层优化（压缩 + 缓存头）
    # ============================================================
    _register_compression(app)
    _register_cache_headers(app)

    # ============================================================
    # 安全响应头与 CORS
    # ============================================================
    _register_security_headers(app)
    _register_cors(app)

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
    同时保持 request.blueprint 正确，避免破坏 CSRF 豁免和框架功能。
    """
    global _request_endpoint_patched
    if _request_endpoint_patched:
        return

    from flask.wrappers import Request

    _original_endpoint_fget = Request.endpoint.fget  # type: ignore[attr-defined]

    @property  # type: ignore[misc]
    def patched_endpoint(self):
        ep = _original_endpoint_fget(self)
        if ep and "." in ep:
            bp_name = ep.split(".", 1)[0]
            if bp_name.startswith("pages_") or bp_name.startswith("api_v1_"):
                return ep.split(".", 1)[1]
        return ep

    @property  # type: ignore[misc]
    def patched_blueprint(self):
        # 使用原始 endpoint 推导 blueprint，避免 patched_endpoint 截断后丢失蓝图名
        ep = _original_endpoint_fget(self)
        if ep is not None and "." in ep:
            return ep.rpartition(".")[0]
        return None

    Request.endpoint = patched_endpoint  # type: ignore[method-assign]
    Request.blueprint = patched_blueprint  # type: ignore[method-assign]
    _request_endpoint_patched = True


def _generate_trace_id() -> str:
    """生成 12 字符的十六进制 trace_id"""
    return uuid.uuid4().hex[:12]


def _get_current_trace_id() -> str:
    """获取当前请求上下文的 trace_id；不存在时生成新的。"""
    if has_request_context():
        from flask import g
        return getattr(g, "trace_id", _generate_trace_id())
    return _generate_trace_id()


def _register_trace_middleware(app: Flask) -> None:
    """注册追踪中间件：在响应头中注入 X-Trace-Id。"""

    @app.after_request
    def _inject_trace_header(response):
        trace_id = _get_current_trace_id()
        response.headers["X-Trace-Id"] = trace_id
        return response


def _register_profiler(app: Flask) -> None:
    """注册性能分析器（仅在 debug 模式激活自动请求分析）。"""
    from app.core.profiler import Profiler, set_global_profiler

    profiler = Profiler()
    app.profiler = profiler  # type: ignore[attr-defined]
    set_global_profiler(profiler)

    @app.before_request
    def _profile_start() -> None:
        if not app.debug:
            return
        from flask import g
        g._profile_start = time.perf_counter()

    @app.after_request
    def _profile_record(response):
        if not app.debug:
            return response
        from flask import g

        # 排除 profiling 自身端点，避免循环记录
        if request.endpoint in ("debug_profile", "debug_profile_clear"):
            return response

        start = getattr(g, "_profile_start", None)
        if start is not None:
            duration_ms = (time.perf_counter() - start) * 1000
            _profiler = getattr(app, "profiler", None) or profiler
            _profiler.record(
                name=f"http:{request.method}:{request.endpoint or 'unknown'}",
                duration_ms=duration_ms,
                path=request.path,
                status_code=response.status_code,
            )
            g._profile_recorded = True
        return response

    @app.teardown_request
    def _profile_teardown(exc):
        if not app.debug:
            return
        from flask import g
        if getattr(g, "_profile_recorded", False):
            return
        # 排除 profiling 自身端点
        if request.endpoint in ("debug_profile", "debug_profile_clear"):
            return
        start = getattr(g, "_profile_start", None)
        if start is not None:
            duration_ms = (time.perf_counter() - start) * 1000
            _profiler = getattr(app, "profiler", None) or profiler
            _profiler.record(
                name=f"http:{request.method}:{request.endpoint or 'unknown'}",
                duration_ms=duration_ms,
                path=request.path,
                status_code=500 if exc else 200,
            )


def _register_metrics_middleware(app: Flask) -> None:
    """注册指标中间件：记录 HTTP 请求计数与延迟。"""
    from app.core.metrics import MetricsCollector, set_global_collector

    collector = MetricsCollector()
    app.metrics = collector  # type: ignore[attr-defined]
    set_global_collector(collector)

    @app.before_request
    def _metrics_start_timer() -> None:
        from flask import g
        g._metrics_start = time.perf_counter()

    @app.after_request
    def _metrics_record(response):
        from flask import g

        start = getattr(g, "_metrics_start", None)
        latency_ms = (time.perf_counter() - start) * 1000 if start else 0.0
        path = request.path or "unknown"
        collector.record_http_request(
            method=request.method or "UNKNOWN",
            path=path,
            status_code=response.status_code,
            latency_ms=latency_ms,
        )
        # Server-Timing: W3C 性能计时头
        response.headers["Server-Timing"] = f"total;dur={latency_ms:.2f}"
        return response


def _record_error_metric(app: Flask, code: str) -> None:
    """将错误码记录到应用指标收集器（如果存在）。"""
    collector = getattr(app, "metrics", None)
    if collector is not None:
        collector.record_error(code)


def _register_error_handlers(app: Flask) -> None:
    """注册全局错误处理器，所有异常返回统一 JSON 格式并附带 trace_id"""

    @app.errorhandler(400)
    def bad_request(error):
        trace_id = _get_current_trace_id()
        app.logger.warning(
            "[error_code=BAD_REQUEST trace_id=%s] %s %s | %s",
            trace_id,
            request.method,
            request.url,
            getattr(error, "description", str(error)),
        )
        _record_error_metric(app, "BAD_REQUEST")
        return jsonify({
            "success": False,
            "data": None,
            "error": {"code": "BAD_REQUEST", "message": getattr(error, "description", str(error)), "details": None},
            "trace_id": trace_id,
            "meta": {},
        }), 400

    @app.errorhandler(404)
    def not_found(error):
        trace_id = _get_current_trace_id()
        app.logger.warning(
            "[error_code=NOT_FOUND trace_id=%s] %s %s",
            trace_id,
            request.method,
            request.url,
        )
        _record_error_metric(app, "NOT_FOUND")
        return jsonify({
            "success": False,
            "data": None,
            "error": {"code": "NOT_FOUND", "message": "Not Found", "details": None},
            "trace_id": trace_id,
            "meta": {},
        }), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        trace_id = _get_current_trace_id()
        app.logger.warning(
            "[error_code=METHOD_NOT_ALLOWED trace_id=%s] %s %s",
            trace_id,
            request.method,
            request.url,
        )
        _record_error_metric(app, "METHOD_NOT_ALLOWED")
        return jsonify({
            "success": False,
            "data": None,
            "error": {"code": "METHOD_NOT_ALLOWED", "message": "Method Not Allowed", "details": None},
            "trace_id": trace_id,
            "meta": {},
        }), 405

    @app.errorhandler(500)
    def internal_error(error):
        trace_id = _get_current_trace_id()
        app.logger.error(
            "[error_code=INTERNAL_ERROR trace_id=%s] %s %s | %s\n%s",
            trace_id,
            request.method,
            request.url,
            str(error),
            traceback.format_exc(),
            exc_info=False,
        )
        _record_error_metric(app, "INTERNAL_ERROR")
        return jsonify({
            "success": False,
            "data": None,
            "error": {"code": "INTERNAL_ERROR", "message": "Internal Server Error", "details": None},
            "trace_id": trace_id,
            "meta": {},
        }), 500

    @app.errorhandler(Exception)
    def unhandled_exception(error):
        trace_id = _get_current_trace_id()
        app.logger.error(
            "[error_code=UNHANDLED_EXCEPTION trace_id=%s] endpoint=%s method=%s url=%s | %s\n%s",
            trace_id,
            request.endpoint,
            request.method,
            request.url,
            str(error),
            traceback.format_exc(),
            exc_info=False,
        )
        _record_error_metric(app, "UNHANDLED_EXCEPTION")
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


def _register_security_headers(app: Flask) -> None:
    """注册全局安全响应头（CSP、HSTS、X-Frame-Options 等）。"""

    @app.after_request
    def _add_security_headers(response):
        # 防止 MIME 类型嗅探
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        # 防止点击劫持
        response.headers.setdefault("X-Frame-Options", "DENY")
        # XSS 保护（旧浏览器兼容）
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        # Referrer 策略
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        # 权限策略
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), payment=()",
        )
        # 内容安全策略（CSP）
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self';"
        )
        response.headers.setdefault("Content-Security-Policy", csp)
        # HSTS（仅生产环境 HTTPS）
        if not app.debug and request.is_secure:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


def _register_cors(app: Flask) -> None:
    """注册 CORS：API 端点开放跨域，页面端点不开放。"""
    try:
        from flask_cors import CORS
    except ImportError:
        app.logger.warning("flask-cors not installed, CORS disabled")
        return

    # 允许的来源（通过环境变量配置，默认仅 localhost）
    origins = os.environ.get("CORS_ORIGINS", "http://localhost:5000,http://127.0.0.1:5000")
    origin_list = [o.strip() for o in origins.split(",") if o.strip()]

    CORS(
        app,
        resources={
            r"/api/v1/*": {
                "origins": origin_list,
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization", "X-Trace-Id"],
                "supports_credentials": True,
            },
            r"/metrics": {
                "origins": origin_list,
                "methods": ["GET"],
            },
        },
    )


def _register_compression(app: Flask) -> None:
    """注册 gzip 压缩（JSON/HTML/文本响应）。"""
    try:
        from flask_compress import Compress

        Compress(app)
    except ImportError:
        app.logger.warning("flask-compress not installed, gzip compression disabled")


def _register_cache_headers(app: Flask) -> None:
    """为静态资源和 API 响应添加浏览器缓存头。"""

    @app.after_request
    def _add_cache_headers(response):
        path = request.path

        # 静态资源：1 天缓存（CSS/JS/图片/字体）
        if path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=86400"
            return response

        # API 读取端点：5 分钟缓存（GET /api/v1/trends, /api/v1/prompts 等）
        if path.startswith("/api/v1/") and request.method == "GET":
            response.headers["Cache-Control"] = "public, max-age=300"
            return response

        # HTML 页面：不缓存（动态内容）
        if response.content_type and "text/html" in response.content_type:
            response.headers["Cache-Control"] = "no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            return response

        return response


def _init_cache(app: Flask) -> None:
    """初始化 Flask-Caching（Redis 优先，内存 fallback）。"""
    from app.core.flask_cache import cache

    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        cache_config = {
            "CACHE_TYPE": "RedisCache",
            "CACHE_REDIS_URL": redis_url,
            "CACHE_DEFAULT_TIMEOUT": 300,
        }
    else:
        cache_config = {
            "CACHE_TYPE": "SimpleCache",
            "CACHE_DEFAULT_TIMEOUT": 300,
        }

    app.config.from_mapping(cache_config)
    cache.init_app(app)
