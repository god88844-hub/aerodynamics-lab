"""M9 Phase 3 regression tests: the dataset-audit findings are guarded here so
the transcription/consistency regressions can never silently return.

Covers the two M9 findings:
  F1  monotonicity must be evaluated PER VOLTAGE PLANE (mixing planes
      interleaves rows and produced a false decrease at the 820 gf plateau)
  F2  per-row measured voltages are stored, and power == V_measured * I
      holds to publication rounding (<= 0.5 %); plane normalization <= 2 %
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_SCRIPT = REPO_ROOT / "scripts" / "audit_datasets.py"


@pytest.fixture(scope="module")
def audit_report() -> dict:
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location("audit_datasets", AUDIT_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["audit_datasets"] = mod
    spec.loader.exec_module(mod)
    from physics.propulsion.loader import ComponentLibrary

    library = ComponentLibrary(REPO_ROOT / "data" / "components")
    return {
        "mn3508": mod.audit_dataset(library, "tmotor_mn3508_kv380", 0.381),
        "p80": mod.audit_dataset(library, "tmotor_p80iii_kv100", 0.762),
    }


def test_mn3508_consistency_checks_pass(audit_report):
    r = audit_report["mn3508"]
    for f in r["findings"]:
        if isinstance(f.get("status"), str):
            assert f["status"] == "pass", (f["check"], f)


def test_p80_consistency_checks_pass(audit_report):
    r = audit_report["p80"]
    for f in r["findings"]:
        if isinstance(f.get("status"), str):
            assert f["status"] == "pass", (f["check"], f)


def test_p80_measured_voltages_recorded(audit_report):
    """Finding F2: per-row measured voltages must be present as provenance."""
    from physics.propulsion.loader import ComponentLibrary

    library = ComponentLibrary(REPO_ROOT / "data" / "components")
    motor = library.motor("tmotor_p80iii_kv100")
    for row in motor.test_data:
        assert row.voltage_measured_v is not None
        # plane voltage is the normalized nominal
        assert row.voltage_v == pytest.approx(47.9)


def test_p80_figure_of_merit_in_literature_band(audit_report):
    """The bench data must be consistent with momentum theory: the propeller
    figure of merit stays in the 0.45–0.95 literature band across the table."""
    r = audit_report["p80"]
    assert r["fm_values"] is not None
    assert all(0.45 < f < 0.95 for f in r["fm_values"])
    # and remarkably stable across the table (0.80-0.82) — a data-quality signal
    assert max(r["fm_values"]) - min(r["fm_values"]) < 0.05
