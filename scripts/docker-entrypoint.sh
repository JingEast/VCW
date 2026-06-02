#!/bin/bash
# =============================================================================
# VCW Docker Entrypoint
# 处理数据库初始化、迁移后启动应用
# =============================================================================
set -e

_log() {
    echo "[entrypoint] $*"
}

# 等待依赖服务就绪
_log "Waiting for services..."
python scripts/wait-for-services.py || {
    _log "Services not ready, exiting"
    exit 1
}

# 数据库自动初始化（仅 SQLite 或测试环境）
if [[ "${DATABASE_URL:-}" == sqlite://* ]] || [[ "${FLASK_DEBUG:-false}" == "true" ]]; then
    _log "Initializing database..."
    python -c "
import sys
sys.path.insert(0, '/app')
from app import create_app
app = create_app()
with app.app_context():
    from vcw_copywriter.db.session import init_db
    init_db()
" || _log "Database init skipped or failed (non-fatal)"
fi

# 执行传入的命令
_log "Starting: $*"
exec "$@"
