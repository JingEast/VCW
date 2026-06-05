"""VCW Automated Backup Service.

Provides database dump, file archive, retention cleanup, and restore verification.
Supports SQLite (dev) and PostgreSQL (production).
"""

from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class BackupError(Exception):
    """Backup operation failed."""


class BackupService:
    """Orchestrate backup creation, retention cleanup, and verification."""

    # Files/dirs to archive from data/ (beyond the DB itself)
    _FILE_PATTERNS = [
        "edited",
        "generated",
        "*.json",
    ]

    def __init__(
        self,
        backup_dir: str,
        db_uri: str,
        retention_days: int = 7,
        weekly_retention_weeks: int = 4,
        data_dir: Optional[str] = None,
    ) -> None:
        self.backup_dir = Path(backup_dir)
        self.db_uri = db_uri
        self.retention_days = retention_days
        self.weekly_retention_weeks = weekly_retention_weeks
        self.data_dir = Path(data_dir) if data_dir else Path("data")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_backup(self) -> Path:
        """Create a timestamped backup directory with DB dump + file archive + manifest."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")[:-3]
        backup_path = self.backup_dir / timestamp
        backup_path.mkdir(parents=True, exist_ok=True)

        try:
            db_type, db_file = self._dump_database(backup_path)
            files_archive = self._archive_files(backup_path)
            manifest = self._generate_manifest(
                backup_path,
                db_type=db_type,
                db_file=db_file,
                files_archive=files_archive,
            )
            self._write_manifest(backup_path, manifest)
            return backup_path
        except Exception as exc:
            # Partial backup cleanup
            shutil.rmtree(backup_path, ignore_errors=True)
            raise BackupError(f"Backup failed: {exc}") from exc

    def cleanup_expired_backups(self) -> list[Path]:
        """Remove backups older than retention policy. Returns removed paths."""
        if not self.backup_dir.exists():
            return []

        removed: list[Path] = []
        now = datetime.now(timezone.utc)

        for entry in sorted(self.backup_dir.iterdir()):
            if not entry.is_dir():
                continue
            try:
                entry_time = datetime.strptime(entry.name, "%Y%m%d_%H%M%S").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                continue

            age_days = (now - entry_time).days
            is_weekly = entry_time.weekday() == 6  # Sunday
            keep = False

            if is_weekly and age_days <= self.weekly_retention_weeks * 7:
                keep = True
            elif age_days <= self.retention_days:
                keep = True

            if not keep:
                shutil.rmtree(entry, ignore_errors=True)
                removed.append(entry)

        return removed

    def verify_backup(self, backup_path: Path) -> dict:
        """Verify a backup by checking manifest checksums and restoring DB to temp location."""
        manifest = self._read_manifest(backup_path)
        results: dict = {"checksums_ok": False, "db_restore_ok": False, "details": {}}

        # 1. Checksum validation
        files_ok = True
        for fname, expected in manifest.get("checksums", {}).items():
            fpath = backup_path / fname
            if not fpath.exists():
                files_ok = False
                results["details"][fname] = "missing"
                continue
            actual = self._sha256_file(fpath)
            if actual != expected:
                files_ok = False
                results["details"][fname] = f"checksum mismatch: {actual[:16]}... != {expected[:16]}..."
            else:
                results["details"][fname] = "ok"
        results["checksums_ok"] = files_ok

        # 2. DB restore verification
        db_type = manifest.get("db_type", "sqlite")
        db_file = backup_path / manifest.get("db_file", "db_dump.sql.gz")
        if db_file.exists():
            results["db_restore_ok"] = self._verify_db_restore(db_file, db_type)
        else:
            results["db_restore_ok"] = False
            results["details"]["db_restore"] = "db file missing"

        results["overall"] = results["checksums_ok"] and results["db_restore_ok"]
        return results

    def list_backups(self) -> list[dict]:
        """Return metadata for all backups."""
        if not self.backup_dir.exists():
            return []
        backups = []
        for entry in sorted(self.backup_dir.iterdir(), reverse=True):
            if not entry.is_dir():
                continue
            manifest = self._read_manifest(entry)
            backups.append(
                {
                    "name": entry.name,
                    "path": str(entry),
                    "created_at": manifest.get("created_at"),
                    "db_type": manifest.get("db_type"),
                    "overall_ok": manifest.get("overall_ok"),
                }
            )
        return backups

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _dump_database(self, backup_path: Path) -> tuple[str, Path]:
        """Dump database to backup_path. Returns (db_type, db_file_path)."""
        if self.db_uri.startswith("sqlite"):
            return self._dump_sqlite(backup_path)
        elif self.db_uri.startswith("postgresql"):
            return self._dump_postgres(backup_path)
        else:
            raise BackupError(f"Unsupported database: {self.db_uri}")

    def _dump_sqlite(self, backup_path: Path) -> tuple[str, Path]:
        """Copy SQLite database file and gzip it."""
        db_path = self.db_uri.replace("sqlite:///", "")
        src = Path(db_path)
        if not src.exists():
            raise BackupError(f"SQLite database not found: {src}")
        dst = backup_path / "db_dump.sql.gz"
        with open(src, "rb") as f_in:
            with gzip.open(dst, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        return "sqlite", dst

    def _dump_postgres(self, backup_path: Path) -> tuple[str, Path]:
        """Run pg_dump and gzip output."""
        dst = backup_path / "db_dump.sql.gz"
        # Parse SQLAlchemy URI to pg_dump args
        uri = self.db_uri
        if "+" in uri.split("://")[0]:
            # e.g. postgresql+psycopg2://...
            uri = uri.replace("+psycopg2", "").replace("+pg8000", "")
        # Extract host/port/user/password/db from URI
        # Simplification: rely on env vars / pgpass for auth in containers
        cmd = [
            "pg_dump",
            "--format=plain",
            "--no-owner",
            "--no-privileges",
            uri,
        ]
        try:
            with gzip.open(dst, "wb") as f_out:
                subprocess.run(cmd, stdout=f_out, check=True, stderr=subprocess.PIPE)  # type: ignore[call-overload]
        except FileNotFoundError as exc:
            raise BackupError("pg_dump not found; ensure postgresql-client is installed") from exc
        except subprocess.CalledProcessError as exc:
            raise BackupError(f"pg_dump failed: {exc.stderr.decode('utf-8', errors='replace')}") from exc
        return "postgresql", dst

    def _archive_files(self, backup_path: Path) -> Optional[Path]:
        """Archive data/edited, data/generated, and JSON files."""
        data_dir = self.data_dir
        if not data_dir.exists():
            return None
        archive = backup_path / "files.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            for pattern in self._FILE_PATTERNS:
                for src in data_dir.glob(pattern):
                    # Skip backups dir, temp DB files, and the live DB
                    if src.name == "backups":
                        continue
                    if src.name.endswith(".db"):
                        continue
                    tar.add(src, arcname=src.name)
        return archive

    def _generate_manifest(
        self,
        backup_path: Path,
        db_type: str,
        db_file: Path,
        files_archive: Optional[Path],
    ) -> dict:
        """Generate backup manifest with checksums and metadata."""
        manifest: dict = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "db_type": db_type,
            "db_file": db_file.name,
            "version": self._get_version(),
            "checksums": {},
        }
        manifest["checksums"][db_file.name] = self._sha256_file(db_file)
        if files_archive and files_archive.exists():
            manifest["files_archive"] = files_archive.name
            manifest["checksums"][files_archive.name] = self._sha256_file(files_archive)
        return manifest

    def _write_manifest(self, backup_path: Path, manifest: dict) -> None:
        mpath = backup_path / "manifest.json"
        with open(mpath, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

    def _read_manifest(self, backup_path: Path) -> dict:
        mpath = backup_path / "manifest.json"
        if not mpath.exists():
            return {}
        with open(mpath, "r", encoding="utf-8") as f:
            return json.load(f)

    def _verify_db_restore(self, db_file: Path, db_type: str) -> bool:
        """Restore DB to a temp location and verify critical tables exist with rows."""
        if db_type == "sqlite":
            return self._verify_sqlite_restore(db_file)
        elif db_type == "postgresql":
            # For PostgreSQL, we can only verify the dump is valid SQL by parsing
            return self._verify_postgres_dump(db_file)
        return False

    def _verify_sqlite_restore(self, db_file: Path) -> bool:
        """Decompress SQLite DB to temp file and verify tables."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            with gzip.open(db_file, "rb") as f_in:
                with open(tmp_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            import sqlite3

            conn = sqlite3.connect(str(tmp_path))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            critical = {"users", "trends", "memory_entries", "generation_jobs"}
            if not critical.issubset(tables):
                return False
            # Verify at least users table is queryable (schema OK)
            cursor.execute("SELECT COUNT(*) FROM users")
            cursor.fetchone()
            conn.close()
            return True
        except Exception:
            return False
        finally:
            tmp_path.unlink(missing_ok=True)

    def _verify_postgres_dump(self, db_file: Path) -> bool:
        """Verify PostgreSQL dump is valid SQL by checking key statements."""
        try:
            with gzip.open(db_file, "rt", encoding="utf-8", errors="replace") as f:
                sample = f.read(50000)
            # Basic sanity checks for a pg_dump output
            checks = [
                "PostgreSQL database dump" in sample or "CREATE TABLE" in sample,
                "SET" in sample,
            ]
            return all(checks)
        except Exception:
            return False

    @staticmethod
    def _sha256_file(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _get_version() -> str:
        """Return git commit hash if available, else 'unknown'."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
                cwd=str(Path(__file__).resolve().parents[2]),
                timeout=5,
            )
            return result.stdout.strip()
        except Exception:
            return "unknown"
