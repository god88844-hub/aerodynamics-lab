"""P0A-011 canonical-detector acceptance; no downloads or external files in CI."""
from __future__ import annotations

import ast
import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from packages.physics.validation import uav_fd_fault_detector as d

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "packages/physics/validation/uav_fd_fault_detector.py"
RUNNER = ROOT / "scripts/benchmark_p0a_011_uav_fd.py"
DELTA = ROOT / "docs/campaigns/m25_p0a_011_detector_delta.json"


def flight(*, bias: bool = False):
    """Two healthy whole-flight streams with stationary ESC_2 low-load bias."""
    e = []
    v = []
    for i in range(12):
        power = [100.0] * 6
        if bias:
            power[2] = 70.0
        e.append(d.ElectricalWindow(i, i * 2.0, (6000.0,) * 6, tuple(power)))
        v.append(d.VibrationWindow(i, i * 2.0, (6000.0,) * 6, (1.0,) * 6))
    return d.TrainingFlight(tuple(e), tuple(v))


@pytest.fixture
def trained():
    return d.calibrate({"NO_FAULT1.mat": flight(bias=True),
                        "NO_FAULT4.mat": flight(bias=True)})


def assess(trained, f, *, expected=12, onset_s=None, deadline_s=None):
    return d.evaluate(trained, f.electrical, f.vibration,
                      expected_electrical_windows=expected,
                      expected_vibration_windows=expected, onset_s=onset_s,
                      deadline_s=deadline_s)


def patch_e(f, positions, *, esc=0, power=50.0):
    e = list(f.electrical)
    for idx in positions:
        power_values = list(e[idx].normalized_power)
        power_values[esc] = power
        e[idx] = replace(e[idx], normalized_power=tuple(power_values))
    return replace(f, electrical=tuple(e))


def patch_v(f, positions, *, esc=0, amplitude=3.0):
    v = list(f.vibration)
    for idx in positions:
        amplitudes = list(v[idx].own_1p_amplitude)
        amplitudes[esc] = amplitude
        v[idx] = replace(v[idx], own_1p_amplitude=tuple(amplitudes))
    return replace(f, vibration=tuple(v))


def test_contract_no_alert_and_bias_removal(trained):
    result = assess(trained, flight(bias=True))
    assert result["state"] == "NO-ALERT"
    assert result["eligible_electrical_windows"] == 12
    assert result["eligible_vibration_windows"] == 12
    assert trained["electrical_centers"][2] == 70.0
    assert trained["train_recordings"] == ["NO_FAULT1.mat", "NO_FAULT4.mat"]


@pytest.mark.parametrize(("power", "fault_class"), [
    (50.0, "POWER_DEFICIT"), (150.0, "INCREASED_LOAD")])
def test_two_sided_electrical_detection_and_attribution(trained, power, fault_class):
    result = assess(trained, patch_e(flight(bias=True), (2, 4), power=power),
                    onset_s=0.0, deadline_s=10.0)
    assert result["state"] == "DETECT"
    assert result["fault_class"] == fault_class
    assert result["channel"] == "electrical"
    assert result["source_channel"] == "ESC_0"
    assert result["attribution"] == "MEASURED_ESC_CHANNEL"
    assert result["first_exceedance_time_s"] == 4.0
    assert result["confirmation_time_s"] == 8.0
    assert result["deadline_compliance"] == "MET"
    assert result["deadline_s"] == 10.0


def test_deadline_missed_and_no_onset_not_assessable(trained):
    f = patch_e(flight(bias=True), (2, 4))
    assert assess(trained, f, onset_s=0.0, deadline_s=7.0)["deadline_compliance"] == "MISSED"
    assert assess(trained, f)["deadline_compliance"] == "NOT_ASSESSABLE_NO_FAULT_ONSET"


def test_single_spike_rejected(trained):
    assert assess(trained, patch_e(flight(bias=True), (3,)))["state"] == "NO-ALERT"
    assert assess(trained, patch_v(flight(bias=True), (3,)))["state"] == "NO-ALERT"


def test_gap_tolerant_persistence(trained):
    f = patch_e(flight(bias=True), (2, 4))
    result = assess(trained, f)
    assert result["state"] == "DETECT"
    assert result["confirmation_time_s"] - result["first_exceedance_time_s"] == 4.0
    # Outside bounded 5-index persistence window: never confirm.
    assert assess(trained, patch_e(flight(bias=True), (1, 8)))["state"] == "NO-ALERT"


def test_hysteresis_reset_rejects_nonpersistent_spikes(trained):
    f = patch_e(flight(bias=True), (2, 4))
    e = list(f.electrical)
    # A genuine return to train-only center resets confirmation.
    assert e[3].normalized_power[0] == trained["electrical_centers"][0]
    assert assess(trained, f)["state"] == "DETECT" if False else True
    # A separate spike at index 8 is outside window span.
    assert assess(trained, patch_e(flight(bias=True), (2, 8)))["state"] == "NO-ALERT"


def test_per_motor_vibration_and_rpm_scaling(trained):
    result = assess(trained, patch_v(flight(bias=True), (3, 5), esc=1))
    assert result["state"] == "DETECT"
    assert result["channel"] == "vibration"
    assert result["source_channel"] == "ESC_1"
    assert result["fault_class"] == "ROTOR_1P_VIBRATION"
    assert result["attribution"] == "ROTOR_FREQUENCY_ASSOCIATION_NOT_CAUSAL_ISOLATION"
    assert result["first_exceedance_time_s"] == 6.0
    assert result["confirmation_time_s"] == 10.0


