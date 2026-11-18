"""Create a consistent SQLite backup, or restore one into a new database file."""

from __future__ import annotations

import argparse
from contextlib import closing
from hashlib import sha256
import os
from pathlib import Path
import sqlite3
import tempfile


def snapshot(source: Path, destination: Path) -> str:
    """Publish a checked snapshot atomically, preserving any existing destination."""
    source = source.resolve(strict=True)
    destination = destination.absolute()
    if destination.exists():
        raise FileExistsError(destination)
    descriptor, name = tempfile.mkstemp(prefix=".aeroforge-snapshot-", dir=destination.parent)
    staged = Path(name)
    os.close(descriptor)
    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original:
            with closing(sqlite3.connect(staged)) as copied:
                original.backup(copied)
                if copied.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise ValueError("SQLite integrity check failed")
                if copied.execute("PRAGMA foreign_key_check").fetchone() is not None:
                    raise ValueError("SQLite foreign key check failed")
                copied.execute("PRAGMA journal_mode=DELETE")
        with staged.open("r+b") as data:
            digest = sha256()
            for chunk in iter(lambda: data.read(1024 * 1024), b""):
                digest.update(chunk)
            os.fsync(data.fileno())
        # Both files share a filesystem. The link publishes only the complete,
        # checked database and fails if another writer claims the path first.
        os.link(staged, destination)
        return digest.hexdigest()
    finally:
        staged.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path, help="A new path in an existing directory")
    args = parser.parse_args()
    print(snapshot(args.source, args.destination))


if __name__ == "__main__":
    main()
