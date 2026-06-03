#!/usr/bin/env bash
# shellcheck disable=SC2059
# =============================================================================
# GitHub Secrets Configuration Checker
# REL-02 remediation helper — verifies CI/CD secrets are set in GitHub.
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

API_URL="https://api.github.com/repos/${REPO}/actions/secrets"

echo "============================================================================="
echo "GitHub Secrets Check for: ${REPO}"
echo "============================================================================="

# Fetch list of secrets
RESPONSE=$(curl -s -H "Authorization: token ${TOKEN}" \
    -H "Accept: application/vnd.github.v3+json" \
    "${API_URL}")

# Check for API errors
if echo "$RESPONSE" | grep -q '"message"'; then
    echo "ERROR: GitHub API request failed:"
    echo "$RESPONSE" | grep '"message"' | head -1
    exit 1
fi

# Extract secret names
SECRET_NAMES=$(echo "$RESPONSE" | grep -o '"name" : "[^"]*"' | sed 's/"name" : "//;s/"$//' || true)

REQUIRED_SECRETS=("DOCKER_USERNAME" "DOCKER_PASSWORD" "CODECOV_TOKEN")
MISSING=()
CONFIGURED=()

for SECRET in "${REQUIRED_SECRETS[@]}"; do
    if echo "$SECRET_NAMES" | grep -qx "$SECRET"; then
        CONFIGURED+=("$SECRET")
    else
        MISSING+=("$SECRET")
    fi
done

echo ""
echo "CONFIGURED SECRETS (${#CONFIGURED[@]}/${#REQUIRED_SECRETS[@]}):"
if [ ${#CONFIGURED[@]} -eq 0 ]; then
    echo "  (none)"
else
    for SECRET in "${CONFIGURED[@]}"; do
        echo "  ✅ ${SECRET}"
    done
fi

echo ""
echo "MISSING SECRETS (${#MISSING[@]}/${#REQUIRED_SECRETS[@]}):"
if [ ${#MISSING[@]} -eq 0 ]; then
    echo "  (none)"
else
    for SECRET in "${MISSING[@]}"; do
        echo "  ❌ ${SECRET}"
    done
fi

echo ""
echo "============================================================================="
if [ ${#MISSING[@]} -eq 0 ]; then
    echo "RESULT: All required secrets are configured. REL-02 is CLOSED."
    echo "============================================================================="
    exit 0
else
    echo "RESULT: ${#MISSING[@]} secret(s) missing. CI/CD push/deploy stages will be skipped."
    echo "============================================================================="
    echo ""
    echo "To configure secrets, visit:"
    echo "  https://github.com/${REPO}/settings/secrets/actions"
    echo ""
    echo "Required secrets:"
    echo "  DOCKER_USERNAME   — Docker Hub username for image push"
    echo "  DOCKER_PASSWORD   — Docker Hub access token or password"
    echo "  CODECOV_TOKEN     — Codecov upload token (optional, coverage will skip if missing)"
    exit 1
fi
