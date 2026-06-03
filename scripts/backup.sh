#!/usr/bin/env bash
# shellcheck disable=SC2059
# =============================================================================
# VCW Manual Backup Trigger
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

BACKUP_DIR="${BACKUP_DIR:-data/backups}"
DB_URI="${DATABASE_URL:-sqlite:///data/vcw.db}"

echo "============================================================================="
echo "VCW Backup"
echo "============================================================================="
echo "Project:  ${PROJECT_DIR}"
echo "DB URI:   ${DB_URI}"
echo "Backup:   ${BACKUP_DIR}"
echo ""

cd "${PROJECT_DIR}"

# Ensure backup directory exists
mkdir -p "${BACKUP_DIR}"

# Run backup via Python (reuses BackupService directly)
python - <<PY
import sys
sys.path.insert(0, "${PROJECT_DIR}")
from app.services.backup_service import BackupService

svc = BackupService(backup_dir="${BACKUP_DIR}", db_uri="${DB_URI}")
try:
    path = svc.create_backup()
    removed = svc.cleanup_expired_backups()
    print(f"✅ Backup created: {path}")
    print(f"🗑️  Expired backups removed: {len(removed)}")
except Exception as e:
    print(f"❌ Backup failed: {e}")
    sys.exit(1)
PY

echo ""
echo "============================================================================="
