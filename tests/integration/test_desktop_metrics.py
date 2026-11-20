import os
import subprocess
import sys
import time

from desktop_worker.metrics import ProcessTreeObserver, process_inventory
from desktop_worker.supervision import terminate_record


def test_observer_records_current_process_and_owned_child_memory():
    child = subprocess.Popen([getattr(sys, "_base_executable", sys.executable), "-c", "import os,time; x=bytearray(16000000); print(os.getpid(),flush=True); time.sleep(20)"],
                             stdout=subprocess.PIPE, text=True,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    actual_child = int(child.stdout.readline())
    observer = ProcessTreeObserver(os.getpid())
    try:
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            sample = observer.sample()
            if any(p["pid"] == actual_child and p["resident_bytes"] > 16000000 for p in sample["processes"]):
                break
            time.sleep(0.05)
        else:
            raise AssertionError("Observer missed the actual child allocation")
        assert process_inventory()[child.pid] == os.getpid()
        report = observer.report()
        assert report["desktop_os_peak_resident_bytes"] > 0
        assert report["sampled_peak_worker_resident_sum_bytes"] >= 8000000
        attributed = observer.report(actual_child)
        assert attributed["desktop_pid"] == actual_child
        assert attributed["desktop_os_peak_resident_bytes"] >= 16000000
        assert attributed["sampled_peak_worker_resident_sum_bytes"] < report["sampled_peak_worker_resident_sum_bytes"]
        assert attributed["launcher_os_peak_resident_bytes"] > 0
        terminate_record(observer.processes[actual_child].record(), group=False)
        child.wait(timeout=5)
        assert all(p["pid"] != actual_child for p in observer.sample()["processes"])
    finally:
        if actual_child in observer.processes and observer.processes[actual_child].alive():
            terminate_record(observer.processes[actual_child].record(), group=False)
        if child.poll() is None:
            child.kill()
        child.wait(timeout=5)
        observer.close()
        child.stdout.close()
