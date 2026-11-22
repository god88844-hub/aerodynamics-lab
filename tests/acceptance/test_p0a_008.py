"""P0A-008 — diagnose the UIUC signed-thrust disagreement (diagnosis only).

The M24 UIUC benchmark recorded exactly one CT sign disagreement: the 6,018
RPM holdout sweep row at J = 0.671, where the source measures CT = -0.0001
and the RPM-aware interpolator predicts a small positive CT. This task
reproduces the row from the pinned sources and audits every candidate cause
one by one; it changes NO physics behavior (diagnosis only).

CI-unconditional tests assert the committed evidence: the frozen results
artifact, the diagnosis artifact (whose arithmetic is re-derivable offline
from its own inputs), the resolution argument, and the structural fact that
the prediction path contains no unit/axis conversion at all. The opt-in test
(environment variable AEROFORGE_UIUC_SWEEPS pointing at a local directory
holding the six pinned sweep files) re-hashes the sources, re-runs the frozen
benchmark bit-identically, and re-derives every diagnostic value live.

Reference: docs/acceptance/P0A-008.md,
docs/campaigns/M24_2_6_UIUC_AXIAL_SWEEPS.md,
docs/campaigns/m24_uiuc_axial_sweeps_freeze.json,
docs/campaigns/m24_uiuc_axial_sweeps_results.json,
docs/campaigns/m24_uiuc_sign_disagreement_diagnosis.json.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FREEZE = REPO_ROOT / "docs/campaigns/m24_uiuc_axial_sweeps_freeze.json"
RESULTS = REPO_ROOT / "docs/campaigns/m24_uiuc_axial_sweeps_results.json"
DIAGNOSIS = REPO_ROOT / "docs/campaigns/m24_uiuc_sign_disagreement_diagnosis.json"
BENCH_SCRIPT = REPO_ROOT / "scripts/benchmark_uiuc_axial_sweeps.py"
REGISTRY = REPO_ROOT / "data/research/registry.json"
SWEEP_DIR = os.environ.get("AEROFORGE_UIUC_SWEEPS", "")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def results() -> dict:
    return _load(RESULTS)


@pytest.fixture(scope="module")
def diagnosis() -> dict:
    return _load(DIAGNOSIS)


# ---------------------------------------------------------------------------
# The frozen baseline records exactly one CT sign disagreement
# ---------------------------------------------------------------------------


def test_frozen_results_record_one_sign_disagreement(results):
    assert results["rows_scored"] == 42
    sweeps = {r["rpm"]: r for r in results["heldout_sweeps"]}
    for rpm in (5000.0, 6005.0):
        assert sweeps[rpm]["measured_nonpositive_ct"] == 0
        assert sweeps[rpm]["thrust_sign_disagreements"]["axial_interpolator"] == 0
    offending = sweeps[6018.0]
    assert offending["measured_nonpositive_ct"] == 1
    assert offending["thrust_sign_disagreements"] == {
        "axial_interpolator": 1, "advance_ratio_only": 0, "static_reference": 1}


# ---------------------------------------------------------------------------
# The diagnosis artifact pins the exact row and predictions (self-consistent)
# ---------------------------------------------------------------------------


def _mix(low: float, high: float, weight: float) -> float:
    """Same algebraic form as the benchmark's mix(): low + weight*(high-low)."""
    return low + weight * (high - low)


def test_diagnosis_pins_the_exact_row(diagnosis):
    assert diagnosis["row"] == {"rpm": 6018.0, "j": 0.671,
                                "measured_ct": -0.0001, "measured_cp": 0.0085}
    src = diagnosis["source"]
    assert src["offending_file"] == "apce_10x5_kt0824_6018.txt"
    assert src["offending_file_sha256"] == \
        "9f8a6f9c8775a8cf2334b7b8a6f75b9c4ebbd0ad7474da4938de05557c0278bb"
    # The freeze binds to the same hash.
    freeze = _load(FREEZE)
    holdout = {h["file"]: h["sha256"] for h in freeze["holdout"]}
    assert holdout[src["offending_file"]] == src["offending_file_sha256"]


