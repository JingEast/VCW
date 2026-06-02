#!/bin/bash
# =============================================================================
# VCW CI Docker 冒烟测试脚本
# 用途：在 GitHub Actions / CI 环境中验证镜像构建、服务启动、健康探测
#
# 前置条件：
#   docker compose -p vcw build 已完成
# =============================================================================
set -e

PROJECT="vcw"
COMPOSE="docker compose -p ${PROJECT}"

_log() { echo "[ci-smoke] $*"; }
_fail() { echo "[ci-smoke] FAIL: $*"; exit 1; }

# 收集容器日志的辅助函数（失败时调用）
_dump_logs() {
    _log "Dumping container logs for debugging..."
    mkdir -p docker-logs
    local services=("postgres" "redis" "web" "worker" "beat")
    for svc in "${services[@]}"; do
        local cid
        cid=$($COMPOSE ps -q "$svc" 2>/dev/null) || true
        if [ -n "$cid" ]; then
            docker logs "$cid" > "docker-logs/${svc}.log" 2>&1 || true
        fi
    done
}

trap '_dump_logs' ERR

# ------------------------------------------------------------------------------
# Step 1: 启动服务
# ------------------------------------------------------------------------------
_log "Step 1/5: Starting all services..."
$COMPOSE up -d

# 等待基础设施就绪（web 的 wait-for-services.py 会处理剩余等待）
_log "Waiting 15s for infrastructure bootstrap..."
sleep 15

# ------------------------------------------------------------------------------
# Step 2: 基础设施健康检查
# ------------------------------------------------------------------------------
_log "Step 2/5: Infrastructure health checks"

POSTGRES_CID=$($COMPOSE ps -q postgres)
REDIS_CID=$($COMPOSE ps -q redis)
WEB_CID=$($COMPOSE ps -q web)
WORKER_CID=$($COMPOSE ps -q worker)

[ -n "$POSTGRES_CID" ] || _fail "postgres container not found"
[ -n "$REDIS_CID" ]    || _fail "redis container not found"
[ -n "$WEB_CID" ]      || _fail "web container not found"
[ -n "$WORKER_CID" ]   || _fail "worker container not found"

_log "  → PostgreSQL (pg_isready)"
docker exec "$POSTGRES_CID" pg_isready -U vcw -d vcw >/dev/null || _fail "PostgreSQL not ready"

_log "  → Redis (redis-cli ping)"
docker exec "$REDIS_CID" redis-cli ping | grep -q PONG || _fail "Redis did not respond PONG"

# ------------------------------------------------------------------------------
# Step 3: Web 服务健康检查
# ------------------------------------------------------------------------------
_log "Step 3/5: Web service health checks"

_log "  → Web /health (with retry, max 60s)"
HEALTH_STATUS="000"
for i in $(seq 1 30); do
    HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/health || echo "000")
    if [ "$HEALTH_STATUS" = "200" ]; then
        break
    fi
    sleep 2
done
[ "$HEALTH_STATUS" = "200" ] || _fail "Web /health returned $HEALTH_STATUS"
curl -s http://localhost:5000/health | python3 -m json.tool || true

_log "  → Web /metrics"
METRICS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/metrics || echo "000")
[ "$METRICS_STATUS" = "200" ] || _fail "Web /metrics returned $METRICS_STATUS"

# ------------------------------------------------------------------------------
# Step 4: Celery Worker 健康检查
# ------------------------------------------------------------------------------
_log "Step 4/5: Celery Worker health checks"

_log "  → Worker inspect ping (with retry, max 60s)"
for i in $(seq 1 30); do
    if docker exec "$WORKER_CID" celery -A celery_app inspect ping >/dev/null 2>&1; then
        break
    fi
    sleep 2
done
docker exec "$WORKER_CID" celery -A celery_app inspect ping >/dev/null || _fail "Celery Worker not responding"

# ------------------------------------------------------------------------------
# Step 5: 镜像与非 root 运行校验
# ------------------------------------------------------------------------------
_log "Step 5/5: Image & runtime verification"

# 镜像体积（仅日志记录，不设硬性阈值）
WEB_IMAGE=$(docker inspect --format='{{.Config.Image}}' "$WEB_CID")
IMAGE_SIZE=$(docker images --format "{{.Size}}" "$WEB_IMAGE" 2>/dev/null || echo "unknown")
_log "  → Web image size: $IMAGE_SIZE"

# 非 root 用户验证
_log "  → Container running user"
WEB_USER=$(docker exec "$WEB_CID" ps aux 2>/dev/null | grep -v grep | grep -m1 python | awk '{print $1}')
[ "$WEB_USER" = "vcw" ] || _fail "Web container not running as vcw (actual: ${WEB_USER:-<empty>})"
_log "  → Web container user: $WEB_USER (uid=$(docker exec "$WEB_CID" id -u vcw))"

# 容器内 /app 目录权限
APP_OWNER=$(docker exec "$WEB_CID" stat -c '%U' /app)
[ "$APP_OWNER" = "vcw" ] || _fail "/app owner is not vcw (actual: $APP_OWNER)"

_log "======================================"
_log "All Docker smoke checks passed ✓"
_log "======================================"
