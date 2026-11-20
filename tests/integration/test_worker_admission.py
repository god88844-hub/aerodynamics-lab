import math
from pathlib import Path

import pytest

from desktop_worker.resources import (GIB, MIB, ResourceBudget, admission, capacity_snapshot,
                                      runtime_failure, workspace_size)


def capacity(total=8 * GIB, available=4 * GIB, disk=8 * GIB):
    return {"total_bytes": total, "available_bytes": available, "disk_free_bytes": disk}


def test_admission_preserves_requested_allowances_and_reserves_headroom():
    request = ResourceBudget()
    result = admission(request, capacity(), wall_limit_s=30)
    assert result["status"] == "admitted"
    assert result["requested"] == request.document()
    assert result["effective"]["memory_bytes"] == GIB
    assert result["effective"]["wall_time_s"] == 30
    assert result["reserve_bytes"] == GIB
    assert result["effective"]["os_hard_memory_cap"] is False
    assert admission(request, capacity(available=GIB))["reasons"] == ["insufficient_memory_headroom"]
    assert admission(request, capacity(disk=128 * MIB))["reasons"] == ["insufficient_workspace_headroom"]
    # Warm engines have already consumed resident memory; only the allowance's growth is new.
    assert admission(request, capacity(available=GIB + 256 * MIB), resident_bytes=800 * MIB)["status"] == "admitted"


@pytest.mark.parametrize("change", [{"memory_bytes": True}, {"workspace_bytes": 0},
    {"wall_time_s": math.nan}, {"wall_time_s": math.inf}, {"wall_time_s": True},
    {"execution": "remote"}, {"contract_version": "unknown"}])
def test_invalid_or_unsupported_budget_is_refused(change):
    with pytest.raises((ValueError, TypeError)):
        ResourceBudget.from_dict({**ResourceBudget().document(), **change})


def test_runtime_budget_and_pressure_failures_are_explicit():
    request = ResourceBudget()
    assert runtime_failure(request, capacity(), GIB + 1, 0) == "memory_budget_exceeded"
    assert runtime_failure(request, capacity(), 0, 256 * MIB + 1) == "workspace_budget_exceeded"
    assert runtime_failure(request, capacity(available=512 * MIB), 0, 0) == "memory_headroom_exhausted"
    assert runtime_failure(request, capacity(disk=32 * MIB), 0, 0) == "workspace_headroom_exhausted"


def test_real_capacity_and_controlled_workspace_observation(tmp_path):
    observed = capacity_snapshot(tmp_path)
    assert observed["total_bytes"] >= observed["available_bytes"] > 0
    assert observed["disk_free_bytes"] > 0
    (tmp_path / "bytes.bin").write_bytes(b"abc")
    assert workspace_size(tmp_path) == 3
