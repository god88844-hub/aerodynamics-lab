"""P0A-009 — correct and verify the supported signed aerodynamic regime.

Implements and verifies the canonical signed axial-flow propeller regime in
``packages/physics/aerodynamics/axial_prop.py``:

  - exact SI equations (J = V_a/(nD), T = rho n^2 D^4 CT, Q = rho n^2 D^5 CP
    / (2 pi), P = 2 pi n Q = rho n^3 D^5 CP) with signs preserved end to end
    (positive-thrust and windmilling CT < 0) and body-frame rotor-axis
    projection,
  - fail-closed envelope contract (typed refusals for n <= 0, reverse/vortex-
    ring axial inflow V_a < 0, and any (J, RPM) outside the frozen M24
    calibration envelope; non-fatal labeling via ``classify``),
  - the canonical module as the M24 prediction path (bridge test against the
    frozen protocol's interpolation on the pinned calibration knots),
  - the principled resolution-aware sign classification (measurement sign
    indeterminacy from the 4-decimal source resolution ONLY; prediction
    magnitude against the PREDECLARED M24 tolerances — no predicted-side
    count threshold, per the P0A-008 reviewer guardrail),
  - per-row delta published WITHOUT mutating the frozen M24 baseline.

CI-unconditional: every per-row prediction is re-derivable bit-exactly from
the delta artifact's pinned calibration knots through the canonical module.
Opt-in (AEROFORGE_UIUC_SWEEPS): live re-hash, live frozen-benchmark
bit-identity, live re-derivation.

Reference: docs/acceptance/P0A-009.md, docs/acceptance/P0A-008.md (frozen),
docs/campaigns/m24_uiuc_signed_regime_delta.json,
docs/campaigns/M24_2_6_UIUC_AXIAL_SWEEPS.md, docs/VALIDATION_TOLERANCES.md.
"""

from __future__ import annotations

import json
import os
import sys
from math import isfinite, pi
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DELTA = REPO_ROOT / "docs/campaigns/m24_uiuc_signed_regime_delta.json"
FROZEN_RESULTS = REPO_ROOT / "docs/campaigns/m24_uiuc_axial_sweeps_results.json"
SWEEP_DIR = os.environ.get("AEROFORGE_UIUC_SWEEPS", "")

sys.path[:0] = [str(REPO_ROOT / "packages"), str(REPO_ROOT / "packages/shared-schemas"),
                str(REPO_ROOT / "scripts")]

from physics.aerodynamics.axial_prop import (  # noqa: E402
    AxialEnvelope,
    AxialEnvelopeError,
    AxialPropellerModel,
    PlaneKnots,
    body_frame_force,
    body_frame_torque,
)

RHO = 1.225
D = 0.254


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def delta() -> dict:
    return _load(DELTA)


@pytest.fixture(scope="module")
def model(delta) -> AxialPropellerModel:
    knots = delta["calibration_knots"]
    low = PlaneKnots(tuple(tuple(k) for k in knots["low"]))
    high = PlaneKnots(tuple(tuple(k) for k in knots["high"]))
    envelope = AxialEnvelope(
        rpm_min=delta["envelope"]["rpm"][0], rpm_max=delta["envelope"]["rpm"][1],
        j_min=delta["envelope"]["j"][0], j_max=delta["envelope"]["j"][1],
        provenance=delta["envelope"]["provenance"])
    return AxialPropellerModel(
        ((knots["low_plane_rpm"], low), (knots["high_plane_rpm"], high)),
        diameter_m=delta["diameter_m"], envelope=envelope)


def _synthetic_model() -> AxialPropellerModel:
    """Two analytic linear planes with a zero-CT crossing inside the envelope
    (so both CT signs are reachable without extrapolation)."""
    low = PlaneKnots(tuple((0.10 + 0.05 * i, 0.10 - 0.03 * i, 0.050 - 0.001 * i)
                           for i in range(12)))
    high = PlaneKnots(tuple((0.10 + 0.05 * i, 0.11 - 0.03 * i, 0.052 - 0.001 * i)
                            for i in range(12)))
    envelope = AxialEnvelope(rpm_min=4000.0, rpm_max=7000.0, j_min=0.10,
                             j_max=0.65, provenance="synthetic analytic planes")
    return AxialPropellerModel(((4000.0, low), (7000.0, high)),
                               diameter_m=D, envelope=envelope)


