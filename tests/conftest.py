"""
pytest 全局 fixtures

设计原则：
  1. session 级别的 app fixture 减少重复创建开销。
  2. 内存数据库避免测试污染生产数据。
  3. DI 容器支持 override，便于 mock 外部依赖。
  4. 测试蓝图在应用初始化时注册，避免运行时注册报错。
"""

import os

# 强制覆盖为内存数据库，避免 .env 或 pytest-cov 预先导入导致 engine 指向错误数据库
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["VCW_API_KEY"] = "test-api-key-for-pytest"

import pytest
from flask import Blueprint


def _register_test_routes(app):
    """注册仅用于测试的路由（触发各类错误场景）"""
    bp = Blueprint("test_routes", __name__)

    @bp.route("/trigger-500")
    def trigger_500():
        raise RuntimeError("intentional test exception")

    @bp.route("/trigger-500-format")
    def trigger_500_format():
        raise ValueError("sensitive details")

    @bp.route("/trigger-500-debug")
    def trigger_500_debug():
        raise TypeError("debug mode error")

    @bp.route("/trigger-400")
    def trigger_400():
        from werkzeug.exceptions import BadRequest
        raise BadRequest("missing required field")

    app.register_blueprint(bp)


@pytest.fixture(scope="session")
def app():
    """创建测试专用的 Flask 应用实例"""
    from app import create_app

    app = create_app()
    app.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",
        "WTF_CSRF_ENABLED": False,
        "PROPAGATE_EXCEPTIONS": True,
    })

    # 注册测试路由（必须在 yield 之前，避免运行时注册）
    _register_test_routes(app)

    # 确保内存数据库表已创建（供 TaskQueue 等使用）
    with app.app_context():
        from vcw_copywriter.db.session import init_db
        init_db()

    yield app

    # 清理：关闭数据库连接
    with app.app_context():
        from vcw_copywriter.db.session import engine
        engine.dispose()


@pytest.fixture
def client(app):
    """创建 Flask test_client"""
    return app.test_client()


@pytest.fixture
def runner(app):
    """创建 Flask CLI test_runner"""
    return app.test_cli_runner()


@pytest.fixture
def container(app):
    """获取当前应用容器（支持 override/clear）"""
    with app.app_context():
        from app.core.container import get_container
        yield get_container
