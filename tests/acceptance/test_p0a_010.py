"""P0A-010 — reproduce M25 misses and healthy-flight false alarms.

DIAGNOSIS-AND-FREEZE task: reproduces the frozen M25 UAV-FD decisions per
whole recording, verifies whole-recording partition integrity and zero
label-to-feature leakage, and pins the exact per-recording decision counts.
No detector threshold, feature logic or physics behavior is changed here
(detector repairs belong to P0A-011).

CI-unconditional: asserts the committed frozen artifacts (per-recording
verdicts, window counts, thresholds), the whole-recording partition
disjointness between calibration and holdout, and the structural absence of
label-to-feature leakage in both benchmark scripts. Opt-in
(`AEROFORGE_UAV_FD_DIR` pointing at the eight pinned publisher .mat files):
re-runs BOTH frozen benchmarks end-to-end and asserts bit-identical freezes
and results, then re-derives the per-recording decision table.

Reference: docs/acceptance/P0A-010.md,
docs/campaigns/M25_2_6_UAV_FD_ROTOR_ORDER.md,
docs/campaigns/M25_7_11_UAV_FD_ESC_POWER.md,
docs/campaigns/m25_uav_fd_rotor_order_freeze.json,
docs/campaigns/m25_uav_fd_rotor_order_results.json,
docs/campaigns/m25_uav_fd_esc_power_freeze.json,
docs/campaigns/m25_uav_fd_esc_power_results.json.
"""

from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VIB_RESULTS = REPO_ROOT / "docs/campaigns/m25_uav_fd_rotor_order_results.json"
VIB_FREEZE = REPO_ROOT / "docs/campaigns/m25_uav_fd_rotor_order_freeze.json"
ESC_RESULTS = REPO_ROOT / "docs/campaigns/m25_uav_fd_esc_power_results.json"
ESC_FREEZE = REPO_ROOT / "docs/campaigns/m25_uav_fd_esc_power_freeze.json"
VIB_SCRIPT = REPO_ROOT / "scripts/benchmark_uav_fd_rotor_order.py"
ESC_SCRIPT = REPO_ROOT / "scripts/benchmark_uav_fd_esc_power.py"
SWEEP_DIR = os.environ.get("AEROFORGE_UAV_FD_DIR", "")