# ---------------------------------------------------------------------------
# Exact SI equations and dimensional consistency
# ---------------------------------------------------------------------------


def test_exact_si_equations_and_dimensional_consistency():
    model = _synthetic_model()
    rpm, v_a, rho = 6018.0, 6.5, 1.225  # J ~ 0.255: positive-CT blend region
    load = model.evaluate(rpm, v_a, rho)
    n = rpm / 60.0
    assert load.j == pytest.approx(v_a / (n * D), rel=1e-15)
    # T = rho n^2 D^4 CT (hand-computed identity)
    assert load.thrust_n == pytest.approx(rho * n**2 * D**4 * load.ct, rel=1e-15)
    # Q = rho n^2 D^5 CP / (2 pi) and P = 2 pi n Q = rho n^3 D^5 CP (exact)
    assert load.torque_n_m == pytest.approx(
        rho * n**2 * D**5 * load.cp / (2.0 * pi), rel=1e-15)
    assert load.power_w == pytest.approx(2.0 * pi * n * load.torque_n_m, rel=1e-15)
    assert load.power_w == pytest.approx(rho * n**3 * D**5 * load.cp, rel=1e-15)
    # Positive-thrust regime: signs follow the coefficients.
    assert load.ct > 0 and load.thrust_n > 0 and load.torque_n_m > 0
    assert load.power_w > 0


def test_windmilling_sign_preserved_end_to_end():
    """CT < 0 inside the envelope flips the thrust sign while the shaft still
    absorbs power (CP > 0): the signed regime is continuous across the
    zero-thrust crossing, not sign-clamped."""
    model = _synthetic_model()
    # The analytic low plane (CT = 0.10 - 0.6*(J - 0.10)) crosses CT = 0 at
    # J = 0.266667: query just past it at 4000 RPM (pure low plane).
    j_cross = 0.10 + 0.10 / 0.6
    n_4000 = 4000.0 / 60.0
    load = model.evaluate(4000.0, (j_cross + 1e-3) * n_4000 * D, RHO)
    assert load.ct < 0
    assert load.thrust_n < 0                    # thrust pulls the opposite way
    assert load.torque_n_m > 0 and load.power_w > 0  # shaft still absorbs power
    force = body_frame_force(load, np.array([0.0, 0.0, 1.0]))
    assert force[2] < 0
    # Continuity: the load at the crossing J is ~zero thrust.
    crossing = model.evaluate(4000.0, j_cross * n_4000 * D, RHO)
    assert abs(crossing.thrust_n) < 1e-9
    # The 6018 RPM query used above stays inside the positive-CT blend region.
    assert model.coefficients(6.5 / ((6018.0 / 60.0) * D), 6018.0)[0] > 0


# ---------------------------------------------------------------------------
# Body-frame projection: axis invariance, flips, fail-closed axes
# ---------------------------------------------------------------------------


def test_body_frame_axis_rotation_invariance_and_flip():
    model = _synthetic_model()
    load = model.evaluate(6018.0, 6.5, RHO)
    for axis in (np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]),
                 np.array([0.0, 0.0, 1.0]),
                 np.array([1.0, 1.0, 1.0]) / np.sqrt(3.0),
                 np.array([0.3, -0.5, 0.2])):
        force = body_frame_force(load, axis)
        torque = body_frame_torque(load, axis)
        # Magnitude is orientation-invariant and equals the signed thrust.
        assert np.linalg.norm(force) == pytest.approx(abs(load.thrust_n), rel=1e-15)
        assert np.linalg.norm(torque) == pytest.approx(abs(load.torque_n_m), rel=1e-15)
        # Direction is the (normalized) declared axis.
        unit = axis / np.linalg.norm(axis)
        assert np.allclose(force, load.thrust_n * unit, rtol=0, atol=1e-15)
        assert np.allclose(torque, load.torque_n_m * unit, rtol=0, atol=1e-15)
    # Flipping the axis flips the force; a non-unit axis is normalized.
    base = body_frame_force(load, np.array([0.0, 0.0, 1.0]))
    flipped = body_frame_force(load, np.array([0.0, 0.0, -5.0]))
    assert np.allclose(flipped, -base, rtol=0, atol=1e-15)
    # Fail-closed axes.
    for bad in (np.zeros(3), np.array([np.nan, 0.0, 0.0]),
                np.array([np.inf, 0.0, 0.0])):
        with pytest.raises(ValueError):
            body_frame_force(load, bad)
        with pytest.raises(ValueError):
            body_frame_torque(load, bad)


