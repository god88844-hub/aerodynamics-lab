"""P0A-026: Fail-closed registration of frozen component and multirotor validation protocols."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from physics.validation.protocol_registry import load_frozen_protocol_catalog, register_validation_protocol

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "data" / "research" / "frozen_protocols.json"


def test_frozen_protocol_catalog_loads_and_binds_all_tolerances():
    loaded = load_frozen_protocol_catalog(CATALOG)
    assert len(loaded["protocols"]) == 2
    for entry in loaded["protocols"]:
        assert entry["independently_approved"] is False
        assert entry["decision_equivalent_to_physical_testing"] is False
        assert set(entry["tolerance_bindings"]) == {"M21", "M22", "M23", "M24", "M25", "M26", "M27"}
        assert len(entry["calibration_experiments"]) >= 1
        assert len(entry["holdout_experiments"]) >= 2
        assert len(entry["frozen_protocol_sha256"]) == 64


def test_missing_holdout_calibration_or_tolerance_refuses_registration():
    raw = json.loads(CATALOG.read_text(encoding="utf-8"))["protocols"][0]
    proto = dict(raw["protocol"])
    tol = dict(raw["tolerance_bindings"])

    # Missing M27 tolerance binding fails closed
    tol_missing = {k: v for k, v in tol.items() if k != "M27"}
    with pytest.raises(ValueError, match="M27"):
        register_validation_protocol(proto, tolerance_bindings=tol_missing)

    # Missing calibration group fails closed
    no_cal = dict(proto, experiments=[e for e in proto["experiments"] if e["role"] == "holdout"])
    with pytest.raises(ValueError, match="calibration"):
        register_validation_protocol(no_cal, tolerance_bindings=tol)

    # Fewer than two holdout experiments fails closed
    one_hold = dict(proto, experiments=proto["experiments"][:2])
    with pytest.raises(ValueError, match="two held-out"):
        register_validation_protocol(one_hold, tolerance_bindings=tol)


def test_cli_register_protocol_and_reconcile_registry(tmp_path):
    in_path = tmp_path / "req.json"
    out_path = tmp_path / "out.json"
    in_path.write_text(json.dumps({"catalog_path": str(CATALOG)}), encoding="utf-8")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/lab_project.py"), "register-protocol", str(in_path), str(out_path)],
        check=True,
        cwd=ROOT,
    )
    out = json.loads(out_path.read_text(encoding="utf-8"))
    assert len(out["protocols"]) == 2
    subprocess.run([sys.executable, str(ROOT / "scripts/reconcile_registry.py"), "--check"], check=True, cwd=ROOT)
