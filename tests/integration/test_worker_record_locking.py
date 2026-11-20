"""Real Windows sharing locks; publication must retry or fail without torn data."""
import ctypes
from ctypes import wintypes
import json
import os
import threading
import time

import pytest

from desktop_worker.io import read_control_bytes, write_result

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows file sharing semantics")


def lock_without_delete_share(path, share_mode=1):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateFileW(str(path), 0x80000000, share_mode, None, 3, 0, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    return kernel, handle


def test_atomic_record_retries_a_real_transient_windows_read_lock(tmp_path):
    record = tmp_path / "resource-usage.json"
    write_result(record, {"sequence": 1})
    kernel, handle = lock_without_delete_share(record)
    released = threading.Event()

    def release():
        time.sleep(0.12)
        kernel.CloseHandle(handle)
        released.set()

    thread = threading.Thread(target=release)
    thread.start()
    try:
        write_result(record, {"sequence": 2})
    finally:
        thread.join()
    assert released.is_set()
    assert json.loads(record.read_bytes()) == {"sequence": 2}
    assert not list(tmp_path.glob(".lab-output-*"))


def test_control_reader_retries_a_real_exclusive_windows_lock(tmp_path):
    record = tmp_path / "approved.json"
    write_result(record, {"approved": True})
    kernel, handle = lock_without_delete_share(record, share_mode=0)

    def release():
        time.sleep(0.12)
        kernel.CloseHandle(handle)

    thread = threading.Thread(target=release)
    thread.start()
    try:
        assert json.loads(read_control_bytes(record)) == {"approved": True}
    finally:
        thread.join()


def test_control_reader_fails_bounded_on_persistent_exclusive_lock(tmp_path):
    record = tmp_path / "approved.json"
    write_result(record, {"approved": True})
    original = record.read_bytes()
    kernel, handle = lock_without_delete_share(record, share_mode=0)
    started = time.monotonic()
    try:
        with pytest.raises(PermissionError):
            read_control_bytes(record)
    finally:
        kernel.CloseHandle(handle)
    assert 0.45 <= time.monotonic() - started < 2
    assert record.read_bytes() == original


def test_persistent_windows_lock_fails_bounded_and_preserves_previous_record(tmp_path):
    record = tmp_path / "resource-usage.json"
    write_result(record, {"sequence": 1})
    original = record.read_bytes()
    kernel, handle = lock_without_delete_share(record)
    started = time.monotonic()
    try:
        with pytest.raises(OSError):
            write_result(record, {"sequence": 2})
    finally:
        kernel.CloseHandle(handle)
    assert 0.45 <= time.monotonic() - started < 2
    assert record.read_bytes() == original
    assert not list(tmp_path.glob(".lab-output-*"))