# ---------------------------------------------------------------------------
# Fail-closed envelope contract
# ---------------------------------------------------------------------------


def test_envelope_refusals_are_typed_and_named():
    model = _synthetic_model()
    cases = [
        (0.0, 1.0, RHO, "n <= 0"),
        (-100.0, 1.0, RHO, "n <= 0"),
        (6018.0, -1.0, RHO, "reverse"),
        (6018.0, 100.0, RHO, "outside the calibration envelope"),
        (100.0, 1.0, RHO, "outside the calibration envelope"),
        (8000.0, 1.0, RHO, "outside the calibration envelope"),
        (float("nan"), 1.0, RHO, "finite"),
        (6018.0, float("nan"), RHO, "finite"),
        (6018.0, 1.0, 0.0, "density"),
    ]
    for rpm, v_a, rho, needle in cases:
        with pytest.raises(AxialEnvelopeError) as exc:
            model.evaluate(rpm, v_a, rho)
        assert needle in str(exc.value)
    # Non-fatal labeling names the same reasons without raising.
    labels = [model.classify(rpm, v_a, rho) for rpm, v_a, rho, _ in cases]
    assert all(label.startswith("out_of_envelope:") for label in labels)
    assert "supported" == model.classify(6018.0, 6.5, RHO)
    # J below the envelope (zero axial speed) is also refused.
    with pytest.raises(AxialEnvelopeError):
        model.evaluate(6018.0, 0.0, RHO)


def test_envelope_is_declared_not_hardcoded():
    """The envelope and diameter are caller-declared inputs bound to frozen
    calibration evidence; the module refuses inverted/invalid declarations."""
    low = PlaneKnots(tuple((0.10 + 0.05 * i, 0.10, 0.05) for i in range(3)))
    with pytest.raises(ValueError):
        AxialEnvelope(rpm_min=7000.0, rpm_max=4000.0, j_min=0.1, j_max=0.6,
                      provenance="inverted")
    with pytest.raises(ValueError):
        AxialPropellerModel(((4000.0, low), (7000.0, low)), 0.254,
                            AxialEnvelope(rpm_min=4000.0, rpm_max=7000.0,
                                          j_min=0.05, j_max=0.2,
                                          provenance="outside plane support"))


# ---------------------------------------------------------------------------
# Canonical module is the M24 prediction path (bridge to the frozen protocol)
# ---------------------------------------------------------------------------


