"""P0A-038 partial verification: 16 GB native 200-part benchmark receipt + low-memory refusal + open hardware gate."""

from __future__ import annotations

import json
from pathlib import Path

from desktop_worker.resources import GIB, ResourceBudget, admission, capacity_snapshot

ROOT = Path(__file__).resolve().parents[2]


def test_16gb_native_200part_observation_meets_local_fps_and_latency_targets() -> None:
    obs_path = ROOT / "docs/prototypes/measurements/native-16gb/native_200part_observation.json"
    obs = json.loads(obs_path.read_text(encoding="utf-8"))
    assert obs["parts"] == 200
    assert obs["frames"] == 600
    assert obs["mean_fps"] >= 30.0
    assert obs["p95_ms"] <= 33.333333
    assert obs["peak_working_set_bytes"] > 0


def test_p0a_038_remains_open_pending_distinct_8gb_and_tier2_machines() -> None:
    plan = json.loads((ROOT / "docs/planning/tasks.json").read_text(encoding="utf-8-sig"))
    task = next(t for t in plan["tasks"] if t["id"] == "P0A-038")
    assert task["status"] == "todo"
    proof = (ROOT / "docs/acceptance/P0A-038.md").read_text(encoding="utf-8")
    assert "8 GB integrated-GPU machine" in proof
    assert "Tier 2 dedicated-GPU machine" in proof


def test_host_capacity_and_low_memory_refusal_contract(tmp_path: Path) -> None:
    cap = capacity_snapshot(tmp_path)
    assert cap["total_bytes"] >= cap["available_bytes"] > 0
    decision = admission(
        ResourceBudget(),
        {"total_bytes": cap["total_bytes"], "available_bytes": GIB, "disk_free_bytes": cap["disk_free_bytes"]},
    )
    assert decision["status"] == "refused"
    assert decision["reasons"] == ["insufficient_memory_headroom"]
