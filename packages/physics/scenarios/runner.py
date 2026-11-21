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
    - any ESC branch current or shared bus voltage above its declared rating,
    - arm root bending stress at/above material yield,
    - ground impact (z below start with negative speed at ground level),
    - attitude loss (|tilt| > 45 deg — unrecoverable for this controller class).
  NON-CRITICAL (logged, run continues):
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

from dataclasses import dataclass, field

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
        self.continuous_duration_s = motor.max_continuous_duration_s or 180.0
        self._over_current_time = np.zeros(1)  # resized per unit count
        self._warning_latched = False
        self._v_bus_seed: float | None = None  # previous tick's converged bus
        self.energy_wh = 0.0

    def step(self, thrusts: np.ndarray, dt: float) -> LoopAux:
        n = len(thrusts)
        if len(self._over_current_time) != n:
            self._over_current_time = np.zeros(n)
        events: list[dict] = []
        rpm_lo, rpm_hi = self.dataset.envelope()["rpm_range_merged"]

        # Causal state: everything below uses the SOC at this tick's clock.
        soc_pre = self.soc
        v_oc = self.battery.ocv_pack(soc_pre)

        # Fixed-point bus solve: currents depend on v_bus, v_bus on total draw.
        # Seeded with the previous tick's converged bus voltage (past state)
        # or the OCV on the first tick. A sagged bus leaving the measured
        # motor-data voltage excursion mid-solve is the collapse regime of
        # this data-limited model — converted to the typed refusal below.
        v_bus = self._v_bus_seed if self._v_bus_seed is not None else v_oc
        currents = np.zeros(n)
        rpms = np.zeros(n)
        converged = False
        try:
            for _ in range(BUS_SOLVE_MAX_ITERATIONS):
                total_current = 0.0
                for i, thrust in enumerate(thrusts):
                    if thrust > self.max_thrust_n:
                        if not any(
                            e["kind"] == "over_max_thrust" and e.get("motor") == i
                            for e in events
                        ):
                            events.append({
                                "kind": "over_max_thrust",
                                "critical": True,
                                "motor": i,
                                "message": (
                                    f"motor {i} commanded {thrust:.1f} N above the measured "
                                    f"static maximum {self.max_thrust_n:.1f} N (propeller "
                                    "over-speed territory — outside validated envelope)"
                                ),
                                "t_s": None,
                            })
                        rpms[i] = float("nan")
                        currents[i] = float("nan")
                        continue
                    if thrust <= 1e-9:
                        rpms[i] = 0.0
                        currents[i] = 0.0
                        continue
                    gf = thrust / 9.80665e-3
                    gf_table_min = float(self.dataset._merged_thrust_gf.min())
                    if gf < gf_table_min:
                        # Descent regime below the measured table: DECLARED
                        # extrapolation (static scaling + nearest-plane current),
                        # flagged non-critically once per tick.
                        rpm = self.dataset.thrust_rpm_extrapolated(gf).value
                        cur = self.dataset.current_a_extrapolated(rpm, v_bus).value
                        if not any(e["kind"] == "thrust_below_envelope" for e in events):
                            events.append({
                                "kind": "thrust_below_envelope",
                                "critical": False,
                                "message": (
                                    f"per-motor thrust {thrust:.2f} N below the measured "
                                    f"static minimum {gf_table_min * 9.80665e-3:.2f} N — "
                                    "rpm/current are declared extrapolations (uncertainty "
                                    "widened)"
                                ),
                                "t_s": None,
                            })
                    else:
                        f = lambda r: float(self.dataset.thrust_gf(r).value) - gf  # noqa: E731
                        rpm = brentq(f, float(rpm_lo), float(rpm_hi), xtol=1e-3)
                        cur = self.dataset.current_a(rpm, v_bus).value
                    rpms[i] = rpm
                    currents[i] = cur
                    total_current += cur
                v_new = self.battery.voltage_under_load(soc_pre, total_current)
                if abs(v_new - v_bus) < BUS_SOLVE_TOLERANCE_V:
                    v_bus = v_new
                    converged = True
                    break
                v_bus = 0.5 * (v_bus + v_new)
        except OutOfEnvelopeError as exc:
            raise VoltageCollapseError(
                "bus voltage left the measured motor-data voltage excursion "
                f"during the solve at {soc_pre:.1f}% SOC ({exc}) — the demanded "
                "operating point is not attainable on measured data "
                "(fail closed)"
            ) from exc
        if not converged:
            raise PowertrainError(
                f"bus voltage solve did not converge in {BUS_SOLVE_MAX_ITERATIONS} "
                f"iterations at {soc_pre:.1f}% SOC (last v_bus={v_bus:.3f} V, OCV "
                f"{v_oc:.2f} V) — the demanded operating point has no stable "
                "quasi-static solution at this clock"
            )
        self._v_bus_seed = v_bus

        # Attainable-output gate: the commanded electrical power must lie
        # inside the pack's exact constant-power feasibility boundary
        # (V_oc^2 / (4 R) at this SOC). Above it the bus collapses — the
        # commanded propulsion output is NOT attainable and is not simulated.
        total_current = float(np.nansum(currents))
        demanded_power_w = v_bus * total_current
        max_power_w = self.battery.max_deliverable_power_w(soc_pre)
        if demanded_power_w > max_power_w:
            raise VoltageCollapseError(
                f"demanded bus power {demanded_power_w:.1f} W exceeds the pack's "
                f"maximum deliverable power {max_power_w:.1f} W at {soc_pre:.1f}% SOC "
                f"(OCV {v_oc:.2f} V, R {self.battery.spec.internal_resistance_ohm:.4f} "
                "ohm) — voltage collapse; the commanded propulsion output is not "
                "attainable"
            )

        # Battery drain over the tick, then threshold brackets: the loaded
        # cell voltage is evaluated on the start-of-tick state and bracketed
        # through the tick's linear SOC drain, so a crossing is stamped at
        # its bracketed time (equality and tick edges fire deterministically).
        soc_post = self.battery.soc_after(soc_pre, total_current, dt)
        self.energy_wh += v_bus * total_current * dt / 3600.0
        self.soc = soc_post

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
            })

        # Motor thermal rule (datasheet-backed): continuous rating for the
        # datasheet's continuous duration; 2x rating instantaneous destruction.
        if self.max_continuous_a is not None:
            for i, cur in enumerate(currents):
                if not np.isfinite(cur):
                    continue
                if cur > 2.0 * self.max_continuous_a:
                    events.append({
                        "kind": "motor_overcurrent_destructive",
                        "critical": True,
                        "message": (
                            f"motor {i} at {cur:.1f} A > 2x continuous rating "
                            f"{self.max_continuous_a:.1f} A — instantaneous burnout"
                        ),
                        "t_s": None,
                    })
                elif cur > self.max_continuous_a:
                    self._over_current_time[i] += dt
                    if self._over_current_time[i] > self.continuous_duration_s:
                        events.append({
                            "kind": "motor_burnout",
                            "critical": True,
                            "message": (
                                f"motor {i} above continuous current "
                                f"{self.max_continuous_a:.1f} A for "
                                f"{self._over_current_time[i]:.0f} s > rated "
                                f"{self.continuous_duration_s:.0f} s — thermal burnout"
                            ),
                            "t_s": None,
                        })
                else:
                    self._over_current_time[i] = 0.0

        for i, current in enumerate(currents):
            issue = self.esc.current_issue(current)
            if issue:
                events.append({"kind": "esc_overcurrent", "critical": True,
                               "message": f"rotor {i}: {issue}", "t_s": None})
        voltage_issue = self.esc.voltage_issue(v_bus)
        if voltage_issue:
            events.append({"kind": "esc_overvoltage", "critical": True,
                           "message": voltage_issue, "t_s": None})

        return LoopAux(
            v_bus=v_bus,
            soc_pct=self.soc,
            per_motor_rpm=rpms.tolist(),
            per_motor_current_a=currents.tolist(),
            total_current_a=total_current,
            total_power_w=v_bus * total_current,
            events=events,
        )