# The frozen whole-recording decision table (published in
# docs/acceptance/P0A-010.md). Verdicts are the frozen per-indicator
# outcomes; TP/FN/FP/TN classify each indicator against the publisher label.
DECISION_TABLE = {
    # (recording, indicator): (label, verdict, agreement)
    ("NO_FAULT5.mat", "rotor_order"): (False, "NO_ALERT", "NO_ALERT_ON_HEALTHY_SOURCE"),
    ("NO_FAULT5.mat", "accel_rms"): (False, "FAULT_INDICATOR_ALERT", "FALSE_ALERT"),
    ("FAULT_M3_10.mat", "rotor_order"): (True, "NO_ALERT", "MISSED"),
    ("FAULT_M3_10.mat", "accel_rms"): (True, "NO_ALERT", "MISSED"),
    ("FAULT_M4_10.mat", "rotor_order"): (True, "FAULT_INDICATOR_ALERT", "DETECTED"),
    ("FAULT_M4_10.mat", "accel_rms"): (True, "NO_ALERT", "MISSED"),
    ("NO_FAULT6.mat", "speed_normalized_power"): (False, "ESC_POWER_ALERT", "FALSE_ALERT"),
    ("NO_FAULT6.mat", "power_baseline"): (False, "NO_ALERT", "NO_ALERT_ON_HEALTHY_SOURCE"),
    ("NO_FAULT6.mat", "rotor_order_vibration"): (False, "NO_ALERT", "NO_ALERT_ON_HEALTHY_SOURCE"),
    ("NO_FAULT6.mat", "either_indicator"): (False, "COMBINED_ALERT", "FALSE_ALERT"),
    ("FAULT_M1_10.mat", "speed_normalized_power"): (True, "NO_ALERT", "MISSED"),
    ("FAULT_M1_10.mat", "power_baseline"): (True, "NO_ALERT", "MISSED"),
    ("FAULT_M1_10.mat", "rotor_order_vibration"): (True, "NO_ALERT", "MISSED"),
    ("FAULT_M1_10.mat", "either_indicator"): (True, "NO_ALERT", "MISSED"),
    ("FAULT_M5_10.mat", "speed_normalized_power"): (True, "NO_ALERT", "MISSED"),
    ("FAULT_M5_10.mat", "power_baseline"): (True, "NO_ALERT", "MISSED"),
    ("FAULT_M5_10.mat", "rotor_order_vibration"): (True, "FAULT_INDICATOR_ALERT", "DETECTED"),
    ("FAULT_M5_10.mat", "either_indicator"): (True, "COMBINED_ALERT", "DETECTED"),
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def vib_results() -> dict:
    return _load(VIB_RESULTS)


@pytest.fixture(scope="module")
def vib_freeze() -> dict:
    return _load(VIB_FREEZE)


@pytest.fixture(scope="module")
def esc_results() -> dict:
    return _load(ESC_RESULTS)


@pytest.fixture(scope="module")
def esc_freeze() -> dict:
    return _load(ESC_FREEZE)


# ---------------------------------------------------------------------------
# Frozen per-recording decisions, pinned exactly (CI-safe)
# ---------------------------------------------------------------------------


def test_rotor_order_decisions_pinned(vib_results):
    flights = vib_results["flights"]
    assert set(flights) == {"NO_FAULT5.mat", "FAULT_M3_10.mat", "FAULT_M4_10.mat"}
    for (recording, indicator), (label, verdict, agreement) in DECISION_TABLE.items():
        if recording not in flights or indicator not in flights[recording]["models"]:
            continue
        block = flights[recording]["models"][indicator]
        assert flights[recording]["published_fault_label"] == label, recording
        assert block["verdict"] == verdict, (recording, indicator)
        assert block["agreement"] == agreement, (recording, indicator)


def test_rotor_order_window_and_exceedance_counts_pinned(vib_results):
    flights = vib_results["flights"]
    assert flights["NO_FAULT5.mat"]["eligible_windows"] == 23
    assert flights["FAULT_M3_10.mat"]["eligible_windows"] == 34
    assert flights["FAULT_M4_10.mat"]["eligible_windows"] == 31
    # The detected fault exceeded in 22 of 31 windows; the missed fault in 0.
    m4 = flights["FAULT_M4_10.mat"]["models"]["rotor_order"]
    m3 = flights["FAULT_M3_10.mat"]["models"]["rotor_order"]
    assert (m4["exceeding_windows"], m4["longest_consecutive_exceedance"],
            m4["first_alert_window"]) == (22, 6, 6)
    assert (m3["exceeding_windows"], m3["longest_consecutive_exceedance"]) == (0, 0)
    # M1's vibration also stayed under the alert rule (3 isolated exceedances).
    assert flights["FAULT_M3_10.mat"]["models"]["accel_rms"]["longest_consecutive_exceedance"] == 1
    assert flights["FAULT_M4_10.mat"]["models"]["accel_rms"]["longest_consecutive_exceedance"] == 1
    # The healthy flight's accel-RMS false alert: 3 exceedances, run of 2 at
    # window 55 — the whole-recording FP.
    healthy = flights["NO_FAULT5.mat"]["models"]["accel_rms"]
    assert (healthy["exceeding_windows"], healthy["longest_consecutive_exceedance"],
            healthy["first_alert_window"]) == (3, 2, 55)


def test_esc_power_decisions_pinned(esc_results):
    flights = esc_results["flights"]
    assert set(flights) == {"NO_FAULT6.mat", "FAULT_M1_10.mat", "FAULT_M5_10.mat"}
    for (recording, indicator), (label, verdict, agreement) in DECISION_TABLE.items():
        if recording not in flights or indicator not in flights[recording]["comparisons"]:
            continue
        block = flights[recording]["comparisons"][indicator]
        assert flights[recording]["published_fault_label"] == label, recording
        assert block["verdict"] == verdict, (recording, indicator)
        assert block["agreement"] == agreement, (recording, indicator)
    # The healthy ESC false alert came from ESC_2 with a single repeat alarm.
    healthy = flights["NO_FAULT6.mat"]["comparisons"]["speed_normalized_power"]
    assert healthy["repeat_alarms_by_source_esc"] == {"ESC_2": 1}
    assert healthy["above_threshold_windows"] == 5
    # The missed faults had above-threshold windows but NO repeat alarm on
    # one ESC (the alert rule needs two ADJACENT windows led by the SAME ESC).
    assert flights["FAULT_M1_10.mat"]["comparisons"]["speed_normalized_power"]["above_threshold_windows"] == 5
    assert flights["FAULT_M1_10.mat"]["comparisons"]["power_baseline"]["above_threshold_windows"] == 0
    assert flights["FAULT_M5_10.mat"]["comparisons"]["speed_normalized_power"]["above_threshold_windows"] == 4
    assert flights["FAULT_M5_10.mat"]["comparisons"]["power_baseline"]["above_threshold_windows"] == 4
    for recording in ("FAULT_M1_10.mat", "FAULT_M5_10.mat"):
        for feature in ("speed_normalized_power", "power_baseline"):
            block = flights[recording]["comparisons"][feature]
            assert block["repeat_alarms_by_source_esc"] == {}, (recording, feature)
    # Vibration: M5 exceeded in EVERY scored window (36/36, run 26) while M1
    # had 3 isolated exceedances (run 1).
    assert (flights["FAULT_M5_10.mat"]["comparisons"]["rotor_order_vibration"]["exceeding_windows"],
            flights["FAULT_M5_10.mat"]["comparisons"]["rotor_order_vibration"]["longest_consecutive_exceedance"]) == (36, 26)
    assert (flights["FAULT_M1_10.mat"]["comparisons"]["rotor_order_vibration"]["exceeding_windows"],
            flights["FAULT_M1_10.mat"]["comparisons"]["rotor_order_vibration"]["longest_consecutive_exceedance"]) == (3, 1)


def test_frozen_thresholds_pinned(vib_freeze, esc_freeze):
    assert vib_freeze["thresholds"] == {"rotor_order": 0.103437127,
                                       "accel_rms": 0.587594531}
    assert vib_freeze["healthy_calibration_median_rpm_support"] == [5377.5, 6049.5]
    assert vib_freeze["calibration_flights"]["NO_FAULT1.mat"]["eligible_windows"] == 20
    assert vib_freeze["calibration_flights"]["NO_FAULT4.mat"]["eligible_windows"] == 21
    assert esc_freeze["models"]["speed_normalized_power"]["deficit_threshold"] == \
        pytest.approx(0.106696969, abs=1e-12)
    assert esc_freeze["models"]["power_baseline"]["deficit_threshold"] == \
        pytest.approx(0.24889605, abs=1e-12)
    assert esc_freeze["calibrated_median_rpm"] == [5379.75, 6148.75]


# ---------------------------------------------------------------------------
# Whole-recording partition integrity (calibration vs holdout disjoint)
# ---------------------------------------------------------------------------


def test_calibration_and_holdout_partitions_disjoint_whole_recording(
        vib_freeze, esc_freeze, vib_results, esc_results):
    """The frozen splits partition whole recordings: a .mat file is either a
    calibration recording or a holdout recording — never split across, and
    never both."""
    vib_train = tuple(vib_freeze["calibration_flights"])
    vib_holdout = set(vib_results["flights"])
    assert not (set(vib_train) & vib_holdout), "split-flight leakage"
    esc_train = tuple(esc_freeze["calibration_flights"])
    esc_holdout = set(esc_results["flights"])
    assert not (set(esc_train) & esc_holdout), "split-flight leakage"
    # The ESC calibration reuses the SAME healthy recordings as the vibration
    # calibration (one calibration set, two indicator fits).
    assert set(esc_train) == set(vib_train)
    # The earlier vibration HOLDOUT recordings are excluded from the ESC
    # batch entirely (M25.7: "excluded from the calibration and this
    # evaluation").
    assert not (vib_holdout & esc_holdout)


def test_holdout_labels_are_publisher_file_names(vib_freeze, esc_freeze):
    """Labels come from the publisher's recording names, carried verbatim, and
    every manifest file maps to exactly one partition role."""
    for freeze in (vib_freeze, esc_freeze):
        manifest = freeze["source_files"]
        train = set(freeze["calibration_flights"])
        for name, pinned in manifest.items():
            assert name.startswith(("NO_FAULT", "FAULT_M"))
            assert isinstance(pinned["bytes"], int) and len(pinned["sha256"]) == 64
        # The healthy TRAIN flights are named NO_FAULT (no fault label).
        assert all(name.startswith("NO_FAULT") for name in train)
    # The vibration holdout labels carried through the results verbatim.
    assert json.dumps(_load(VIB_RESULTS)["flights"]["FAULT_M3_10.mat"]["published_fault_label"]) == "true"
    assert json.dumps(_load(VIB_RESULTS)["flights"]["NO_FAULT5.mat"]["published_fault_label"]) == "false"


# ---------------------------------------------------------------------------
# Anti-leakage: no label may enter feature extraction or scoring
# ---------------------------------------------------------------------------


# The fault-label carriers: the publisher label dictionaries and the
# agreement parameters. FILES/TRAIN are source manifests / partition
# selectors and carry no fault label.
LABEL_IDENTIFIERS = ("HOLDOUT", "published_fault_label", "known_fault")
WHOLE_RECORDING_LAYERS = {"compare", "agreement", "combined_verdict", "main"}


def _reads_label_values(script: Path) -> set[str]:
    """Function names that READ fault-label VALUES: any subscript or value
    iteration of the label dictionaries, or a fault-label parameter.
    Membership tests (``name in HOLDOUT``) and key-only uses select
    recordings by identity and are NOT label reads."""
    tree = ast.parse(script.read_text(encoding="utf-8"))
    referencing = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        reads = False
        for sub in ast.walk(node):
            if (isinstance(sub, ast.Subscript) and isinstance(sub.value, ast.Name)
                    and sub.value.id in LABEL_IDENTIFIERS):
                reads = True  # HOLDOUT[name] -> label value
            if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                    and isinstance(sub.func.value, ast.Name)
                    and sub.func.value.id in LABEL_IDENTIFIERS
                    and sub.func.attr in ("items", "values", "get")):
                reads = True  # unpacks (name, label) pairs
            if isinstance(sub, ast.Name) and sub.id in (
                    "known_fault", "published_fault_label"):
                reads = True
        args = {a.arg for a in node.args.args + node.args.kwonlyargs}
        if reads or (args & {"fault", "known_fault", "published_fault_label"}):
            referencing.add(node.name)
    return referencing


