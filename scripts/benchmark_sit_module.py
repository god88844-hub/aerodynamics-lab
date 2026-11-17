"""Chronological voltage and temperature replay of the SIT transporter module."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.integrate import cumulative_trapezoid, trapezoid
from scipy.optimize import LinearConstraint, minimize, nnls

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "packages"), str(ROOT / "packages/shared-schemas")]

from aeroforge_schemas.component import BatterySpec
from physics.propulsion.battery import BatteryPack

SOURCE = "https://doi.org/10.25447/sit.21301188.v1"
SOURCE_SHA256 = "a4679465b35455ca429519fbc47f04f6e42bea608e0de12b978d482873456205"
SOURCE_BYTES = 9_397_987
PLAN = "m21-sit-electrothermal-v1"
CALIBRATION = range(1, 51)
HOLDOUT = {"mid_life": range(151, 201), "late_life": range(329, 379)}
CAPACITY_AH = 5.0
CHARGED_CELL_LIMIT_V = 4.2
VOLTAGE_TAUS = (2, 5, 10, 20, 40, 80)
THERMAL_TAUS = (0, 2, 5, 10, 20, 40)
LIMITS = {"module_v": 80.0, "pack_v": 19.8, "pack_c": 70.0, "charge_ah": 5.0, "current_a": 400.0}
HEADERS = ("Discharge Cycle #", "Time [s]", "Voltage [V]", "Test current [A]", "Test capacity [Ah]")
LABELS = ("module", "P1", "P2", "P3", "P4")


@dataclass
class Cycle:
    number: int
    t: np.ndarray
    current: np.ndarray
    charge_ah: np.ndarray
    recorded_ah: np.ndarray
    voltages: np.ndarray
    temperatures: np.ndarray
    ambient: np.ndarray


def digest(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def load_cycles(path: Path, numbers: range) -> tuple[list[Cycle], dict]:
    from openpyxl import load_workbook  # Optional dependency for this offline benchmark.

    with path.open("rb") as raw:
        if path.stat().st_size != SOURCE_BYTES or hashlib.file_digest(raw, "sha256").hexdigest() != SOURCE_SHA256:
            raise ValueError("workbook does not match the pinned SIT publisher bytes")
    book = load_workbook(path, read_only=True, data_only=True)
    accepted, rejected = [], {}
    try:
        for number in numbers:
            table = book[str(number)].iter_rows(max_col=16, values_only=True)
            header = next(table)
            normalized = tuple(" ".join(str(v).split()) for v in header)
            if normalized[:5] != HEADERS:
                raise ValueError(f"unexpected header in source cycle {number}")
            if not all(
                str(header[index]).startswith(f"UUT2P{pack} {name}")
                for pack in range(1, 5) for index, name in ((6 + pack, "Voltage"), (10 + pack, "Temp"))
            ) or not str(header[-1]).startswith("Ambient Temp"):
                raise ValueError(f"unexpected pack identity columns in source cycle {number}")
            kept = [row for row in table if any(v is not None for v in row)]
            try:
                data = np.array([(*row[:5], *row[7:16]) for row in kept], dtype=float)
            except (TypeError, ValueError):
                rejected[number] = "unparseable_sample"
                continue
            if len(data) < 3 or not np.isfinite(data).all():
                rejected[number] = "missing_or_nonfinite_sample"
                continue
            index, t, module_v, current, recorded_ah = data[:, :5].T
            if (index != number).any() or t[0] != 0 or not np.allclose(np.diff(t), 2, rtol=0, atol=1e-6):
                rejected[number] = "unexpected_cycle_or_sample_clock"
                continue
            voltages = data[:, [2, 5, 6, 7, 8]]
            if (current < 0).any() or (voltages <= 0).any() or (recorded_ah < 0).any():
                rejected[number] = "invalid_discharge_sample"
                continue
            accepted.append(Cycle(number, t, current, cumulative_trapezoid(current, t, initial=0) / 3600,
                                  recorded_ah, voltages, data[:, 9:13], data[:, 13]))
    finally:
        book.close()
    return accepted, rejected


def filtered(signal: np.ndarray, t: np.ndarray, tau_s: float) -> np.ndarray:
    if tau_s == 0:
        return signal.copy()
    result = np.zeros_like(signal)
    for i, dt in enumerate(np.diff(t)):
        decay = np.exp(-dt / tau_s)
        result[i + 1] = decay * result[i] + (1 - decay) * (signal[i] + signal[i + 1]) / 2
    return result


def scaled_fit(design: np.ndarray, target: np.ndarray) -> np.ndarray:
    scale = np.linalg.norm(design, axis=0)
    if (scale == 0).any() or not np.isfinite(scale).all():
        raise ValueError("calibration does not excite every fitted term")
    return nnls(design / scale, target)[0] / scale


def ocv_basis(charge: np.ndarray, knots: np.ndarray) -> np.ndarray:
    # A positive base and descending nonnegative increments keep the OCV monotone.
    steps = np.clip((knots[1:] - charge[:, None]) / np.diff(knots), 0, 1)
    return np.column_stack((np.ones(len(charge)), steps))


def fit_bounded_ocv(design: np.ndarray, target: np.ndarray, knots: int, cells: int) -> np.ndarray:
    coeffs = scaled_fit(design, target)
    limit = CHARGED_CELL_LIMIT_V * cells
    if coeffs[:knots].sum() <= limit:
        return coeffs
    # Convex least squares with nonnegative terms and one upper OCV bound.
    scale = np.linalg.norm(design, axis=0)
    y_scale = np.linalg.norm(target)
    x = design / scale
    y = target / y_scale
    gram, xy = x.T @ x, x.T @ y
    bound = np.r_[y_scale / scale[:knots], np.zeros(len(scale) - knots)]
    initial = coeffs * scale / y_scale
    initial[:knots] *= limit / (bound @ initial)
    fit = minimize(
        lambda b: 0.5 * b @ gram @ b - xy @ b, initial,
        jac=lambda b: gram @ b - xy, method="SLSQP",
        bounds=[(0, None)] * len(scale), constraints=[LinearConstraint(bound, 0, limit)],
        options={"ftol": 1e-13, "maxiter": 500},
    )
    if not fit.success or bound @ fit.x > limit + 1e-8:
        raise ValueError(f"could not enforce the charged-cell OCV bound: {fit.message}")
    return fit.x * y_scale / scale


def battery_models(ocv_v: np.ndarray, ohms: np.ndarray, knots: np.ndarray) -> list[BatteryPack]:
    soc = (100 * (1 - knots / CAPACITY_AH))[::-1]
    return [
        BatteryPack(BatterySpec(
            id=f"sit_uut2_{label}", name=f"SIT UUT2 {label}", chemistry="LiPo",
            cells_series=cells, capacity_ah=CAPACITY_AH, internal_resistance_ohm=r,
            ocv_curve=[{"soc_pct": s, "cell_voltage_v": v / cells} for s, v in zip(soc, volts[::-1], strict=True)],
            source={"source": "Fitted from SIT UUT2 calibration cycles", "url": SOURCE, "estimated": True},
        ))
        for label, cells, volts, r in zip(LABELS, (24, 6, 6, 6, 6), ocv_v.T, ohms, strict=True)
    ]


def fit_voltage(cycles: list[Cycle], knots: np.ndarray, taus: tuple[int, ...]) -> dict:
    charge = np.concatenate([c.charge_ah for c in cycles])
    current = np.concatenate([c.current for c in cycles])
    observations = np.vstack([c.voltages for c in cycles])
    basis = ocv_basis(charge, knots)
    candidates = []
    for tau in taus:
        columns = [basis, -current]
        if tau:
            columns.append(-np.concatenate([filtered(c.current, c.t, tau) for c in cycles]))
        x = np.column_stack(columns)
        coeffs = np.stack([
            fit_bounded_ocv(x, observation, len(knots), cells)
            for observation, cells in zip(observations.T, (24, 6, 6, 6, 6), strict=True)
        ], axis=1)
        curves = ocv_basis(knots, knots) @ coeffs[:len(knots)]
        series = coeffs[len(knots)]
        polarization = coeffs[-1] if tau else np.zeros(len(LABELS))
        batteries = battery_models(curves, series, knots)
        soc = 100 * (1 - charge / CAPACITY_AH)
        errors = []
        for j, model in enumerate(batteries):
            predicted = np.array([model.voltage_under_load(q, i) for q, i in zip(soc, current, strict=True)])
            if tau:
                predicted += x[:, -1] * polarization[j]
            errors.append(float(np.mean((predicted - observations[:, j]) ** 2)))
        candidates.append((float(np.mean(errors)), {
            "tau_s": tau, "ocv_v": curves.round(10).tolist(), "series_ohm": series.round(12).tolist(),
            "polarization_ohm": polarization.round(12).tolist(),
        }))
    return min(candidates, key=lambda candidate: candidate[0])[1]


def thermal_response(
    cycle: Cycle, initial: float, heat_proxy: np.ndarray, source_gain: float, cooling_rate: float,
) -> np.ndarray:
    result = np.empty_like(cycle.t)
    result[0] = initial
    for j, dt in enumerate(np.diff(cycle.t)):
        ambient = (cycle.ambient[j] + cycle.ambient[j + 1]) / 2
        heat = source_gain * (heat_proxy[j] + heat_proxy[j + 1]) / 2
        if cooling_rate:
            weight = -np.expm1(-cooling_rate * dt)
            result[j + 1] = result[j] + weight * (ambient - result[j] + heat / cooling_rate)
        else:
            result[j + 1] = result[j] + heat * dt
    return result


def fit_thermal(cycles: list[Cycle], taus: tuple[int, ...]) -> list[dict]:
    heat = {tau: [filtered(c.current ** 2, c.t, tau) for c in cycles] for tau in taus}
    result = []
    for pack in range(4):
        cooling = []
        for c in cycles:
            use = (c.t >= 150) & (c.t <= 300)
            if use.sum() >= 5 and np.max(c.current[use]) <= 1:
                temp = c.temperatures[use, pack]
                cooling.append((trapezoid(c.ambient[use] - temp, c.t[use]), temp[-1] - temp[0]))
        if not cooling:
            raise ValueError("no low-current cooling segments in the calibration cycles")
        features = np.asarray(cooling)
        rate = float(scaled_fit(features[:, :1], features[:, 1])[0])
        candidates = []
        for tau in taus:
            passive, responses, targets = [], [], []
            for c, proxy in zip(cycles, heat[tau], strict=True):
                target = c.temperatures[:, pack]
                base = thermal_response(c, target[0], proxy, 0, rate)
                unit = thermal_response(c, target[0], proxy, 1, rate)
                passive.append(base)
                responses.append(unit - base)
                targets.append(target)
            base, response, target = map(np.concatenate, (passive, responses, targets))
            gain = float(scaled_fit(response[:, None], target - base)[0])
            error = float(np.mean((base + gain * response - target) ** 2))
            candidates.append((error, {"tau_s": tau, "source_gain": round(gain, 14), "cooling_rate": round(rate, 12)}))
        result.append(min(candidates, key=lambda candidate: candidate[0])[1])
    return result


def calibrate(path: Path) -> dict:
    cycles, rejected = load_cycles(path, CALIBRATION)
    if len(cycles) < 30:
        raise ValueError("too few usable early source cycles")
    maximum = max(float(c.charge_ah[-1]) for c in cycles)
    if not 3.5 < maximum <= CAPACITY_AH:
        raise ValueError("unexpected calibration discharge-charge range")
    knots = np.array([0, 0.4, 1.2, 2.1, 3.0, maximum])
    return {
        "plan": PLAN, "source_sha256": SOURCE_SHA256, "calibration_count": len(cycles),
        "excluded_calibration_cycles": rejected, "max_charge_ah": maximum, "charge_knots_ah": knots.tolist(),
        "fixed_r": fit_voltage(cycles, knots, (0,)), "one_rc": fit_voltage(cycles, knots, VOLTAGE_TAUS),
        "direct_heating": fit_thermal(cycles, (0,)), "lagged_heating": fit_thermal(cycles, THERMAL_TAUS),
    }


def voltage_prediction(c: Cycle, model: dict, batteries: list[BatteryPack]) -> np.ndarray:
    soc = 100 * (1 - c.charge_ah / CAPACITY_AH)
    state = filtered(c.current, c.t, model["tau_s"]) if model["tau_s"] else np.zeros_like(c.t)
    return np.column_stack([
        np.array([b.voltage_under_load(q, i) for q, i in zip(soc, c.current, strict=True)]) - rp * state
        for b, rp in zip(batteries, model["polarization_ohm"], strict=True)
    ])


def temperature_prediction(c: Cycle, models: list[dict]) -> np.ndarray:
    return np.column_stack([
        thermal_response(c, initial, filtered(c.current ** 2, c.t, m["tau_s"]), m["source_gain"], m["cooling_rate"])
        for initial, m in zip(c.temperatures[0], models, strict=True)
    ])


def breaches(v: np.ndarray, temp: np.ndarray, charge: np.ndarray, current: np.ndarray) -> dict[str, np.ndarray]:
    return {
        "module_low_v": v[:, 0] < LIMITS["module_v"],
        "any_pack_low_v": np.any(v[:, 1:] < LIMITS["pack_v"], axis=1),
        "any_pack_high_temp": np.any(temp > LIMITS["pack_c"], axis=1),
        "capacity_exceeded": charge > LIMITS["charge_ah"],
        "nameplate_current_exceeded": current > LIMITS["current_a"],
    }


def exposure(observed: list[dict], predicted: list[dict]) -> dict:
    result = {}
    for name in observed[0]:
        reference = [flags[name].any() for flags in observed]
        modeled = [flags[name].any() for flags in predicted]
        result[name] = {
            "observed_cycles": int(sum(reference)), "predicted_cycles": int(sum(modeled)),
            "missed_cycles": int(sum(a and not b for a, b in zip(reference, modeled, strict=True))),
            "false_alarm_cycles": int(sum(b and not a for a, b in zip(reference, modeled, strict=True))),
        }
    return result


def errors(values: list[np.ndarray]) -> dict:
    series = np.concatenate([np.ravel(v) for v in values])
    return {k: round(float(v), 8) for k, v in {
        "mae": np.mean(np.abs(series)), "rmse": np.sqrt(np.mean(series ** 2)),
        "bias": np.mean(series), "maximum_absolute_error": np.max(np.abs(series)),
    }.items()}


def compare(path: Path, freeze: dict) -> dict:
    if freeze["plan"] != PLAN or freeze["source_sha256"] != SOURCE_SHA256:
        raise ValueError("calibration artifact is for a different plan or source")
    knots = np.array(freeze["charge_knots_ah"])
    battery = {
        name: battery_models(np.array(freeze[name]["ocv_v"]), np.array(freeze[name]["series_ohm"]), knots)
        for name in ("fixed_r", "one_rc")
    }
    results = {}
    for cohort, range_ in HOLDOUT.items():
        cycles, rejected = load_cycles(path, range_)
        # Out-of-domain coulomb trajectories are visible and excluded from
        # voltage fitting/scoring. The raw-data limit check still includes them.
        supported = [c for c in cycles if c.charge_ah[-1] <= freeze["max_charge_ah"]]
        observed = [breaches(c.voltages, c.temperatures, c.recorded_ah, c.current) for c in cycles]
        observed_limits = {
            name: int(sum(flags[name].any() for flags in observed)) for name in observed[0]
        } if observed else {}
        if not supported:
            results[cohort] = {
                "status": "FAILED_SAMPLED_STUDY_LIMIT" if any(observed_limits.values()) else "NO_IN_ENVELOPE_CYCLES",
                "source_rejections": rejected, "outside_charge_support": len(cycles),
                "observed_limits_all_admitted_cycles": observed_limits,
            }
            continue
        observed_supported = [breaches(c.voltages, c.temperatures, c.recorded_ah, c.current) for c in supported]
        thermal = {
            name: [temperature_prediction(c, freeze[name]) for c in supported]
            for name in ("direct_heating", "lagged_heating")
        }
        models = {}
        for v_name, t_name in (("fixed_r", "direct_heating"), ("one_rc", "lagged_heating")):
            v_pred = [voltage_prediction(c, freeze[v_name], battery[v_name]) for c in supported]
            t_pred = thermal[t_name]
            v_errors = [p - c.voltages for p, c in zip(v_pred, supported, strict=True)]
            t_errors = [p - c.temperatures for p, c in zip(t_pred, supported, strict=True)]
            energy = [trapezoid((p[:, 0] - c.voltages[:, 0]) * c.current, c.t) / 3600
                      for p, c in zip(v_pred, supported, strict=True)]
            models[v_name] = {
                "module_voltage_v": errors([v[:, 0] for v in v_errors]),
                "pack_voltage_v": errors([v[:, 1:] for v in v_errors]),
                "pack_temperature_c": errors(t_errors),
                "net_delivered_energy_wh": errors([np.asarray(energy)]),
                "limit_screen": exposure(observed_supported, [
                    breaches(v, temp, c.charge_ah, c.current)
                    for v, temp, c in zip(v_pred, t_pred, supported, strict=True)
                ]),
            }
        limit_crossed = any(observed_limits.values()) or any(
            gate["predicted_cycles"] for m in models.values() for gate in m["limit_screen"].values()
        )
        results[cohort] = {
            "status": "FAILED_SAMPLED_STUDY_LIMIT" if limit_crossed else "INCONCLUSIVE_FOR_PACK_ACCEPTANCE",
            "cycles_scored": len(supported), "samples_scored": sum(len(c.t) for c in supported),
            "source_rejections": rejected, "outside_charge_support": len(cycles) - len(supported),
            "observed_limits_all_admitted_cycles": observed_limits,
            "temperature_initial_persistence_c": errors([c.temperatures[0] - c.temperatures for c in supported]),
            "models": models,
        }
    return {"plan": PLAN, "frozen_calibration_canonical_sha256": digest(freeze), "cohorts": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("calibrate", "evaluate"))
    parser.add_argument("workbook", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--freeze", type=Path)
    args = parser.parse_args()
    fit = calibrate(args.workbook)
    if args.action == "evaluate":
        if args.freeze is None or digest(json.loads(args.freeze.read_bytes())) != digest(fit):
            parser.error("the frozen fit must reproduce from the pinned calibration cycles")
        report = compare(args.workbook, fit)
    else:
        report = fit
    args.output.write_bytes((json.dumps(report, indent=2, allow_nan=False) + "\n").encode())


if __name__ == "__main__":
    main()
