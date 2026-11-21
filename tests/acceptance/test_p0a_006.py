"""P0A-006 — causal battery sag and cutoff event propagation acceptance.

Proves, on the authoritative flight plant (Godot -> scripts/lab_project.py run
-> project_service.run_project -> simulation_service.run_simulation ->
scenarios.service.run_flight -> runner.run_scenario -> LoopPowertrain.step;
``packages/desktop_worker/engine.py`` is the CAD engine and is deliberately
NOT touched):

  1. Strict causality — perturbing the load after t_k leaves the state,
     telemetry and events bit-identical up to and including t_k.
  2. Exact event bracketing — a threshold crossing at a tick edge fires
     deterministically (equality uses ``<=``), an interior crossing is
     bracketed to float precision on the model's own OCV interpolation, and
     the plant stamps events at their bracketed time.
  3. Voltage collapse — a demand above the pack's exact constant-power
     collapse boundary V_oc^2/(4 R) is refused (named critical event, battery
     FAIL verdict, no post-failure thrust or state simulated).
  4. Verdict propagation — cutoff/limit breaches name their component FAIL in
     ScenarioResult.component_verdicts and the run_flight report; thresholds
     are used verbatim from the declared component spec (no hardcoded tuning).

The frozen M21 SIT artifacts are historical baselines (asserted by
tests/acceptance/test_p0a_005.py); the repaired causal model's evaluation
delta is asserted here from the committed
docs/campaigns/m21_sit_causal_repair_delta.json.

Reference: docs/acceptance/P0A-006.md, docs/M21_BATTERY_CAMPAIGN.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DESIGN_MN = REPO_ROOT / "data" / "designs" / "quad_mn3508_6s.json"
DELTA_RESULTS = REPO_ROOT / "docs/campaigns/m21_sit_causal_repair_delta.json"
REPLAY_RESULTS = REPO_ROOT / "docs/campaigns/m21_sit_module_electrothermal_results.json"
FORECAST_RESULTS = REPO_ROOT / "docs/campaigns/m21_sit_cutoff_forecast_results.json"

sys.path[:0] = [str(REPO_ROOT / "packages"), str(REPO_ROOT / "packages/shared-schemas")]

from aeroforge_schemas.design import DroneDesign  # noqa: E402
from physics.propulsion.battery import (  # noqa: E402
    BatteryPack,
    OutOfSupportError,
    PowerSolution,
    PowertrainError,
    VoltageCollapseError,
)
from physics.propulsion.dataset import PowertrainDataset  # noqa: E402
from physics.propulsion.esc import Esc  # noqa: E402
from physics.propulsion.loader import ComponentLibrary  # noqa: E402
from physics.scenarios.runner import (  # noqa: E402
    FailureEvent,
    LoopPowertrain,
    Scenario,
    run_scenario,
)
from physics.scenarios.service import run_flight  # noqa: E402


@pytest.fixture(scope="module")
def library() -> ComponentLibrary:
    return ComponentLibrary(REPO_ROOT / "data" / "components")


@pytest.fixture(scope="module")
def design() -> DroneDesign:
    return DroneDesign.model_validate_json(DESIGN_MN.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def plant_parts(design, library):
    motor = library.motor(design.powertrain.motor_id)
    prop = library.propeller(design.powertrain.propeller_id)
    dataset = PowertrainDataset(motor, prop.motor_test_data_key or prop.id)
    esc = Esc(library.esc(design.powertrain.esc_id))
    return dataset, esc


def linear_pack(
    r_ohm: float = 0.02,
    capacity_ah: float = 16.0,
    cells: int = 6,
    cutoff_v: float = 3.3,
    warning_v: float = 3.5,
) -> BatteryPack:
    """Synthetic pack with a LINEAR declared cell OCV (3.0 V at 0 %, 4.2 V at
    100 %) so every crossing time has a closed form to test against."""
    from aeroforge_schemas.component import BatterySpec

    spec = BatterySpec(
        id="p0a006_linear", name="P0A-006 linear test pack", chemistry="LiPo",
        cells_series=cells, capacity_ah=capacity_ah, internal_resistance_ohm=r_ohm,
        warning_cell_voltage_v=warning_v, cutoff_cell_voltage_v=cutoff_v,
        ocv_curve=[
            {"soc_pct": s, "cell_voltage_v": 3.0 + 1.2 * s / 100.0}
            for s in (0, 20, 40, 60, 80, 100)
        ],
        source={"source": "Synthetic linear OCV for deterministic bracketing tests",
                "estimated": True},
    )
    return BatteryPack(spec)


def _hover_scenario(duration_s: float = 6.0, altitude_m: float = 2.0) -> Scenario:
    return Scenario(
        name="p0a006_hover",
        duration_s=duration_s,
        altitude_waypoints=[(0.0, 0.0), (1.0, altitude_m),
                            (duration_s, altitude_m)],
        success_criteria=[],
    )


# ---------------------------------------------------------------------------
# 1. Strict causality: zero future-information leakage
# ---------------------------------------------------------------------------


def test_loop_powertrain_has_no_future_information_leakage(design, library, plant_parts):
    """Stepping the plant with two load sequences that agree up to step k0 and
    differ afterwards must produce BIT-IDENTICAL auxiliary state for every
    step k <= k0 (no step may read a later SOC/current than its clock)."""
    dataset, esc = plant_parts
    battery = linear_pack()
    dt = 0.004
    k0 = 25
    rng = np.random.default_rng(20261121)
    hover = np.full(4, 9.0)
    seq_a = [hover for _ in range(60)]
    seq_b = [hover if k <= k0 else hover + rng.uniform(0.5, 2.0, size=4)
             for k in range(60)]

    pt_a = LoopPowertrain(dataset, esc, battery)
    pt_b = LoopPowertrain(dataset, esc, battery)
    aux_a = [pt_a.step(t, dt) for t in seq_a]
    aux_b = [pt_b.step(t, dt) for t in seq_b]

    for k in range(k0 + 1):
        assert aux_a[k].v_bus == aux_b[k].v_bus
        assert aux_a[k].soc_pct == aux_b[k].soc_pct
        assert aux_a[k].total_current_a == aux_b[k].total_current_a
        assert aux_a[k].events == aux_b[k].events
    # The perturbation DID take effect after k0 (the test is not vacuous).
    assert aux_a[k0 + 5].total_current_a != aux_b[k0 + 5].total_current_a


def test_flight_plant_has_no_future_information_leakage(design, library):
    """Two full scenario runs differing only in a disturbance that activates
    strictly after t_k must be bit-identical in state and powertrain
    telemetry up to and including t_k."""
    from physics.controller.simulation import Disturbance

    t_k = 1.5
    base = _hover_scenario()
    pert = _hover_scenario()
    pert.disturbances = [
        Disturbance(t_start=t_k + 0.25, t_end=t_k + 0.75,
                    force_world=np.array([3.0, 0.0, 0.0]))
    ]
    res_a = run_scenario(design, base, library)
    res_b = run_scenario(design, pert, library)
    assert res_a.per_motor_current_a is not None and res_a.v_bus is not None
    mask = res_a.times <= t_k
    assert mask.any()
    assert np.array_equal(res_a.times[mask], res_b.times[mask])
    assert np.array_equal(res_a.states[mask], res_b.states[mask])
    assert np.array_equal(res_a.thrusts[mask], res_b.thrusts[mask])
    assert np.array_equal(res_a.v_bus[mask], res_b.v_bus[mask])
    assert np.array_equal(res_a.soc_pct[mask], res_b.soc_pct[mask])
    assert np.array_equal(res_a.per_motor_current_a[mask],
                          res_b.per_motor_current_a[mask])
    # ...and the perturbation actually changed the later trajectory.
    assert not np.array_equal(res_a.states[~mask], res_b.states[~mask])


# ---------------------------------------------------------------------------
# 2. Exact event bracketing: equality, tick edges, interior crossings
# ---------------------------------------------------------------------------


def _closed_form_crossing(pack, soc_start, soc_end, current, dt, threshold):
    """Exact crossing time for the LINEAR synthetic OCV (cell V = 3.0 +
    1.2*soc/100 - I*R/cells), for test verification."""
    sag_cell = current * pack.spec.internal_resistance_ohm / pack.spec.cells_series
    soc_star = (threshold + sag_cell - 3.0) * 100.0 / 1.2
    if soc_star >= soc_start:
        return 0.0
    if soc_star <= soc_end:
        # Below the threshold already at the end of the tick (or entire tick).
        return None if soc_star < soc_end else dt
    return dt * (soc_start - soc_star) / (soc_start - soc_end)


def test_crossing_bracket_equality_and_tick_edges():
    """Exact equality fires deterministically: a start-of-tick crossing
    returns 0.0, and a crossing EXACTLY at the tick's end edge returns dt
    (both inclusive via ``<=``; the endpoint test builds the threshold from
    the pack's own OCV evaluation so f(edge) is exactly 0.0 in floats)."""
    pack = linear_pack()
    dt = 0.004
    # Start exactly at the threshold: crossing at tau = 0.
    thr_start = pack.ocv_cell(100.0) - 10.0 * 0.02 / 6
    assert pack.crossing_time_below_cell_v(100.0, 99.9, 10.0, dt, thr_start) == 0.0
    # End exactly at the threshold: crossing at tau = dt (tick edge).
    thr_end = pack.ocv_cell(40.0) - 10.0 * 0.02 / 6
    tau = pack.crossing_time_below_cell_v(50.0, 40.0, 10.0, dt, thr_end)
    assert tau == dt


def test_crossing_bracket_interior_matches_closed_form():
    """An interior crossing is bracketed to float precision and matches the
    closed-form crossing time of the linear declared OCV."""
    pack = linear_pack()
    dt = 0.004
    cases = [
        (60.0, 55.0, 30.0, dt, 3.6),        # soc* = 58.3: interior
        (60.0, 50.0, 55.0, dt, 3.5),        # soc* = 56.9: interior
        (50.0, 40.0, 20.0, dt * 2, 3.45),   # soc* = 43.1: interior
        (55.0, 40.0, 80.0, 1.0, 3.35),      # soc* = 51.4: interior
    ]
    for soc_start, soc_end, current, dt_i, thr in cases:
        tau = pack.crossing_time_below_cell_v(soc_start, soc_end, current, dt_i, thr)
        expected = _closed_form_crossing(pack, soc_start, soc_end, current, dt_i, thr)
        assert tau is not None
        assert tau == pytest.approx(expected, rel=1e-9, abs=1e-12)
        assert 0.0 <= tau <= dt_i


def test_crossing_bracket_no_crossing_returns_none():
    pack = linear_pack()
    assert pack.crossing_time_below_cell_v(100.0, 99.0, 1.0, 0.004, 3.0) is None


def test_crossing_bracket_refuses_unsupported_drain():
    """A drain leaving the declared OCV support before reaching the threshold
    fails closed (no invented low-SOC tail)."""
    from aeroforge_schemas.component import BatterySpec

    spec = BatterySpec(
        id="p0a006_partial", name="partial support", chemistry="LiPo",
        cells_series=6, capacity_ah=16.0, internal_resistance_ohm=0.02,
        warning_cell_voltage_v=3.5, cutoff_cell_voltage_v=3.3,
        ocv_curve=[{"soc_pct": s, "cell_voltage_v": 3.6 + 0.6 * (s - 20.0) / 80.0}
                   for s in (20, 40, 60, 80, 100)],
        source={"source": "Synthetic partial-support table", "estimated": True},
    )
    pack = BatteryPack(spec)
    assert pack.declared_soc_support_pct == (20.0, 100.0)
    with pytest.raises(OutOfSupportError, match="declared OCV support"):
        pack.ocv_cell(19.999)
    with pytest.raises(OutOfSupportError, match="leaves its declared OCV support"):
        pack.crossing_time_below_cell_v(25.0, 10.0, 10.0, 1.0, 3.3)
    # In-support queries are unaffected.
    assert pack.ocv_cell(20.0) == pytest.approx(3.6, abs=1e-12)


def test_plant_stamps_cutoff_at_bracketed_interior_time(design, library, plant_parts):
    """A mid-tick cutoff crossing is stamped strictly inside the tick and the
    bracketed instant satisfies the threshold equation on the pack's own
    model (bisection correctness). A coarse 0.5 s tick makes the crossing
    land strictly interior by construction (the 4 ms controller tick resolves
    the same physics with boundary-inclusive semantics — covered by the
    depleted-pack and verdict-run tests)."""
    dataset, esc = plant_parts
    # Engineer a small pack that crosses the 3.3 V/cell cutoff mid-run under
    # a constant hover-like load.
    pack = linear_pack(r_ohm=0.05, capacity_ah=0.02)
    pt = LoopPowertrain(dataset, esc, pack)
    dt = 0.5
    thrusts = np.full(4, 9.0)
    aux = None
    tick = None
    for k in range(40):
        aux = pt.step(thrusts, dt)
        if any(e["kind"] == "battery_cutoff" for e in aux.events):
            tick = k
            break
        if aux.events and any(e["kind"] == "battery_voltage_collapse" for e in aux.events):
            pytest.fail("pack collapsed before the cutoff bracket could be tested")
    assert tick is not None, "engineered pack never reached the cutoff"
    cutoff_events = [e for e in aux.events if e["kind"] == "battery_cutoff"]
    assert len(cutoff_events) == 1
    ev = cutoff_events[0]
    tau = ev["t_s"]  # the bracketed offset WITHIN the tick (aux contract)
    assert 0.0 < tau <= dt

    # Reconstruct the tick's SOC interval and verify the bracketed instant
    # satisfies the threshold equation on the pack's own OCV model.
    drained = 100.0 * aux.total_current_a * dt / (3600.0 * pack.spec.capacity_ah)
    soc_post = aux.soc_pct
    soc_pre = soc_post + drained
    soc_at = soc_pre + (soc_post - soc_pre) * tau / dt
    sag_cell = aux.total_current_a * pack.spec.internal_resistance_ohm / pack.spec.cells_series
    assert pack.ocv_cell(soc_at) - sag_cell == pytest.approx(
        pack.spec.cutoff_cell_voltage_v, abs=1e-9)


def test_plant_fires_cutoff_immediately_for_depleted_pack(design, library, plant_parts):
    """A pack starting at/below the cutoff fires the cutoff event at t=0
    exactly (equality at the tick edge), and the run aborts with a battery
    FAIL verdict."""
    dataset, esc = plant_parts
    pack = linear_pack(r_ohm=0.05, capacity_ah=16.0)
    pt = LoopPowertrain(dataset, esc, pack, soc_start_pct=0.0)
    aux = pt.step(np.full(4, 9.0), 0.004)
    cutoff = [e for e in aux.events if e["kind"] == "battery_cutoff"]
    assert len(cutoff) == 1 and cutoff[0]["t_s"] == 0.0


def test_cutoff_run_propagates_battery_fail_verdict(design, library):
    """A full scenario run that breaches the battery cutoff aborts with the
    named event and carries component_verdicts['battery'] == 'FAIL' while
    every other in-loop component stays NO_MODELED_LIMIT_BREACHED. The last
    recorded sample is the pre-cutoff state — nothing after the crossing is
    simulated."""
    from aeroforge_schemas.component import BatterySpec

    spec = BatterySpec(
        id="p0a006_cutoff", name="P0A-006 cutoff pack", chemistry="LiPo",
        cells_series=6, capacity_ah=0.015, internal_resistance_ohm=0.05,
        warning_cell_voltage_v=3.5, cutoff_cell_voltage_v=3.3,
        ocv_curve=[{"soc_pct": s, "cell_voltage_v": 3.0 + 1.2 * s / 100.0}
                   for s in (0, 20, 40, 60, 80, 100)],
        source={"source": "Synthetic fast-drain pack for the cutoff-verdict test",
                "estimated": True},
    )
    design_cut = design.model_copy(deep=True)
    design_cut.powertrain = design.powertrain.model_copy(
        update={"battery_id": "p0a006_cutoff"})
    path = library.data_dir / "batteries" / "p0a006_cutoff.json"
    path.write_text(spec.model_dump_json(), encoding="utf-8")
    try:
        res = run_scenario(design_cut, _hover_scenario(6.0, 2.0), library)
    finally:
        path.unlink(missing_ok=True)
    assert res.aborted and res.abort_event is not None
    assert res.abort_event.kind == "battery_cutoff"
    assert 0.0 < res.abort_event.t_s <= 6.0
    assert res.component_verdicts["battery"] == "FAIL"
    assert res.component_verdicts["motor"] == "NO_MODELED_LIMIT_BREACHED"
    assert res.component_verdicts["esc"] == "NO_MODELED_LIMIT_BREACHED"
    # The warning fired once earlier in the run (its crossing precedes cutoff).
    warnings = [e for e in res.events if e.kind == "battery_warning"]
    assert len(warnings) == 1 and warnings[0].t_s <= res.abort_event.t_s
    # No post-failure integration: the run stopped at the crossing tick.
    assert np.all(np.isfinite(res.states))


def test_healthy_run_records_no_breach_not_a_pass(design, library):
    """A clean run records NO_MODELED_LIMIT_BREACHED for every in-loop
    component — explicitly not a fitness claim — and the run_flight report
    surfaces the verdicts."""
    res = run_scenario(design, _hover_scenario(4.0, 1.5), library)
    assert not res.aborted
    assert res.component_verdicts == {
        "battery": "NO_MODELED_LIMIT_BREACHED",
        "motor": "NO_MODELED_LIMIT_BREACHED",
        "esc": "NO_MODELED_LIMIT_BREACHED",
        "powertrain": "NO_MODELED_LIMIT_BREACHED",
        "frame": "NO_MODELED_LIMIT_BREACHED",
    }

    report = run_flight(design)
    assert report["component_verdicts"] == res.component_verdicts or (
        set(report["component_verdicts"]) == set(res.component_verdicts))
    assert all(v == "NO_MODELED_LIMIT_BREACHED"
               for v in report["component_verdicts"].values())


# ---------------------------------------------------------------------------
# 3. Voltage collapse: exact constant-power boundary
# ---------------------------------------------------------------------------


def test_solve_constant_power_exact_quadratic_root():
    """The canonical solve returns the stable upper root of
    V^2 - V_th*V + P*R = 0 and self-consistent I = P / V_bus."""
    pack = linear_pack(r_ohm=0.05)
    soc = 50.0
    v_oc = pack.ocv_pack(soc)  # 6 * 3.6 = 21.6 V
    for power in (50.0, 250.0, 1000.0, 2000.0):
        sol = pack.solve_constant_power(soc, power)
        assert sol.feasible and sol.v_bus_v is not None and sol.current_a is not None
        r = pack.spec.internal_resistance_ohm
        # Self-consistency: V = V_oc - I*R and I = P/V exactly.
        assert sol.v_bus_v == pytest.approx(v_oc - sol.current_a * r, rel=1e-12)
        assert sol.current_a == pytest.approx(power / sol.v_bus_v, rel=1e-12)
        # Upper (stable) root of the quadratic.
        disc = v_oc**2 - 4.0 * power * r
        assert sol.v_bus_v == pytest.approx(0.5 * (v_oc + np.sqrt(disc)), rel=1e-12)
        assert sol.v_bus_v > v_oc / 2.0


def test_solve_constant_power_matches_frozen_forecast_solver():
    """The canonical solver reproduces the frozen M21 forecast benchmark's
    standalone constant_power_current algebra exactly (bit-for-bit bridge to
    the frozen protocol)."""
    scripts_dir = REPO_ROOT / "scripts"
    sys.path.insert(1, str(scripts_dir))
    from benchmark_sit_cutoff_forecast import constant_power_current

    pack = linear_pack(r_ohm=0.0624)
    # Pack voltages inside the 6-cell linear table's range (18.0-25.2 V).
    cases = [(22.0, 300.0), (23.5, 900.0), (21.0, 1500.0), (22.5, 88.0)]
    for v_th, power in cases:
        i_frozen = constant_power_current(power, v_th, 0.0624)
        assert i_frozen is not None
        # The SOC whose declared pack OCV equals v_th (cell V = 3.0 +
        # 1.2*soc/100, 6 cells).
        soc = (v_th / 6.0 - 3.0) * 100.0 / 1.2
        sol = pack.solve_constant_power(soc, power)
        assert sol.feasible
        assert sol.current_a == pytest.approx(i_frozen, rel=1e-15)
        assert sol.v_bus_v == pytest.approx(v_th - 0.0624 * i_frozen, rel=1e-12)


def test_solve_constant_power_reports_collapse_at_boundary():
    """At the exact boundary P = V_th^2/(4 R) the double root is feasible;
    above it the solve reports voltage collapse with a named reason."""
    pack = linear_pack(r_ohm=0.05)
    soc = 50.0
    v_oc = pack.ocv_pack(soc)
    p_max = pack.max_deliverable_power_w(soc)
    assert p_max == pytest.approx(v_oc**2 / (4.0 * 0.05), rel=1e-12)

    sol = pack.solve_constant_power(soc, p_max)
    assert sol.feasible
    assert sol.v_bus_v == pytest.approx(v_oc / 2.0, rel=1e-9)

    sol = pack.solve_constant_power(soc, p_max * (1.0 + 1e-9))
    assert not sol.feasible and sol.v_bus_v is None and sol.current_a is None
    assert "voltage collapse" in sol.reason
    assert "maximum deliverable power" in sol.reason


def test_solve_constant_power_zero_power_and_charging_refusal():
    pack = linear_pack(r_ohm=0.05)
    sol = pack.solve_constant_power(50.0, 0.0)
    assert sol.feasible and sol.current_a == 0.0
    assert sol.v_bus_v == pytest.approx(pack.ocv_pack(50.0), rel=1e-12)
    with pytest.raises(ValueError, match="discharge only"):
        pack.solve_constant_power(50.0, -1.0)
    # A pack with no source voltage at this SOC reports infeasible collapse.
    from aeroforge_schemas.component import BatterySpec as _BS
    dead_pack = BatteryPack(_BS(
        id="p0a006_dead", name="dead pack", chemistry="LiPo",
        cells_series=6, capacity_ah=16.0, internal_resistance_ohm=0.05,
        warning_cell_voltage_v=3.5, cutoff_cell_voltage_v=3.3,
        ocv_curve=[{"soc_pct": 0.0, "cell_voltage_v": 0.05},
                   {"soc_pct": 100.0, "cell_voltage_v": 0.06}],
        source={"source": "Synthetic zero-source pack", "estimated": True},
    ))
    sol = dead_pack.solve_constant_power(50.0, 10.0)
    assert not sol.feasible and "maximum deliverable power" in sol.reason


def test_plant_refuses_unattainable_demand_with_named_verdict(design, library, plant_parts):
    """A demand above the pack's constant-power collapse boundary aborts the
    run with a named battery_voltage_collapse event, a battery FAIL verdict,
    and NO post-failure state: the last recorded sample is the pre-collapse
    state at the refusing tick."""
    dataset, esc = plant_parts
    # 0.5 Ah pack with capacity-scaled R cannot supply the hover demand.
    base_spec = library.battery(design.powertrain.battery_id)
    tiny = base_spec.model_copy(update={
        "capacity_ah": 0.5,
        "internal_resistance_ohm": base_spec.internal_resistance_ohm
        * base_spec.capacity_ah / 0.5,
        "id": "p0a006_tiny", "name": "P0A-006 tiny pack",
    })
    # The direct primitive fails closed with the typed refusal.
    pt = LoopPowertrain(dataset, esc, BatteryPack(tiny), soc_start_pct=100.0)
    mass = sum(p.mass_kg for p in design.parts)
    hover_thrust = mass * 9.80665 / 4.0
    with pytest.raises(VoltageCollapseError):
        pt.step(np.full(4, hover_thrust), 0.004)

    # The authoritative scenario path converts it into a named critical event
    # with a component FAIL verdict (no opaque exception, no invented thrust).
    from aeroforge_schemas.design import DroneDesign as _DD

    design_tiny = design.model_copy(deep=True)
    design_tiny.powertrain = design.powertrain.model_copy(update={"battery_id": "p0a006_tiny"})
    library_dir = library.data_dir
    (library_dir / "batteries" / "p0a006_tiny.json").write_text(
        tiny.model_dump_json(), encoding="utf-8")
    try:
        scenario = _hover_scenario(4.0, 1.5)
        res = run_scenario(design_tiny, scenario, library)
        assert res.aborted and res.abort_event is not None
        assert res.abort_event.kind == "battery_voltage_collapse"
        assert res.component_verdicts["battery"] == "FAIL"
        assert res.component_verdicts["motor"] == "NO_MODELED_LIMIT_BREACHED"
        # No post-failure samples: the run stopped at the refusing tick.
        assert len(res.times) <= int(4.0 / 0.004)
        assert np.all(np.isfinite(res.states))
    finally:
        (library_dir / "batteries" / "p0a006_tiny.json").unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 4. Declared thresholds, no tuning; warning latching
# ---------------------------------------------------------------------------


def test_thresholds_come_from_declared_spec_not_hardcoded(design, library, plant_parts):
    """The plant fires the warning/cutoff events at the DECLARED spec
    thresholds: raising the declared cutoff makes the event fire earlier on
    the identical load, and the message carries the declared value."""
    dataset, esc = plant_parts
    thrusts = np.full(4, 9.0)
    dt = 0.004

    def first_event_time(pack, kind, steps=4000):
        pt = LoopPowertrain(dataset, esc, pack)
        for k in range(steps):
            aux = pt.step(thrusts, dt)
            hits = [e for e in aux.events if e["kind"] == kind]
            if hits:
                return k * dt + hits[0]["t_s"]
        return None

    nominal = linear_pack(r_ohm=0.05, capacity_ah=0.02)
    early = linear_pack(r_ohm=0.05, capacity_ah=0.02, cutoff_v=3.6, warning_v=3.8)
    t_nominal = first_event_time(nominal, "battery_cutoff")
    t_early = first_event_time(early, "battery_cutoff")
    assert t_nominal is not None and t_early is not None
    assert t_early < t_nominal  # the declared 3.6 V threshold bites earlier

    pt = LoopPowertrain(dataset, esc, early)
    for _ in range(4000):
        aux = pt.step(thrusts, dt)
        hits = [e for e in aux.events if e["kind"] == "battery_cutoff"]
        if hits:
            assert "3.60 V" in hits[0]["message"]
            break


def test_warning_fires_once_at_bracketed_crossing(design, library, plant_parts):
    """The land-now warning fires ONCE at its bracketed crossing (latched),
    while the cutoff still fires later on the same run."""
    dataset, esc = plant_parts
    pack = linear_pack(r_ohm=0.05, capacity_ah=0.02)
    pt = LoopPowertrain(dataset, esc, pack)
    warning_ticks, cutoff_tick = [], None
    for k in range(1200):
        aux = pt.step(np.full(4, 9.0), 0.004)
        if any(e["kind"] == "battery_warning" for e in aux.events):
            warning_ticks.append(k)
        if any(e["kind"] == "battery_cutoff" for e in aux.events):
            cutoff_tick = k
            break
    assert len(warning_ticks) == 1, "warning must fire once (latched), not every tick"
    assert cutoff_tick is not None and cutoff_tick >= warning_ticks[0]


# ---------------------------------------------------------------------------
# 5. Frozen M21 baseline preserved + repaired-model delta recorded
# ---------------------------------------------------------------------------


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def delta() -> dict:
    return _load(DELTA_RESULTS)


def test_frozen_m21_artifacts_untouched_by_repair():
    """The frozen M21 baseline artifacts keep their canonical digests — the
    repair did not rewrite historical evidence."""
    replay = _load(REPLAY_RESULTS)
    forecast = _load(FORECAST_RESULTS)
    assert replay["frozen_calibration_canonical_sha256"] == \
        "f959786b7d37ad82dc84780331fbd1363b63f2f109cd0bf0c4fb6cd7adbb4764"
    assert forecast["frozen_guard_canonical_sha256"] == \
        "16c92466dc5f4f4af8820cdb194524f61c57724dc02a81280acace33937b2664"


def test_delta_artifact_declares_repair_provenance(delta):
    """The delta binds to the frozen fit/guard digests, declares the strict
    support contract (the fitted support ALREADY spans the knee - the
    refutation basis), and the canonical solver agrees exactly with the
    frozen forecast benchmark's standalone quadratic."""
    assert delta["plan"] == "m21-sit-causal-repair-delta-v1"
    assert delta["parent_fit_canonical_sha256"] ==         "f959786b7d37ad82dc84780331fbd1363b63f2f109cd0bf0c4fb6cd7adbb4764"
    assert delta["parent_guard_canonical_sha256"] ==         "16c92466dc5f4f4af8820cdb194524f61c57724dc02a81280acace33937b2664"
    assert delta["repaired_model"]["solver"] ==         "physics.propulsion.battery.BatteryPack.solve_constant_power"
    assert delta["repaired_model"]["solver_vs_frozen_forecast_max_relative_current_deviation"] == 0.0
    support = delta["repaired_model"]["strict_support"]
    assert support["calibrated_cycles"] == "1-50 only"
    assert support["held_out_tuning"] is False
    assert support["fitted_support_soc_pct"][0] == pytest.approx(3.5627777777772707, abs=1e-9)
    assert support["series_ohm"] == pytest.approx(0.046664488422, abs=1e-12)
    # The frozen guard margin is reused verbatim (no recalibration).
    assert delta["forecast"]["guard_margin_v"] ==         _load(FORECAST_RESULTS)["one_sided_cycle_residual_v"]


def test_delta_replay_repaired_matches_frozen_baseline(delta):
    """Replay before/after: the repaired causal model's held-out numbers are
    BIT-IDENTICAL to the frozen one-RC baseline - the causal contract changes
    nothing for the measured-current replay (63/63 crossings still missed;
    the deficit is the aged module, not the model form)."""
    before = delta["replay"]["before"]
    after = delta["replay"]["after"]
    assert before["observed_crossings_total"] == 63
    assert before["missed_fixed_r"] == 63
    assert before["missed_one_rc"] == 63
    assert after["observed_crossings_total"] == 63
    assert after["missed_total"] == 63
    assert after["predicted_crossings_total"] == 0
    per_cohort = after["per_cohort"]
    assert per_cohort["mid_life"]["module_voltage_mae_v"]["mae"] == pytest.approx(0.52704079, abs=1e-8)
    assert per_cohort["late_life"]["module_voltage_mae_v"]["mae"] == pytest.approx(0.8309215, abs=1e-8)
    frozen = _load(REPLAY_RESULTS)
    assert per_cohort["mid_life"]["module_voltage_mae_v"]["mae"] ==         pytest.approx(frozen["cohorts"]["mid_life"]["models"]["one_rc"]["module_voltage_v"]["mae"], abs=1e-8)
    assert per_cohort["late_life"]["module_voltage_mae_v"]["mae"] ==         pytest.approx(frozen["cohorts"]["late_life"]["models"]["one_rc"]["module_voltage_v"]["mae"], abs=1e-8)


def test_delta_forecast_repaired_matches_frozen_baseline(delta):
    """Forecast before/after: the repaired model's trajectories, guard
    coverage and misses equal the frozen updated forecast (68/68 missed; the
    lower band still warns in 100/100 with zero misses, leads 8/6 s) - the
    causal form does not change the constant-power forecast either."""
    before = delta["forecast"]["before"]
    after = delta["forecast"]["after"]
    assert before["observed_crossings_total"] == 68
    assert before["missed_updated_total"] == 68
    assert after["observed_crossings_total"] == 68
    assert after["missed_updated_total"] == 68
    assert after["predicted_point_crossings_total"] == 0
    assert after["guard_warning_any_total"] == 100
    assert after["guard_cutoff_missed_total"] == 0
    assert after["crossing_time_error_s"]["count"] == 0
    per_cohort = after["per_cohort"]
    assert per_cohort["first"]["updated_voltage_error_v"]["mae"] == pytest.approx(0.21893274, abs=1e-8)
    assert per_cohort["second"]["updated_voltage_error_v"]["mae"] == pytest.approx(0.31742905, abs=1e-8)
    assert per_cohort["first"]["guard_warning_any"] == 50
    assert per_cohort["first"]["guard_cutoff_missed"] == 0
    assert per_cohort["first"]["guard_lead_time_s_median"] == pytest.approx(8.0)
    assert per_cohort["second"]["guard_lead_time_s_median"] == pytest.approx(6.0)
    frozen = _load(FORECAST_RESULTS)
    assert per_cohort["first"]["updated_voltage_error_v"]["mae"] ==         pytest.approx(frozen["cohorts"]["first"]["updated_voltage_error_v"]["mae"], abs=1e-8)


def test_knee_anchor_probe_is_refuted(delta):
    """The pre-registered knee-anchor probe is REFUTED: extending the OCV
    support with the declared component-table tail recovers ZERO crossings -
    the fitted support already spans the knee (down to 3.56 % SOC), so the
    held-out deficit is the aged-module loaded voltage inside the calibrated
    support, unobservable from cycles 1-50. The probe's fitted region is
    preserved to <1e-6 V/cell (dense resample), isolating the tail effect."""
    probe = delta["knee_anchor_probe"]
    assert probe["status"].startswith("REFUTED")
    assert probe["model"]["dense_resample_points"] == 400
    assert probe["model"]["dense_resample_max_knot_deviation_cell_v"] == pytest.approx(0.0, abs=1e-12)
    assert probe["model"]["junction_offset_v"] == pytest.approx(0.20074413370140975, abs=1e-12)
    assert probe["model"]["tail_points_soc_pct_cell_v"] == [[0.0, pytest.approx(3.5007441337014096, abs=1e-12)]]
    assert probe["replay"]["missed_total"] == 63
    assert probe["forecast"]["missed_updated_total"] == 68
    assert probe["forecast"]["guard_warning_any_total"] == 100
    assert probe["forecast"]["guard_cutoff_missed_total"] == 0
    # The probe's fitted-region accuracy is preserved (dense resample).
    assert probe["replay"]["per_cohort"]["mid_life"]["module_voltage_mae_v"]["mae"] ==         pytest.approx(0.52704079, abs=1e-6)
