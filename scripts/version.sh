#!/bin/bash
# =============================================================================
# VCW 语义版本号生成脚本
#
# 用法：
#   bash scripts/version.sh [major|minor|patch]
#
# 基于最新 git tag 自动递增版本号，默认递增 patch。
# =============================================================================
set -e

BUMP="${1:-patch}"

# 获取最新 tag（如果没有则默认 v0.0.0）
LATEST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")
LATEST_TAG=${LATEST_TAG#v}

IFS='.' read -r MAJOR MINOR PATCH <<< "$LATEST_TAG"

case "$BUMP" in
    major)
        MAJOR=$((MAJOR + 1))
        MINOR=0
        PATCH=0
        ;;
    minor)
        MINOR=$((MINOR + 1))
        PATCH=0
        ;;
    patch)
        PATCH=$((PATCH + 1))
        ;;
    *)
        echo "Usage: $0 [major|minor|patch]" >&2
        exit 1
        ;;
esac

echo "v${MAJOR}.${MINOR}.${PATCH}"