def test_predictions_rederive_from_the_artifacts_own_inputs(diagnosis):
    """The pinned predicted CT is re-derivable offline from the artifact's own
    interpolation inputs (no external data needed) — the blend arithmetic and
    the zero-crossing chain are self-consistent."""
    inputs = diagnosis["interpolation_inputs"]
    w = inputs["rpm_blend_weight"]
    lo = inputs["low_plane"]["interpolated_ct"]
    hi = inputs["high_plane"]["interpolated_ct"]
    predicted = diagnosis["predictions"]["axial_interpolator_ct"]
    assert predicted == pytest.approx(_mix(lo, hi, w), rel=1e-12)
    assert w == pytest.approx((6018.0 - 4005.0) / (6708.5 - 4005.0), rel=1e-15)
    crossings = diagnosis["zero_ct_crossings_j"]
    model_crossing = _mix(crossings["low_plane"], crossings["high_plane"], w)
    assert model_crossing == pytest.approx(crossings["rpm_blended_model"], rel=1e-12)
    assert crossings["model_minus_measured"] == pytest.approx(
        crossings["rpm_blended_model"] - crossings["measured_6018_sweep"], abs=1e-15)


def test_diagnosis_values_match_committed_magnitudes(diagnosis):
    predictions = diagnosis["predictions"]
    assert predictions["axial_interpolator_ct"] == pytest.approx(+0.000217845, abs=1e-9)
    assert predictions["advance_ratio_only_ct"] == pytest.approx(-0.000770588, abs=1e-9)
    assert predictions["static_reference_ct"] == pytest.approx(+0.098022744, abs=1e-9)
    assert predictions["signed_error_axial_ct"] == pytest.approx(+0.000317845, abs=1e-9)
    crossings = diagnosis["zero_ct_crossings_j"]
    assert crossings["low_plane"] == pytest.approx(0.6559365080, abs=1e-9)
    assert crossings["high_plane"] == pytest.approx(0.6776666667, abs=1e-9)
    assert crossings["measured_6018_sweep"] == pytest.approx(0.6704666667, abs=1e-9)
    assert crossings["rpm_blended_model"] == pytest.approx(0.6721165743, abs=1e-9)
    assert crossings["model_minus_measured"] == pytest.approx(0.0016499077, abs=1e-9)


# ---------------------------------------------------------------------------
# Resolution argument: the measured CT is exactly -1 count of the source format
# ---------------------------------------------------------------------------


def test_measured_ct_is_one_count_of_the_source_resolution(diagnosis):
    resolution = diagnosis["resolution"]
    assert resolution["table_ct_decimal_places"] == 4
    assert resolution["one_count_ct"] == pytest.approx(0.0001)
    assert resolution["measured_ct_in_counts"] == pytest.approx(-1.0)
    # The neighbors straddle the real zero crossing: the offending row is the
    # first sampled point past it, not a physical negative-thrust regime.
    neighbors = diagnosis["neighbors"]
    assert [n[1] > 0 for n in neighbors] == [True, False, False]
    assert neighbors[0][1] == pytest.approx(+0.0044)  # J = 0.647
    assert neighbors[2][1] == pytest.approx(-0.0048)  # J = 0.697
    # The model-vs-measured crossing offset is 0.25 % of J — two to three
    # sample spacings; the sign call at this row is decided inside the
    # source's resolution.
    offset = diagnosis["zero_ct_crossings_j"]["model_minus_measured"]
    assert 0.0 < offset < 0.002
    assert offset / 0.671 == pytest.approx(0.00246, abs=1e-3)


def test_physical_scale_is_declared_estimate_only(diagnosis):
    scale = diagnosis["physical_scale_unverified_estimate"]
    assert scale["marked"].startswith("UNVERIFIED_ESTIMATE")
    assert scale["assumed_density_kg_m3"] == pytest.approx(1.225)
    assert scale["rev_per_s"] == pytest.approx(6018.0 / 60.0)
    assert scale["diameter_m"] == pytest.approx(10 * 0.0254)
    # One table count of CT at this RPM is ~0.5 gf; the signed error ~1.7 gf.
    assert 0.0 < scale["one_count_thrust_n"] < 0.01
    assert scale["signed_error_thrust_n"] < 10.0 * scale["one_count_thrust_n"]


# ---------------------------------------------------------------------------
# Structural audit: no unit/axis conversion exists in the prediction path
# ---------------------------------------------------------------------------


