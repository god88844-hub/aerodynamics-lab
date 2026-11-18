"""Recover committed WAL data and refuse failed or destructive publication."""

from hashlib import sha256
import sqlite3
from unittest.mock import patch

import pytest

from app.persistence.snapshot import snapshot


def test_recover_wal_snapshot_and_preserve_existing_destination(tmp_path):
    source = tmp_path / "live.db"
    backup = tmp_path / "backup.db"
    restored = tmp_path / "restored.db"
    with sqlite3.connect(source) as live:
        live.execute("PRAGMA journal_mode=WAL")
        live.execute("CREATE TABLE records (id INTEGER PRIMARY KEY, value TEXT)")
        live.execute("INSERT INTO records VALUES (1, 'committed')")
        live.commit()
        live.execute("INSERT INTO records VALUES (2, 'uncommitted')")
        digest = snapshot(source, backup)
        assert digest == sha256(backup.read_bytes()).hexdigest()
        snapshot(backup, restored)
        with sqlite3.connect(restored) as recovered:
            assert recovered.execute("SELECT * FROM records").fetchall() == [(1, "committed")]
            assert recovered.execute("PRAGMA journal_mode").fetchone() == ("delete",)
        before = backup.read_bytes()
        with pytest.raises(FileExistsError):
            snapshot(source, backup)
        assert backup.read_bytes() == before
    live.close()


def test_failed_snapshot_never_publishes_or_creates_missing_source(tmp_path):
    source, target = tmp_path / "source.db", tmp_path / "backup.db"
    with pytest.raises(FileNotFoundError):
        snapshot(source, target)
    assert not source.exists() and not target.exists()
    source.write_bytes(b"corrupted database")
    with pytest.raises(sqlite3.DatabaseError):
        snapshot(source, target)
    assert not target.exists()
    assert list(tmp_path.glob(".aeroforge-snapshot-*")) == []


def test_destination_claimed_during_backup_is_preserved(tmp_path):
    source, target = tmp_path / "source.db", tmp_path / "backup.db"
    with sqlite3.connect(source) as live:
        live.execute("CREATE TABLE records (id INTEGER)")
    live.close()
    def competing_writer(*args):
        target.write_bytes(b"another backup")
        raise FileExistsError(target)
    with patch("app.persistence.snapshot.os.link", side_effect=competing_writer):
        with pytest.raises(FileExistsError):
            snapshot(source, target)
    assert target.read_bytes() == b"another backup"
    assert list(tmp_path.glob(".aeroforge-snapshot-*")) == []
