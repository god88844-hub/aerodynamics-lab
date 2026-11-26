"""Atomic local worker records, usable without loading numerical dependencies."""

import json
import os
from pathlib import Path
import tempfile
import time


def json_bytes(payload: dict) -> bytes:
    return (json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _windows_access_lock(error: OSError) -> bool:
    winerror = getattr(error, "winerror", None)
    return os.name == "nt" and (winerror in (5, 32, 33) or (winerror is None and error.errno == 13))


def unlink_control_record(path: Path) -> None:
    """Retire a control marker after transient readers release their Windows handles."""
    deadline = time.monotonic() + 0.5
    while True:
        try:
            path.unlink(missing_ok=True)
            return
        except OSError as error:
            if not _windows_access_lock(error) or time.monotonic() >= deadline:
                raise
            time.sleep(0.01)


MAX_CONTROL_RECORD_BYTES = 1024 * 1024


def read_control_bytes(path: Path) -> bytes:
    """Read one bounded record; tolerate only brief Windows sharing/access locks."""
    deadline = time.monotonic() + 0.5
    while True:
        try:
            with path.open("rb") as stream:
                raw = stream.read(MAX_CONTROL_RECORD_BYTES + 1)
            break
        except PermissionError as error:
            # CPython's CRT open can report only EACCES, without winerror.
            if not _windows_access_lock(error) or time.monotonic() >= deadline:
                raise
            time.sleep(0.01)
    if len(raw) > MAX_CONTROL_RECORD_BYTES:
        raise ValueError("Worker control record is oversized")
    return raw


def write_result(destination: Path, payload: dict) -> None:
    content = json_bytes(payload).decode("utf-8")
    descriptor, temporary = tempfile.mkstemp(prefix=".lab-output-", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        # Windows readers may briefly hold a handle without FILE_SHARE_DELETE.
        # The temporary writer is closed; retry only those sharing/access errors.
        # A persistent lock still fails, preserving the previous complete record.
        deadline = time.monotonic() + 0.5
        while True:
            try:
                os.replace(temporary, destination)
                break
            except OSError as error:
                if not _windows_access_lock(error) or time.monotonic() >= deadline:
                    raise
                time.sleep(0.01)
    finally:
        Path(temporary).unlink(missing_ok=True)


def write_started(destination: Path | None) -> None:
    if destination:
        write_result(destination, {"worker_pid": os.getpid()})
