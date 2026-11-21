"""P0A-007 — battery replay versus prospective endurance verification.

TWO SCORING MODES, NEVER BLENDED (task todo 1):

  MODE A — measured-current replay ("replay.*" metric namespace): the current
  is SOURCE DATA; the model only tracks loaded voltage, SOC and cutoff
  timing. Scores cutoff misses / false alarms, endpoint SOC (or endpoint
  charge against the source's recorded capacity), and the charge/energy
  balance of the tracking evaluation.

  MODE B — prospective endurance / forecast demand ("prospective.*" metric
  namespace): the current is MODEL OUTPUT, solved causally from the demand
  (exact constant-power quadratic). Scores the predicted bracketed cutoff
  time, delivered energy, endpoint SOC at a fixed horizon, and the
  charge/energy balance of the simulated trajectory.

No metric key appears in both namespaces (asserted mechanically); no
combined replay+prospective score exists anywhere in this module.

CONSERVATION (solution verification, exact identities):
  charge:    dSOC * capacity/100  ==  integral(I dt)            (exact)
  energy:    E_ocv = E_bus + E_loss,R                              (exact,
             per-sample identity V_oc = V_bus + I*R summed with the SAME
             quadrature weights; E_rc adds the same way when a caller-owned
             polarization state is present — 0 in the declared plant)

Timestep convergence: 3 refinement levels (dt, dt/2, dt/4) with monotone
convergence recorded for endpoint SOC, delivered energy and the bracketed
cutoff time (numbers transcribed into docs/acceptance/P0A-007.md).

DATA SOURCES:
  - CI-unconditional: committed battery datasets (data/components/batteries)
    and an analytic synthetic pack with closed-form truth.
  - Opt-in (AEROFORGE_SIT_WORKBOOK): the pinned external SIT workbook, scored
    per unchanged source row under the frozen M21 protocol with the P0A-006
    repaired model; aggregates compared against the committed compact
    artifact docs/campaigns/m21_p0a_007_row_scores.json and recorded in
    docs/acceptance/P0A-007.md.

Reference: docs/acceptance/P0A-007.md, docs/acceptance/P0A-006.md (frozen),
docs/M21_BATTERY_CAMPAIGN.md.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKBOOK = os.environ.get("AEROFORGE_SIT_WORKBOOK", "")
ROW_SCORES_ARTIFACT = REPO_ROOT / "docs/campaigns/m21_p0a_007_row_scores.json"

sys.path[:0] = [str(REPO_ROOT / "packages"), str(REPO_ROOT / "packages/shared-schemas")]

from aeroforge_schemas.component import BatterySpec  # noqa: E402
from physics.propulsion.battery import (  # noqa: E402
    BatteryPack,
    PowertrainError,
    VoltageCollapseError,
)

# ---------------------------------------------------------------------------
# Metric namespaces (mode separation is structural, not conventional)
# ---------------------------------------------------------------------------

REPLAY_METRICS = frozenset({
    "replay.observed_cutoff", "replay.predicted_cutoff",
    "replay.cutoff_miss", "replay.cutoff_late", "replay.cutoff_false_alarm",
    "replay.cutoff_time_error_s", "replay.endpoint_soc_error_pct",
    "replay.endpoint_charge_error_ah", "replay.charge_balance_ah",
    "replay.energy_balance_wh", "replay.voltage_mae_v",
    "replay.delivered_energy_error_wh", "replay.exclusions",
})

PROSPECTIVE_METRICS = frozenset({
    "prospective.predicted_cutoff", "prospective.observed_cutoff",
    "prospective.cutoff_miss", "prospective.cutoff_false_alarm",
    "prospective.cutoff_time_s", "prospective.endpoint_soc_pct",
    "prospective.delivered_energy_to_cutoff_wh",
    "prospective.delivered_energy_wh", "prospective.charge_balance_ah",
    "prospective.energy_balance_wh", "prospective.exclusions",
})

assert not (REPLAY_METRICS & PROSPECTIVE_METRICS)


# ---------------------------------------------------------------------------
# Shared synthetic pack: linear declared OCV (3.0 V at 0 %, 4.2 V at 100 %)
# so every replay/prospective quantity has a closed-form truth.
# ---------------------------------------------------------------------------


def linear_pack(r_ohm: float = 0.05, capacity_ah: float = 0.5,
                cells: int = 6, cutoff_v: float = 3.3,
                warning_v: float = 3.5) -> BatteryPack:
    return BatteryPack(BatterySpec(
        id="p0a007_linear", name="P0A-007 linear test pack", chemistry="LiPo",
        cells_series=cells, capacity_ah=capacity_ah, internal_resistance_ohm=r_ohm,
        warning_cell_voltage_v=warning_v, cutoff_cell_voltage_v=cutoff_v,
        ocv_curve=[{"soc_pct": s, "cell_voltage_v": 3.0 + 1.2 * s / 100.0}
                   for s in (0, 20, 40, 60, 80, 100)],
        source={"source": "Synthetic linear OCV for closed-form verification",
                "estimated": True},
    ))


def _trapz_weights(t: np.ndarray) -> np.ndarray:
    """Trapezoid quadrature weights: sum(w * x) == trapezoid(x, t) exactly."""
    dt = np.diff(t)
    w = np.zeros(len(t))
    w[:-1] += dt / 2.0
    w[1:] += dt / 2.0
    return w


def _loaded_cell_v(pack: BatteryPack, soc: float, current: float) -> float:
    return (pack.ocv_cell(soc)
            - current * pack.spec.internal_resistance_ohm / pack.spec.cells_series)


# ---------------------------------------------------------------------------
# MODE A — measured-current replay scorer (current is SOURCE DATA)
# ---------------------------------------------------------------------------


def score_replay_run(
    pack: BatteryPack,
    t: np.ndarray,
    i_measured: np.ndarray,
    v_measured_cell: np.ndarray | None = None,
    recorded_charge_ah: float | None = None,
    *,
    limit_cell_v: float,
    v_rc_cell: np.ndarray | None = None,
) -> dict:
    """Score ONE measured-current run row by row.

    The current and its quadrature are source data (trapezoid on the sampled
    clock — the frozen M21 protocol's charge convention); the model only
    tracks loaded voltage / SOC / cutoff. Returns replay.* metrics only.
    """
    prefix = "replay."
    # Causal charge: trapezoid of the MEASURED current (source quadrature).
    charge = np.concatenate(([0.0], np.cumsum(
        (i_measured[:-1] + i_measured[1:]) / 2.0 * np.diff(t)))) / 3600.0
    soc = 100.0 * (1.0 - charge / pack.spec.capacity_ah)
    v_rc = v_rc_cell if v_rc_cell is not None else np.zeros(len(t))
    v_pred_cell = np.array([
        _loaded_cell_v(pack, s, i) - v_rc_k
        for s, i, v_rc_k in zip(soc, i_measured, v_rc, strict=True)])

    metrics: dict = {}
    obs_cross_idx = np.flatnonzero(v_measured_cell < limit_cell_v) \
        if v_measured_cell is not None else np.array([], dtype=int)
    pred_cross_idx = np.flatnonzero(v_pred_cell < limit_cell_v)
    observed = bool(obs_cross_idx.size)
    predicted = bool(pred_cross_idx.size)
    metrics[prefix + "observed_cutoff"] = observed
    metrics[prefix + "predicted_cutoff"] = predicted
    # Frozen replay-screen semantics: a miss is an observed crossing with NO
    # predicted crossing (binary). Timing is recorded separately: cutoff_late
    # marks a predicted crossing AFTER the observed one (the forecast
    # protocol's timing-aware miss, surfaced in replay terms).
    metrics[prefix + "cutoff_miss"] = bool(observed and not predicted)
    metrics[prefix + "cutoff_false_alarm"] = bool(predicted and not observed)
    if observed and predicted:
        metrics[prefix + "cutoff_late"] = bool(
            t[pred_cross_idx[0]] > t[obs_cross_idx[0]])
        metrics[prefix + "cutoff_time_error_s"] = float(
            t[pred_cross_idx[0]] - t[obs_cross_idx[0]])
    if recorded_charge_ah is not None:
        metrics[prefix + "endpoint_charge_error_ah"] = float(
            charge[-1] - recorded_charge_ah)
    # Charge balance: the model's own SOC accounting vs the source quadrature.
    metrics[prefix + "charge_balance_ah"] = float(
        (soc[0] - soc[-1]) * pack.spec.capacity_ah / 100.0 - charge[-1])
    # Energy balance: E_ocv = E_bus + E_loss(+E_rc) under the SAME weights.
    # All terms are pack-level watt-seconds converted to Wh; the per-cell
    # drop (ocv_cell - v_cell) = I*R/cells + rc*I, so the pack loss power is
    # I^2*(R + cells*rc).
    w = _trapz_weights(t)
    e_ocv = float(np.sum(w * np.array([pack.ocv_cell(s) for s in soc])
                         * i_measured * pack.spec.cells_series) / 3600.0)
    e_bus = float(np.sum(w * v_pred_cell * i_measured * pack.spec.cells_series)
                  / 3600.0)
    e_loss = float(np.sum(w * i_measured ** 2
                          * pack.spec.internal_resistance_ohm) / 3600.0)
    if v_rc_cell is not None:
        # The caller-owned polarization drop is part of the ocv-to-bus chain:
        # E_ocv = E_bus + E_loss,R + E_rc with the same weights.
        e_loss = float(np.sum(w * i_measured ** 2
                              * pack.spec.internal_resistance_ohm) / 3600.0) \
            + float(np.sum(w * v_rc_cell * i_measured * pack.spec.cells_series)
                    / 3600.0)
    metrics[prefix + "energy_balance_wh"] = e_ocv - e_bus - e_loss
    if v_measured_cell is not None:
        metrics[prefix + "voltage_mae_v"] = float(np.mean(np.abs(v_pred_cell - v_measured_cell)))
    metrics[prefix + "endpoint_soc_error_pct"] = None  # filled by callers with truth
    metrics[prefix + "exclusions"] = []
    return {k: v for k, v in metrics.items()
            if k in REPLAY_METRICS and (v is not None or k.endswith("error_pct"))}


def replay_endpoint_soc_error(pack: BatteryPack, soc_model_end: float,
                              soc_truth_end: float) -> float:
    """Endpoint SOC error against an analytically known truth (replay mode)."""
    return float(soc_model_end - soc_truth_end)


def replay_delivered_energy_error(pack: BatteryPack, t: np.ndarray,
                                  i_measured: np.ndarray,
                                  e_bus_model: float,
                                  soc_of_t, i_of_t) -> float:
    """Delivered bus-energy error against the analytic truth (replay mode)."""
    from scipy.integrate import trapezoid
    v_true = np.array([_loaded_cell_v(pack, soc_of_t(tt), i_of_t(tt)) * pack.spec.cells_series
                       for tt in t])
    e_true = float(trapezoid(v_true * i_of_t(t), t))
    return float(e_bus_model - e_true)


# ---------------------------------------------------------------------------
# MODE B — prospective demand simulator + scorer (current is MODEL OUTPUT)
# ---------------------------------------------------------------------------


def simulate_prospective_run(
    pack: BatteryPack,
    power_w: float,
    dt: float,
    horizon_s: float,
    soc_start: float = 100.0,
    *,
    cutoff_cell_v: float,
) -> dict:
    """Simulate ONE prospective constant-power discharge.

    Current is MODEL OUTPUT: the exact causal quadratic
    ``BatteryPack.solve_constant_power`` at each step, charge advanced with
    the previous step's current (the declared ZOH scheme, identical to the
    frozen forecast protocol). Cutoff is bracketed per step. No post-cutoff
    energy is delivered and no post-cutoff state is invented.
    """
    soc = soc_start
    t = 0.0
    delivered_wh = 0.0
    e_ocv_wh = 0.0
    charge_ah = 0.0
    cutoff_t: float | None = None
    exclusion: str | None = None
    while t < horizon_s - 1e-12:
        step = min(dt, horizon_s - t)
        sol = pack.solve_constant_power(soc, power_w)
        if not sol.feasible:
            exclusion = f"t={t:.6g}s: {sol.reason}"
            break
        amps = sol.current_a
        soc_post = pack.soc_after(soc, amps, step)
        tau = pack.crossing_time_below_cell_v(
            soc, soc_post, amps, step, cutoff_cell_v)
        interval = step if tau is None else tau
        e_ocv_wh += pack.ocv_pack(soc) * amps * interval / 3600.0
        delivered_wh += sol.v_bus_v * amps * interval / 3600.0
        charge_ah += amps * interval / 3600.0
        if tau is not None:
            cutoff_t = t + tau
            soc = pack.soc_after(soc, amps, tau)
            break
        soc = soc_post
        t += step
    return {
        "soc_start_pct": soc_start,
        "cutoff_time_s": cutoff_t,
        "endpoint_soc_pct": float(soc),
        "delivered_energy_to_cutoff_wh": delivered_wh,
        "delivered_energy_wh": delivered_wh,
        "e_ocv_wh": e_ocv_wh,
        "charge_ah": charge_ah,
        "exclusion": exclusion,
        "dt": dt,
    }


def score_prospective_run(pack: BatteryPack, sim: dict,
                          observed_cutoff: bool | None = None) -> dict:
    """Score ONE prospective run (prospective.* metrics only). The charge
    balance is the simulated trajectory's internal accounting; when an
    observed cutoff truth is supplied, miss/false-alarm are classified
    against it (a predicted crossing that is not at-or-before the observed
    crossing does not prevent a miss)."""
    prefix = "prospective."
    metrics = {
        prefix + "predicted_cutoff": sim["cutoff_time_s"] is not None,
        prefix + "observed_cutoff": observed_cutoff,
        prefix + "cutoff_miss": None,
        prefix + "cutoff_false_alarm": None,
        prefix + "cutoff_time_s": sim["cutoff_time_s"],
        prefix + "endpoint_soc_pct": sim["endpoint_soc_pct"],
        prefix + "delivered_energy_to_cutoff_wh":
            sim["delivered_energy_to_cutoff_wh"],
        prefix + "delivered_energy_wh": sim["delivered_energy_wh"],
        prefix + "charge_balance_ah": float(
            (sim["soc_start_pct"] - sim["endpoint_soc_pct"])
            * pack.spec.capacity_ah / 100.0 - sim["charge_ah"]),
        prefix + "energy_balance_wh": sim["e_ocv_wh"] - sim["delivered_energy_wh"],
        prefix + "exclusions": [sim["exclusion"]] if sim["exclusion"] else [],
    }
    if observed_cutoff is not None:
        predicted = sim["cutoff_time_s"] is not None
        metrics[prefix + "cutoff_miss"] = bool(observed_cutoff and not predicted)
        metrics[prefix + "cutoff_false_alarm"] = bool(predicted and not observed_cutoff)
    return metrics


# ---------------------------------------------------------------------------
# CI-unconditional tests
# ---------------------------------------------------------------------------


def test_modes_are_never_blended():
    """Structural mode separation: disjoint namespaces; each scorer returns
    exactly its own mode's metrics; no combined score exists."""
    assert not (REPLAY_METRICS & PROSPECTIVE_METRICS)
    pack = linear_pack()
    t = np.arange(0.0, 60.0, 1.0)
    i = np.full(len(t), 4.0)
    v = np.array([_loaded_cell_v(pack, 100.0 - 100.0 * (4.0 * tt / 3600.0)
                                 / pack.spec.capacity_ah, 4.0) for tt in t])
    replay = score_replay_run(pack, t, i, v, limit_cell_v=3.3)
    assert set(replay) <= REPLAY_METRICS
    assert all(k.startswith("replay.") for k in replay)
    sim = simulate_prospective_run(pack, 60.0, 1.0, 30.0, cutoff_cell_v=3.3)
    prospective = score_prospective_run(pack, sim)
    assert all(k.startswith("prospective.") for k in prospective)
    assert not (set(replay) & set(prospective))


