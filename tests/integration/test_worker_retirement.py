"""Windows exit signaling must decide retirement, while live failures still fail."""
import os
import subprocess
import sys
import threading
import time

import pytest

from desktop_worker import supervision

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows process handles")


def owned_process():
    child = subprocess.Popen([getattr(sys, "_base_executable", sys.executable), "-c", "import time; time.sleep(60)"],
                             creationflags=subprocess.CREATE_NO_WINDOW)
    reference = supervision.ProcessRef(child.pid)
    return child, reference


def test_nonzero_tree_command_accepts_verified_delayed_process_exit(monkeypatch):
    child, reference = owned_process()
    thread = threading.Thread(target=lambda: (time.sleep(0.12), child.terminate()))
    # Controlled command failure while the real owned process is exiting asynchronously.
    monkeypatch.setattr(supervision.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 128, b"", b"already terminating"))
    thread.start()
    try:
        supervision.terminate_record(reference.record(), group=True)
        assert not reference.alive()
    finally:
        thread.join()
        if child.poll() is None:
            child.kill()
        child.wait(timeout=5)
        reference.close()


def test_failed_command_with_live_owned_process_is_not_cleanup_success(monkeypatch):
    child, reference = owned_process()
    monkeypatch.setattr(supervision.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, b"", b"denied"))
    started = time.monotonic()
    try:
        with pytest.raises(OSError, match="owned worker process tree"):
            supervision.terminate_record(reference.record(), group=True)
        assert reference.alive()
        assert time.monotonic() - started < 2
    finally:
        child.kill()
        child.wait(timeout=5)
        reference.close()
