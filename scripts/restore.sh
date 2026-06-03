#!/usr/bin/env bash
# shellcheck disable=SC2059
# =============================================================================
# VCW Restore from Backup
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

BACKUP_NAME="${1:-}"
BACKUP_DIR="${BACKUP_DIR:-data/backups}"

echo "============================================================================="
echo "VCW Restore"
echo "============================================================================="

if [ -z "$BACKUP_NAME" ]; then
    echo "Usage: $0 <backup_name>"
    echo ""
    echo "Available backups:"
    ls -1 "${PROJECT_DIR}/${BACKUP_DIR}" 2>/dev/null || echo "  (none)"
    exit 1
fi

BACKUP_PATH="${PROJECT_DIR}/${BACKUP_DIR}/${BACKUP_NAME}"
if [ ! -d "$BACKUP_PATH" ]; then
    echo "❌ Backup not found: ${BACKUP_PATH}"
    exit 1
fi

echo "Backup:   ${BACKUP_PATH}"
echo ""

# Show manifest
cat "${BACKUP_PATH}/manifest.json" 2>/dev/null || echo "(no manifest)"
echo ""

read -r -p "⚠️  This will OVERWRITE current data. Continue? [y/N] " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Restore database
cd "${PROJECT_DIR}"
python - <<PY
import sys
import gzip
import shutil
import json
from pathlib import Path

sys.path.insert(0, "${PROJECT_DIR}")

backup_path = Path("${BACKUP_PATH}")
manifest_path = backup_path / "manifest.json"
if not manifest_path.exists():
    print("❌ manifest.json missing")
    sys.exit(1)

with open(manifest_path, "r", encoding="utf-8") as f:
    manifest = json.load(f)

db_type = manifest.get("db_type", "sqlite")
db_file = backup_path / manifest.get("db_file", "db_dump.sql.gz")

if db_type == "sqlite":
    db_path = Path("data/vcw.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(db_file, "rb") as f_in:
        with open(db_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    print(f"✅ SQLite DB restored to {db_path}")
elif db_type == "postgresql":
    print("⚠️  PostgreSQL restore requires manual pg_restore:")
    print(f"   gunzip -c {db_file} | psql <your_database>")
else:
    print(f"❌ Unknown db_type: {db_type}")
    sys.exit(1)

# Restore files archive
files_archive = backup_path / "files.tar.gz"
if files_archive.exists():
    import tarfile
    with tarfile.open(files_archive, "r:gz") as tar:
        tar.extractall(path="data/")
    print(f"✅ Files restored from {files_archive}")
else:
    print("ℹ️  No files archive found")

print("")
print("🎉 Restore complete. Restart the application to use restored data.")
PY

echo ""
echo "============================================================================="
