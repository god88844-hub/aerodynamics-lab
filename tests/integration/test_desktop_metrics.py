import os
import subprocess
import sys
import time

from desktop_worker.metrics import ProcessTreeObserver, process_inventory


def test_observer_records_current_process_and_owned_child_memory():
    child = subprocess.Popen([getattr(sys, "_base_executable", sys.executable), "-c", "import time; x=bytearray(16000000); time.sleep(20)"],
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    observer = ProcessTreeObserver(os.getpid())
    try:
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            sample = observer.sample()
            if any(p["pid"] == child.pid and p["resident_bytes"] > 8000000 for p in sample["processes"]):
                break
            time.sleep(0.05)
        else:
            raise AssertionError("Observer missed the actual child allocation")
        assert process_inventory()[child.pid] == os.getpid()
        report = observer.report()
        assert report["desktop_os_peak_resident_bytes"] > 0
        assert report["sampled_peak_worker_resident_sum_bytes"] >= 8000000
        child.terminate()
        child.wait(timeout=5)
        assert all(p["pid"] != child.pid for p in observer.sample()["processes"])
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=5)
        observer.close()
