"""M26.8 regime-by-channel holdout availability, from rehashed original files.

This is a *reported* coverage preflight, not physically authenticated flights.
It distinguishes calibration from holdout and never pools unrelated regimes.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from physics.validation.flight_channel_coverage import audit_original_flight_channel_coverage
from physics.validation.flight_holdout_preflight import prepare_whole_flight_holdout_manifest
from physics.validation.flight_channel_csv import _CHANNEL_UNITS

_REQUIRED = {"operating_regime_id", "channel"}


def audit_regime_holdout_coverage(
    root, source_manifest: Mapping, *,
    holdout_case: Mapping,
    original_csv_sources: Sequence[Mapping],
    required_regime_channels: Sequence[Mapping],
    minimum_distinct_holdout_groups_per_regime: int = 2,
) -> dict:
    """Count distinct operator-declared held-out groups in each exact regime."""
    if (type(minimum_distinct_holdout_groups_per_regime) is not int
            or not 2 <= minimum_distinct_holdout_groups_per_regime <= 50):
        raise ValueError("minimum_distinct_holdout_groups_per_regime must be 2..50")
    if (not isinstance(holdout_case, Mapping)
            or set(holdout_case) != {
                "frozen_model_git_sha", "frozen_protocol_sha256", "preregistered_utc",
                "frozen_model_utc", "partitions", "minimum_holdout_groups",
            }):
        raise ValueError("exact frozen holdout_case fields required")
    if (isinstance(required_regime_channels, (str, bytes))
            or not isinstance(required_regime_channels, Sequence)
            or not 1 <= len(required_regime_channels) <= 100):
        raise ValueError("1..100 required regime-channel pairs needed")
    pairs = set()
    for row in required_regime_channels:
        if not isinstance(row, Mapping) or set(row) != _REQUIRED:
            raise ValueError("each required regime-channel pair must have exact keys")
        regime, channel = row["operating_regime_id"], row["channel"]
        if (not isinstance(regime, str) or not regime
                or len(regime) > 100 or channel not in _CHANNEL_UNITS):
            raise ValueError("unsupported regime or channel")
        pair = (regime, channel)
        if pair in pairs:
            raise ValueError("duplicate required regime-channel pair")
        pairs.add(pair)

    split = prepare_whole_flight_holdout_manifest(root, source_manifest, **holdout_case)
    availability = audit_original_flight_channel_coverage(
        root, source_manifest,
        required_channels=sorted({x[1] for x in pairs}),
        original_csv_sources=original_csv_sources,
        minimum_distinct_flights_per_channel=2,
    )
    by_flight = {row["flight_id"]: row for row in split["partitions"]}
    groups = {}
    for (regime, channel) in sorted(pairs):
        eligible_flights = set(availability["required_channel_coverage"][channel][
            "declared_flight_ids_with_usable_recordings"
        ])
        eligible_groups = sorted({
            by_flight[flight]["experimental_group_id"]
            for flight in eligible_flights
            if flight in by_flight
            and by_flight[flight]["partition"] == "holdout"
            and by_flight[flight]["operating_regime_id"] == regime
        })
        groups[f"{regime}/{channel}"] = {
            "operating_regime_id": regime,
            "channel": channel,
            "declared_holdout_groups_with_supported_original_csv": eligible_groups,
            "declared_distinct_holdout_group_count": len(eligible_groups),
            "coverage_requirement_met": len(eligible_groups) >= minimum_distinct_holdout_groups_per_regime,
            "true_independence_authenticated": False,
        }
    missing = [name for name, entry in groups.items() if not entry["coverage_requirement_met"]]
    if not availability["operator_reported_coverage_consistent"]:
        missing.append("global original-file/clock/calibration/rights coverage is not complete")
    ready = not missing
    return {
        "status": (
            "OPERATOR_REPORTED_REGIME_HOLDOUT_COVERAGE_SUFFICIENT_UNAUTHENTICATED"
            if ready else "REGIME_HOLDOUT_CHANNEL_COVERAGE_INCOMPLETE"
        ),
        "archive_id": source_manifest["archive_id"],
        "canonical_split_sha256": split["canonical_split_sha256"],
        "regime_channel_coverage": groups,
        "coverage_blockers": missing,
        "operator_reported_coverage_sufficient": ready,
        "external_source_and_rights_authenticated": False,
        "real_holdout_flights_and_sensor_calibration_authenticated": False,
        "physical_prediction_agreement_established": False,
        "flight_release_authorized": False,
    }
