#!/usr/bin/env bash
# shellcheck disable=SC2059
# =============================================================================
# GitHub Environment Configuration Checker
# REL-03 remediation helper — verifies CI/CD environments and protection rules.
# =============================================================================
set -euo pipefail

REPO="${1:-}"
TOKEN="${GITHUB_TOKEN:-${GH_TOKEN:-}}"

if [ -z "$REPO" ]; then
    echo "Usage: $0 <owner/repo>"
    echo "Example: $0 JingEast/VCW"
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

API_BASE="https://api.github.com/repos/${REPO}"

echo "============================================================================="
echo "GitHub Environment Check for: ${REPO}"
echo "============================================================================="

check_environment() {
    local env_name="$1"
    local require_protection="${2:-false}"
    local env_url="${API_BASE}/environments/${env_name}"

    local response
    response=$(curl -s -H "Authorization: token ${TOKEN}" \
        -H "Accept: application/vnd.github.v3+json" \
        "${env_url}")

    if echo "$response" | grep -q '"message":"Not Found"'; then
        echo "  ❌ ${env_name}: Environment does not exist"
        if [ "$require_protection" = "true" ]; then
            return 1
        fi
        return 0
    fi

    local rules
    rules=$(echo "$response" | grep -o '"type":"[^"]*"' | sed 's/"type":"//;s/"$//' || true)

    if [ -z "$rules" ]; then
        echo "  ⚠️  ${env_name}: Environment exists but has NO protection rules"
        if [ "$require_protection" = "true" ]; then
            return 1
        fi
    else
        echo "  ✅ ${env_name}: Environment exists with protection rules:"
        echo "$rules" | sed 's/^/     - /'
    fi
    return 0
}

echo ""
echo "Checking environments..."
EXIT_CODE=0

if ! check_environment "staging" false; then
    EXIT_CODE=1
fi

if ! check_environment "production" true; then
    EXIT_CODE=1
fi

echo ""
echo "============================================================================="
if [ "$EXIT_CODE" -eq 0 ]; then
    echo "RESULT: All required environments are configured. REL-03 is CLOSED."
    echo "============================================================================="
    exit 0
else
    echo "RESULT: Environment configuration incomplete."
    echo "============================================================================="
    echo ""
    echo "To configure environments, visit:"
    echo "  https://github.com/${REPO}/settings/environments"
    echo ""
    echo "Recommended protection rules for production:"
    echo "  - Required reviewers (1+ person)"
    echo "  - Wait timer (optional)"
    echo "  - Deployment branches (restrict to main/master)"
    echo ""
    echo "Staging may remain without protection rules for auto-deployment."
    exit 1
fi
