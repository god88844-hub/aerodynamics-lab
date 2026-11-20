"""Versioned local CAD admission policy, independent of native/Pydantic imports."""

import ctypes
from dataclasses import asdict, dataclass
import math
import os
from pathlib import Path
import shutil

MIB = 1024**2
GIB = 1024**3
VERSION = "local_cad_resources_1"


@dataclass(frozen=True)
class ResourceBudget:
    contract_version: str = VERSION
    memory_bytes: int = GIB
    workspace_bytes: int = 256 * MIB
    wall_time_s: float = 60.0

    def __post_init__(self):
        if self.contract_version != VERSION:
            raise ValueError("Unsupported local resource contract")
        for key, lower in (("memory_bytes", 16 * MIB), ("workspace_bytes", MIB)):
            value = getattr(self, key)
            if type(value) is not int or not lower <= value <= 1024 * GIB:
                raise ValueError(f"{key} must be an integer between {lower} and {1024 * GIB}")
        if isinstance(self.wall_time_s, bool) or not isinstance(self.wall_time_s, (int, float)) or not math.isfinite(self.wall_time_s) or not 0.01 <= self.wall_time_s <= 900:
            raise ValueError("wall_time_s must be finite and between 0.01 and 900")

    @classmethod
    def from_dict(cls, document):
        if not isinstance(document, dict):
            raise ValueError("Resource request must be an object")
        if set(document) - set(cls.__dataclass_fields__):
            raise ValueError("Unknown local resource field")
        return cls(**document)

    def document(self):
        return asdict(self)


def memory_capacity() -> dict:
    if os.name == "nt":
        class Status(ctypes.Structure):
            _fields_ = [("length", ctypes.c_uint32), ("load", ctypes.c_uint32),
                        *[(key, ctypes.c_uint64) for key in ("total", "available", "page_total", "page_available", "virtual_total", "virtual_available", "extended")]]
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(Status)]
        kernel.GlobalMemoryStatusEx.restype = ctypes.c_int
        status = Status()
        status.length = ctypes.sizeof(status)
        if not kernel.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"total_bytes": status.total, "available_bytes": status.available}
    values = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, _, value = line.partition(":")
        if key in ("MemTotal", "MemAvailable"):
            values[key] = int(value.split()[0]) * 1024
    return {"total_bytes": values["MemTotal"], "available_bytes": values["MemAvailable"]}


def capacity_snapshot(directory: Path) -> dict:
    return {**memory_capacity(), "disk_free_bytes": shutil.disk_usage(directory).free}


def workspace_size(directory: Path) -> int:
    total = 0
    for path in directory.rglob("*"):
        try:
            if path.is_file():
                total += path.stat().st_size
        except FileNotFoundError:  # a native temporary file can disappear during observation
            pass
    return total


def admission(budget: ResourceBudget, capacity: dict, *, resident_bytes=0, workspace_bytes=0,
              wall_limit_s=900) -> dict:
    if any(type(capacity.get(key)) is not int or capacity[key] < 0
           for key in ("total_bytes", "available_bytes", "disk_free_bytes")):
        raise ValueError("A complete nonnegative capacity observation is required")
    reserve = max(GIB, capacity["total_bytes"] // 8)
    memory_growth = max(0, budget.memory_bytes - resident_bytes)
    workspace_growth = max(0, budget.workspace_bytes - workspace_bytes)
    reasons = []
    if resident_bytes > budget.memory_bytes:
        reasons.append("memory_budget_exceeded")
    if workspace_bytes > budget.workspace_bytes:
        reasons.append("workspace_budget_exceeded")
    if capacity["available_bytes"] < memory_growth + reserve:
        reasons.append("insufficient_memory_headroom")
    if capacity["disk_free_bytes"] < workspace_growth + 64 * MIB:
        reasons.append("insufficient_workspace_headroom")
    return {"contract_version": VERSION, "status": "refused" if reasons else "admitted", "reasons": reasons,
            "requested": budget.document(), "capacity": capacity, "reserve_bytes": reserve,
            "additional_memory_bytes": memory_growth, "additional_workspace_bytes": workspace_growth,
            "estimate_basis": "declared bounded CAD allowance; not a validated predictor of arbitrary native jobs",
            "effective": {**budget.document(), "wall_time_s": min(budget.wall_time_s, wall_limit_s),
                          "execution": "local", "memory_accounting": "sampled_process_tree_resident_sum",
                          "memory_sample_s": 0.1, "os_hard_memory_cap": False,
                          "cpu_limit": None, "gpu_limit": None}}


def runtime_failure(budget: ResourceBudget, capacity: dict, resident_bytes: int, workspace_bytes: int):
    if resident_bytes > budget.memory_bytes:
        return "memory_budget_exceeded"
    if workspace_bytes > budget.workspace_bytes:
        return "workspace_budget_exceeded"
    if capacity["available_bytes"] < max(GIB, capacity["total_bytes"] // 8):
        return "memory_headroom_exhausted"
    if capacity["disk_free_bytes"] < 64 * MIB:
        return "workspace_headroom_exhausted"
    return None