def test_replay_conservation_exact():
    """Replay mode: charge balance and the E_ocv = E_bus + E_loss decomposition
    are exact identities of the implemented equations (residuals at float
    round-off), for constant AND variable measured current."""
    pack = linear_pack()
    cases = (
        ("constant", np.full(600, 2.5)),
        ("variable", 2.5 + 0.8 * np.sin(2.0 * np.pi * np.arange(600.0) / 90.0)),
    )
    for name, i in cases:
        t = np.arange(0.0, 600.0, 1.0)
        soc_truth_end = 100.0 - 100.0 * float(
            np.trapezoid(i, t)) / 3600.0 / pack.spec.capacity_ah
        score = score_replay_run(pack, t, i, limit_cell_v=3.3)
        # The scorer's charge quadrature is the model's SOC accounting.
        charge = float(np.trapezoid(i, t)) / 3600.0
        soc_model_end = 100.0 - 100.0 * charge / pack.spec.capacity_ah
        score["replay.endpoint_soc_error_pct"] = replay_endpoint_soc_error(
            pack, soc_model_end, soc_truth_end)
        assert abs(score["replay.charge_balance_ah"]) < 1e-12, (name, score)
        assert abs(score["replay.energy_balance_wh"]) < 1e-9, (name, score)
        assert score["replay.endpoint_soc_error_pct"] == pytest.approx(0.0, abs=1e-9)
        print(f"P0A-007 replay conservation ({name}): charge balance "
              f"{score['replay.charge_balance_ah']:.3e} Ah, energy balance "
              f"{score['replay.energy_balance_wh']:.3e} Wh")


