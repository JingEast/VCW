#!/bin/bash
# =============================================================================
# VCW 自动回滚脚本
#
# 用法：
#   bash scripts/rollback.sh <staging|production>
# =============================================================================
set -e

ENVIRONMENT="${1:-staging}"
COMPOSE="docker compose"
STABLE_TAG_FILE="/tmp/vcw-${ENVIRONMENT}-stable-tag.txt"

_log() { echo "[rollback:$ENVIRONMENT] $*"; }
_fail() { echo "[rollback:$ENVIRONMENT] FAIL: $*"; exit 1; }

if [ ! -f "$STABLE_TAG_FILE" ]; then
    _fail "No stable tag recorded at $STABLE_TAG_FILE"
fi

STABLE_TAG=$(cat "$STABLE_TAG_FILE")
_log "Rolling back to stable tag: $STABLE_TAG"

COMPOSE_FILES="-f docker-compose.yml"
if [ "$ENVIRONMENT" = "staging" ]; then
    COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.staging.yml"
elif [ "$ENVIRONMENT" = "production" ]; then
    COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.prod.yml"
fi

export IMAGE_TAG="$STABLE_TAG"
$COMPOSE $COMPOSE_FILES pull || _fail "Failed to pull stable images"
$COMPOSE $COMPOSE_FILES up -d || _fail "Failed to restart with stable images"

# 验证回滚后健康
for i in $(seq 1 30); do
    if curl -sf http://localhost:5000/health >/dev/null 2>&1; then
        _log "Rollback health check passed"
        exit 0
    fi
    sleep 2
done

_fail "Rollback health check timeout"
