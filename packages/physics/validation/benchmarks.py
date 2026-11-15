"""Benchmark framework and the M2 propulsion benchmarks.

A benchmark declares its tolerance BEFORE running (pre-registered acceptance),
then reports metrics and a pass/fail — mirroring docs/validation_strategy.md.
Results distinguish:
  - "pass"/"fail": gated benchmarks with declared tolerances,
  - "reported": informational cross-checks whose residuals are documented
    (e.g. the lumped DC motor model, which is known NOT to close against the
    loaded bench data — that finding is the point of running it).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from physics.constants import GF_TO_N
from physics.propulsion.dataset import PowertrainDataset


@dataclass
class BenchmarkResult:
    name: str
    status: str  # "pass" | "fail" | "reported"
    metrics: dict = field(default_factory=dict)
    tolerances: dict = field(default_factory=dict)
    notes: str = ""

    def summary(self) -> str:
        metrics = ", ".join(f"{k}={v:.4g}" for k, v in self.metrics.items())
        return f"[{self.status.upper():8s}] {self.name}: {metrics}"


def benchmark_knot_readback(
    dataset: PowertrainDataset, tolerance: float = 0.005
) -> BenchmarkResult:
    """Every measured knot must be reproduced within ``tolerance`` (relative).

    This is the spec's M2 acceptance gate: 'The simulation produces thrust and
    current values matching the given data table (within interpolation error).'
    """
    max_rel = 0.0
    n_points = 0
    for plane in dataset.planes:
        for rpm, thrust_gf, current in zip(
            plane.rpm, plane.thrust_gf, plane.current_a
        ):
            thr_err = abs(dataset.thrust_gf(float(rpm)).value - float(thrust_gf)) / max(
                float(thrust_gf), 1e-9
            )
            cur = dataset.current_a(float(rpm), float(plane.voltage_v))
            cur_err = abs(cur.value - float(current)) / float(current)
            max_rel = max(max_rel, thr_err, cur_err)
            n_points += 2
    passed = max_rel <= tolerance
    return BenchmarkResult(
        name="propulsion knot read-back (thrust + current)",
        status="pass" if passed else "fail",
        metrics={"max_relative_error": max_rel, "points_checked": n_points},
        tolerances={"max_relative_error": tolerance},
        notes="interpolation must reproduce the measured table at the knots",
    )


def benchmark_thrust_voltage_scatter(
    dataset: PowertrainDataset, tolerance_pct: float = 5.0
) -> BenchmarkResult:
    """Static thrust must be voltage-independent: cross-plane scatter in the
    overlap band quantifies bench repeatability (folded into uncertainty)."""
    if dataset.scatter_pct == 0.0 and len(dataset.planes) < 2:
        return BenchmarkResult(
            name="static thrust cross-voltage scatter",
            status="reported",
            metrics={"scatter_pct": 0.0},
            tolerances={"scatter_pct": tolerance_pct},
            notes="single voltage plane — no scatter measurable",
        )
    passed = dataset.scatter_pct <= tolerance_pct
    return BenchmarkResult(
        name="static thrust cross-voltage scatter",
        status="pass" if passed else "fail",
        metrics={"scatter_pct": dataset.scatter_pct},
        tolerances={"scatter_pct": tolerance_pct},
        notes="scatter between the 14.8 V and 22.2 V planes in the overlap band",
    )


def benchmark_full_throttle_table(
    dataset: PowertrainDataset, voltage: float
) -> BenchmarkResult:
    """Full-throttle operating point vs the measured table row (M2 'simulate a
    full-thrust run and compare to the provided data')."""
    plane = max(dataset.planes, key=lambda p: abs(p.voltage_v - voltage))
    rpm_row = plane.rpm[-1]
    thrust_row_gf = plane.thrust_gf[-1]
    current_row = plane.current_a[-1]
    power_row = plane.current_a[-1] * plane.voltage_v

    rpm_res = dataset.rpm_at_throttle(1.0, plane.voltage_v)
    thr_res = dataset.thrust_n(rpm_res.value)
    cur_res = dataset.current_a(rpm_res.value, plane.voltage_v)
    power_pred = cur_res.value * plane.voltage_v

    metrics = {
        "thrust_rel_err_pct": abs(thr_res.value - thrust_row_gf * GF_TO_N)
        / (thrust_row_gf * GF_TO_N)
        * 100.0,
        "current_rel_err_pct": abs(cur_res.value - current_row) / current_row * 100.0,
        "power_rel_err_pct": abs(power_pred - power_row) / power_row * 100.0,
        "rpm_rel_err_pct": abs(rpm_res.value - rpm_row) / rpm_row * 100.0,
    }
    # Read-back through the mapping chain must stay within interpolation error.
    tol = 0.5  # percent
    passed = all(v <= tol for v in metrics.values())
    return BenchmarkResult(
        name=f"full-throttle table reproduction @ {plane.voltage_v} V",
        status="pass" if passed else "fail",
        metrics=metrics,
        tolerances={"all_rel_err_pct": tol},
        notes="throttle->rpm->thrust/current chain reproduces the 100% table row",
    )


def benchmark_lumped_dc_crosscheck(dataset: PowertrainDataset) -> BenchmarkResult:
    """INFORMATIONAL cross-check of the lumped DC motor model.

    Calibrate (Ke, R) on the LOW-voltage plane via duty = throttle/100 and
    D*V = Ke*omega + R*I; validate against the HIGH-voltage plane. Residuals
    are reported (not gated): the BLDC+ESC chain's inductive/timing effects
    are known to break the pure DC model — quantifying that gap is the
    benchmark's purpose, and it justifies the table-driven model of record.
    """
    if len(dataset.planes) < 2:
        return BenchmarkResult(
            name="lumped DC motor cross-check",
            status="reported",
            notes="requires two voltage planes",
        )
    cal, val = dataset.planes[0], dataset.planes[-1]

    duty = cal.throttle_pct / 100.0
    omega = cal.rpm * 2.0 * np.pi / 60.0
    # Least squares on D*V = Ke*omega + R*I
    a = np.column_stack([omega, cal.current_a])
    b = duty * cal.voltage_v
    (ke, r), *_ = np.linalg.lstsq(a, b, rcond=None)

    duty_v = val.throttle_pct / 100.0
    omega_v = val.rpm * 2.0 * np.pi / 60.0
    i_pred = (duty_v * val.voltage_v - ke * omega_v) / r
    err = i_pred - val.current_a
    rmse = float(np.sqrt(np.mean(err**2)))
    max_err = float(np.max(np.abs(err)))
    rel = err / val.current_a
    return BenchmarkResult(
        name="lumped DC motor cross-check (cal 14.8 V -> val 22.2 V)",
        status="reported",
        metrics={
            "ke_eff_v_s_per_rad": float(ke),
            "r_eff_ohm": float(r),
            "current_rmse_a": rmse,
            "current_max_abs_err_a": max_err,
            "current_max_rel_err_pct": float(np.max(np.abs(rel)) * 100.0),
        },
        tolerances={},
        notes=(
            "lumped DC model residual — expected to be significant for BLDC+ESC "
            "(inductance/timing); the measured-table interpolation is the model "
            "of record. No gate: informational."
        ),
    )


def run_propulsion_benchmarks(dataset: PowertrainDataset) -> list[BenchmarkResult]:
    return [
        benchmark_knot_readback(dataset),
        benchmark_thrust_voltage_scatter(dataset),
        benchmark_full_throttle_table(dataset, voltage=dataset.voltage_range[1]),
        benchmark_lumped_dc_crosscheck(dataset),
    ]
