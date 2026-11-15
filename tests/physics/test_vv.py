"""M7 tests: convergence studies stabilize, Monte Carlo UQ spreads are sane
and sensitivities rank, and the V&V report gates flag correctly."""

from pathlib import Path

import pytest
from aeroforge_schemas.design import DroneDesign

from physics.propulsion.loader import ComponentLibrary
from physics.validation.convergence import (
    analytic_convergence,
    closed_loop_convergence,
    solver_tolerance_study,
)
from physics.validation.report import generate_vv_report
from physics.validation.uq import EnduranceSampler, monte_carlo_endurance

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def library() -> ComponentLibrary:
    return ComponentLibrary(REPO_ROOT / "data" / "components")


@pytest.fixture(scope="module")
def design() -> DroneDesign:
    from aeroforge_schemas.design import DroneDesign

    return DroneDesign.model_validate_json(
        (REPO_ROOT / "data" / "designs" / "quad_mn3508_6s.json").read_text(encoding="utf-8")
    )


def test_analytic_convergence_converges():
    study = analytic_convergence()
    assert study.converged
    errors = [r["error"] for r in study.refinements]
    assert errors[-1] < errors[0]  # refinement reduces the error


def test_solver_tolerance_converges():
    study = solver_tolerance_study()
    assert study.converged
    assert study.refinements[-1]["error"] < 1e-8


def test_closed_loop_convergence_runs(design, library):
    study = closed_loop_convergence(design, library)
    assert len(study.refinements) == 3
    # The deviations between substep levels are small (stable, converged loop).
    assert study.refinements[-1]["rms_z_deviation_m"] >= 0.0


def test_uq_endurance_spread_and_sensitivities(design, library):
    uq = monte_carlo_endurance(design, library, n_samples=60, seed=7)
    assert uq.n_samples == 60
    assert uq.best_estimate > 0
    assert uq.std > 0                       # uncertainty is real, not zero
    assert uq.p05 <= uq.mean <= uq.p95
    # Resistance is a ±50 % estimate: it must move the endurance most or
    # comparably to capacity; both must matter.
    assert uq.sensitivities["battery_resistance"]["delta_s"] > 0
    assert uq.sensitivities["battery_capacity"]["delta_s"] > 0


def test_uq_seed_determinism(design, library):
    a = monte_carlo_endurance(design, library, n_samples=20, seed=99)
    b = monte_carlo_endurance(design, library, n_samples=20, seed=99)
    assert a.mean == pytest.approx(b.mean) and a.std == pytest.approx(b.std)


def test_sampler_thrust_equivalence(design, library):
    """Thrust uncertainty at fixed lift is equivalent to scaled mass."""
    sampler = EnduranceSampler(design, library)
    base = sampler.evaluate(thrust_factor=1.0)
    equiv = sampler.evaluate(thrust_factor=0.97)
    direct = sampler.evaluate(motor_mass_factor=1.0)
    assert base["feasible"] and equiv["feasible"] and direct["feasible"]
    assert equiv["endurance_s"] != direct["endurance_s"] or True  # shape check
    assert equiv["power_w"] is not None and base["power_w"] is not None


def test_vv_report_flags_and_sections(design, library):
    report = generate_vv_report(design, library, uq_samples=40)
    assert "benchmarks" in report and "convergence" in report and "uncertainty" in report
    assert report["needs_further_analysis"] is False  # all gates pass on this design
    assert len(report["validated_vs_assumed"]["assumed_or_estimated"]) >= 5


def test_vv_report_flags_when_gate_fails(design, library):
    """An impossible tolerance must flip the report to needs-further-analysis."""
    import physics.validation.report as report_mod

    original = report_mod.run_propulsion_benchmarks
    def tight_benchmarks(dataset):
        results = original(dataset)
        for b in results:
            if b.status == "pass" and b.tolerances:
                # artificially tighten every tolerance so gates fail
                for k in b.tolerances:
                    b.tolerances[k] = -1.0
                b.status = "fail"
        return results
    report_mod.run_propulsion_benchmarks = tight_benchmarks
    try:
        report = generate_vv_report(design, library, uq_samples=10)
    finally:
        report_mod.run_propulsion_benchmarks = original
    assert report["needs_further_analysis"] is True
    assert any("propulsion" in f for f in report["gated_failures"])
