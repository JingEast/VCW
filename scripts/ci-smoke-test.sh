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
_fail() { echo "[ci-smoke] FAIL: $*"; _dump_logs; exit 1; }

# 收集容器日志的辅助函数（失败时调用）
_dump_logs() {
    _log "Dumping container logs for debugging..."
    mkdir -p docker-logs

    # 记录所有容器状态（含已退出）
    $COMPOSE ps -a > docker-logs/compose-ps.log 2>&1 || true
    docker ps -a --filter "name=vcw-" >> docker-logs/compose-ps.log 2>&1 || true

    local services=("postgres" "redis" "web" "worker" "beat")
    for svc in "${services[@]}"; do
        local cid
        # 尝试获取运行中或已停止的容器 ID
        cid=$($COMPOSE ps -q "${svc}" 2>/dev/null | head -n1) || true
        if [ -n "$cid" ]; then
            _log "  → collecting logs for ${svc} (${cid:0:12})"
            docker logs "$cid" > "docker-logs/${svc}.log" 2>&1 || true
            docker inspect --format '{{json .State}}' "$cid" > "docker-logs/${svc}-state.json" 2>&1 || true
            docker inspect --format '{{json .Config.Env}}' "$cid" > "docker-logs/${svc}-env.json" 2>&1 || true
        else
            _log "  → no container found for ${svc}"
        fi
    done
}

# 保留 ERR trap 作为双重保险；_fail 也会显式调用 _dump_logs
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
HEALTH_BODY=""
for i in $(seq 1 30); do
    HEALTH_BODY=$(curl -s http://localhost:5000/health || echo '{"error":"curl-failed"}')
    HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/health || echo "000")
    if [ "$HEALTH_STATUS" = "200" ]; then
        break
    fi
    # 每 10 秒打印一次容器状态与健康响应体，便于诊断
    if [ $((i % 5)) -eq 0 ]; then
        WEB_STATE=$($COMPOSE ps --status running --services web 2>/dev/null || true)
        _log "    retry ${i}/30, health=${HEALTH_STATUS}, body=${HEALTH_BODY}, web running services: ${WEB_STATE:-<none>}"
    fi
    sleep 2
done
if [ "$HEALTH_STATUS" != "200" ]; then
    _log "Web container status before fail:"
    $COMPOSE ps web || true
    _log "Last /health response body: ${HEALTH_BODY}"
    _log "Last 50 lines of web container logs:"
    docker logs "$WEB_CID" --tail 50 2>&1 || true
    _fail "Web /health returned ${HEALTH_STATUS}"
fi
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
