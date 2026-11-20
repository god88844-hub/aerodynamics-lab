"""Read-only local process observation; sampled resident sums include shared pages."""

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import sys
import time

from desktop_worker.supervision import ProcessRef


def process_inventory() -> dict[int, int]:
    if os.name == "nt":
        class Entry(ctypes.Structure):
            _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD), ("pid", wintypes.DWORD),
                        ("heap", ctypes.c_size_t), ("module", wintypes.DWORD), ("threads", wintypes.DWORD),
                        ("parent", wintypes.DWORD), ("priority", wintypes.LONG), ("flags", wintypes.DWORD),
                        ("name", wintypes.WCHAR * 260)]
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        for name in ("Process32FirstW", "Process32NextW"):
            function = getattr(kernel, name)
            function.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
            function.restype = wintypes.BOOL
        handle = kernel.CreateToolhelp32Snapshot(2, 0)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        result = {}
        try:
            entry = Entry()
            entry.size = ctypes.sizeof(entry)
            more = kernel.Process32FirstW(handle, ctypes.byref(entry))
            while more:
                result[entry.pid] = entry.parent
                more = kernel.Process32NextW(handle, ctypes.byref(entry))
            if ctypes.get_last_error() != 18:
                raise ctypes.WinError(ctypes.get_last_error())
            return result
        finally:
            kernel.CloseHandle(handle)
    if not sys.platform.startswith("linux"):
        raise ValueError("Memory observation currently supports Windows and Linux")
    result = {}
    for directory in Path("/proc").iterdir():
        if directory.name.isdigit():
            try:
                fields = (directory / "stat").read_text().rsplit(")", 1)[1].split()
                result[int(directory.name)] = int(fields[1])
            except (FileNotFoundError, ProcessLookupError):
                pass
    return result


def resident_memory(process: ProcessRef) -> dict:
    if os.name == "nt":
        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD),
                        *[(key, ctypes.c_size_t) for key in ("peak", "resident", "qp", "q", "np", "n", "page", "page_peak", "private")]]
        function = process.kernel.K32GetProcessMemoryInfo
        function.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        function.restype = wintypes.BOOL
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        if not function(process.handle, ctypes.byref(counters), counters.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"resident_bytes": counters.resident, "os_peak_resident_bytes": counters.peak,
                "private_commit_bytes": counters.private}
    values = {}
    for line in Path(f"/proc/{process.pid}/status").read_text().splitlines():
        key, _, value = line.partition(":")
        if key in ("VmRSS", "VmHWM"):
            values[key] = int(value.split()[0]) * 1024
    return {"resident_bytes": values.get("VmRSS", 0), "os_peak_resident_bytes": values.get("VmHWM", 0),
            "private_commit_bytes": None}


class ProcessTreeObserver:
    def __init__(self, root_pid: int):
        self.root_pid = root_pid
        self.processes = {root_pid: ProcessRef(root_pid)}
        self.started = time.monotonic()
        self.samples = []

    def sample(self):
        start = time.monotonic()
        inventory = process_inventory()
        alive = {pid for pid, ref in self.processes.items() if ref.alive()}
        while True:
            new = {pid for pid, parent in inventory.items() if parent in alive and pid not in self.processes}
            if not new:
                break
            for pid in new:
                try:
                    ref = ProcessRef(pid)
                    self.processes[pid] = ref
                    if ref.alive():
                        alive.add(pid)
                except (ProcessLookupError, FileNotFoundError):
                    pass
                inventory.pop(pid, None)
        records = []
        for pid, ref in self.processes.items():
            if not ref.alive():
                continue
            try:
                records.append({**ref.record(), **resident_memory(ref), "desktop": pid == self.root_pid})
            except OSError:
                if ref.alive():
                    raise  # an inaccessible process is not a zero-memory measurement
        sample = {"elapsed_s": time.monotonic() - self.started, "processes": records,
                  "worker_resident_bytes": sum(p["resident_bytes"] for p in records if not p["desktop"]),
                  "observer_s": time.monotonic() - start}
        self.samples.append(sample)
        return sample

    def report(self, desktop_pid=None):
        desktop_pid = self.root_pid if desktop_pid is None else desktop_pid
        if desktop_pid not in self.processes:
            raise ValueError("The actual desktop process was not observed")
        for sample in self.samples:
            for process in sample["processes"]:
                process["desktop"] = process["pid"] == desktop_pid
                process["launcher"] = process["pid"] == self.root_pid and desktop_pid != self.root_pid
            sample["worker_resident_bytes"] = sum(p["resident_bytes"] for p in sample["processes"]
                                                   if not p["desktop"] and not p["launcher"])
        records = [p for sample in self.samples for p in sample["processes"]]
        return {"method": "Windows working set / Linux VmRSS; 100 ms requested sampling",
            "desktop_pid": desktop_pid, "root_launcher_pid": self.root_pid,
            "limitations": "Resident sums double-count shared pages. Short-lived processes or peaks between samples may be missed. No GPU or unique physical-memory accounting; no OS memory cap.",
            "desktop_os_peak_resident_bytes": max((p["os_peak_resident_bytes"] for p in records if p["desktop"]), default=0),
            "launcher_os_peak_resident_bytes": max((p["os_peak_resident_bytes"] for p in records if p["launcher"]), default=0),
            "sampled_peak_worker_resident_sum_bytes": max((s["worker_resident_bytes"] for s in self.samples), default=0),
            "sample_count": len(self.samples), "samples": self.samples,
            "observed_processes": [ref.record() for ref in self.processes.values()]}

    def close(self):
        for ref in self.processes.values():
            ref.close()
