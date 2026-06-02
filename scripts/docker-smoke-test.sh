#!/bin/bash
# =============================================================================
# VCW Docker 全链路冒烟测试脚本
# 用途：构建镜像 → 拉起服务 → 逐个验证健康探测
#
# 执行方式：
#   bash scripts/docker-smoke-test.sh
# =============================================================================
set -e

PROJECT="vcw"
COMPOSE="docker compose -p ${PROJECT}"
if command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    COMPOSE="docker-compose -p ${PROJECT}"
fi

_log() { echo "[smoke-test] $*"; }
_fail() { echo "[smoke-test] FAIL: $*"; exit 1; }

# ------------------------------------------------------------------------------
# Step 1: 构建镜像
# ------------------------------------------------------------------------------
_log "Step 1/4: 构建生产镜像..."
$COMPOSE build --no-cache
_log "构建完成"

# 校验镜像体积与非 root 运行
WEB_IMAGE=$($COMPOSE config --format json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['services']['web'].get('image',''))" || true)
if [ -z "$WEB_IMAGE" ]; then
    WEB_IMAGE="${PROJECT}-web"
fi

if docker images --format "{{.Repository}}" | grep -q "^${PROJECT}-web$"; then
    SIZE=$(docker images --format "{{.Size}}" "${PROJECT}-web" | head -1)
    _log "镜像体积: $SIZE"
fi

_log "验证非 root 用户..."
docker run --rm --entrypoint "" "${PROJECT}-web" id vcw >/dev/null 2>&1 || _fail "vcw 用户不存在"
UID_CHECK=$(docker run --rm --entrypoint "" "${PROJECT}-web" id -u vcw 2>/dev/null | tr -d '[:space:]')
[ "$UID_CHECK" = "1000" ] || _fail "vcw UID 不是 1000 (实际: $UID_CHECK)"
_log "非 root 用户校验通过 (uid=1000)"

# ------------------------------------------------------------------------------
# Step 2: 启动服务
# ------------------------------------------------------------------------------
_log "Step 2/4: 启动所有服务..."
$COMPOSE up -d

# 等待服务进入稳定状态
sleep 10

# ------------------------------------------------------------------------------
# Step 3: 逐个验证健康探测
# ------------------------------------------------------------------------------
_log "Step 3/4: 健康探测验证"

POSTGRES_CID=$($COMPOSE ps -q postgres)
REDIS_CID=$($COMPOSE ps -q redis)
WEB_CID=$($COMPOSE ps -q web)
WORKER_CID=$($COMPOSE ps -q worker)

# 3.1 PostgreSQL
_log "  → PostgreSQL (pg_isready)"
docker exec "$POSTGRES_CID" pg_isready -U vcw -d vcw || _fail "PostgreSQL 未就绪"

# 3.2 Redis
_log "  → Redis (redis-cli ping)"
docker exec "$REDIS_CID" redis-cli ping | grep -q PONG || _fail "Redis 未响应 PONG"

# 3.3 Web /health
_log "  → Web /health"
HEALTH_STATUS="000"
for i in $(seq 1 30); do
    HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/health || echo "000")
    if [ "$HEALTH_STATUS" = "200" ]; then
        break
    fi
    sleep 2
done
[ "$HEALTH_STATUS" = "200" ] || _fail "Web /health 返回 $HEALTH_STATUS"
curl -s http://localhost:5000/health | python3 -m json.tool || true

# 3.4 Web /metrics
_log "  → Web /metrics"
METRICS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/metrics)
[ "$METRICS_STATUS" = "200" ] || _fail "Web /metrics 返回 $METRICS_STATUS"

# 3.5 Worker (celery inspect ping)
_log "  → Celery Worker (inspect ping)"
for i in $(seq 1 30); do
    if docker exec "$WORKER_CID" celery -A celery_app inspect ping >/dev/null 2>&1; then
        break
    fi
    sleep 2
done
docker exec "$WORKER_CID" celery -A celery_app inspect ping >/dev/null || _fail "Celery Worker 未响应"

# 3.6 容器内用户验证
_log "  → 容器运行用户"
WEB_USER=$(docker exec "$WEB_CID" ps aux 2>/dev/null | grep -v grep | grep -m1 python | awk '{print $1}')
[ "$WEB_USER" = "vcw" ] || _fail "Web 容器未以 vcw 用户运行 (实际: ${WEB_USER:-<empty>})"

_log "所有健康探测通过 ✓"

# ------------------------------------------------------------------------------
# Step 4: 清理（可选）
# ------------------------------------------------------------------------------
_log "Step 4/4: 测试完成。如需清理运行: $COMPOSE down -v"

_log "======================================"
_log "Docker 全链路自测通过"
_log "======================================"
