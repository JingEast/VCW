#!/bin/bash
# =============================================================================
# VCW 版本发布脚本
#
# 用法：
#   bash scripts/bump-version.sh [major|minor|patch]
#
# 自动生成新版本号、打 tag、推送触发 Release。
# =============================================================================
set -e

BUMP="${1:-patch}"
NEW_VERSION=$(bash "$(dirname "$0")/version.sh" "$BUMP")

echo "Bumping version: $NEW_VERSION"

# 更新 CHANGELOG（追加）
DATE=$(date +%Y-%m-%d)
{
    echo "## $NEW_VERSION ($DATE)"
    echo ""
    git log "$(git describe --tags --abbrev=0 2>/dev/null || echo "")..HEAD" --pretty=format:"- %s" || echo "- New release"
    echo ""
    echo ""
} > /tmp/changelog-entry.md

if [ -f CHANGELOG.md ]; then
    cat /tmp/changelog-entry.md CHANGELOG.md > /tmp/CHANGELOG-new.md
    mv /tmp/CHANGELOG-new.md CHANGELOG.md
else
    cat /tmp/changelog-entry.md > CHANGELOG.md
fi

git add CHANGELOG.md
git commit -m "chore(release): $NEW_VERSION" || true
git tag -a "$NEW_VERSION" -m "Release $NEW_VERSION"
git push origin "$NEW_VERSION"

echo "Released $NEW_VERSION"