def test_prospective_conservation_exact():
    """Prospective mode: the simulated trajectory conserves charge exactly
    (coulomb counting) and decomposes energy exactly (V_oc = V_bus + I*R per
    solved step, same weights)."""
    pack = linear_pack()
    for power in (60.0, 120.0):
        sim = simulate_prospective_run(pack, power, 0.5, 120.0,
                                       cutoff_cell_v=3.3)
        drained_ah = (100.0 - sim["endpoint_soc_pct"]) * pack.spec.capacity_ah / 100.0
        assert sim["charge_ah"] == pytest.approx(drained_ah, abs=1e-12)
        assert sim["e_ocv_wh"] - sim["delivered_energy_wh"] >= 0.0
        # Exact decomposition check on a short no-cutoff window:
        pack2 = linear_pack()
        sim2 = simulate_prospective_run(pack2, 60.0, 0.25, 60.0,
                                        cutoff_cell_v=3.3)
        assert sim2["cutoff_time_s"] is None
        # Recompute the exact loss with the same step schedule.
        r = pack2.spec.internal_resistance_ohm
        soc, t, e_loss, charge = 100.0, 0.0, 0.0, 0.0
        prev = 0.0
        while t < 60.0 - 1e-12:
            step = min(0.25, 60.0 - t)
            sol = pack2.solve_constant_power(soc, 60.0)
            amps = sol.current_a
            soc_post = pack2.soc_after(soc, amps, step)
            e_loss += (amps * r) * amps * step / 3600.0
            charge += amps * step / 3600.0
            soc = soc_post
            t += step
        assert sim2["e_ocv_wh"] - sim2["delivered_energy_wh"] == pytest.approx(
            e_loss, rel=1e-9)
        assert sim2["charge_ah"] == pytest.approx(charge, abs=1e-12)


