"""Atomic local worker records, usable without loading numerical dependencies."""

import json
import os
from pathlib import Path
import tempfile
import time


def json_bytes(payload: dict) -> bytes:
    return (json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


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
                if os.name != "nt" or error.winerror not in (5, 32, 33) or time.monotonic() >= deadline:
                    raise
                time.sleep(0.01)
    finally:
        Path(temporary).unlink(missing_ok=True)


def write_started(destination: Path | None) -> None:
    if destination:
        write_result(destination, {"worker_pid": os.getpid()})
