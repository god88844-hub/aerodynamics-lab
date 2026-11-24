"""Flight scenario framework (M4): profiles, failure monitors, powertrain in
the loop, and the runner with abort semantics.

Policy (declared, per docs/validation_strategy.md "component failure =
project failure"):
  CRITICAL (abort the run immediately, name the cause):
    - thrust demand above the measured static table max (motor over-speed
      equivalent — the prop cannot deliver it),
    - motor current above 2x the datasheet continuous rating (instant
      destructive overcurrent),
    - motor current above the continuous rating sustained for the datasheet's
      continuous duration (180 s for the MN3508) — thermal burnout,
    - battery loaded cell voltage reaching the cutoff threshold — bracketed
      to its exact in-tick crossing time (equality and tick edges fire
      deterministically; P0A-006),
    - a powertrain demand the pack cannot supply (above the exact
      constant-power collapse boundary) or a state outside the declared
      model support — fail-closed refusals become named critical events, the
      commanded propulsion output is not simulated (P0A-006),
    - any declared branch current, voltage, RPM, thermal dwell or actuator
      limit excursion at its branch's resolved operating point,
    - unsupported branch mechanisms terminate with INCONCLUSIVE,
    - arm root bending stress at/above material yield,
    - ground impact (z below start with negative speed at ground level),
    - attitude loss (|tilt| > 45 deg — unrecoverable for this controller class).
  Logged without an immediate integration abort:
    - supported motor/ESC cutout records a branch FAIL and continues only
      the bounded controller response with the failed branch disabled,
    - battery warning cell voltage — fires once at its bracketed crossing
      (land-now threshold; latched thereafter),
    - per-tick over-current below the destructive threshold (counted; the
      sustained rule above is the abort criterion),
    - structural margin < 1.5 (warn).

Design-level acceptance: a run that hits a critical failure returns
``aborted=True`` with the named event instead of silently continuing, and
``component_verdicts`` records FAIL for each component whose declared hard
limit was breached (absence of a breach is recorded, and is NOT a fitness
claim).
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import asdict, dataclass, field
from typing import Literal

import numpy as np
from scipy.optimize import brentq

from physics.controller.attitude import ControlTargets, QuadcopterController
from physics.controller.mixer import Mixer
from physics.controller.sensors import SensorConfig, SensorModel
from physics.dynamics.quaternion import conjugate, rotate, rotation_matrix
from physics.dynamics.rigid_body import make_state, normalize_state
from physics.integration.rk4 import rk4_step
from physics.integration.runtime_limit import check_time_limit
from physics.propulsion.battery import (
    BatteryPack,
    OutOfSupportError,
    PowertrainError,
    VoltageCollapseError,
)
from physics.propulsion.branches import BranchFailure, BranchFinding, BranchLimits, limit_findings
from physics.propulsion.dataset import OutOfEnvelopeError, PowertrainDataset
from physics.propulsion.esc import Esc
from physics.structures.beam import check_arm, effective_arm_spans_m
from physics.structures.materials import MaterialProps, load_materials


# ------------------------------------------------------------------ profiles


def altitude_at(waypoints: list[tuple[float, float]], t: float) -> float:
    """Piecewise-linear altitude schedule [(t0, z0), (t1, z1), ...]."""
    if t <= waypoints[0][0]:
        return waypoints[0][1]
    for (t0, z0), (t1, z1) in zip(waypoints, waypoints[1:]):
        if t0 <= t <= t1:
            return z0 + (z1 - z0) * (t - t0) / (t1 - t0)
    return waypoints[-1][1]


# ------------------------------------------------------------- powertrain loop

# Quasi-static bus solve bounds: the damped fixed point converges for any
# supported demand (seeded with the previous tick's converged bus voltage —
# past state only, so still causal); non-convergence is a declared refusal
# (the demand has no stable quasi-static solution), never a silent last
# iterate. Tolerance matches StaticPowertrain.solve_bus.
BUS_SOLVE_MAX_ITERATIONS = 24
BUS_SOLVE_TOLERANCE_V = 1e-4


@dataclass
class LoopAux:
    """Per-tick powertrain quantities (quasi-static bus solve)."""

    v_bus: float
    soc_pct: float
    per_motor_rpm: list[float]
    per_motor_current_a: list[float]
    total_current_a: float
    total_power_w: float
    events: list[dict] = field(default_factory=list)
    delivered_thrust_n: np.ndarray | None = None
    attainable_thrust_n: np.ndarray | None = None
    branch_voltage_v: np.ndarray | None = None


class BranchSupportError(PowertrainError):
    def __init__(self, branch_id: int, message: str) -> None:
        super().__init__(f"rotor {branch_id}: unsupported branch electrical state ({message})")
        self.branch_id = branch_id


@dataclass(frozen=True)
class BatteryLimitFinding:
    battery_id: str
    limit: str
    observed: float
    threshold: float
    unit: str


class DemandedPowerLimitError(VoltageCollapseError):
    def __init__(self, finding: BatteryLimitFinding) -> None:
        self.finding = finding
        super().__init__(
            f"requested {finding.observed:.2f} W exceeds the pack's constant-power "
            f"limit {finding.threshold:.2f} W at this tick"
        )


class BusOperatingPointError(PowertrainError):
    """The model cannot resolve the loaded operating point within its support."""


class LoopPowertrain:
    """Sourced powertrain evaluated per control tick: thrust commands ->
    rpm/current via the measured dataset; battery SOC integration and bus
    sag quasi-static. Quasi-static is valid because bus dynamics are far
    faster than the control loop but change slowly at hover bandwidth.

    Causal contract (P0A-006): every quantity in ``step`` is a function of
    the state at the START of the tick (SOC at the tick's clock) and the
    commanded load — no step reads a later SOC or current than its clock.
    The loaded bus voltage is solved at the start-of-tick SOC and threshold
    crossings (warning/cutoff) are bracketed through the tick's linear SOC
    drain with exact equality and tick-edge handling. A demand the pack
    cannot supply (above the exact constant-power collapse boundary) raises
    ``VoltageCollapseError`` — the commanded propulsion output is not
    attainable and is never simulated."""

    def __init__(
        self,
        dataset: PowertrainDataset,
        esc: Esc,
        battery: BatteryPack,
        soc_start_pct: float = 100.0,
    ) -> None:
        self.dataset = dataset
        self.esc = esc
        self.battery = battery
        self.soc = soc_start_pct
        self.max_thrust_n = float(dataset.thrust_n(float(dataset.envelope()["rpm_range_merged"][1])).value)
        motor = dataset.motor
        self.max_continuous_a = motor.max_continuous_current_a
        self.continuous_duration_s = motor.max_continuous_duration_s
        self._over_current_time = np.zeros(1)  # resized per unit count
        self._branch_over_current_time = np.zeros(1)
        self._warning_latched = False
        self._v_bus_seed: float | None = None  # previous tick's converged bus
        self.energy_wh = 0.0

    def step(
        self, thrusts: np.ndarray, dt: float, *,
        branches: tuple[BranchLimits, ...] | None = None,
        cutout: int | None = None,
    ) -> LoopAux:
        """Resolve one tick. With no branches supplied, solve fixed load demand."""
        n = len(thrusts)
        if len(self._over_current_time) != n:
            self._over_current_time = np.zeros(n)
            self._branch_over_current_time = np.zeros(n)
        events: list[dict] = []
        rpm_lo, rpm_hi = self.dataset.envelope()["rpm_range_merged"]
        thrust_min_n = float(self.dataset.thrust_n(float(rpm_lo)).value)
        rpm_cache: dict[float, float] = {}

        def rpm_at_thrust(thrust: float) -> float:
            if thrust not in rpm_cache:
                gf = thrust / 9.80665e-3
                if thrust < thrust_min_n:
                    rpm = self.dataset.thrust_rpm_extrapolated(gf).value
                else:
                    rpm = brentq(
                        lambda r: float(self.dataset.thrust_n(r).value) - thrust,
                        float(rpm_lo), float(rpm_hi), xtol=1e-3,
                    )
                rpm_cache[thrust] = rpm
            return rpm_cache[thrust]

        def operating_point(request: float, voltage: float, ceiling: float) -> tuple[float, float, float]:
            thrust = Mixer.project_branch(request, ceiling)
            if thrust <= 1e-9:
                return 0.0, 0.0, 0.0
            rpm = rpm_at_thrust(thrust)
            current = (self.dataset.current_a_extrapolated(rpm, voltage)
                       if thrust < thrust_min_n else self.dataset.current_a(rpm, voltage)).value
            return thrust, rpm, current

        rejected = set()
        for i, thrust in enumerate(thrusts):
            if i != cutout and thrust > self.max_thrust_n:
                rejected.add(i)
                events.append({
                    "kind": "over_max_thrust", "critical": True, "t_s": None,
                    "message": f"motor {i} requested {thrust:.2f} N above the "
                               f"measured static maximum {self.max_thrust_n:.2f} N",
                    "branch": BranchFinding(i, "actuator", "static_thrust_envelope",
                                            float(thrust), self.max_thrust_n, "N"),
                })

        # Solve V_bus at the start SOC using the actual projected branch loads.
        # The previous tick is a numerical seed only.
        soc_pre = self.soc
        v_oc = self.battery.ocv_pack(soc_pre)
        v_bus = self._v_bus_seed if self._v_bus_seed is not None else v_oc
        currents, rpms, delivered, ceilings, voltages = np.zeros((5, n))
        converged = False

        def demand_limit() -> DemandedPowerLimitError | None:
            # A fixed request at OCV can prove a named constant-power limit.
            # Failed numerical iterates alone cannot prove that limit.
            lo, hi = self.dataset.supported_voltage_range
            if not lo <= v_oc <= hi or rejected or any(b.series_resistance_ohm for b in branches or ()):
                return None
            try:
                demand_w = v_oc * sum(
                    operating_point(float(request), v_oc, self.max_thrust_n)[2]
                    for i, request in enumerate(thrusts) if i != cutout
                )
            except OutOfEnvelopeError:
                return None
            limit_w = self.battery.max_deliverable_power_w(soc_pre)
            if demand_w > limit_w:
                return DemandedPowerLimitError(BatteryLimitFinding(
                    self.battery.spec.id, "constant_power_demand", demand_w, limit_w, "W",
                ))
            return None

        try:
            for _ in range(BUS_SOLVE_MAX_ITERATIONS):
                shared_ceiling = (self.dataset.attainable_static_thrust_n(v_bus)
                                  if branches is not None else self.max_thrust_n)
                points: dict[float, tuple[float, float, float]] = {}
                for i, request in enumerate(thrusts):
                    if i == cutout:
                        continue
                    voltages[i] = v_bus
                    ceilings[i] = shared_ceiling
                    if i in rejected:
                        continue
                    resistance = branches[i].series_resistance_ohm if branches is not None else 0.0
                    if resistance:
                        def point(voltage: float) -> tuple[float, float, float]:
                            return operating_point(
                                float(request), voltage, self.dataset.attainable_static_thrust_n(voltage)
                            )

                        # Restrict the wiring solve to the dataset's declared
                        # voltage support. An unsupported load is a refusal.
                        v_min = self.dataset.supported_voltage_range[0]
                        try:
                            v_branch = brentq(
                                lambda v: v + resistance * point(v)[2] - v_bus,
                                v_min, v_bus, xtol=1e-8,
                            )
                            delivered[i], rpms[i], currents[i] = point(v_branch)
                            voltages[i] = v_branch
                            ceilings[i] = self.dataset.attainable_static_thrust_n(v_branch)
                        except (OutOfEnvelopeError, ValueError) as exc:
                            raise BranchSupportError(i, str(exc)) from exc
                    else:
                        if request not in points:
                            points[request] = operating_point(float(request), v_bus, shared_ceiling)
                        delivered[i], rpms[i], currents[i] = points[request]
                v_new = self.battery.voltage_under_load(soc_pre, float(currents.sum()))
                if abs(v_new - v_bus) < BUS_SOLVE_TOLERANCE_V:
                    if branches is None:
                        v_bus = v_new
                    converged = True
                    break
                v_bus = 0.5 * (v_bus + v_new)
        except (OutOfEnvelopeError, VoltageCollapseError) as exc:
            if branches is None:
                # Preserve the fixed-demand primitive's established refusal.
                raise VoltageCollapseError(str(exc)) from exc
            exceeded = demand_limit()
            if exceeded is not None:
                raise exceeded from exc
            raise BusOperatingPointError(
                f"loaded bus left model support at {soc_pre:.1f}% SOC: {exc}"
            ) from exc
        if not converged:
            raise BusOperatingPointError(
                f"bus voltage solve did not converge in {BUS_SOLVE_MAX_ITERATIONS} "
                f"iterations at {soc_pre:.1f}% SOC (last v_bus={v_bus:.3f} V, OCV "
                f"{v_oc:.2f} V)"
            )
        self._v_bus_seed = v_bus
        if np.any((delivered > 0.0) & (delivered < thrust_min_n)):
            events.append({
                "kind": "thrust_below_envelope", "critical": False, "t_s": None,
                "message": "below-table static thrust: rpm/current are declared extrapolations",
            })

        # Attainable-output gate: the commanded electrical power must lie
        # inside the pack's exact constant-power feasibility boundary
        # (V_oc^2 / (4 R) at this SOC). Above it the bus collapses — the
        # commanded propulsion output is NOT attainable and is not simulated.
        total_current = float(np.nansum(currents))
        demanded_power_w = v_bus * total_current
        max_power_w = self.battery.max_deliverable_power_w(soc_pre)
        if demanded_power_w > max_power_w:
            raise DemandedPowerLimitError(BatteryLimitFinding(
                self.battery.spec.id, "constant_power_demand", demanded_power_w, max_power_w, "W",
            ))

        # Battery drain over the tick, then threshold brackets: the loaded
        # cell voltage is evaluated on the start-of-tick state and bracketed
        # through the tick's linear SOC drain, so a crossing is stamped at
        # its bracketed time (equality and tick edges fire deterministically).
        soc_post = self.battery.soc_after(soc_pre, total_current, dt)
        if not self._warning_latched:
            tau_warn = self.battery.crossing_time_below_cell_v(
                soc_pre, soc_post, total_current, dt,
                self.battery.spec.warning_cell_voltage_v,
            )
            if tau_warn is not None:
                self._warning_latched = True
                events.append({
                    "kind": "battery_warning",
                    "critical": False,
                    "message": (
                        f"battery loaded cell voltage reaches the "
                        f"{self.battery.spec.warning_cell_voltage_v:.2f} V warning "
                        f"threshold {tau_warn * 1e3:.1f} ms into the tick "
                        f"({total_current:.1f} A draw) — land now"
                    ),
                    "t_s": tau_warn,
                })
        tau_cut = self.battery.crossing_time_below_cell_v(
            soc_pre, soc_post, total_current, dt,
            self.battery.spec.cutoff_cell_voltage_v,
        )
        if tau_cut is not None:
            events.append({
                "kind": "battery_cutoff",
                "critical": True,
                "message": (
                    f"battery loaded cell voltage reaches the "
                    f"{self.battery.spec.cutoff_cell_voltage_v:.2f} V cutoff "
                    f"{tau_cut * 1e3:.1f} ms into the tick ({total_current:.1f} A "
                    "draw) — pack depleted; no post-cutoff thrust is simulated"
                ),
                "t_s": tau_cut,
                "battery": BatteryLimitFinding(
                    self.battery.spec.id, "loaded_cell_cutoff",
                    v_new / self.battery.spec.cells_series if tau_cut == 0.0
                    else self.battery.spec.cutoff_cell_voltage_v,
                    self.battery.spec.cutoff_cell_voltage_v, "V",
                ),
            })

        def add_finding(kind: str, finding: BranchFinding, message: str,
                        offset: float | None = None) -> None:
            events.append({"kind": kind, "critical": True, "branch": finding,
                           "message": message, "t_s": offset})

        def check_thermal(i: int, current: float, threshold: float | None,
                          duration: float | None, elapsed: np.ndarray, component: str) -> None:
            if threshold is None or duration is None or current <= threshold:
                elapsed[i] = 0.0
                return
            previous = elapsed[i]
            elapsed[i] += dt
            if elapsed[i] >= duration:
                offset = max(0.0, min(dt, duration - previous))
                add_finding(
                    "motor_burnout" if component == "motor" else "branch_thermal_limit",
                    BranchFinding(i, component, "thermal_current_duration", duration, duration, "s"),
                    f"rotor {i}: above {threshold:.2f} A for {duration:.4f} s",
                    offset,
                )

        for i, current in enumerate(currents):
            if i == cutout:
                continue
            if self.max_continuous_a is not None and current > 2.0 * self.max_continuous_a:
                threshold = 2.0 * self.max_continuous_a
                add_finding(
                    "motor_overcurrent_destructive",
                    BranchFinding(i, "motor", "destructive_current", float(current), threshold, "A"),
                    f"rotor {i}: {current:.2f} A exceeds the {threshold:.2f} A destructive limit",
                )
            else:
                check_thermal(i, current, self.max_continuous_a, self.continuous_duration_s,
                              self._over_current_time, "motor")
            issue = self.esc.current_issue(current)
            if issue:
                add_finding(
                    "esc_overcurrent",
                    BranchFinding(i, "esc", "branch_current", float(current),
                                  self.esc.spec.max_continuous_current_a, "A"),
                    f"rotor {i}: {issue}",
                )
            voltage = float(voltages[i]) if branches is not None else v_bus
            issue = self.esc.voltage_issue(voltage)
            if issue and branches is not None:
                add_finding(
                    "esc_overvoltage",
                    BranchFinding(i, "esc", "branch_overvoltage", voltage,
                                  self.esc.spec.max_voltage_v, "V"),
                    f"rotor {i}: {issue}",
                )
            if branches is not None:
                limits = branches[i]
                check_thermal(i, current, limits.thermal_current_a, limits.thermal_duration_s,
                              self._branch_over_current_time, "esc")
                for finding in limit_findings(i, limits, float(current), voltage,
                                              float(rpms[i]), float(delivered[i])):
                    add_finding(finding.limit, finding,
                                f"rotor {i}: {finding.limit} at {finding.observed:.4f} {finding.unit}"
                                f" crossed {finding.threshold:.4f} {finding.unit}")
        if branches is None and (issue := self.esc.voltage_issue(v_bus)):
            events.append({"kind": "esc_overvoltage", "critical": True,
                           "message": issue, "t_s": None})

        if branches is not None:
            abort_offsets = [ev["t_s"] or 0.0 for ev in events if ev["critical"]]
            elapsed = min(abort_offsets, default=dt)
            events = [ev for ev in events if (ev["t_s"] or 0.0) <= elapsed]
        else:
            elapsed = dt  # fixed-demand primitive retains its full-tick accounting
        self.soc = self.battery.soc_after(soc_pre, total_current, elapsed)
        self.energy_wh += v_bus * total_current * elapsed / 3600.0

        return LoopAux(
            v_bus=v_bus,
            soc_pct=self.soc,
            per_motor_rpm=rpms.tolist(),
            per_motor_current_a=currents.tolist(),
            total_current_a=total_current,
            total_power_w=v_bus * total_current,
            events=events,
            delivered_thrust_n=delivered,
            attainable_thrust_n=ceilings,
            branch_voltage_v=voltages,
        )


# ------------------------------------------------------------------ monitors


@dataclass(frozen=True)
class FailureEvent:
    t_s: float
    kind: str
    critical: bool
    message: str
    branch: BranchFinding | None = None
    battery: BatteryLimitFinding | None = None


def check_attitude(state: np.ndarray, t: float, limit_deg: float = 45.0) -> FailureEvent | None:
    R = rotation_matrix(state[6:10])
    cos_tilt = max(-1.0, min(1.0, R[2, 2]))
    tilt_deg = float(np.degrees(np.arccos(cos_tilt)))
    if tilt_deg > limit_deg:
        return FailureEvent(
            t, "attitude_loss", True,
            f"total tilt {tilt_deg:.1f} deg > {limit_deg:.0f} deg — unrecoverable "
            "for this controller class"
        )
    return None


def check_ground(
    state: np.ndarray, t: float, ground_z: float = -0.02, crash_vz_m_s: float = -1.0
) -> FailureEvent | None:
    """Ground contact below ``ground_z`` is a CRASH only when the vertical
    speed exceeds the gentle-touchdown threshold; slow contact is a landing."""
    if state[2] < ground_z and state[5] < crash_vz_m_s:
        return FailureEvent(
            t, "ground_crash", True,
            f"hard ground impact: z={state[2]:.3f} m at vertical speed "
            f"{state[5]:.2f} m/s (threshold {crash_vz_m_s:.1f} m/s)"
        )
    return None


def check_structure(
    thrusts: np.ndarray,
    t: float,
    effective_arm_lengths_m: list[float],
    tube_od_m: float,
    tube_id_m: float,
    material: MaterialProps,
) -> tuple[FailureEvent | None, float]:
    """Check each rotor's own thrust and effective lever, not max thrust
    against one (possibly underestimated) declared arm length."""
    forces = np.asarray(thrusts, dtype=float)
    spans = np.asarray(effective_arm_lengths_m, dtype=float)
    if (forces.ndim != 1 or spans.ndim != 1 or len(forces) == 0
            or forces.shape != spans.shape or not np.all(np.isfinite(forces))
            or not np.all(np.isfinite(spans)) or np.any(forces < 0)
            or np.any(spans <= 0)):
        raise ValueError("structural check needs matching finite thrust/span vectors")

    checks = [
        check_arm(float(force), float(span), tube_od_m, tube_id_m, material)
        for force, span in zip(forces, spans)
    ]
    worst_i = int(np.argmin([check.margin for check in checks]))
    worst = checks[worst_i]
    event = None
    if not worst.ok:
        event = FailureEvent(
            t, "structure_yield", True,
            f"STRUCTURAL FAILURE: rotor {worst_i} at effective span "
            f"{spans[worst_i]:.4f} m: {worst.message} "
            f"— margin {worst.margin:.2f} < 1.0"
        )
    return event, worst.margin


# ------------------------------------------------------------------- runner


@dataclass
class Scenario:
    name: str
    duration_s: float
    altitude_waypoints: list[tuple[float, float]]
    position_waypoints: list[tuple[float, tuple[float, float]]] | None = None
    initial_altitude_m: float = 0.0
    disturbances: list = field(default_factory=list)
    motor_failure_at_s: float | None = None      # kill motor 0 from this time
    sensor_config: SensorConfig | None = None    # None = perfect state knowledge
    success_criteria: list = field(default_factory=list)  # (name, callable(res))
    branch_limits: dict[int, BranchLimits] = field(default_factory=dict)
    branch_failure: BranchFailure | None = None
    # Streamed values enter at their timestamps. Planned routes are entirely
    # authored and available before the run, including their segment slopes.
    reference_mode: Literal["streamed", "planned"] = "streamed"


@dataclass(frozen=True)
class FlightClockTrace:
    """One row per attempted controller tick, with explicit state sample clocks."""

    state_start: np.ndarray
    state_time_s: np.ndarray
    electrical_time_s: np.ndarray
    command_wrench: np.ndarray
    nominal_thrust_n: np.ndarray
    applied_rotor_wrench: np.ndarray
    previous_wrench_residual: np.ndarray
    integrated: np.ndarray


@dataclass
class ScenarioResult:
    scenario: str
    aborted: bool
    abort_event: FailureEvent | None
    events: list[FailureEvent]
    times: np.ndarray
    states: np.ndarray
    thrusts: np.ndarray
    per_motor_current_a: np.ndarray | None
    v_bus: np.ndarray | None
    soc_pct: np.ndarray | None
    energy_wh: float
    time_to_altitude_s: float | None
    max_altitude_m: float
    structural_margin_min: float | None
    success: dict[str, bool]
    success_all: bool | None
    notes: list[str]
    allocation_counts: dict[str, int] = field(default_factory=dict)
    # P0A-006: per-component verdict over the run. "FAIL" = a declared hard
    # limit was breached; "NO_MODELED_LIMIT_BREACHED" = the component was in
    # the loop with its modeled limits checked and none breached (NOT a
    # fitness claim); "NOT_SIMULATED" = the component was not in the loop.
    component_verdicts: dict[str, str | dict] = field(default_factory=dict)
    flight_verdict: str = "NO_MODELED_LIMIT_BREACHED"
    attainable_thrust_n: np.ndarray | None = None
    branch_voltage_v: np.ndarray | None = None
    per_motor_rpm: np.ndarray | None = None
    wrench_residual: np.ndarray | None = None
    clock: FlightClockTrace | None = None


# Component owning each critical limit event (P0A-006 verdict propagation).
_COMPONENT_OF_EVENT: dict[str, str] = {
    "battery_cutoff": "battery",
    "battery_voltage_collapse": "battery",
    "motor_overcurrent_destructive": "motor",
    "motor_burnout": "motor",
    "esc_overcurrent": "esc",
    "esc_overvoltage": "esc",
    "structure_yield": "frame",
}


def _ordered_waypoints(points, label: str):
    ordered = sorted(points, key=lambda point: point[0])
    if any(not np.isfinite(t) or t < 0 or not np.all(np.isfinite(value)) for t, value in ordered):
        raise ValueError(f"{label} references must have finite values and nonnegative times")
    if any(a[0] == b[0] for a, b in zip(ordered, ordered[1:])):
        raise ValueError(f"{label} reference timestamps must be unique")
    return ordered


def _target_source(scenario: Scenario):
    altitude = _ordered_waypoints(scenario.altitude_waypoints, "altitude")
    position = _ordered_waypoints(scenario.position_waypoints or [], "position")
    if not altitude:
        raise ValueError("scenario must have at least one altitude reference")
    if scenario.reference_mode == "planned":
        # These piecewise-linear routes are given to the controller at run
        # initialization. No live future samples are read to construct them.
        def planned(t: float) -> ControlTargets:
            pos, vel = _position_velocity_at(position, t) if position else (None, None)
            return ControlTargets(altitude_at(altitude, t), position_xy=pos, velocity_xy=vel,
                                  velocity_z=_altitude_velocity_at(altitude, t))
        return planned
    if scenario.reference_mode != "streamed":
        raise ValueError("reference_mode must be 'streamed' or 'planned'")
    altitude_times = [t for t, _ in altitude]
    position_times = [t for t, _ in position]

    def streamed(t: float) -> ControlTargets:
        iz = bisect_right(altitude_times, t) - 1
        ixy = bisect_right(position_times, t) - 1
        return ControlTargets(
            altitude[iz][1] if iz >= 0 else scenario.initial_altitude_m,
            position_xy=position[ixy][1] if ixy >= 0 else None,
        )

    return streamed


def run_scenario(
    design,
    scenario: Scenario,
    library=None,
    control_dt_s: float = 0.004,
    substeps: int = 2,
) -> ScenarioResult:
    """Run a scenario on the design; aborts on critical failure events."""
    from physics.dynamics.design_adapter import build_multirotor

    if not np.isfinite(control_dt_s) or control_dt_s <= 0.0 or type(substeps) is not int or substeps < 1:
        raise ValueError("flight clock requires a finite positive period and at least one substep")
    targets_at = _target_source(scenario)
    plant, _ = build_multirotor(design)
    controller = QuadcopterController(plant)
    count = len(plant.rotors)
    fault = scenario.branch_failure
    if scenario.motor_failure_at_s is not None:
        if fault is not None:
            raise ValueError("only one branch failure may be specified")
        fault = BranchFailure(0, scenario.motor_failure_at_s, "motor_cutout")
    branch_ids = set(scenario.branch_limits)
    if fault is not None:
        branch_ids.add(fault.branch_id)
    if any(type(i) is not int or not 0 <= i < count for i in branch_ids):
        raise ValueError("branch ID must be a zero-based design rotor index")
    branches = tuple(scenario.branch_limits.get(i, BranchLimits()) for i in range(count))

    # Optional sourced powertrain in the loop (mixer ceiling + aux telemetry).
    aux_enabled = design.powertrain is not None and library is not None
    if aux_enabled and (not design.powertrain.motor_id
                        or not design.powertrain.propeller_id
                        or not design.powertrain.esc_id
                        or not design.powertrain.battery_id):
        raise ValueError(
            "powertrain block is incomplete (motor/propeller/esc/battery id "
            "missing) — fail closed instead of simulating a partial powertrain"
        )
    loop_pt: LoopPowertrain | None = None
    if aux_enabled:
        motor = library.motor(design.powertrain.motor_id)
        prop = library.propeller(design.powertrain.propeller_id)
        battery_spec = library.battery(design.powertrain.battery_id)
        esc_spec = library.esc(design.powertrain.esc_id)
        dataset = PowertrainDataset(motor, prop.motor_test_data_key or prop.id)
        battery = BatteryPack(battery_spec)
        rpm_hi = float(dataset.envelope()["rpm_range_merged"][1])
        max_thrust = float(dataset.thrust_n(rpm_hi).value)
        controller.mixer = Mixer(plant, max_thrust_per_rotor_n=max_thrust)
        loop_pt = LoopPowertrain(dataset, Esc(esc_spec), battery)

    # Structural check setup (fail-closed: a declared frame must be checkable).
    material: MaterialProps | None = None
    effective_spans_m: list[float] | None = None
    if design.frame is not None:
        if library is None:
            raise ValueError(
                "design declares a frame but no component library was provided — "
                "the structural check cannot run (fail closed)"
            )
        materials = load_materials(library.data_dir / "materials.json")
        if design.frame.material_id not in materials:
            raise ValueError(
                f"frame material {design.frame.material_id!r} not in materials.json "
                "— structural check cannot run (fail closed)"
            )
        material = materials[design.frame.material_id]
        effective_spans_m = effective_arm_spans_m(
            design.frame.arm_length_m, [rotor.position_m for rotor in design.rotors]
        )

    sensors = SensorModel(scenario.sensor_config) if scenario.sensor_config else None

    state = make_state(
        r_world=np.array([0.0, 0.0, scenario.initial_altitude_m]),
        v_world=np.zeros(3),
        q_bw=np.array([1.0, 0.0, 0.0, 0.0]),
        omega_body=np.zeros(3),
    )
    body = plant.body
    dt = control_dt_s / substeps
    if not np.isfinite(scenario.duration_s) or scenario.duration_s <= 0.0:
        raise ValueError("scenario duration must be finite and positive")
    n_steps = int(round(scenario.duration_s / control_dt_s))

    times, states, thrusts_log = [], [], []
    cur_log, vbus_log, soc_log = [], [], []
    ceilings_log, branch_v_log, rpm_log, residual_log = [], [], [], []
    state_start_log, state_time_log, electrical_time_log = [], [], []
    command_log, nominal_log, applied_log, previous_log, integrated_log = [], [], [], [], []
    cutout = None
    events: list[FailureEvent] = []
    abort_event: FailureEvent | None = None
    struct_margins: list[float] = []
    energy_wh = 0.0
    notes: list[str] = []
    if not aux_enabled:
        notes.append("no sourced powertrain attached: currents/v_bus are not "
                     "simulated; energy is not reported (ideal actuators)")
    if design.frame is None:
        notes.append("no frame geometry in design: structural monitor skipped")
    else:
        assert effective_spans_m is not None  # computed fail-closed above
        radial_spans = [
            float(np.hypot(rotor.position_m[0], rotor.position_m[1]))
            for rotor in design.rotors
        ]
        if any(abs(span - design.frame.arm_length_m) > 1e-6 for span in radial_spans):
            notes.append(
                "STRUCTURAL GEOMETRY MISMATCH: frame.arm_length_m differs from "
                "the rotor's body-frame radial distance; using per-rotor "
                "max(declared, geometric) span. Review frame-root assumptions. "
                "Earlier structural margins must be recalculated."
            )
        notes.append(
            "structural check: independent per-rotor static cantilever bending "
            "from assumed body-frame root, effective spans (m): "
            + ", ".join(f"{length:.4f}" for length in effective_spans_m)
            + "; no fasteners, dynamics, torsion or fatigue"
        )
    if scenario.sensor_config is None:
        notes.append("perfect state knowledge (sensor noise/latency disabled)")

    z_max_cmd = scenario.initial_altitude_m
    if n_steps <= 0:
        raise ValueError("scenario must cover at least one control tick")

    for k in range(n_steps):
        check_time_limit()
        t = k * control_dt_s

        if fault is not None and cutout is None and t >= fault.at_s:
            component = {"motor_cutout": "motor", "esc_cutout": "esc"}.get(fault.kind)
            if component is None:
                abort_event = FailureEvent(
                    t, "unsupported_branch_failure", True,
                    f"rotor {fault.branch_id}: unsupported failure mechanism {fault.kind!r}",
                    BranchFinding(fault.branch_id, "actuator", fault.kind, status="INCONCLUSIVE"),
                )
                events.append(abort_event)
                break
            cutout = fault.branch_id
            events.append(FailureEvent(
                t, "branch_cutout", False, f"rotor {cutout}: {component} cutout",
                BranchFinding(cutout, component, "branch_availability", 0.0, 1.0),
            ))
        if scenario.branch_limits and loop_pt is None:
            for i in sorted(scenario.branch_limits):
                abort_event = FailureEvent(
                    t, "branch_model_missing", True, f"rotor {i} has no sourced electrical model",
                    BranchFinding(i, "actuator", "electrical_model", status="INCONCLUSIVE"),
                )
                events.append(abort_event)
            break

        state_start_log.append(state.copy())
        previous_log.append(controller.delivery_feedback.copy())
        measured = sensors.measure(state, t) if sensors else state
        targets = targets_at(t)
        z_max_cmd = max(z_max_cmd, targets.altitude_m)
        nominal = controller.step(measured, targets, control_dt_s)
        wrench = controller.mixer.requested_wrench
        command_log.append((controller.mixer.matrix @ nominal if wrench is None else wrench).copy())
        nominal_log.append(nominal.copy())
        thrusts = nominal.copy()
        if cutout is not None:
            thrusts[cutout] = controller.mixer.project_branch(thrusts[cutout], 0.0)

        event_start = len(events)
        aux = None
        if loop_pt is not None:
            soc_before, energy_before = loop_pt.soc, loop_pt.energy_wh
            try:
                aux = loop_pt.step(nominal, control_dt_s, branches=branches, cutout=cutout)
            except PowertrainError as exc:
                branch = None
                if isinstance(exc, VoltageCollapseError):
                    kind = "battery_voltage_collapse"
                elif isinstance(exc, BusOperatingPointError):
                    kind = "bus_operating_point_unsupported"
                elif isinstance(exc, OutOfSupportError):
                    kind = "battery_out_of_support"
                elif isinstance(exc, BranchSupportError):
                    kind = "branch_out_of_support"
                    branch = BranchFinding(
                        exc.branch_id, "esc", "electrical_model", status="INCONCLUSIVE"
                    )
                else:
                    kind = "powertrain_refused"
                battery_finding = exc.finding if isinstance(exc, DemandedPowerLimitError) else None
                events.append(FailureEvent(t, kind, True, str(exc), branch, battery_finding))
                # Retain the pre-tick state with zero applied propulsion.
                thrusts = np.zeros_like(nominal)
            else:
                thrusts = aux.delivered_thrust_n
                for ev in aux.events:
                    offset = ev["t_s"]
                    events.append(FailureEvent(
                        t if offset is None else t + offset, ev["kind"], ev["critical"],
                        ev["message"], ev.get("branch"), ev.get("battery"),
                    ))
        residual_log.append(controller.record_delivery(nominal, thrusts))

        # Monitors.
        ev = check_ground(state, t)
        if ev:
            events.append(ev)
        ev = check_attitude(state, t)
        if ev:
            events.append(ev)
        if material is not None and design.frame is not None:
            ev, margin = check_structure(
                thrusts, t, effective_spans_m,
                design.frame.tube_od_m, design.frame.tube_id_m, material)
            struct_margins.append(margin)
            if ev:
                events.append(ev)

        tick_events = sorted(events[event_start:], key=lambda e: e.t_s)
        events[event_start:] = tick_events
        abort_event = next((e for e in tick_events if e.critical), None)
        stop = (k + 1) * control_dt_s if abort_event is None else abort_event.t_s
        if aux is not None:
            if abort_event is not None and abort_event.kind in {"ground_crash", "attitude_loss", "structure_yield"}:
                loop_pt.soc, loop_pt.energy_wh = soc_before, energy_before
                aux.soc_pct = soc_before
            cur_log.append(aux.per_motor_current_a)
            vbus_log.append(aux.v_bus)
            soc_log.append(aux.soc_pct)
            ceilings_log.append(aux.attainable_thrust_n)
            branch_v_log.append(aux.branch_voltage_v)
            rpm_log.append(aux.per_motor_rpm)
            energy_wh = loop_pt.energy_wh
        electrical_time_log.append(stop if aux is not None else t)
        integrated_log.append(abort_event is None)
        if abort_event is not None:
            state_time_log.append(t)
            applied_log.append(np.zeros(4))
            times.append(t)
            states.append(state.copy())
            thrusts_log.append(thrusts.copy())
            break

        # Sample disturbances once at the tick boundary. RK stages may rotate
        # the held force but cannot read a command/event from a later tick.
        active = [d for d in scenario.disturbances if d.active(t)]

        def deriv(_t: float, x: np.ndarray) -> np.ndarray:
            fb, tb = plant.net_force_torque(x, thrusts)
            for d in active:
                if d.force_world is not None:
                    fb = fb + rotate(conjugate(x[6:10]), d.force_world)
                if d.torque_body is not None:
                    tb = tb + np.asarray(d.torque_body, dtype=float)
            return body.derivs(x, fb, tb)

        for j in range(substeps):
            state = normalize_state(rk4_step(deriv, t + j * dt, state, dt))

        state_time_log.append(stop)
        applied_log.append(controller.mixer.matrix @ thrusts)
        times.append(t)
        states.append(state.copy())
        thrusts_log.append(thrusts.copy())

    times_arr = np.array(times)
    states_arr = np.array(states).reshape(-1, len(state))
    # Time to altitude: first time z >= 95% of the max commanded altitude,
    # staying there for >= 1 s.
    if scenario.reference_mode == "planned":
        z_max_cmd = max(z for _, z in scenario.altitude_waypoints)
    time_to_alt = None
    above = states_arr[:, 2] >= 0.95 * z_max_cmd
    for i in range(len(above) - int(1.0 / control_dt_s)):
        if above[i] and above[i:i + int(1.0 / control_dt_s)].all():
            time_to_alt = state_time_log[i]
            break

    success: dict[str, bool] = {}
    for name, fn in scenario.success_criteria:
        try:
            success[name] = bool(fn(_ResultView(res=None, times=np.array(state_time_log),
                                                states=states_arr,
                                                time_to_alt=time_to_alt,
                                                energy_wh=energy_wh,
                                                events=events)))
        except Exception as exc:  # noqa: BLE001 — criteria must not crash the run
            success[name] = False
            notes.append(f"success criterion {name!r} raised: {exc}")
    success_all = all(success.values()) if success else None

    # Component verdicts (P0A-006): every component that was in the loop with
    # modeled limits starts at NO_MODELED_LIMIT_BREACHED — explicitly NOT a
    # fitness claim — and a critical limit breach names its component FAIL.
    component_verdicts: dict[str, str | dict] = {}
    if aux_enabled:
        for comp in ("battery", "motor", "esc", "powertrain"):
            component_verdicts[comp] = "NO_MODELED_LIMIT_BREACHED"
    if design.frame is not None:
        component_verdicts["frame"] = "NO_MODELED_LIMIT_BREACHED"
    unknown_events = {"battery_out_of_support", "bus_operating_point_unsupported",
                      "powertrain_refused", "branch_out_of_support",
                      "unsupported_branch_failure", "branch_model_missing"}
    known_failure = False
    unknown = False
    for ev in events:
        comp = _COMPONENT_OF_EVENT.get(ev.kind)
        if comp is not None and ev.critical:
            component_verdicts[comp] = "FAIL"
        elif ev.kind in {"battery_out_of_support", "bus_operating_point_unsupported"}:
            component_verdicts["battery"] = "INCONCLUSIVE"
        elif ev.kind == "powertrain_refused":
            component_verdicts["powertrain"] = "INCONCLUSIVE"
        if ev.battery is not None:
            pack = component_verdicts.setdefault("battery:pack", {
                "status": "FAIL", "component": "battery", "findings": [],
            })
            pack["findings"].append({**asdict(ev.battery), "t_s": ev.t_s})
        if ev.branch is not None:
            finding = ev.branch
            key = f"{finding.component}:{finding.branch_id}"
            verdict = component_verdicts.setdefault(key, {
                "status": finding.status, "branch_id": finding.branch_id,
                "component": finding.component, "findings": [],
            })
            verdict["findings"].append({**asdict(finding), "t_s": ev.t_s})
            if finding.status == "FAIL":
                component_verdicts[finding.component] = verdict["status"] = "FAIL"
        if ev.kind in unknown_events:
            unknown = True
        elif ev.critical or ev.branch is not None:
            known_failure = True

    flight_verdict = ("FAIL" if known_failure else "INCONCLUSIVE" if unknown
                      else "NO_MODELED_LIMIT_BREACHED")
    if flight_verdict != "NO_MODELED_LIMIT_BREACHED":
        success_all = False

    return ScenarioResult(
        scenario=scenario.name,
        aborted=abort_event is not None,
        abort_event=abort_event,
        events=events,
        times=times_arr,
        states=states_arr,
        thrusts=np.array(thrusts_log).reshape(-1, count),
        per_motor_current_a=np.array(cur_log) if cur_log else None,
        v_bus=np.array(vbus_log) if vbus_log else None,
        soc_pct=np.array(soc_log) if soc_log else None,
        energy_wh=energy_wh,
        time_to_altitude_s=time_to_alt,
        max_altitude_m=float(states_arr[:, 2].max()) if len(states_arr) else 0.0,
        structural_margin_min=float(np.min(struct_margins)) if struct_margins else None,
        success=success,
        success_all=success_all,
        notes=notes,
        allocation_counts=controller.allocation_counts.copy(),
        component_verdicts=component_verdicts,
        flight_verdict=flight_verdict,
        attainable_thrust_n=np.array(ceilings_log) if ceilings_log else None,
        branch_voltage_v=np.array(branch_v_log) if branch_v_log else None,
        per_motor_rpm=np.array(rpm_log) if rpm_log else None,
        wrench_residual=np.array(residual_log).reshape(-1, 4),
        clock=FlightClockTrace(
            state_start=np.array(state_start_log).reshape(-1, len(state)),
            state_time_s=np.array(state_time_log),
            electrical_time_s=np.array(electrical_time_log),
            command_wrench=np.array(command_log).reshape(-1, 4),
            nominal_thrust_n=np.array(nominal_log).reshape(-1, count),
            applied_rotor_wrench=np.array(applied_log).reshape(-1, 4),
            previous_wrench_residual=np.array(previous_log).reshape(-1, 4),
            integrated=np.array(integrated_log, dtype=bool),
        ),
    )


def _altitude_velocity_at(waypoints, t: float) -> float:
    """Segment slope of the piecewise-linear altitude schedule."""
    if t <= waypoints[0][0] or t >= waypoints[-1][0]:
        return 0.0
    for (t0, z0), (t1, z1) in zip(waypoints, waypoints[1:]):
        if t0 <= t <= t1:
            return (z1 - z0) / max(t1 - t0, 1e-9)
    return 0.0


def _position_velocity_at(waypoints, t: float):
    """Piecewise-linear (x, y) schedule with per-segment velocity feedforward."""
    if t <= waypoints[0][0]:
        return waypoints[0][1], (0.0, 0.0)
    for (t0, p0), (t1, p1) in zip(waypoints, waypoints[1:]):
        if t0 <= t <= t1:
            f = (t - t0) / (t1 - t0)
            pos = (p0[0] + (p1[0] - p0[0]) * f, p0[1] + (p1[1] - p0[1]) * f)
            dt_seg = max(t1 - t0, 1e-9)
            vel = ((p1[0] - p0[0]) / dt_seg, (p1[1] - p0[1]) / dt_seg)
            return pos, vel
    return waypoints[-1][1], (0.0, 0.0)


class _ResultView:
    """Minimal read-only view handed to success criteria callables."""

    def __init__(self, res, times, states, time_to_alt, energy_wh, events):
        self.times = times
        self.states = states
        self.time_to_altitude_s = time_to_alt
        self.energy_wh = energy_wh
        self.events = events


# ------------------------------------------------------------ stock scenarios


def takeoff_climb_scenario(hover_alt_m: float = 5.0, duration_s: float = 16.0) -> Scenario:
    """0 -> hover_alt: fast climb phase, then a slower arrival segment (the
    piecewise-linear profile must decelerate BEFORE the target — a linear
    profile demanding an instant stop would overshoot by v/kd)."""
    t_climb = hover_alt_m / 2.0  # nominal 2 m/s average
    waypoints = [
        (0.0, 0.0),
        (0.6 * t_climb, 0.75 * hover_alt_m),  # fast climb phase (2.5 m/s)
        (t_climb, hover_alt_m),               # slower arrival segment (1.25 m/s)
        (duration_s, hover_alt_m),            # hold
    ]

    def reached(view) -> bool:
        return view.time_to_altitude_s is not None

    return Scenario(
        name=f"takeoff_climb_{hover_alt_m:.0f}m",
        duration_s=duration_s,
        altitude_waypoints=waypoints,
        reference_mode="planned",
        success_criteria=[("reached_altitude", reached),
                          ("no_critical_failure", lambda v: not any(e.critical for e in v.events))],
    )


def landing_scenario(start_alt_m: float = 5.0, duration_s: float = 14.0) -> Scenario:
    """Descend from start_alt to ground; success = gentle touchdown, stays down.
    The last 4 s hold z=0 so the exponential approach settles."""
    waypoints = [(0.0, start_alt_m), (duration_s - 4.0, 0.0), (duration_s, 0.0)]

    def gentle_touchdown(view) -> bool:
        z_end = view.states[-1, 2]
        vz_end = view.states[-1, 5]
        return abs(z_end) < 0.05 and abs(vz_end) < 1.5

    return Scenario(
        name=f"landing_from_{start_alt_m:.0f}m",
        duration_s=duration_s,
        altitude_waypoints=waypoints,
        reference_mode="planned",
        initial_altitude_m=start_alt_m,
        success_criteria=[("gentle_touchdown", gentle_touchdown),
                          ("no_critical_failure", lambda v: not any(e.critical for e in v.events))],
    )


def forward_flight_scenario(distance_m: float = 5.0, speed_m_s: float = 2.0) -> Scenario:
    """Climb to 3 m, fly forward `distance` m at `speed` with an accel-shaped
    deceleration segment, success = arrival within tolerance."""
    climb_t = 3.0 / 2.0
    fly_t = distance_m / speed_m_s
    duration = climb_t + fly_t + 3.0 + 2.0
    waypoints = [(0.0, 0.0), (climb_t, 3.0), (duration, 3.0)]
    # Transit at speed, then a two-segment deceleration into the stop.
    x_dec1 = distance_m - 0.8 * speed_m_s * 0.8   # 0.8 m/s over the last 0.8 s
    pos = [
        (0.0, (0.0, 0.0)),
        (climb_t, (0.0, 0.0)),
        (climb_t + fly_t - 0.8, (x_dec1, 0.0)),
        (climb_t + fly_t, (distance_m, 0.0)),
        (duration, (distance_m, 0.0)),
    ]

    def arrived(view) -> bool:
        tail = view.states[view.times >= view.times[-1] - 1.5]
        return bool(np.abs(tail[:, 0] - distance_m).max() < 0.3)

    return Scenario(
        name=f"forward_flight_{distance_m:.0f}m",
        duration_s=duration,
        altitude_waypoints=waypoints,
        reference_mode="planned",
        position_waypoints=pos,
        success_criteria=[("arrived", arrived),
                          ("no_critical_failure", lambda v: not any(e.critical for e in v.events))],
    )


def motor_failure_scenario(hover_alt_m: float = 2.0, failure_at_s: float = 4.0) -> Scenario:
    """Take off and hover, then kill motor 0: the run must ABORT with a named
    unrecoverable-state event (spec Prompt 6)."""
    waypoints = [(0.0, 0.0), (failure_at_s - 1.0, hover_alt_m),
                 (failure_at_s + 6.0, hover_alt_m)]
    return Scenario(
        name="motor_failure_injection",
        duration_s=failure_at_s + 8.0,
        altitude_waypoints=waypoints,
        reference_mode="planned",
        motor_failure_at_s=failure_at_s,
        success_criteria=[],
    )