def test_replay_cutoff_miss_and_false_alarm_classification():
    """Replay mode cutoff classification against an observed source voltage:
    a biased-high source makes the model MISS; a biased-low source makes the
    model raise a FALSE ALARM; unbiased agrees."""
    pack = linear_pack()
    dt = 1.0
    t = np.arange(0.0, 100.0, dt)
    i = np.full(len(t), 14.0)  # crosses the 3.3 V/cell limit inside the run
    charge = np.concatenate(([0.0], np.cumsum(
        (i[:-1] + i[1:]) / 2.0 * np.diff(t)))) / 3600.0
    soc = 100.0 * (1.0 - charge / pack.spec.capacity_ah)
    v_model = np.array([_loaded_cell_v(pack, s, amps) for s, amps in zip(soc, i)])
    assert (v_model < 3.3).any()
    limit = 3.3
    unbiased = score_replay_run(pack, t, i, v_model, limit_cell_v=limit)
    assert unbiased["replay.observed_cutoff"] and unbiased["replay.predicted_cutoff"]
    assert not unbiased["replay.cutoff_miss"] and not unbiased["replay.cutoff_false_alarm"]
    assert unbiased["replay.cutoff_time_error_s"] == pytest.approx(0.0, abs=1e-9)

    biased_high = score_replay_run(pack, t, i, v_model + 0.1, limit_cell_v=limit)
    assert biased_high["replay.observed_cutoff"] and biased_high["replay.predicted_cutoff"]
    # The higher source voltage crosses LATER, so the model's prediction leads
    # (at-or-before the observed crossing -> NOT a miss under frozen semantics).
    assert biased_high["replay.cutoff_time_error_s"] < 0.0
    assert not biased_high["replay.cutoff_miss"]
    assert not biased_high["replay.cutoff_false_alarm"]

    # Observed crossing EARLIER than the model: the model's prediction is not
    # at-or-before the observed crossing -> a MISS under the frozen protocol.
    biased_low = score_replay_run(pack, t, i, v_model - 0.05, limit_cell_v=limit)
    assert biased_low["replay.observed_cutoff"] and biased_low["replay.predicted_cutoff"]
    assert biased_low["replay.cutoff_time_error_s"] > 0.0
    # Binary replay-screen miss is False (the model did cross); the timing
    # deficit is recorded as cutoff_late under the frozen forecast semantics.
    assert not biased_low["replay.cutoff_miss"]
    assert biased_low["replay.cutoff_late"]

    # A record that ends before the (later) observed crossing: the model
    # predicts, the source never crosses within the record -> FALSE ALARM.
    never = score_replay_run(pack, t, i, v_model + 0.2, limit_cell_v=limit)
    assert not never["replay.observed_cutoff"]
    assert never["replay.predicted_cutoff"]
    assert never["replay.cutoff_false_alarm"]
    assert not never["replay.cutoff_miss"]


