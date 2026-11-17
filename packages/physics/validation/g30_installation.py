"""M17: compare external same-G30 propeller experiment *without* claiming motor/installation equivalence.

The paper used a T-Motor MN1010 KV135 + nearby mounting plate.
AeroForge's 60-kg capstone uses a T-Motor P80 III KV100 + G30x10.5.
RPM-overlapping thrust residuals are descriptive only; different installed
flow, motor and bench conditions BLOCK any independent vehicle validation.
The source's reported 3234 W for row #2 is preserved and flagged, not fixed.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import mean

from physics.propulsion.dataset import OutOfEnvelopeError, PowertrainDataset
from physics.propulsion.loader import ComponentLibrary

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "data" / "benchmarks" / "public" / "g30_2025" / "bench_table_5.json"
DATA = ROOT / "data" / "components"


def _finite(x: object) -> bool:
    return type(x) in (int, float) and math.isfinite(x)


def compare_g30_public_bench(*, source: Path | None = None,
                             component_library: ComponentLibrary | None = None) -> dict:
    """No extrapolation, no power comparison across different motors, no model mutation."""
    spec = json.loads((source or SOURCE).read_text(encoding="utf-8"))
    if spec.get("id") != "dombrovschi_2025_g30_mn1010_plate":
        raise ValueError("unexpected experimental source ID")
    if not spec.get("doi") == "10.3390/technologies13120542":
        raise ValueError("experimental publication DOI is missing or changed")
    if not spec.get("motor_match") is False or not spec.get("bench_installation_match_verified") is False:
        raise ValueError("hardware and installation mismatch must not be overridden")
    if not spec.get("propeller_geometry_match") is True:
        raise ValueError("G30 comparison requires same declared propeller geometry")
    measurements = spec.get("measurements")
    if not isinstance(measurements, list) or len(measurements) != 9:
        raise ValueError("expected nine published operating points")
    library = component_library or ComponentLibrary(DATA)
    motor = library.motor("tmotor_p80iii_kv100")
    prop = library.propeller("tmotor_g30x105_cf")
    if prop.diameter_in != 30 or prop.pitch_in != 10.5:
        raise ValueError("AeroForge propeller geometry no longer matches reference")
    if motor.id != "tmotor_p80iii_kv100":
        raise ValueError("AeroForge motor mismatch declaration is invalid")
    model = PowertrainDataset(motor, prop.motor_test_data_key or prop.id)
    envelope = model.envelope()
    lo, hi = model._merged_rpm[0], model._merged_rpm[-1]
    source_rows = []
    overlap = []
    anomalies = []
    prev_rpm = 0.0
    for i, obs in enumerate(measurements, start=1):
        if set(obs) != {"case", "rpm", "voltage_v", "current_a", "force_n", "reported_power_w"}:
            raise ValueError("published measurement column schema changed")
        if obs["case"] != i or any(not _finite(v) for v in obs.values()):
            raise ValueError("nonfinite, duplicate or out-of-order experimental source values")
        if (obs["rpm"] <= prev_rpm or obs["voltage_v"] <= 0 or obs["current_a"] <= 0
                or obs["force_n"] <= 0 or obs["reported_power_w"] <= 0):
            raise ValueError("physically invalid operating point")
        prev_rpm = obs["rpm"]
        computed_power = obs["voltage_v"] * obs["current_a"]
        difference_w = obs["reported_power_w"] - computed_power
        # A 2% mismatch is not precision proof: conservative QA threshold
        # catches published transcription/units errors without correcting data.
        power_inconsistent = abs(difference_w) > max(.02 * computed_power, .25)
        if power_inconsistent:
            anomalies.append({
                "case": obs["case"], "source_reported_power_w": obs["reported_power_w"],
                "voltage_times_current_w": computed_power,
                "difference_w": difference_w,
                "reason": "published_power_inconsistent_with_reported_voltage_and_current",
            })
        row = {
            **obs,
            "calculated_power_from_voltage_times_current_w": computed_power,
            "published_power_is_internally_consistent": not power_inconsistent,
            "within_aeroforge_reference_rpm_range": bool(lo <= obs["rpm"] <= hi),
            "aeroforge_reference_thrust_n": None,
            "thrust_difference_external_minus_reference_n": None,
            "relative_difference_pct_vs_reference": None,
            "difference_is_a_physically_valid_prediction_error": False,
        }
        if lo <= obs["rpm"] <= hi:
            # This interpolation uses the P80 bench *only*, never the external
            # measurement rows. It is a different installed assembly.
            try:
                predicted = model.thrust_n(obs["rpm"]).value
            except OutOfEnvelopeError as exc:
                raise ValueError("inconsistent RPM envelope handling") from exc
            difference = obs["force_n"] - predicted
            row["aeroforge_reference_thrust_n"] = predicted
            row["thrust_difference_external_minus_reference_n"] = difference
            row["relative_difference_pct_vs_reference"] = 100 * difference / predicted
            overlap.append(row)
        source_rows.append(row)
    return {
        "dataset_id": spec["id"],
        "source": {
            "paper": spec["title"],
            "authors": spec["authors"],
            "doi": spec["doi"],
            "url": spec["url"],
            "license": spec["license"],
            "source_test_motor": spec["test_motor"],
            "source_test_esc": spec["test_esc"],
            "source_test_mount": spec["test_mount"],
            "original_raw_sensor_record_available": False,
            "reported_measurements_not_authenticated_by_aeroforge": True,
        },
        "reference": {
            "propeller_id": prop.id,
            "motor_id": motor.id,
            "same_propeller_geometry": True,
            "same_motor": False,
            "same_mounting_configuration_verified": False,
            "rpm_envelope": [float(lo), float(hi)],
            "model": "P80 manufacturer_static_thrust_PCHIP_vs_rpm",
        },
        "data_quality": {
            "published_measurement_count": len(source_rows),
            "reported_power_inconsistency_count": len(anomalies),
            "reported_power_anomalies": anomalies,
            "provenance_issue": "published Table 5 power must NOT be silently corrected",
        },
        "comparison": {
            "in_envelope_count": len(overlap),
            "out_of_envelope_count": len(source_rows) - len(overlap),
            "mean_absolute_relative_difference_pct_descriptive_only":
                mean(abs(r["relative_difference_pct_vs_reference"]) for r in overlap)
                if overlap else None,
            "mean_signed_relative_difference_pct_descriptive_only":
                mean(r["relative_difference_pct_vs_reference"] for r in overlap)
                if overlap else None,
            "rows": source_rows,
        },
        "verdict": "REAL_EXPERIMENTAL_PROP_DATA_BUT_INSTALLATION_AND_MOTOR_MISMATCH",
        "independent_physical_validation_of_aeroforge_reference": False,
        "supports_automatic_ground_effect_correction": False,
        "supports_aeroforge_electrical_power_comparison": False,
        "supports_human_flight_or_aircraft_safety_claim": False,
        "physical_equivalence_established": False,
        "limitations": [
            "Same propeller model does not establish same assembly performance under another motor and mount",
            "Published MN1010 KV135 motor is different from AeroForge P80 III KV100 motor",
            "Paper's nearby mounting plate, 50 mm spacing and downstream aerodynamic obstruction change measured thrust",
            "Reference P80 manufacturer test mounting, ambient conditions and full uncertainty are not matched",
            "No experimental force or power data were used to calibrate or modify the existing P80 model",
            "Below-envelope rows are never extrapolated; overlap residuals are descriptive and not a validation success metric",
            "Published row #2 has a severe electrical-power inconsistency; raw value retained and explicitly flagged",
            "Original instrument calibration, raw sensor files and uncertainty budget not independently audited",
            "Do not apply a ground-effect correction derived from this paper to the capstone or any aircraft",
            "Real flight validation still requires exactly matched independent physical hardware tests",
        ],
    }
