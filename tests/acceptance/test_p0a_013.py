"""Freeze the QDrone conditional-model miss without requiring source downloads."""

from hashlib import md5, sha256
import json
import os
from pathlib import Path
import runpy

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
CAMPAIGNS = ROOT / "docs/campaigns"
CAMPAIGN_ID = "m26_qdrone_voltage"
ENV = "AEROFORGE_QDRONE_DATA_DIR"
PATHS = {
    "manifest": CAMPAIGNS / f"{CAMPAIGN_ID}_sources.json",
    "freeze": CAMPAIGNS / f"{CAMPAIGN_ID}_freeze.json",
    "results": CAMPAIGNS / f"{CAMPAIGN_ID}_results.json",
}
PINS_LF = {
    "manifest": "7fefbbb4c0874696968ad2100a33a1b3b52176b045e9f6b0a6bf8e870b12a66c",
    "freeze": "e0b0a18c54df3084b66e99a3ecd3c5e387c87625fbb2b8d9dc9a133acf048fa7",
    "results": "b3110efa03fb1d4408db67ac689c0ec9b05a24da3819448e0cc83b14bdf28fae",
}
BENCH = runpy.run_path(str(ROOT / "scripts/benchmark_qdrone_voltage_transfer.py"))


def lf_bytes(path):
    return path.read_bytes().replace(b"\r\n", b"\n")


def formatted(result):
    return (json.dumps(result, indent=2, allow_nan=False) + "\n").encode("utf-8")


def recorded(role):
    return json.loads(lf_bytes(PATHS[role]))


def qualification():
    registry = json.loads((ROOT / "data/research/registry.json").read_text(encoding="utf-8"))
    return registry["development_reproductions"][CAMPAIGN_ID]


def test_pinned_manifest_calibration_partition_and_results():
    assert {role: sha256(lf_bytes(path)).hexdigest() for role, path in PATHS.items()} == PINS_LF
    manifest = recorded("manifest")
    assert manifest["doi"] == qualification()["publisher_doi"] == "10.5281/zenodo.19464105"
    assert manifest["calibration"] == [
        {"controller": "original_mpc", "trajectory": "9a"},
        {"controller": "battery_aware_mpc", "trajectory": "9b"},
    ]
    assert manifest["holdout"] == [
        {"controller": "original_mpc", "trajectory": "11a", "reported_energy": "12a"},
        {"controller": "battery_aware_mpc", "trajectory": "11b", "reported_energy": "12b"},
    ]
    pins = {key: export["sha256"] for key, export in manifest["exports"].items()}
    assert set(pins) == {"9a", "9b", "11a", "11b", "12a", "12b"}
    assert qualification()["publisher_sha256_exact"] == pins
    assert recorded("freeze")["manifest_sha256"] == PINS_LF["manifest"]


def test_study_threshold_and_measured_inputs_propagate_to_canonical_registry():
    evidence = qualification()
    canonical = json.loads((ROOT / "data/registry.json").read_text(encoding="utf-8"))
    campaign = next(item for item in canonical["campaigns"] if item["id"] == CAMPAIGN_ID)
    assert campaign["development_reproduction"] == evidence
    assert evidence["milestone"] == "P0A-013"
    assert evidence["evidence_role"] == campaign["policy_role"] == "DEVELOPMENT"
    assert evidence["physical_acceptance"] == campaign["physical_acceptance"] == "UNVALIDATED"
    assert evidence["source_replay_env"] == ENV
    assert evidence["repository_sha256_lf"] == PINS_LF
    assert evidence["threshold"]["role"] == "STUDY_SPECIFIC_THRESHOLD"
    assert evidence["threshold"]["comparison"] == "FIRST_EXPORTED_SAMPLE_STRICTLY_BELOW"
    assert (evidence["threshold"]["value_v"] == recorded("freeze")["voltage_reference_line_v"]
            == BENCH["REFERENCE_LINE_V"] == 14.0)
    roles = evidence["channel_roles"]
    assert {name for name, entry in roles.items() if entry["role"] == "MEASURED_INPUT"} == {
        BENCH["AUXILIARY"], *BENCH["ACTUATORS"],
    }
    assert roles[BENCH["COMMAND"]]["role"] == "EXOGENOUS_MISSION_REFERENCE"