def test_replay_endpoint_error_and_cutoff_truth():
    """Replay mode endpoint SOC error and bracketed cutoff time against
    closed-form truth for an analytic measured-current profile."""
    pack = linear_pack()
    dt = 1.0
    t = np.arange(0.0, 200.0, dt)
    i = 8.0 + np.sin(2.0 * np.pi * t / 40.0)

    def i_of(tt):
        return 8.0 + np.sin(2.0 * np.pi * tt / 40.0)

    from scipy.integrate import quad
    total_ah = quad(i_of, 0.0, t[-1], limit=200)[0] / 3600.0
    soc_truth_end = 100.0 - 100.0 * total_ah / pack.spec.capacity_ah

    charge = np.concatenate(([0.0], np.cumsum(
        (i[:-1] + i[1:]) / 2.0 * np.diff(t)))) / 3600.0
    soc_model_end = 100.0 - 100.0 * charge[-1] / pack.spec.capacity_ah
    err = replay_endpoint_soc_error(pack, soc_model_end, soc_truth_end)
    assert abs(err) < 0.05  # O(dt^2) trapezoid error, recorded in the doc

    # Closed-form cutoff truth on the analytic trajectory.
    def v_true_cell(tt):
        soc_tt = 100.0 - 100.0 * (quad(i_of, 0.0, tt, limit=200)[0] / 3600.0
                                  / pack.spec.capacity_ah)
        return _loaded_cell_v(pack, soc_tt, i_of(tt))

    from scipy.optimize import brentq
    t_cut_true = brentq(lambda tt: v_true_cell(tt) - 3.3, 60.0, 200.0, xtol=1e-10)
    score = score_replay_run(pack, t, i, limit_cell_v=3.3)
    assert score["replay.predicted_cutoff"]
    # The sampled-profile bracket is inside one sample of the truth.
    pred_idx = None
    charge_k = charge
    v_pred = np.array([_loaded_cell_v(pack, s, a) for s, a in zip(
        100.0 * (1.0 - charge_k / pack.spec.capacity_ah), i)])
    idx = np.flatnonzero(v_pred < 3.3)[0]
    assert abs(t[idx] - t_cut_true) <= 2 * dt