def test_canonical_predictions_match_frozen_protocol_bit_exactly(delta, model):
    """The canonical coefficients reproduce the frozen M24 protocol's
    interpolation bit-exactly on the pinned knots — benchmark code and
    flight-engine code cannot drift apart."""
    from benchmark_uiuc_axial_sweeps import interpolate

    knots = delta["calibration_knots"]
    low = [tuple(k) for k in knots["low"]]
    high = [tuple(k) for k in knots["high"]]
    for j in np.linspace(delta["envelope"]["j"][0], delta["envelope"]["j"][1], 41):
        j = float(j)
        ct_frozen_low, cp_frozen_low = interpolate(low, j)
        ct_frozen_high, cp_frozen_high = interpolate(high, j)
        ct_mod_low, cp_mod_low = model._planes[knots["low_plane_rpm"]].interpolate(j)
        ct_mod_high, cp_mod_high = model._planes[knots["high_plane_rpm"]].interpolate(j)
        assert (ct_mod_low, cp_mod_low) == (ct_frozen_low, cp_frozen_low)
        assert (ct_mod_high, cp_mod_high) == (ct_frozen_high, cp_frozen_high)
    weight = (6018.0 - knots["low_plane_rpm"]) / (
        knots["high_plane_rpm"] - knots["low_plane_rpm"])
    lo_ct, lo_cp = interpolate(low, 0.5)
    hi_ct, hi_cp = interpolate(high, 0.5)
    ct_frozen = lo_ct + weight * (hi_ct - lo_ct)
    cp_frozen = lo_cp + weight * (hi_cp - lo_cp)
    ct_mod, cp_mod = model.coefficients(0.5, 6018.0)
    assert (ct_mod, cp_mod) == (ct_frozen, cp_frozen)


def test_delta_artifact_rows_rederive_bit_exactly(delta, model):
    """Every pinned per-row prediction re-derives bit-exactly from the
    artifact's own calibration knots through the canonical module; the SI
    columns satisfy the exact equations; the classification fields are
    consistent with the rule."""
    n_checked = 0
    for row in delta["rows"]:
        ct_pred, cp_pred = model.coefficients(row["j"], row["rpm"])
        assert ct_pred == row["ct_pred"] and cp_pred == row["cp_pred"]
        n = row["rpm"] / 60.0
        assert row["thrust_n_declared_rho"] == pytest.approx(
            delta["declared_rho_kg_m3"] * n**2 * delta["diameter_m"]**4
            * row["ct_pred"], rel=1e-15)
        assert row["power_w_declared_rho"] == pytest.approx(
            2.0 * pi * n * row["torque_n_m_declared_rho"], rel=1e-15)
        assert row["measurement_sign_indeterminate"] == (
            abs(row["ct_meas"]) <= delta["measurement_sign_resolution"]["delta_res_ct"])
        assert row["ct_error_within_predeclared"] == (
            abs(row["ct_error"]) <= delta["predeclared_tolerances"]["ct_mae"])
        assert row["envelope_class"] == "supported"
        n_checked += 1
    assert n_checked == delta["after"]["rows_scored"] == 42
    assert len(delta["excluded_rows"]) == delta["after"]["rows_excluded_envelope"] == 5
    assert all(r["envelope_class"].startswith("out_of_envelope:")
               for r in delta["excluded_rows"])


# ---------------------------------------------------------------------------
# Guardrail 1: principled resolution rule — NO predicted-side count threshold
# ---------------------------------------------------------------------------


def test_resolution_rule_has_no_predicted_count_threshold(delta):
    rule = delta["measurement_sign_resolution"]["rule"]
    assert "NO predicted-side count threshold" in rule
    # Measurement indeterminacy depends ONLY on the source resolution.
    assert delta["measurement_sign_resolution"]["delta_res_ct"] == pytest.approx(0.0001)
    assert delta["measurement_sign_resolution"]["table_ct_decimal_places"] == 4
    blob = json.dumps(delta["sign_disagreement_row_classifications"])
    assert "10 counts" not in blob and "ten counts" not in blob


def test_sign_classification_separates_indeterminacy_from_magnitude(delta):
    """At the diagnosed row: the measured sign is indeterminate for every
    model (same measurement); the axial interpolator's magnitude error is
    inside the predeclared CT tolerance while static_reference fails it
    cleanly — without any predicted-count constant."""
    models = delta["sign_disagreement_row_classifications"]["models"]
    row = delta["sign_disagreement_row_classifications"]["row"]
    assert row["measured_ct"] == -0.0001
    axial = models["axial_interpolator"]
    static = models["static_reference"]
    aro = models["advance_ratio_only"]
    assert axial["sign_disagreement"] and static["sign_disagreement"]
    assert not aro["sign_disagreement"]
    assert all(models[m]["measurement_sign_indeterminate"] for m in models)
    assert axial["magnitude_within_predeclared_ct_tolerance"] is True
    assert axial["prediction_magnitude_error"] == pytest.approx(0.000317845, abs=1e-9)
    assert static["magnitude_within_predeclared_ct_tolerance"] is False
    assert static["prediction_magnitude_error"] == pytest.approx(0.098122744, abs=1e-6)
    counts = delta["after"]["sign_classification"]
    assert counts["hard_sign_disagreements"] == 0
    assert counts["measurement_sign_indeterminate_disagreements"] == 2
    assert counts["magnitude_failures_at_disagreements"] == 1