def test_prediction_path_has_no_unit_or_axis_conversion():
    """The benchmark interpolates the publisher's OWN signed CT/J columns:
    read_table returns the raw file floats, and the only RPM use is a
    dimensionless blend weight. Conventions therefore cannot alter the sign —
    asserted structurally against the script text."""
    text = BENCH_SCRIPT.read_text(encoding="utf-8")
    # The RPM blend weight is the sole RPM use in the prediction path.
    assert "weight = (rpm - low_rpm) / (high_rpm - low_rpm)" in text
    # No density, diameter, rotational-speed or force-scaling vocabulary.
    lowered = text.lower()
    for banned in ("rho", "density", "diameter", "0.0254", "rad/s",
                   "newton", "gf", "1.225", "math.pi", "np."):
        assert banned not in lowered, banned
    # Predictions are pure linear interpolation of the source columns.
    assert "values[:3]" in text  # read_table passes the raw publisher floats
    assert '("J", "CT", "CP", "eta")' in text  # the publisher's own header


def test_root_cause_and_repair_spec_recorded(diagnosis):
    assert diagnosis["root_cause"] == "resolution_limited_zero_crossing_straddle"
    assert "Not a code/sign/unit defect" in diagnosis["root_cause_statement"]
    spec = diagnosis["repair_spec_for_p0a_009"]
    assert any("resolution" in s and "limited" in s for s in spec)
    assert any("per-row predicted values" in s for s in spec)
    assert any("Predeclare" in s for s in spec)


def test_registry_records_the_diagnosis_outcome():
    registry = _load(REGISTRY)

    def find(obj, key):
        if isinstance(obj, dict):
            if obj.get("id") == key:
                return obj
            for value in obj.values():
                found = find(value, key)
                if found is not None:
                    return found
        elif isinstance(obj, list):
            for value in obj:
                found = find(value, key)
                if found is not None:
                    return found
        return None

    entry = find(registry, "uiuc_propellers")
    assert entry is not None
    gaps = json.dumps(entry["uncertainty_and_gaps"])
    assert "P0A-008" in gaps and "resolution-limited" in gaps


# ---------------------------------------------------------------------------
# Opt-in: live re-derivation from the pinned publisher files
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not SWEEP_DIR, reason="the six pinned UIUC sweep files stay "
                    "outside the repository; set AEROFORGE_UIUC_SWEEPS to a local "
                    "directory for the live re-derivation")
def test_live_rederivation_matches_the_pinned_diagnosis():
    scripts_dir = REPO_ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(1, str(scripts_dir))
    from benchmark_uiuc_axial_sweeps import (
        PLAN, STATIC_FILE, evaluate, interpolate, mix, read_table,
    )

    source_dir = Path(SWEEP_DIR)
    freeze_bytes = PLAN.read_bytes().replace(b"\r\n", b"\n")
    plan = json.loads(freeze_bytes)
    static = read_table(STATIC_FILE, plan["static_sha256"], ("RPM", "CT", "CP"),
                        normalize_line_endings=True)
    low_rec, ul_rec, uh_rec = plan["calibration"]
    low = read_table(source_dir / low_rec["file"], low_rec["sha256"],
                     ("J", "CT", "CP", "eta"))
    seam = plan["upper_plane_seam_j"]
    high = [r for r in read_table(source_dir / ul_rec["file"], ul_rec["sha256"],
                                  ("J", "CT", "CP", "eta")) if r[0] < seam]
    high += [r for r in read_table(source_dir / uh_rec["file"], uh_rec["sha256"],
                                   ("J", "CT", "CP", "eta")) if r[0] >= seam]
    weight = (6018.0 - low_rec["rpm"]) / ((ul_rec["rpm"] + uh_rec["rpm"]) / 2.0
                                          - low_rec["rpm"])
    lo = interpolate(low, 0.671)[0]
    hi = interpolate(high, 0.671)[0]

    diagnosis = _load(DIAGNOSIS)
    assert diagnosis["predictions"]["axial_interpolator_ct"] == _mix(lo, hi, weight)
    holdout = next(r for r in plan["holdout"] if r["rpm"] == 6018)
    rows = read_table(source_dir / holdout["file"], holdout["sha256"],
                      ("J", "CT", "CP", "eta"))
    measured = next(r for r in rows if r[0] == 0.671)
    assert diagnosis["row"]["measured_ct"] == measured[1]

    # The frozen benchmark reproduces the committed results bit-identically.
    live = evaluate(source_dir)
    committed = _load(RESULTS)
    del live["plan_sha256"], committed["plan_sha256"]
    assert json.dumps(live, sort_keys=True) == json.dumps(committed, sort_keys=True)