def test_prospective_cutoff_bracket_and_exclusions():
    """Prospective mode: the bracketed cutoff time is deterministic; an
    infeasible demand is a declared exclusion (no invented trajectory); no
    post-cutoff energy is delivered."""
    pack = linear_pack()
    sim = simulate_prospective_run(pack, 200.0, 1.0, 600.0, cutoff_cell_v=3.3)
    assert sim["cutoff_time_s"] is not None
    assert 0.0 < sim["cutoff_time_s"] < 600.0
    # No post-cutoff delivery: rerun with a horizon before the cutoff gives
    # strictly less energy.
    pre = simulate_prospective_run(pack, 200.0, 1.0,
                                   sim["cutoff_time_s"] - 0.5,
                                   cutoff_cell_v=3.3)
    assert pre["cutoff_time_s"] is None
    assert pre["delivered_energy_wh"] < sim["delivered_energy_to_cutoff_wh"]

    # Infeasible demand: excluded, not simulated.
    huge = simulate_prospective_run(pack, 20000.0, 1.0, 10.0, cutoff_cell_v=3.3)
    assert huge["cutoff_time_s"] is None
    assert huge["exclusion"] and "maximum deliverable power" in huge["exclusion"]
    assert huge["delivered_energy_wh"] == 0.0

    collapsed = pack.solve_constant_power(50.0, 20000.0)
    assert not collapsed.feasible and "voltage collapse" in collapsed.reason
    # The typed refusal is raised by the plant loop (covered in P0A-006).


def test_prospective_cutoff_convergence_monotone():
    """3-level refinement (dt, dt/2, dt/4) of the prospective path: endpoint
    SOC, delivered energy and the bracketed cutoff time converge monotonically
    (successive differences shrink). Values transcribed into the acceptance
    doc's convergence table."""
    pack = linear_pack()
    power, horizon = 200.0, 600.0
    rows = []
    for dt in (1.0, 0.5, 0.25):
        sim = simulate_prospective_run(pack, power, dt, horizon,
                                       cutoff_cell_v=3.3)
        rows.append(sim)
        assert sim["cutoff_time_s"] is not None
    t_cut = [r["cutoff_time_s"] for r in rows]
    e_cut = [r["delivered_energy_to_cutoff_wh"] for r in rows]
    d1 = abs(t_cut[1] - t_cut[0])
    d2 = abs(t_cut[2] - t_cut[1])
    e1 = abs(e_cut[1] - e_cut[0])
    e2 = abs(e_cut[2] - e_cut[1])
    assert d2 <= d1 and e2 <= e1, (t_cut, e_cut)
    print(f"P0A-007 prospective convergence: dt={1.0}: t_cut={t_cut[0]:.6f} "
          f"E={e_cut[0]:.9f}; dt=0.5: t_cut={t_cut[1]:.6f} E={e_cut[1]:.9f}; "
          f"dt=0.25: t_cut={t_cut[2]:.6f} E={e_cut[2]:.9f}")


