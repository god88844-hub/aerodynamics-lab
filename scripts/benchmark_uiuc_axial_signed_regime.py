"""Post-P0A-009 M24 evaluation through the canonical signed-regime module.

Routes the frozen M24 UIUC axial-sweep protocol through
``packages/physics/aerodynamics/axial_prop.py`` (the canonical signed-regime
model of record) and publishes the per-row delta WITHOUT mutating the frozen
M21/M24 baseline artifacts:

- Per admitted row: canonical coefficients (bit-identical to the frozen
  protocol's interpolation), signed SI quantities (T/Q/P through the exact
  equations, rho declared), measurement-sign-indeterminacy classification
  (|CT_meas| <= delta_res, the 4-decimal source resolution), and prediction
  magnitude against the PREDECLARED M24 tolerances in
  docs/VALIDATION_TOLERANCES.md (CT MAE <= 0.001, CP MAE <= 0.0005).
- No predicted-side count threshold exists in the rule (P0A-008 reviewer
  guardrail): measurement indeterminacy depends only on the instrument/table
  resolution; prediction quality is judged separately.
- DEVELOPMENT protocol revision locked prospectively for future confirmatory
  holdouts; no M24 physical acceptance is claimed from DEVELOPMENT data.

Usage (sources stay outside the repository):
    python scripts/benchmark_uiuc_axial_signed_regime.py SWEEP_DIRECTORY OUTPUT.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from math import isfinite, pi
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "packages")]

from physics.aerodynamics.axial_prop import (  # noqa: E402
    AxialEnvelope,
    AxialPropellerModel,
    PlaneKnots,
)

PLAN = ROOT / "docs/campaigns/m24_uiuc_axial_sweeps_freeze.json"
FROZEN_RESULTS = ROOT / "docs/campaigns/m24_uiuc_axial_sweeps_results.json"
STATIC_FILE = ROOT / "data/benchmarks/uiuc/apce_10x5_static_pg0819.txt"
PLAN_NAME = "m24-uiuc-signed-regime-delta-v1"
# Predeclared M24 tolerances (docs/VALIDATION_TOLERANCES.md, policy v1.0.0,
# PROSPECTIVE_PENDING_OWNER_AND_QUALIFIED_REVIEW — DEVELOPMENT protocol
# revision locked prospectively; no physical acceptance claim).
PREDECLARED_CT_MAE = 0.001
PREDECLARED_CP_MAE = 0.0005
# Declared air density for the published SI-scale columns (estimate for
# magnitude illustration only; the scored metrics are dimensionless).
DECLARED_RHO_KG_M3 = 1.225
# The M24 hardware: APC Thin Electric 10x5 -> D = 10 in = 0.254 m.
DIAMETER_M = 10.0 * 0.0254
# Measurement sign indeterminacy: the 4-decimal source-table resolution
# (delta_res) — depends ONLY on the instrument/table format.
TABLE_CT_DECIMALS = 4
DELTA_RES_CT = 10.0 ** (-TABLE_CT_DECIMALS)


def read_table(path: Path, checksum: str, header: tuple[str, ...],
               *, normalize_line_endings: bool = False):
    data = path.read_bytes()
    if normalize_line_endings:
        data = data.replace(b"\r\n", b"\n")
    if hashlib.sha256(data).hexdigest() != checksum:
        raise ValueError(f"Unexpected SHA-256 for {path}")
    heading, *lines = data.decode("ascii").splitlines()
    if tuple(heading.split()) != header:
        raise ValueError(f"Unexpected columns in {path}")
    rows = []
    for line in lines:
        values = tuple(map(float, line.split()))
        if len(values) != len(header) or not all(map(isfinite, values)):
            raise ValueError(f"Invalid numeric row in {path}")
        rows.append(values[:3])
    if len(rows) < 2 or any(a[0] >= b[0] for a, b in zip(rows, rows[1:])):
        raise ValueError(f"Expected strictly increasing data in {path}")
    return rows


def build_model(source_dir: Path) -> tuple[AxialPropellerModel, dict]:
    plan_bytes = PLAN.read_bytes().replace(b"\r\n", b"\n")
    plan = json.loads(plan_bytes)
    static = read_table(STATIC_FILE, plan["static_sha256"], ("RPM", "CT", "CP"),
                        normalize_line_endings=True)

    def load(record):
        return read_table(source_dir / record["file"], record["sha256"],
                          ("J", "CT", "CP", "eta"))

    low_record, upper_low_record, upper_high_record = plan["calibration"]
    low = load(low_record)
    seam = plan["upper_plane_seam_j"]
    high = [row for row in load(upper_low_record) if row[0] < seam]
    high.extend(row for row in load(upper_high_record) if row[0] >= seam)
    low_rpm = low_record["rpm"]
    high_rpm = (upper_low_record["rpm"] + upper_high_record["rpm"]) / 2.0
    j_min = max(low[0][0], high[0][0])
    j_max = min(low[-1][0], high[-1][0])

    envelope = AxialEnvelope(
        rpm_min=low_rpm, rpm_max=high_rpm, j_min=j_min, j_max=j_max,
        provenance="frozen M24 calibration envelope "
                   "(docs/campaigns/m24_uiuc_axial_sweeps_freeze.json)")
    model = AxialPropellerModel(
        ((low_rpm, PlaneKnots(tuple(low))),
         (high_rpm, PlaneKnots(tuple(high)))),
        diameter_m=DIAMETER_M, envelope=envelope)
    provenance = {
        "plan_sha256_normalized": hashlib.sha256(plan_bytes).hexdigest(),
        "source_files": {record["file"]: record["sha256"]
                         for record in [*plan["calibration"], *plan["holdout"]]},
        "static_file_sha256_normalized": hashlib.sha256(
            STATIC_FILE.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
        "low_plane_rpm": low_rpm, "high_plane_rpm": high_rpm,
        "seam_j": seam,
        "calibration_knots_low": [list(row) for row in low],
        "calibration_knots_high": [list(row) for row in high],
        "static_table": [list(row) for row in static],
    }
    return model, provenance


def evaluate_signed_regime(source_dir: Path) -> dict:
    model, provenance = build_model(source_dir)
    frozen = json.loads(FROZEN_RESULTS.read_text(encoding="utf-8"))
    plan_bytes = PLAN.read_bytes().replace(b"\r\n", b"\n")
    plan = json.loads(plan_bytes)
    holdout_files = {record["rpm"]: record for record in plan["holdout"]}

    rows = []
    excluded_rows = []
    for record in plan["holdout"]:
        rpm = record["rpm"]
        sweep = read_table(source_dir / record["file"], record["sha256"],
                           ("J", "CT", "CP", "eta"))
        for j, ct_meas, cp_meas in sweep:
            label = model.classify(rpm, j * (rpm / 60.0) * model.diameter_m,
                                   DECLARED_RHO_KG_M3)
            if label != "supported":
                excluded_rows.append({
                    "rpm": rpm, "j": j, "ct_meas": ct_meas, "cp_meas": cp_meas,
                    "envelope_class": label})
                continue
            ct_pred, cp_pred = model.coefficients(j, rpm)
            load = model.evaluate(rpm, j * (rpm / 60.0) * model.diameter_m,
                                  DECLARED_RHO_KG_M3)
            rows.append({
                "rpm": rpm, "j": j,
                "ct_meas": ct_meas, "cp_meas": cp_meas,
                "ct_pred": ct_pred, "cp_pred": cp_pred,
                "ct_error": ct_pred - ct_meas, "cp_error": cp_pred - cp_meas,
                "envelope_class": "supported",
                "measurement_sign_indeterminate": abs(ct_meas) <= DELTA_RES_CT,
                "ct_error_within_predeclared": abs(ct_pred - ct_meas) <= PREDECLARED_CT_MAE,
                "cp_error_within_predeclared": abs(cp_pred - cp_meas) <= PREDECLARED_CP_MAE,
                "thrust_n_declared_rho": load.thrust_n,
                "torque_n_m_declared_rho": load.torque_n_m,
                "power_w_declared_rho": load.power_w,
            })

    # Sign-disagreement classification under the resolution-aware rule
    # (P0A-008 reviewer guardrail: NO predicted-side count threshold).
    frozen_sweeps = {r["rpm"]: r for r in frozen["heldout_sweeps"]}
    frozen_disagreement = json.loads((
        ROOT / "docs/campaigns/m24_uiuc_sign_disagreement_diagnosis.json"
    ).read_text(encoding="utf-8"))["row"]
    disagreement_classifications = {}
    # Recompute the three models' predictions at the diagnosed row through
    # canonical/frozen forms for the classification record.
    row_rpm, row_j = frozen_disagreement["rpm"], frozen_disagreement["j"]
    ct_meas_row = frozen_disagreement["measured_ct"]
    axial_ct = next(r["ct_pred"] for r in rows
                    if r["rpm"] == row_rpm and r["j"] == row_j)
    stat_ct = _static_interpolation(provenance["static_table"], row_rpm)
    lo = _plane_interpolation(provenance["calibration_knots_low"], row_j)
    hi = _plane_interpolation(provenance["calibration_knots_high"], row_j)
    aro_ct = lo + 0.5 * (hi - lo)
    for model_name, predicted_ct in (
        ("axial_interpolator", axial_ct),
        ("advance_ratio_only", aro_ct),
        ("static_reference", stat_ct),
    ):
        sign_disagrees = (predicted_ct <= 0.0) != (ct_meas_row <= 0.0)
        disagreement_classifications[model_name] = {
            "predicted_ct": predicted_ct,
            "sign_disagreement": sign_disagrees,
            "measurement_sign_indeterminate": abs(ct_meas_row) <= DELTA_RES_CT,
            "prediction_magnitude_error": abs(predicted_ct - ct_meas_row),
            "magnitude_within_predeclared_ct_tolerance":
                abs(predicted_ct - ct_meas_row) <= PREDECLARED_CT_MAE,
        }

    def mae(values):
        return round(sum(abs(v) for v in values) / len(values), 10)

    after = {
        "rows_scored": len(rows),
        "rows_excluded_envelope": len(excluded_rows),
        "ct_mae": mae([r["ct_error"] for r in rows]),
        "cp_mae": mae([r["cp_error"] for r in rows]),
        "sign_classification": {
            "hard_sign_disagreements": sum(
                1 for c in disagreement_classifications.values()
                if c["sign_disagreement"]
                and not c["measurement_sign_indeterminate"]),
            "measurement_sign_indeterminate_disagreements": sum(
                1 for c in disagreement_classifications.values()
                if c["sign_disagreement"] and c["measurement_sign_indeterminate"]),
            "magnitude_failures_at_disagreements": sum(
                1 for c in disagreement_classifications.values()
                if c["sign_disagreement"]
                and not c["magnitude_within_predeclared_ct_tolerance"]),
        },
        "ct_mae_within_predeclared": mae([r["ct_error"] for r in rows]) <= PREDECLARED_CT_MAE,
        "cp_mae_within_predeclared": mae([r["cp_error"] for r in rows]) <= PREDECLARED_CP_MAE,
    }
    before = {
        "rows_scored": frozen["rows_scored"],
        "rows_outside_calibration_j": frozen["rows_outside_calibration_j"],
        "ct_mae": frozen["errors"]["axial_interpolator"]["ct"]["mae"],
        "cp_mae": frozen["errors"]["axial_interpolator"]["cp"]["mae"],
        "sign_disagreements": frozen["heldout_sweeps"][2]["thrust_sign_disagreements"]
        if len(frozen["heldout_sweeps"]) == 3 else None,
    }
    return {
        "plan": PLAN_NAME,
        "source": {
            "url": "https://m-selig.ae.illinois.edu/props/volume-1/data/",
            **{k: v for k, v in provenance.items() if k != "static_table"},
            "static_table_in_repo": str(STATIC_FILE.relative_to(ROOT)),
        },
        "canonical_module": "packages/physics/aerodynamics/axial_prop.py",
        "envelope": {"j": [model.envelope.j_min, model.envelope.j_max],
                     "rpm": [model.envelope.rpm_min, model.envelope.rpm_max],
                     "provenance": model.envelope.provenance},
        "diameter_m": model.diameter_m,
        "declared_rho_kg_m3": DECLARED_RHO_KG_M3,
        "predeclared_tolerances": {
            "ct_mae": PREDECLARED_CT_MAE, "cp_mae": PREDECLARED_CP_MAE,
            "source": "docs/VALIDATION_TOLERANCES.md policy v1.0.0 "
                      "(PROSPECTIVE_PENDING_OWNER_AND_QUALIFIED_REVIEW)",
        },
        "measurement_sign_resolution": {
            "table_ct_decimal_places": TABLE_CT_DECIMALS,
            "delta_res_ct": DELTA_RES_CT,
            "rule": "measurement sign indeterminate iff |CT_meas| <= delta_res; "
                    "prediction quality is judged separately against the "
                    "predeclared M24 CT tolerance; there is NO predicted-side "
                    "count threshold (P0A-008 reviewer guardrail)",
            "protocol_status": "DEVELOPMENT protocol revision locked "
                               "prospectively for future confirmatory holdouts; "
                               "no M24 physical acceptance claimed",
        },
        "calibration_knots": {
            "low_plane_rpm": provenance["low_plane_rpm"],
            "high_plane_rpm": provenance["high_plane_rpm"],
            "seam_j": provenance["seam_j"],
            "low": provenance["calibration_knots_low"],
            "high": provenance["calibration_knots_high"],
        },
        "rows": rows,
        "excluded_rows": excluded_rows,
        "sign_disagreement_row_classifications": {
            "row": {"rpm": row_rpm, "j": row_j, "measured_ct": ct_meas_row},
            "models": disagreement_classifications,
        },
        "before": before,
        "after": after,
    }


def _plane_interpolation(knots, j):
    """Linear interpolation matching the canonical PlaneKnots form exactly."""
    pairs = [(k[0], k[1]) for k in knots]
    for (j_lo, ct_lo), (j_hi, ct_hi) in zip(pairs, pairs[1:]):
        if j_lo <= j <= j_hi:
            weight = (j - j_lo) / (j_hi - j_lo)
            return ct_lo + weight * (ct_hi - ct_lo)
    raise ValueError(f"J {j} outside plane support")


def _static_interpolation(static, rpm):
    """Linear interpolation matching the frozen benchmark's mix form."""
    pairs = [(row[0], row[1]) for row in static]
    for (rpm_lo, ct_lo), (rpm_hi, ct_hi) in zip(pairs, pairs[1:]):
        if rpm_lo <= rpm <= rpm_hi:
            weight = (rpm - rpm_lo) / (rpm_hi - rpm_lo)
            return ct_lo + weight * (ct_hi - ct_lo)
    raise ValueError(f"RPM {rpm} outside static support")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = evaluate_signed_regime(args.source_dir)
    args.output.write_text(json.dumps(result, indent=2) + "\n",
                           encoding="utf-8", newline="\n")
    print(f"wrote {args.output}")
    after = result["after"]
    print(f"rows {after['rows_scored']} (excluded {after['rows_excluded_envelope']}) "
          f"| CT MAE {after['ct_mae']:.10f} | CP MAE {after['cp_mae']:.10f} "
          f"| sign hard {after['sign_classification']['hard_sign_disagreements']} "
          f"indeterminate {after['sign_classification']['measurement_sign_indeterminate_disagreements']}")
