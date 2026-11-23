"""P0A-011: canonical offline/desktop UAV-FD per-motor fault indicator.

DEVELOPMENT ONLY. Training uses whole healthy recordings exclusively; fault
labels cannot enter the feature, calibration, persistence or verdict API.
The shared detector accepts already qualified two-second windows so the desktop
telemetry adapter and offline MAT adapter execute identical decisions.

A 1P frequency association is NOT causal motor isolation when rotor orders
overlap. This module does not certify airworthiness, fault onset, or latency.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from statistics import median
from typing import Mapping, Sequence

TRAIN_IDS = frozenset({"NO_FAULT1.mat", "NO_FAULT4.mat"})
MOTOR_COUNT = 6
WINDOW_SECONDS = 2.0
MIN_ELIGIBLE = 6
MIN_COVERAGE = 0.25
RPM_ENVELOPE = (3600.0, 7800.0)
QUANTILE = 0.95
CONFIRM_K = 2
CONFIRM_W = 5
# Predeclared engineering rules, not fitted from the M25 holdouts.
RELEASE_FRACTION = 0.8
POLICY = "p0a-011-development-v1"


@dataclass(frozen=True)
class ElectricalWindow:
    index: int
    start_s: float
    rpm: tuple[float, ...]
    normalized_power: tuple[float, ...]  # measured W / (RPM / 6000)^3


@dataclass(frozen=True)
class VibrationWindow:
    index: int
    start_s: float
    rpm: tuple[float, ...]
    own_1p_amplitude: tuple[float, ...]  # same shared-IMU 1P spectral method per ESC


@dataclass(frozen=True)
class TrainingFlight:
    electrical: tuple[ElectricalWindow, ...]
    vibration: tuple[VibrationWindow, ...]


def _six(values: Sequence[float], name: str, *, positive: bool = True) -> tuple[float, ...]:
    if len(values) != MOTOR_COUNT:
        raise ValueError(f"{name}: exactly six ESC channels required")
    result = tuple(float(v) for v in values)
    if not all(isfinite(v) and (v > 0 if positive else v >= 0) for v in result):
        raise ValueError(f"{name}: finite {'positive' if positive else 'nonnegative'} values required")
    return result


def _check_window(w: ElectricalWindow | VibrationWindow) -> None:
    if type(w.index) is not int or w.index < 0 or not isfinite(w.start_s) or w.start_s < 0:
        raise ValueError("invalid chronological window metadata")
    rpm = _six(w.rpm, "rpm")
    if not all(RPM_ENVELOPE[0] <= r <= RPM_ENVELOPE[1] for r in rpm):
        raise ValueError("out-of-envelope measured RPM")
    if isinstance(w, ElectricalWindow):
        _six(w.normalized_power, "normalized_power")
    else:
        _six(w.own_1p_amplitude, "own_1p_amplitude", positive=False)


def _check_sequence(windows: Sequence[ElectricalWindow] | Sequence[VibrationWindow]) -> None:
    last_index, last_time = -1, -1.0
    for w in windows:
        _check_window(w)
        if w.index <= last_index or w.start_s <= last_time:
            raise ValueError("duplicate or unordered whole-recording windows")
        last_index, last_time = w.index, w.start_s


def _higher_quantile(samples: Sequence[float]) -> float:
    if not samples:
        raise ValueError("empty train-only calibration distribution")
    ordered = sorted(float(v) for v in samples)
    # Numpy-style method="higher" quantile, index=ceil((n-1)*q).
    from math import ceil
    return ordered[ceil((len(ordered) - 1) * QUANTILE)]


def _vibration_scaled(w: VibrationWindow) -> tuple[float, ...]:
    # Rotor-specific imbalance scaling (one RPM per channel; no fleet maximum).
    return tuple(float(a / (rpm / 6000.0) ** 2)
                 for a, rpm in zip(w.own_1p_amplitude, w.rpm, strict=True))


def _features(w: ElectricalWindow | VibrationWindow, center: Sequence[float]) -> tuple[tuple[str, int, float], ...]:
    values = w.normalized_power if isinstance(w, ElectricalWindow) else _vibration_scaled(w)
    if isinstance(w, ElectricalWindow):
        return tuple((direction, i, value / center[i] - 1 if direction == "INCREASED_LOAD"
                      else 1 - value / center[i])
                     for i, value in enumerate(values)
                     for direction in ("INCREASED_LOAD", "POWER_DEFICIT"))
    return tuple(("ROTOR_1P_VIBRATION", i, value / center[i] - 1)
                 for i, value in enumerate(values))


def calibrate(training: Mapping[str, TrainingFlight]) -> dict:
    """Fit only on the two named, complete, disjoint healthy training flights.

    Label values are deliberately absent from this API; passing a holdout
    recording even alongside the correct two is rejected.
    """
    if set(training) != TRAIN_IDS:
        raise ValueError("calibration requires exactly NO_FAULT1 and NO_FAULT4, no holdouts")
    all_e, all_v = [], []
    per_flight = {}
    for name in sorted(TRAIN_IDS):
        flight = training[name]
        _check_sequence(flight.electrical)
        _check_sequence(flight.vibration)
        if len(flight.electrical) < MIN_ELIGIBLE or len(flight.vibration) < MIN_ELIGIBLE:
            raise ValueError("too few eligible training windows")
        all_e.extend(flight.electrical)
        all_v.extend(flight.vibration)
        per_flight[name] = {"electrical": len(flight.electrical), "vibration": len(flight.vibration)}
    ecenter = [median(w.normalized_power[i] for w in all_e) for i in range(MOTOR_COUNT)]
    vcenter = [median(_vibration_scaled(w)[i] for w in all_v) for i in range(MOTOR_COUNT)]
    if not all(isfinite(x) and x > 0 for x in ecenter + vcenter):
        raise ValueError("uncalibrated or zero healthy motor spectral baseline")
    efeatures = [_features(w, ecenter) for w in all_e]
    vfeatures = [_features(w, vcenter) for w in all_v]
    thresholds = {}
    for channel, features in (("electrical", efeatures), ("vibration", vfeatures)):
        for direction, i, _ in features[0]:
            key = f"{channel}:{direction}:ESC_{i}"
            col = next(j for j, x in enumerate(features[0]) if x[:2] == (direction, i))
            thresholds[key] = _higher_quantile([max(0.0, f[col][2]) for f in features])
    rpm_medians = [median(w.rpm) for w in [*all_e, *all_v]]
    return {
        "policy": POLICY,
        "development_only": True,
        "train_recordings": sorted(TRAIN_IDS),
        "training_windows": per_flight,
        "electrical_centers": ecenter,
        "vibration_centers": vcenter,
        "thresholds": thresholds,
        "median_rpm_support": [min(rpm_medians), max(rpm_medians)],
        "confirmation": {"k": CONFIRM_K, "window_span": CONFIRM_W,
                         "release_fraction": RELEASE_FRACTION},
        "minimum_eligible_windows": MIN_ELIGIBLE,
        "minimum_coverage": MIN_COVERAGE,
    }


def _validate_fit(fit: Mapping) -> None:
    if (not fit or fit.get("policy") != POLICY or fit.get("train_recordings") != sorted(TRAIN_IDS)
            or fit.get("development_only") is not True
            or fit.get("confirmation") != {"k": CONFIRM_K, "window_span": CONFIRM_W,
                                            "release_fraction": RELEASE_FRACTION}):
        raise ValueError("missing or unsupported healthy training calibration")
    _six(fit["electrical_centers"], "healthy electrical calibration")
    _six(fit["vibration_centers"], "healthy vibration calibration")
    lo, hi = fit["median_rpm_support"]
    if not (isfinite(lo) and isfinite(hi) and 0 < lo <= hi):
        raise ValueError("invalid train-only RPM support")
    expected = {
        f"{channel}:{direction}:ESC_{i}"
        for i in range(MOTOR_COUNT)
        for channel, directions in (("electrical", ("INCREASED_LOAD", "POWER_DEFICIT")),
                                    ("vibration", ("ROTOR_1P_VIBRATION",)))
        for direction in directions
    }
    if set(fit["thresholds"]) != expected or not all(
        isfinite(v) and v >= 0 for v in fit["thresholds"].values()
    ):
        raise ValueError("incomplete per-motor train-only thresholds")


def _event(channel: str, direction: str, motor: int, first: float, confirm: float,
           *, onset_s: float | None, deadline_s: float | None) -> dict:
    if onset_s is None:
        compliance = "NOT_ASSESSABLE_NO_FAULT_ONSET"
    elif deadline_s is None:
        compliance = "NOT_ASSESSABLE_NO_DEADLINE"
    else:
        compliance = "MET" if confirm <= onset_s + deadline_s else "MISSED"
    return {
        "state": "DETECT", "fault_class": direction,
        "channel": channel, "source_channel": f"ESC_{motor}",
        "attribution": "ROTOR_FREQUENCY_ASSOCIATION_NOT_CAUSAL_ISOLATION"
                       if channel == "vibration" else "MEASURED_ESC_CHANNEL",
        "first_exceedance_time_s": first, "confirmation_time_s": confirm,
        "time_reference": "SECONDS_RELATIVE_TO_THIS_CHANNEL_RECORDING_START",
        "deadline_s": deadline_s, "deadline_compliance": compliance,
    }


def _scan(channel: str, windows: Sequence[ElectricalWindow] | Sequence[VibrationWindow],
          fit: Mapping, *, onset_s: float | None, deadline_s: float | None) -> dict | None:
    center = fit["electrical_centers"] if channel == "electrical" else fit["vibration_centers"]
    pending: dict[str, list[tuple[int, float]]] = {}
    for w in windows:
        for direction, motor, score in _features(w, center):
            key = f"{channel}:{direction}:ESC_{motor}"
            high = fit["thresholds"][key]
            # Equal-to-training-high is not an exceedance. The lower release
            # bound prevents a marginal return from resetting a live channel;
            # the k-of-W window remains bounded by recording window index.
            if score <= high:
                # A low intervening window is not an alert; it also must not
                # erase earlier independent exceedances inside the bounded
                # k-of-W horizon (the exact M1 failure diagnosed in P0A-010).
                # RELEASE_FRACTION is a post-confirmation latch/release value.
                continue
            queue = pending.setdefault(key, [])
            queue[:] = [(i, t) for i, t in queue if w.index - i < CONFIRM_W]
            queue.append((w.index, w.start_s))
            if len(queue) >= CONFIRM_K:
                return _event(channel, direction, motor, queue[0][1], w.start_s,
                              onset_s=onset_s, deadline_s=deadline_s)
    return None


def evaluate(
    fit: Mapping | None,
    electrical: Sequence[ElectricalWindow] | None,
    vibration: Sequence[VibrationWindow] | None,
    *,
    expected_electrical_windows: int,
    expected_vibration_windows: int,
    onset_s: float | None = None,
    deadline_s: float | None = None,
    unsupported_telemetry_observed: bool = False,
) -> dict:
    """Evaluate exactly the same fit/logic in desktop streams or offline MAT.

    Partial unsupported windows may be excluded at the adapter boundary.
    NO-ALERT requires both channels, six windows each, >=25% window coverage.
    An observed DETECT is retained even if the other channel lacks coverage;
    otherwise missing/out-of-support data fail closed to INCONCLUSIVE.
    """
    if onset_s is not None and (not isfinite(onset_s) or onset_s < 0):
        return {"state": "INCONCLUSIVE", "reason": "INVALID_ONSET"}
    if deadline_s is not None and (not isfinite(deadline_s) or deadline_s < 0):
        return {"state": "INCONCLUSIVE", "reason": "INVALID_DEADLINE"}
    try:
        _validate_fit(fit)
        if electrical is None or vibration is None:
            return {"state": "INCONCLUSIVE", "reason": "MISSING_CHANNEL"}
        for stream, expected in ((electrical, expected_electrical_windows),
                                 (vibration, expected_vibration_windows)):
            if type(expected) is not int or expected < 0 or len(stream) > expected:
                return {"state": "INCONCLUSIVE", "reason": "INVALID_COVERAGE_DENOMINATOR"}
            _check_sequence(stream)
        lo, hi = fit["median_rpm_support"]
        def in_support(w):
            return lo <= median(w.rpm) <= hi
        evalid = [w for w in electrical if in_support(w)]
        vvalid = [w for w in vibration if in_support(w)]
        support_lost = len(evalid) != len(electrical) or len(vvalid) != len(vibration)
        events = [x for x in (
            _scan("electrical", evalid, fit, onset_s=onset_s, deadline_s=deadline_s),
            _scan("vibration", vvalid, fit, onset_s=onset_s, deadline_s=deadline_s),
        ) if x is not None]
        if events:
            return {**min(events, key=lambda e: (e["confirmation_time_s"], e["channel"])),
                    "eligible_electrical_windows": len(evalid),
                    "eligible_vibration_windows": len(vvalid)}
        if support_lost:
            return {"state": "INCONCLUSIVE", "reason": "OUTSIDE_TRAIN_RPM_SUPPORT"}
        if unsupported_telemetry_observed:
            return {"state": "INCONCLUSIVE", "reason": "UNSUPPORTED_TELEMETRY_EXCLUDED"}
        if len(evalid) < MIN_ELIGIBLE or len(vvalid) < MIN_ELIGIBLE:
            return {"state": "INCONCLUSIVE", "reason": "INSUFFICIENT_ELIGIBLE_WINDOWS"}
        if (len(evalid) / max(1, expected_electrical_windows) < MIN_COVERAGE
                or len(vvalid) / max(1, expected_vibration_windows) < MIN_COVERAGE):
            return {"state": "INCONCLUSIVE", "reason": "INSUFFICIENT_COVERAGE"}
        return {"state": "NO-ALERT", "reason": "NO_CONFIRMED_TRAIN_CALIBRATED_EXCURSION",
                "eligible_electrical_windows": len(evalid),
                "eligible_vibration_windows": len(vvalid)}
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return {"state": "INCONCLUSIVE", "reason": "INVALID_OR_OUT_OF_ENVELOPE_TELEMETRY"}