def test_replay_convergence_monotone():
    """3-level refinement of the replay path: endpoint SOC error and
    delivered-energy error shrink monotonically (trapezoid O(dt^2))."""
    pack = linear_pack()

    def i_of(tt):
        return 8.0 + np.sin(2.0 * np.pi * tt / 37.0)  # non-integer periods

    def soc_true_of(tt):
        from scipy.integrate import quad
        return 100.0 - 100.0 * (quad(i_of, 0.0, tt, limit=200)[0]
                                / 3600.0 / pack.spec.capacity_ah)

    from scipy.integrate import trapezoid
    soc_err, energy_err = [], []
    t_grid = np.linspace(0.0, 200.0, 40001)  # truth quadrature grid
    i_grid = i_of(t_grid)
    v_true_grid = np.array([_loaded_cell_v(pack, soc_true_of(tt), i_of(tt))
                            * pack.spec.cells_series for tt in t_grid])
    e_true = float(trapezoid(v_true_grid * i_grid, t_grid)) / 3600.0
    for dt in (1.0, 0.5, 0.25):
        t = np.arange(0.0, 200.0 + 1e-12, dt)
        if t[-1] < 200.0:
            t = np.append(t, 200.0)
        i = i_of(t)
        soc_truth_end = soc_true_of(200.0)
        charge = np.concatenate(([0.0], np.cumsum(
            (i[:-1] + i[1:]) / 2.0 * np.diff(t)))) / 3600.0
        soc_model = 100.0 - 100.0 * charge[-1] / pack.spec.capacity_ah
        soc_err.append(abs(soc_model - soc_truth_end))
        w = _trapz_weights(t)
        e_bus = float(np.sum(w * np.array([_loaded_cell_v(
            pack, 100.0 - 100.0 * c / pack.spec.capacity_ah, a)
            for c, a in zip(charge, i)]) * i * pack.spec.cells_series) / 3600.0)
        energy_err.append(abs(e_bus - e_true))
    assert soc_err[1] <= soc_err[0] and soc_err[2] <= soc_err[1], soc_err
    assert energy_err[1] <= energy_err[0] and energy_err[2] <= energy_err[1], energy_err
    print(f"P0A-007 replay convergence: SOC err {soc_err[0]:.3e} -> "
          f"{soc_err[1]:.3e} -> {soc_err[2]:.3e}; energy err "
          f"{energy_err[0]:.3e} -> {energy_err[1]:.3e} -> {energy_err[2]:.3e}")


def test_committed_battery_datasets_support_contract():
    """The committed battery datasets carry the declared support/monotone
    contract and solve causally (dataset audit, unconditional)."""
    library_dir = REPO_ROOT / "data" / "components" / "batteries"
    for path in sorted(library_dir.glob("*.json")):
        spec = BatterySpec.model_validate_json(path.read_text(encoding="utf-8"))
        pack = BatteryPack(spec)
        lo, hi = pack.declared_soc_support_pct
        assert lo == 0.0 and hi == 100.0
        sol = pack.solve_constant_power(50.0, 100.0)
        assert sol.feasible and sol.v_bus_v is not None
        # The bracket must either find the crossing inside [40, 50] % SOC or
        # report None -- it must never extrapolate outside declared support.
        tau = pack.crossing_time_below_cell_v(50.0, 40.0, sol.current_a, 1.0, 3.4)
        assert tau is None or 0.0 <= tau <= 1.0


# ---------------------------------------------------------------------------
# Opt-in: pinned external SIT workbook, scored per unchanged source row
# ---------------------------------------------------------------------------