# ------------------------------------------------------------------ monitors


@dataclass(frozen=True)
class FailureEvent:
    t_s: float
    kind: str
    critical: bool
    message: str


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
    component_verdicts: dict[str, str] = field(default_factory=dict)


# Component owning each critical limit event (P0A-006 verdict propagation).
_COMPONENT_OF_EVENT: dict[str, str] = {
    "battery_cutoff": "battery",
    "battery_voltage_collapse": "battery",
    "battery_out_of_support": "battery",
    "motor_overcurrent_destructive": "motor",
    "motor_burnout": "motor",
    "esc_overcurrent": "esc",
    "esc_overvoltage": "esc",
    "structure_yield": "frame",
    "powertrain_refused": "powertrain",
}


def run_scenario(
    design,
    scenario: Scenario,
    library=None,
    control_dt_s: float = 0.004,
    substeps: int = 2,
) -> ScenarioResult:
    """Run a scenario on the design; aborts on critical failure events."""
    from physics.dynamics.design_adapter import build_multirotor
    from physics.propulsion.loader import ComponentLibrary

    plant, mass_props = build_multirotor(design)
    controller = QuadcopterController(plant)

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
    else:
        dataset = None

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
    n_steps = int(round(scenario.duration_s / control_dt_s))

    times, states, thrusts_log = [], [], []
    cur_log, vbus_log, soc_log = [], [], []
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

    for k in range(n_steps):
        check_time_limit()
        t = k * control_dt_s

        # Time-parameterized targets from the profiles.
        z_t = altitude_at(scenario.altitude_waypoints, t)
        vz_t = _altitude_velocity_at(scenario.altitude_waypoints, t)
        pos_t = vel_t = None
        if scenario.position_waypoints is not None:
            pos_t, vel_t = _position_velocity_at(scenario.position_waypoints, t)
        targets = ControlTargets(altitude_m=z_t, position_xy=pos_t,
                                 velocity_xy=vel_t, velocity_z=vz_t)

        measured = sensors.measure(state, t) if sensors else state
        thrusts = controller.step(measured, targets, control_dt_s)

        # Failure injection: kill motor 0.
        if scenario.motor_failure_at_s is not None and t >= scenario.motor_failure_at_s:
            thrusts[0] = 0.0

        # Powertrain aux + its events. A fail-closed refusal (the pack cannot
        # supply the demanded operating point, or the state leaves the
        # declared support) becomes a named critical event — the commanded
        # propulsion output is NOT simulated and no post-failure state is
        # invented (P0A-006).
        aux = None
        if loop_pt is not None:
            try:
                aux = loop_pt.step(thrusts, control_dt_s)
            except PowertrainError as exc:
                if isinstance(exc, VoltageCollapseError):
                    kind = "battery_voltage_collapse"
                elif isinstance(exc, OutOfSupportError):
                    kind = "battery_out_of_support"
                else:
                    kind = "powertrain_refused"
                fe = FailureEvent(t_s=t, kind=kind, critical=True, message=str(exc))
                abort_event = fe
                events.append(fe)
            else:
                for ev in aux.events:
                    # "t_s" in a powertrain event is either None (stamp at the
                    # tick start) or the crossing offset WITHIN the tick, so
                    # the absolute event time is the tick start plus the
                    # bracketed offset (P0A-006).
                    t_ev = t if ev["t_s"] is None else t + ev["t_s"]
                    fe = FailureEvent(
                        t_s=t_ev,
                        kind=ev["kind"], critical=ev["critical"],
                        message=ev["message"],
                    )
                    if fe.critical:
                        abort_event = fe
                    events.append(fe)

        # Monitors.
        ev = check_ground(state, t)
        if ev:
            abort_event = ev
            events.append(ev)
        ev = check_attitude(state, t)
        if ev:
            abort_event = ev
            events.append(ev)
        if material is not None and design.frame is not None:
            ev, margin = check_structure(
                thrusts, t, effective_spans_m,
                design.frame.tube_od_m, design.frame.tube_id_m, material)
            struct_margins.append(margin)
            if ev:
                abort_event = ev
                events.append(ev)

        if abort_event is not None:
            # Record the aborting tick's telemetry, then stop.
            times.append(t)
            states.append(state.copy())
            thrusts_log.append(thrusts.copy())
            if aux is not None:
                cur_log.append(aux.per_motor_current_a)
                vbus_log.append(aux.v_bus)
                soc_log.append(aux.soc_pct)
                energy_wh = loop_pt.energy_wh
            break

        # Integrate with disturbances (zero-order hold over the tick).
        f_body, t_body = plant.net_force_torque(state, thrusts)
        for d in scenario.disturbances:
            if d.active(t):
                if d.force_world is not None:
                    f_body = f_body + rotate(conjugate(state[6:10]), d.force_world)
                if d.torque_body is not None:
                    t_body = t_body + np.asarray(d.torque_body, dtype=float)

        def deriv(_t: float, x: np.ndarray) -> np.ndarray:
            fb, tb = plant.net_force_torque(x, thrusts)
            for d in scenario.disturbances:
                if d.active(_t):
                    if d.force_world is not None:
                        fb = fb + rotate(conjugate(x[6:10]), d.force_world)
                    if d.torque_body is not None:
                        tb = tb + np.asarray(d.torque_body, dtype=float)
            return body.derivs(x, fb, tb)

        for _ in range(substeps):
            state = rk4_step(deriv, t, state, dt)
            state = normalize_state(state)
            t += dt

        times.append(k * control_dt_s)
        states.append(state.copy())
        thrusts_log.append(thrusts.copy())
        if aux is not None:
            cur_log.append(aux.per_motor_current_a)
            vbus_log.append(aux.v_bus)
            soc_log.append(aux.soc_pct)
            energy_wh = loop_pt.energy_wh

    times_arr = np.array(times)
    states_arr = np.array(states)
    # Time to altitude: first time z >= 95% of the max commanded altitude,
    # staying there for >= 1 s.
    z_max_cmd = max(z for _, z in scenario.altitude_waypoints)
    time_to_alt = None
    above = states_arr[:, 2] >= 0.95 * z_max_cmd
    for i in range(len(above) - int(1.0 / control_dt_s)):
        if above[i] and above[i:i + int(1.0 / control_dt_s)].all():
            time_to_alt = float(times_arr[i])
            break

    success: dict[str, bool] = {}
    for name, fn in scenario.success_criteria:
        try:
            success[name] = bool(fn(_ResultView(res=None, times=times_arr,
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
    component_verdicts: dict[str, str] = {}
    if aux_enabled:
        for comp in ("battery", "motor", "esc", "powertrain"):
            component_verdicts[comp] = "NO_MODELED_LIMIT_BREACHED"
    if design.frame is not None:
        component_verdicts["frame"] = "NO_MODELED_LIMIT_BREACHED"
    for ev in events:
        comp = _COMPONENT_OF_EVENT.get(ev.kind)
        if comp is not None and ev.critical:
            component_verdicts[comp] = "FAIL"

    return ScenarioResult(
        scenario=scenario.name,
        aborted=abort_event is not None,
        abort_event=abort_event,
        events=events,
        times=times_arr,
        states=states_arr,
        thrusts=np.array(thrusts_log),
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
        motor_failure_at_s=failure_at_s,
        success_criteria=[],
    )