def test_no_label_leakage_into_feature_or_scoring_code():
    """Structural audit: label identifiers (HOLDOUT/TRAIN/FILES/fault) are
    referenced ONLY by the whole-recording layers (compare/agreement/main) —
    never by window extraction, spectral scoring, deficit computation or the
    per-window decision rule."""
    allowed = WHOLE_RECORDING_LAYERS
    for script in (VIB_SCRIPT, ESC_SCRIPT):
        referencing = _reads_label_values(script)
        leaked = referencing - allowed
        assert not leaked, f"label values reached non-agreement code: {leaked}"
    # The feature paths take no label argument at all (parameter-level proof).
    vib_tree = ast.parse(VIB_SCRIPT.read_text(encoding="utf-8"))
    spectral = next(n for n in vib_tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == "spectral_score")
    assert [a.arg for a in spectral.args.args] == ["t", "acceleration", "motor_rpm"]
    esc_tree = ast.parse(ESC_SCRIPT.read_text(encoding="utf-8"))
    deficit = next(n for n in esc_tree.body if isinstance(n, ast.FunctionDef)
                   and n.name == "deficit")
    assert [a.arg for a in deficit.args.args] == ["window", "feature", "healthy_center"]
    # The published label is attached to results only at the whole-recording
    # layer, keyed by recording name.
    for script, key in ((VIB_SCRIPT, "published_fault_label"),
                        (ESC_SCRIPT, "published_fault_label")):
        assert key in script.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Opt-in: bit-identical whole-recording reproduction from publisher bytes
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not SWEEP_DIR, reason="the eight pinned UAV-FD recordings stay "
                    "outside the repository; set AEROFORGE_UAV_FD_DIR for the "
                    "bit-identical reproduction")
def test_live_reproduction_bit_identical(tmp_path):
    sys_path = str(REPO_ROOT / "scripts")
    if sys_path not in sys.path:
        sys.path.insert(1, sys_path)
    import benchmark_uav_fd_esc_power as esc
    import benchmark_uav_fd_rotor_order as vib

    directory = Path(SWEEP_DIR)
    vib_freeze_live = vib.calibrate(directory)
    assert vib.digest(vib_freeze_live) == vib.digest(_load(VIB_FREEZE))
    vib_results_live = vib.compare(directory, vib_freeze_live)
    assert json.dumps(vib_results_live, sort_keys=True) == \
        json.dumps(_load(VIB_RESULTS), sort_keys=True)
    esc_freeze_live = esc.calibrate(directory)
    assert esc.digest(esc_freeze_live) == esc.digest(_load(ESC_FREEZE))
    esc_results_live = esc.compare(directory, esc_freeze_live)
    assert json.dumps(esc_results_live, sort_keys=True) == \
        json.dumps(_load(ESC_RESULTS), sort_keys=True)