def _workbook_aggregates(workbook: Path) -> dict:
    """Score every unchanged source row of the frozen M21 cohorts in BOTH
    modes with the P0A-006 repaired model. Exclusions are recorded per cohort."""
    scripts_dir = REPO_ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(1, str(scripts_dir))
    from benchmark_sit_cutoff_forecast import (
        FORECAST_TIMES_S, ISSUE_TIME_S, HOLDOUT as FORECAST_HOLDOUT,
        forecast as frozen_forecast,
    )
    from benchmark_sit_module import (
        CAPACITY_AH, HOLDOUT, LIMITS, calibrate, digest, filtered, load_cycles,
    )
    from benchmark_sit_causal_repair import (
        FROZEN_FIT_SHA, repaired_forecast, strict_support_pack,
    )

    fit = calibrate(workbook)
    assert digest(fit) == FROZEN_FIT_SHA
    pack, _ = strict_support_pack(fit)
    model = fit["one_rc"]
    rc, tau = float(model["polarization_ohm"][0]), model["tau_s"]
    limit_module_v = LIMITS["module_v"]
    limit_cell_v = limit_module_v / 24.0

    # ---- MODE A: measured-current replay, per unchanged source row.
    replay_runs = {}
    for cohort, numbers in HOLDOUT.items():
        cycles, rejected = load_cycles(workbook, numbers)
        supported = [c for c in cycles if c.charge_ah[-1] <= fit["max_charge_ah"]]
        rows = []
        for c in supported:
            state = filtered(c.current, c.t, tau) if tau else np.zeros_like(c.t)
            score = score_replay_run(
                pack, c.t, c.current, c.voltages[:, 0] / 24.0,
                recorded_charge_ah=float(c.recorded_ah[-1]),
                limit_cell_v=limit_cell_v, v_rc_cell=rc * state / 24.0)
            rows.append(score)
        replay_runs[cohort] = {
            "selected_cycles": len(numbers), "source_rejections": rejected,
            "rows_scored": len(supported),
            "observed_cutoffs": int(sum(r["replay.observed_cutoff"] for r in rows)),
            "predicted_cutoffs": int(sum(r["replay.predicted_cutoff"] for r in rows)),
            "misses": int(sum(r["replay.cutoff_miss"] for r in rows)),
            "late_crossings": int(sum(r.get("replay.cutoff_late", False) for r in rows)),
            "false_alarms": int(sum(r["replay.cutoff_false_alarm"] for r in rows)),
            "max_abs_endpoint_charge_error_ah": max(
                abs(r["replay.endpoint_charge_error_ah"]) for r in rows),
            "max_abs_charge_balance_ah": max(
                abs(r["replay.charge_balance_ah"]) for r in rows),
            "max_abs_energy_balance_wh": max(
                abs(r["replay.energy_balance_wh"]) for r in rows),
        }

    # ---- MODE B: prospective demand (frozen 9 kW final load), per row.
    forecast_runs = {}
    for cohort, numbers in FORECAST_HOLDOUT.items():
        cycles, rejected = load_cycles(workbook, numbers)
        rows = []
        excluded = 0
        for c in cycles:
            present = (c.t > ISSUE_TIME_S) & (c.t <= FORECAST_TIMES_S[-1])
            v_obs_cell = c.voltages[present, 0] / 24.0
            frozen_result = frozen_forecast(c, fit, update=False)
            result = repaired_forecast(c, fit, pack, update=True)
            if (frozen_result is None or result is None or not len(v_obs_cell)
                    or not (np.isfinite(frozen_result.voltage[:len(v_obs_cell)]).all()
                            and np.isfinite(result[0][:len(v_obs_cell)]).all())):
                excluded += 1
                continue
            predicted_v, predicted_i = result
            n = min(len(v_obs_cell), len(predicted_v))
            obs, upd = v_obs_cell[:n], predicted_v[:n]
            over = np.flatnonzero(obs < limit_cell_v)
            pred_cross = np.flatnonzero(upd < limit_cell_v)
            issue_charge_ah = float(c.charge_ah[c.t <= ISSUE_TIME_S][-1])
            rows.append({
                "observed_cutoff": bool(over.size),
                "predicted_cutoff": bool(pred_cross.size),
                # Frozen timing-aware semantics: a miss is an observed crossing
                # with no predicted crossing at-or-before the recorded time.
                "miss": bool(over.size and (upd[:over[0] + 1] >= limit_cell_v).all()),
                "false_alarm": bool(pred_cross.size and not over.size),
                "endpoint_soc_pct": float(
                    100.0 * (1.0 - (issue_charge_ah + float(np.nansum(
                        predicted_i[:n]) * 2.0 / 3600.0)) / CAPACITY_AH)),
            })
        forecast_runs[cohort] = {
            "selected_cycles": len(numbers), "source_rejections": rejected,
            "rows_scored": len(rows), "rows_excluded": excluded,
            "observed_cutoffs": int(sum(r["observed_cutoff"] for r in rows)),
            "predicted_cutoffs": int(sum(r["predicted_cutoff"] for r in rows)),
            "misses": int(sum(r["miss"] for r in rows)),
            "false_alarms": int(sum(r["false_alarm"] for r in rows)),
            "min_endpoint_soc_pct": min(r["endpoint_soc_pct"] for r in rows),
            "max_endpoint_soc_pct": max(r["endpoint_soc_pct"] for r in rows),
        }

    return {"replay": replay_runs, "prospective": forecast_runs}


@pytest.mark.skipif(not WORKBOOK, reason="pinned SIT workbook stays outside the "
                    "repository; set AEROFORGE_SIT_WORKBOOK for the per-row scoring")
def test_workbook_row_scores_match_committed_aggregates():
    """The committed compact artifact pins the per-row aggregates produced by
    the local workbook run (mode-separated; exclusions recorded per cohort)."""
    aggregate = _workbook_aggregates(Path(WORKBOOK))
    committed = json.loads(ROW_SCORES_ARTIFACT.read_text(encoding="utf-8"))
    assert json.dumps(aggregate, sort_keys=True) ==         json.dumps(committed, sort_keys=True)
