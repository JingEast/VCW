"""Tests for BackupService."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from app.services.backup_service import BackupError, BackupService


class TestBackupService:
    """Unit tests for backup creation, cleanup, and verification."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path: Path):
        """Create a temp SQLite DB and backup directory for each test."""
        self.tmp = tmp_path
        self.db_path = tmp_path / "test.db"
        # Create a small SQLite DB with the critical tables
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        cursor.execute("CREATE TABLE trends (id INTEGER PRIMARY KEY, title TEXT)")
        cursor.execute("CREATE TABLE memory_entries (id INTEGER PRIMARY KEY, content TEXT)")
        cursor.execute("CREATE TABLE generation_jobs (id INTEGER PRIMARY KEY, status TEXT)")
        cursor.execute("INSERT INTO users (name) VALUES ('alice')")
        conn.commit()
        conn.close()

        self.backup_dir = tmp_path / "backups"
        self.db_uri = f"sqlite:///{self.db_path}"
        self.data_dir = tmp_path / "data"
        self.svc = BackupService(
            backup_dir=str(self.backup_dir),
            db_uri=self.db_uri,
            retention_days=7,
            weekly_retention_weeks=4,
            data_dir=str(self.data_dir),
        )

    # ------------------------------------------------------------------
    # Backup creation
    # ------------------------------------------------------------------

    def test_create_backup_sqlite(self):
        path = self.svc.create_backup()
        assert path.exists()
        assert (path / "manifest.json").exists()
        assert (path / "db_dump.sql.gz").exists()

        manifest = json.loads((path / "manifest.json").read_text())
        assert manifest["db_type"] == "sqlite"
        assert "checksums" in manifest
        assert "db_dump.sql.gz" in manifest["checksums"]

    def test_create_backup_generates_checksum(self):
        path = self.svc.create_backup()
        manifest = json.loads((path / "manifest.json").read_text())
        db_checksum = manifest["checksums"]["db_dump.sql.gz"]
        assert len(db_checksum) == 64  # sha256 hex

    def test_create_backup_includes_version(self):
        path = self.svc.create_backup()
        manifest = json.loads((path / "manifest.json").read_text())
        assert "version" in manifest
        # version is either a git hash or "unknown"
        assert manifest["version"] != ""

    def test_create_backup_cleanup_on_failure(self):
        # Point to non-existent DB to force failure
        bad_svc = BackupService(
            backup_dir=str(self.backup_dir),
            db_uri="sqlite:///nonexistent/path.db",
        )
        with pytest.raises(BackupError):
            bad_svc.create_backup()
        # Partial backup dir should be cleaned up
        assert len(list(self.backup_dir.iterdir())) == 0

    # ------------------------------------------------------------------
    # File archiving
    # ------------------------------------------------------------------

    def test_create_backup_archives_files(self, tmp_path: Path):
        # Create some data files to archive
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "edited").mkdir()
        (data_dir / "edited" / "draft.md").write_text("hello")
        (data_dir / "generated").mkdir()
        (data_dir / "generated" / "output.md").write_text("world")
        (data_dir / "prompts_custom.json").write_text('{"key": "value"}')

        svc = BackupService(
            backup_dir=str(self.backup_dir),
            db_uri=self.db_uri,
            data_dir=str(data_dir),
        )
        path = svc.create_backup()
        assert (path / "files.tar.gz").exists()
        manifest = json.loads((path / "manifest.json").read_text())
        assert "files.tar.gz" in manifest["checksums"]

    # ------------------------------------------------------------------
    # Retention cleanup
    # ------------------------------------------------------------------

    def test_cleanup_expired_backups_removes_old(self):
        from datetime import datetime, timezone  # noqa: F401

        # Create fake old backups
        old = self.backup_dir / "20240101_000000"
        old.mkdir(parents=True)
        (old / "manifest.json").write_text("{}")

        recent = self.backup_dir / "20990101_000000"
        recent.mkdir(parents=True)
        (recent / "manifest.json").write_text("{}")

        removed = self.svc.cleanup_expired_backups()
        assert old in removed
        assert not old.exists()
        assert recent.exists()

    def test_cleanup_keeps_sunday_weekly_backups(self):
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        # Find a recent Sunday (2 weeks ago)
        days_since_sunday = now.weekday() + 1  # Monday=0 -> need +1 to get to previous Sunday
        recent_sunday = now - timedelta(days=days_since_sunday + 14)
        sunday_name = recent_sunday.strftime("%Y%m%d_000000")

        sunday = self.backup_dir / sunday_name
        sunday.mkdir(parents=True)
        (sunday / "manifest.json").write_text("{}")

        # Monday from same week (should be removed)
        monday_dt = recent_sunday + timedelta(days=1)
        monday_name = monday_dt.strftime("%Y%m%d_000000")
        monday = self.backup_dir / monday_name
        monday.mkdir(parents=True)
        (monday / "manifest.json").write_text("{}")

        removed = self.svc.cleanup_expired_backups()
        assert monday in removed
        assert sunday not in removed
        assert sunday.exists()

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def test_verify_backup_checksums_ok(self):
        path = self.svc.create_backup()
        result = self.svc.verify_backup(path)
        assert result["checksums_ok"] is True

    def test_verify_backup_db_restore_ok(self):
        path = self.svc.create_backup()
        result = self.svc.verify_backup(path)
        assert result["db_restore_ok"] is True
        assert result["overall"] is True

    def test_verify_backup_detects_tampering(self):
        path = self.svc.create_backup()
        # Tamper with the DB file
        db_file = path / "db_dump.sql.gz"
        with open(db_file, "ab") as f:
            f.write(b"TAMPER")
        result = self.svc.verify_backup(path)
        assert result["checksums_ok"] is False
        assert result["overall"] is False

    def test_verify_backup_missing_file(self):
        path = self.svc.create_backup()
        # Remove the DB file
        (path / "db_dump.sql.gz").unlink()
        result = self.svc.verify_backup(path)
        assert result["checksums_ok"] is False
        assert "missing" in str(result["details"]["db_dump.sql.gz"])

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def test_list_backups_sorted(self):
        self.svc.create_backup()
        import time

        time.sleep(0.1)
        self.svc.create_backup()
        backups = self.svc.list_backups()
        assert len(backups) == 2
        assert backups[0]["name"] > backups[1]["name"]

    def test_list_backups_empty(self):
        svc = BackupService(backup_dir=str(self.tmp / "empty"), db_uri=self.db_uri)
        assert svc.list_backups() == []

    # ------------------------------------------------------------------
    # PostgreSQL unsupported locally
    # ------------------------------------------------------------------

    def test_postgres_dump_without_pg_dump_raises(self):
        svc = BackupService(
            backup_dir=str(self.backup_dir),
            db_uri="postgresql://user:pass@localhost/db",
        )
        with pytest.raises(BackupError) as exc_info:
            svc.create_backup()
        assert "pg_dump" in str(exc_info.value)