def test_frozen_voltage_crossing_and_altitude_tracking_miss():
    results = recorded("results")
    assert results["acceptance_status"] == "two_conditional_flights_without_full_aircraft_acceptance"
    original, aware = results["holdout"]
    assert (original["trajectory"], aware["trajectory"]) == ("11a", "11b")
    assert original["scored_samples"] == aware["scored_samples"] == 2600
    assert (
        original["measured_min_voltage_v"], original["predicted_min_voltage_v"],
        original["measured_first_below_reference_s"], original["predicted_first_below_reference_s"],
    ) == (13.727709961, 13.559874402, 1.2075, 1.2075)
    assert (
        aware["measured_min_voltage_v"], aware["predicted_min_voltage_v"],
        aware["measured_first_below_reference_s"], aware["predicted_first_below_reference_s"],
    ) == (14.091064453, 14.172667374, None, None)
    assert original["altitude_prediction_error_m"] == {
        "mae": 1.181952052, "mean_signed_error": 1.175365397,
        "maximum_absolute_error": 1.703516535,
    }
    assert aware["altitude_prediction_error_m"]["mae"] == 0.014259675
    assert (
        original["measured_end_altitude_m"], original["predicted_end_altitude_m"],
        aware["measured_end_altitude_m"], aware["predicted_end_altitude_m"],
    ) == (0.000727378, 1.703516536, 1.706240110, 1.705001228)
    collapse = qualification()["original_mpc_collapse"]
    assert (collapse["start_s"], collapse["end_s"], collapse["samples"]) == (2.5575, 7.0, 1778)
    assert (
        collapse["start_measured_altitude_m"], collapse["start_predicted_altitude_m"],
        collapse["end_predicted_minus_measured_m"],
    ) == (0.677647762, 1.703400118, 1.702789158)
    assert collapse["window_altitude_error_m"] == {
        "mae": 1.659103168, "mean_signed_error": 1.659103168,
        "maximum_absolute_error": 1.703516535,
    }


def collapse_diagnostic(flight, frozen):
    time, altitude = flight[BENCH["TIME"]], flight[BENCH["ALTITUDE"]]
    predicted = BENCH["altitude_prediction"](flight, frozen["altitude_time_constant_s"])
    after = np.flatnonzero(time > BENCH["BASELINE_S"])
    peak = after[np.argmax(altitude[after])]
    baseline = np.median(altitude[time <= BENCH["BASELINE_S"]])
    start = peak + 1 + np.flatnonzero(altitude[peak + 1:] < baseline)[0]

    def rounded(value):
        return round(float(value), 9)

    return {
        "pre_maneuver_hover_m": rounded(baseline),
        "peak_time_s": rounded(time[peak]),
        "peak_measured_altitude_m": rounded(altitude[peak]),
        "start_s": rounded(time[start]),
        "end_s": rounded(time[-1]),
        "samples": len(time) - start,
        "start_measured_altitude_m": rounded(altitude[start]),
        "start_predicted_altitude_m": rounded(predicted[start]),
        "end_predicted_minus_measured_m": rounded(predicted[-1] - altitude[-1]),
        "window_altitude_error_m": BENCH["error_metrics"](predicted[start:], altitude[start:]),
    }


@pytest.mark.skipif(not os.environ.get(ENV), reason=f"set {ENV} for the six external publisher exports")
def test_reproduce_frozen_outputs_bit_for_bit_from_publisher_rows():
    folder = Path(os.environ[ENV])
    manifest = recorded("manifest")
    for export in manifest["exports"].values():
        original = (folder / export["file"]).read_bytes()
        assert len(original) == export["bytes"]
        assert md5(original, usedforsecurity=False).hexdigest() == export["md5"]
        assert sha256(original).hexdigest() == export["sha256"]

    load = BENCH["load_flight"]
    calibration = [load(folder, record, manifest["exports"]) for record in manifest["calibration"]]
    frozen = BENCH["fit"](calibration, sha256(lf_bytes(PATHS["manifest"])).hexdigest())
    assert formatted(frozen) == lf_bytes(PATHS["freeze"])
    results = BENCH["evaluate"](folder, manifest, frozen)
    assert formatted(results) == lf_bytes(PATHS["results"])
    original = next(record for record in manifest["holdout"] if record["controller"] == "original_mpc")
    expected = qualification()["original_mpc_collapse"].copy()
    del expected["definition"]
    assert collapse_diagnostic(load(folder, original, manifest["exports"]), frozen) == expected
