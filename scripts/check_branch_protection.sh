#!/usr/bin/env bash
# shellcheck disable=SC2059
# =============================================================================
# Branch Protection Configuration Checker
# REL-04 remediation helper — verifies main branch protection rules.
# =============================================================================
set -euo pipefail

REPO="${1:-}"
BRANCH="${2:-main}"
TOKEN="${GITHUB_TOKEN:-${GH_TOKEN:-}}"

if [ -z "$REPO" ]; then
    echo "Usage: $0 <owner/repo> [branch]"
    echo "Example: $0 JingEast/VCW main"
    echo ""
    echo "Requires GITHUB_TOKEN or GH_TOKEN environment variable with 'repo' scope."
    exit 1
fi

if [ -z "$TOKEN" ]; then
    echo "ERROR: GITHUB_TOKEN or GH_TOKEN environment variable is required."
    echo "Generate a token at: https://github.com/settings/tokens"
    echo "Required scope: repo (or public_repo for public repositories)"
    exit 1
fi

API_URL="https://api.github.com/repos/${REPO}/branches/${BRANCH}/protection"

echo "============================================================================="
echo "Branch Protection Check for: ${REPO}/${BRANCH}"
echo "============================================================================="

RESPONSE=$(curl -s -H "Authorization: token ${TOKEN}" \
    -H "Accept: application/vnd.github.v3+json" \
    "${API_URL}")

# Check for API errors
if echo "$RESPONSE" | grep -q '"message":"Branch not protected"'; then
    echo ""
    echo "❌ Branch '${BRANCH}' is NOT protected."
    echo ""
    echo "Required protection rules for go-live:"
    echo "  - Require a pull request before merging"
    echo "  - Require status checks to pass (lint, test, migration-check, docker-smoke)"
    echo "  - Restrict pushes that create files larger than 100MB"
    echo ""
    echo "Configure at: https://github.com/${REPO}/settings/branches"
    exit 1
fi

if echo "$RESPONSE" | grep -q '"message":"Not Found"'; then
    echo ""
    echo "❌ Branch '${BRANCH}' not found or token lacks permissions."
    exit 1
fi

echo ""
echo "✅ Branch '${BRANCH}' is protected."
echo ""

# Parse key protection settings
PR_REVIEWS=$(echo "$RESPONSE" | grep -o '"required_pull_request_reviews"' || true)
STATUS_CHECKS=$(echo "$RESPONSE" | grep -o '"required_status_checks"' || true)
RESTRICTIONS=$(echo "$RESPONSE" | grep -o '"restrictions"' || true)

if [ -n "$PR_REVIEWS" ]; then
    echo "  ✅ Require pull request reviews: enabled"
else
    echo "  ⚠️  Require pull request reviews: NOT enabled"
fi

if [ -n "$STATUS_CHECKS" ]; then
    echo "  ✅ Require status checks: enabled"
    CONTEXTS=$(echo "$RESPONSE" | grep -o '"context":"[^"]*"' | sed 's/"context":"//;s/"$//' || true)
    if [ -n "$CONTEXTS" ]; then
        echo "     Required checks:"
        echo "$CONTEXTS" | sed 's/^/       - /'
    fi
else
    echo "  ⚠️  Require status checks: NOT enabled"
fi

if [ -n "$RESTRICTIONS" ]; then
    echo "  ✅ Restrict push access: enabled"
else
    echo "  ⚠️  Restrict push access: NOT enabled"
fi

echo ""
echo "============================================================================="

# Determine overall pass/fail
if [ -n "$PR_REVIEWS" ] && [ -n "$STATUS_CHECKS" ]; then
    echo "RESULT: Branch protection meets go-live minimum. REL-04 is CLOSED."
    echo "============================================================================="
    exit 0
else
    echo "RESULT: Branch protection incomplete. Enable required rules at:"
    echo "  https://github.com/${REPO}/settings/branches"
    echo "============================================================================="
    exit 1
fi