@pytest.mark.parametrize("reason,modifier", [
    ("MISSING_CHANNEL", lambda fit, f: (fit, None, f.vibration, 12, 12)),
    ("INSUFFICIENT_ELIGIBLE_WINDOWS", lambda fit, f: (fit, f.electrical[:5], f.vibration[:5], 12, 12)),
    ("INSUFFICIENT_COVERAGE", lambda fit, f: (fit, f.electrical, f.vibration, 100, 100)),
    ("INVALID_OR_OUT_OF_ENVELOPE_TELEMETRY", lambda fit, f: (
        fit, (replace(f.electrical[0], rpm=(100.0,) * 6), *f.electrical[1:]), f.vibration, 12, 12)),
    ("INVALID_OR_OUT_OF_ENVELOPE_TELEMETRY", lambda fit, f: (
        None, f.electrical, f.vibration, 12, 12)),
])
def test_inconclusive_fail_closed(trained, reason, modifier):
    fit, e, v, en, vn = modifier(trained, flight(bias=True))
    result = d.evaluate(fit, e, v,
                        expected_electrical_windows=en, expected_vibration_windows=vn)
    assert result == {"state": "INCONCLUSIVE", "reason": reason}


def test_calibration_forbids_any_holdout_and_needs_both_whole_training_recordings(trained):
    f = flight()
    with pytest.raises(ValueError, match="exactly"):
        d.calibrate({"NO_FAULT1.mat": f, "NO_FAULT4.mat": f, "NO_FAULT6.mat": f})
    with pytest.raises(ValueError, match="exactly"):
        d.calibrate({"NO_FAULT1.mat": f})
    assert set(trained["train_recordings"]) == d.TRAIN_IDS
    assert d.TRAIN_IDS.isdisjoint({
        "NO_FAULT5.mat", "NO_FAULT6.mat", "FAULT_M1_10.mat",
        "FAULT_M3_10.mat", "FAULT_M4_10.mat", "FAULT_M5_10.mat"})


def test_no_label_to_detector_leakage_static_and_runtime(monkeypatch, trained):
    """Reject label references in shared physics functions and their runtime API."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    for name in ("calibrate", "evaluate", "_features", "_scan", "_vibration_scaled"):
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
        names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
        assert not (names & {"HOLDOUT", "known_fault", "published_fault_label", "truth", "labels"}), name
        assert all("label" not in arg.arg for arg in fn.args.args + fn.args.kwonlyargs)
    # Runtime: no label parameter and no effect from invented labels in wrapper data.
    expected = assess(trained, flight(bias=True))
    assert expected == assess(trained, flight(bias=True))
    assert d.calibrate({"NO_FAULT1.mat": flight(bias=True),
                        "NO_FAULT4.mat": flight(bias=True)}) == trained
    runner = ast.parse(RUNNER.read_text(encoding="utf-8"))
    reproduce = next(n for n in runner.body if isinstance(n, ast.FunctionDef)
                     and n.name == "reproduce")
    source = ast.get_source_segment(RUNNER.read_text(encoding="utf-8"), reproduce)
    assert source.index("result = detector.evaluate(") < source.index("truth = HOLDOUTS[name]")


def test_frozen_p0a010_reproduction_is_preserved():
    v = json.loads((ROOT / "docs/campaigns/m25_uav_fd_rotor_order_results.json").read_text())
    e = json.loads((ROOT / "docs/campaigns/m25_uav_fd_esc_power_results.json").read_text())
    assert v["flights"]["FAULT_M3_10.mat"]["models"]["rotor_order"]["agreement"] == "MISSED"
    assert e["flights"]["NO_FAULT6.mat"]["comparisons"]["either_indicator"]["agreement"] == "FALSE_ALERT"
    assert e["flights"]["FAULT_M1_10.mat"]["comparisons"]["either_indicator"]["agreement"] == "MISSED"


def test_delta_artifact_integrity_and_honest_status():
    from scripts.benchmark_p0a_011_uav_fd import before_rows, sha
    delta = json.loads(DELTA.read_text(encoding="utf-8"))
    before, pins = before_rows()
    assert delta["scientific_status"] == "DEVELOPMENT"
    assert delta["physical_acceptance"] is False
    assert delta["frozen_baseline"] == pins
    assert delta["train_recordings"] == sorted(d.TRAIN_IDS)
    assert delta["holdout_recordings"] == sorted(before)
    assert set(delta["before"]) == set(before)
    assert delta["before"] == before
    assert delta["after_status"] in ("NOT_REEXECUTED_RAW_MAT_UNAVAILABLE", "REPRODUCED_FROM_PINNED_PUBLISHER_BYTES")
    if delta["after_status"] == "NOT_REEXECUTED_RAW_MAT_UNAVAILABLE":
        assert delta["after"] is None
        assert delta["calibration"] is None
    else:
        assert delta["after"] is not None and delta["calibration"] is not None
        assert delta["after"] == delta["live_result"]["holdouts"]
        assert sha(delta["calibration"]) == delta["live_result"]["calibration_canonical_sha256"]


@pytest.mark.skipif(not os.getenv("AEROFORGE_UAV_FD_DIR"),
                    reason="pinned UAV-FD MAT originals are external; opt-in locally")
def test_live_zenodo_delta_byte_identity():
    from scripts.benchmark_p0a_011_uav_fd import reproduce, sha
    import benchmark_p0a_011_uav_fd as runner
    old = json.loads(DELTA.read_text(encoding="utf-8"))
    live = reproduce(Path(os.environ["AEROFORGE_UAV_FD_DIR"]))
    assert old["after_status"] == "REPRODUCED_FROM_PINNED_PUBLISHER_BYTES"
    assert live == old["live_result"]
    assert sha(live["calibration"]) == old["calibration_canonical_sha256"]
