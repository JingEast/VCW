#!/bin/bash
# =============================================================================
# 健康检查脚本
#
# 用法：
#   bash scripts/health-check.sh <url>
# =============================================================================
set -e

URL="${1:-http://localhost:5000}"
TIMEOUT="${2:-60}"

_log() { echo "[health-check] $*"; }
_fail() { echo "[health-check] FAIL: $*"; exit 1; }

_log "Checking $URL/health (timeout ${TIMEOUT}s)..."

for i in $(seq 1 "$((TIMEOUT / 2))"); do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${URL}/health" || echo "000")
    if [ "$STATUS" = "200" ]; then
        _log "Health check passed (HTTP 200)"
        curl -s "${URL}/health" | python3 -m json.tool 2>/dev/null || true
        exit 0
    fi
    _log "Attempt $i: HTTP $STATUS, retrying..."
    sleep 2
done

_fail "Health check failed after ${TIMEOUT}s (last status: $STATUS)"
