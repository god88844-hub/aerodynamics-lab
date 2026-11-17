"""M26.22: replay derived observations and compare frozen predictions.

This screen does not relabel derived measurements as original instrument rows.
Its numerical criteria use explicit, operator-supplied hard errors and bounds;
source custody, independent blindness and physical accuracy remain unproven.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import math

from physics.validation.derived_observation_admission import admit_derived_observation
from physics.validation.frozen_flight_comparison import _csv_rows
from physics.validation.flight_clock_alignment import _finite


def compare_derived_holdout(
    root, manifest, *, holdout_case, derived_csv_path,
    provenance_json_path, channel, maximum_declared_sample_gap_s,
    frozen_prediction_csv_path, frozen_prediction_sha256,
    measurement_hard_error, numerical_hard_error,
    model_discrepancy_hard_error, predeclared_max_conservative_error,
    predeclared_min_robust_coverage,
):
    from physics.validation.flight_holdout_preflight import prepare_whole_flight_holdout_manifest
    admission = admit_derived_observation(
        root, manifest, derived_csv_path=derived_csv_path,
        provenance_json_path=provenance_json_path,
        output_channel=channel,
        maximum_declared_sample_gap_s=maximum_declared_sample_gap_s,
    )
    if not admission["operator_sampling_gap_requirement_met"]:
        raise ValueError("derived observation sampling gaps exceed declared maximum")
    split = prepare_whole_flight_holdout_manifest(root, manifest, **holdout_case)
    chosen = [r for r in split["partitions"] if r["flight_id"] == admission["flight_id_operator_declared"]]
    if len(chosen) != 1 or chosen[0]["partition"] != "holdout":
        raise ValueError("derived original source is not declared whole-flight holdout")
    errors = [
        _finite(v, key, nonnegative=True) for key, v in (
            ("measurement_hard_error", measurement_hard_error),
            ("numerical_hard_error", numerical_hard_error),
            ("model_discrepancy_hard_error", model_discrepancy_hard_error),
        )
    ]
    allowance = _finite(predeclared_max_conservative_error, "predeclared_max_conservative_error", nonnegative=True)
    mincoverage = _finite(predeclared_min_robust_coverage, "predeclared_min_robust_coverage", nonnegative=True)
    if mincoverage > 1 or not math.isfinite(sum(errors)):
        raise ValueError("coverage or total uncertainty outside supported range")
    predpath = Path(frozen_prediction_csv_path)
    original_root = Path(root).resolve(strict=True)
    if predpath.is_symlink() or not predpath.is_file():
        raise ValueError("frozen prediction must be a regular nonsymlink CSV")
    p = predpath.resolve(strict=True)
    if p.is_relative_to(original_root) or p.suffix.lower() != ".csv" or not 0 < p.stat().st_size <= 8_000_000:
        raise ValueError("frozen predictions must be bounded separate CSV outside originals")
    raw_pred = p.read_bytes()
    if sha256(raw_pred).hexdigest() != frozen_prediction_sha256:
        raise ValueError("frozen prediction source SHA-256 mismatch")
    observed_bytes = Path(derived_csv_path).read_bytes()
    if sha256(observed_bytes).hexdigest() != admission["derived_csv_sha256"]:
        raise ValueError("derived observation changed after replay")
    obs = _csv_rows(observed_bytes, ["t_s", channel], "replayed derived observation")
    predictions = _csv_rows(raw_pred, ["t_s", "prediction", "lower", "upper"], "frozen prediction")
    if len(obs) != len(predictions):
        raise ValueError("frozen prediction and derived observation sample counts differ")
    robust = 0
    max_conservative = 0.
    sumsq = 0.
    for (t, value), (pt, predicted, low, high) in zip(obs, predictions):
        if t != pt:
            raise ValueError("frozen prediction grid differs from derived observation; no interpolation")
        if not low <= predicted <= high:
            raise ValueError("frozen prediction estimate outside own interval")
        residual = abs(predicted - value)
        upper = residual + sum(errors)
        if not math.isfinite(upper):
            raise ValueError("unbounded residual")
        max_conservative = max(max_conservative, upper)
        sumsq += residual * residual
        robust += int(low <= value - errors[0] and value + errors[0] <= high)
    rmse = math.sqrt(sumsq / len(obs))
    if not math.isfinite(rmse):
        raise ValueError("unbounded root mean square error")
    coverage = robust / len(obs)
    passed = max_conservative <= allowance and coverage >= mincoverage
    return {
        "status": "DERIVED_HOLDOUT_CONDITIONAL_NUMERIC_PASS_UNAUTHENTICATED" if passed else "FAIL_DERIVED_HOLDOUT_DECLARED_NUMERIC_GATE",
        "flight_id": chosen[0]["flight_id"],
        "experimental_group_id": chosen[0]["experimental_group_id"],
        "operating_regime_id": chosen[0]["operating_regime_id"],
        "channel": channel,
        "source_kind": "derived_from_original_instrument_bytes_not_original",
        "original_source_sha256": admission["original_source_sha256"],
        "derived_csv_sha256": admission["derived_csv_sha256"],
        "conversion_spec_sha256": admission["conversion_spec_sha256"],
        "frozen_prediction_sha256": frozen_prediction_sha256,
        "canonical_split_sha256": split["canonical_split_sha256"],
        "samples_compared": len(obs),
        "nominal_rmse": rmse,
        "max_conservative_residual": max_conservative,
        "robust_interval_coverage_fraction": coverage,
        "operator_declared_numerical_gate_passed": passed,
        "independent_source_unit_calibration_verified": False,
        "physical_prediction_equivalence_established": False,
        "flight_release_authorized": False,
    }