def test_before_vs_after_predictions_unchanged_and_tolerances_recorded(delta):
    """The canonical module reproduces the frozen protocol's predictions
    exactly (the delta is in the classification, not the values), and the
    predeclared M24 tolerances are recorded with their policy provenance."""
    before = delta["before"]
    frozen = _load(FROZEN_RESULTS)
    assert before["rows_scored"] == frozen["rows_scored"] == 42
    assert before["ct_mae"] == frozen["errors"]["axial_interpolator"]["ct"]["mae"]
    assert before["cp_mae"] == frozen["errors"]["axial_interpolator"]["cp"]["mae"]
    assert delta["after"]["ct_mae"] == pytest.approx(before["ct_mae"], abs=1e-12)
    assert delta["after"]["cp_mae"] == pytest.approx(before["cp_mae"], abs=1e-12)
    assert delta["after"]["ct_mae_within_predeclared"] is True
    assert delta["after"]["cp_mae_within_predeclared"] is True
    tol = delta["predeclared_tolerances"]
    assert tol["ct_mae"] == 0.001 and tol["cp_mae"] == 0.0005
    assert "VALIDATION_TOLERANCES.md" in tol["source"]


def test_protocol_revision_locked_prospectively(delta):
    status = delta["measurement_sign_resolution"]["protocol_status"]
    assert "DEVELOPMENT protocol revision" in status
    assert "prospectively" in status
    assert "no M24 physical acceptance" in status


# ---------------------------------------------------------------------------
# Guardrail 3: frozen baselines untouched (pinned metrics assert it)
# ---------------------------------------------------------------------------


def test_frozen_m24_baseline_metrics_unchanged():
    frozen = _load(FROZEN_RESULTS)
    assert frozen["rows_scored"] == 42
    assert frozen["errors"]["axial_interpolator"]["ct"]["mae"] == 0.0006850414
    assert frozen["errors"]["axial_interpolator"]["cp"]["mae"] == 0.0003006659
    assert frozen["heldout_sweeps"][2]["thrust_sign_disagreements"] == {
        "axial_interpolator": 1, "advance_ratio_only": 0, "static_reference": 1}
    assert frozen["acceptance_status"] == \
        "inconclusive_no_predeclared_engineering_tolerances_or_uncertainty"


# ---------------------------------------------------------------------------
# Opt-in: live re-derivation from the pinned publisher files
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not SWEEP_DIR, reason="the six pinned UIUC sweep files stay "
                    "outside the repository; set AEROFORGE_UIUC_SWEEPS for the "
                    "live re-derivation")
def test_live_rederivation_matches_the_pinned_delta():
    from benchmark_uiuc_axial_signed_regime import (
        DELTA_RES_CT, evaluate_signed_regime)
    live = evaluate_signed_regime(Path(SWEEP_DIR))
    committed = _load(DELTA)
    # The live evaluation reproduces the committed delta exactly.
    assert json.dumps(live, sort_keys=True) == json.dumps(committed, sort_keys=True)
    # And the frozen benchmark stays bit-identical under the same sources.
    from benchmark_uiuc_axial_sweeps import evaluate as frozen_evaluate
    frozen_live = frozen_evaluate(Path(SWEEP_DIR))
    frozen_committed = _load(FROZEN_RESULTS)
    del frozen_live["plan_sha256"], frozen_committed["plan_sha256"]
    assert json.dumps(frozen_live, sort_keys=True) == \
        json.dumps(frozen_committed, sort_keys=True)
    assert DELTA_RES_CT == pytest.approx(0.0001)
