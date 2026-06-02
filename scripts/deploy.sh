#!/bin/bash
# =============================================================================
# VCW 部署脚本（支持自动回滚）
#
# 用法：
#   bash scripts/deploy.sh <staging|production> <image_tag>
# =============================================================================
set -e

ENVIRONMENT="${1:-staging}"
IMAGE_TAG="${2:-latest}"
DOCKER_USERNAME="${DOCKER_USERNAME:-vcw}"
COMPOSE="docker compose"
STABLE_TAG_FILE="/tmp/vcw-${ENVIRONMENT}-stable-tag.txt"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-60}"

_log() { echo "[deploy:$ENVIRONMENT] $*"; }
_fail() { echo "[deploy:$ENVIRONMENT] FAIL: $*"; exit 1; }

_log "Starting deployment..."
_log "Image tag: $IMAGE_TAG"

# ------------------------------------------------------------------------------
# 记录当前稳定版本（用于回滚）
# ------------------------------------------------------------------------------
CURRENT_TAG=$(docker images --format "{{.Tag}}" "${DOCKER_USERNAME}/vcw-web:latest" 2>/dev/null | head -1 || echo "")
if [ -n "$CURRENT_TAG" ] && [ "$CURRENT_TAG" != "$IMAGE_TAG" ]; then
    echo "$CURRENT_TAG" > "$STABLE_TAG_FILE"
    _log "Recorded stable tag: $CURRENT_TAG"
fi

# ------------------------------------------------------------------------------
# 环境隔离：选择 compose 覆盖文件
# ------------------------------------------------------------------------------
COMPOSE_FILES="-f docker-compose.yml"
if [ "$ENVIRONMENT" = "staging" ]; then
    COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.staging.yml"
elif [ "$ENVIRONMENT" = "production" ]; then
    COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.prod.yml"
fi

# ------------------------------------------------------------------------------
# 拉取镜像并启动
# ------------------------------------------------------------------------------
_log "Pulling images..."
$COMPOSE $COMPOSE_FILES pull || _fail "Failed to pull images"

_log "Starting services..."
$COMPOSE $COMPOSE_FILES up -d || _fail "Failed to start services"

# ------------------------------------------------------------------------------
# 健康检查（带超时）
# ------------------------------------------------------------------------------
_log "Health check (timeout ${HEALTH_TIMEOUT}s)..."
HEALTH_OK=false
for i in $(seq 1 "$((HEALTH_TIMEOUT / 2))"); do
    if curl -sf http://localhost:5000/health >/dev/null 2>&1; then
        HEALTH_OK=true
        break
    fi
    sleep 2
done

if [ "$HEALTH_OK" = "false" ]; then
    _log "Health check FAILED — initiating rollback"
    if [ -f "$STABLE_TAG_FILE" ]; then
        bash "$(dirname "$0")/rollback.sh" "$ENVIRONMENT"
        _fail "Deployment rolled back to stable version"
    else
        _fail "Health check timeout and no stable tag for rollback"
    fi
fi

_log "Deployment completed successfully"
