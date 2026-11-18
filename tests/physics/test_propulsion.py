"""M2 acceptance tests: sourced propulsion data, interpolation accuracy,
envelope enforcement, battery model, and the static hover scenario.

Spec acceptance (Milestone 2): "The simulation produces thrust and current
values matching the given data table (within interpolation error)"; out-of-
range queries fail closed; the full-throttle run reproduces the table row.
"""

from pathlib import Path

import numpy as np
import pytest

from aeroforge_schemas.component import BatterySpec
from physics.constants import STANDARD_GRAVITY as G
from physics.propulsion.battery import BatteryPack, PowertrainError
from physics.propulsion.dataset import OutOfEnvelopeError, PowertrainDataset
from physics.propulsion.esc import Esc
from physics.propulsion.loader import ComponentLibrary
from physics.propulsion.powertrain import StaticPowertrain
from physics.validation.benchmarks import (
    benchmark_full_throttle_table,
    benchmark_knot_readback,
    benchmark_lumped_dc_crosscheck,
    benchmark_thrust_voltage_scatter,
    run_propulsion_benchmarks,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PROP_KEY = "T-MOTOR 15*5CF"


@pytest.fixture(scope="module")
def library() -> ComponentLibrary:
    return ComponentLibrary(REPO_ROOT / "data" / "components")


@pytest.fixture(scope="module")
def motor(library):
    return library.motor("tmotor_mn3508_kv380")


@pytest.fixture(scope="module")
def dataset(motor) -> PowertrainDataset:
    return PowertrainDataset(motor, PROP_KEY)


@pytest.fixture(scope="module")
def battery(library) -> BatteryPack:
    return BatteryPack(library.battery("generic_6s_lipo_16000mah"))


@pytest.fixture(scope="module")
def esc(library) -> Esc:
    return Esc(library.esc("generic_esc_20a"))


@pytest.fixture(scope="module")
def powertrain(dataset, esc, battery) -> StaticPowertrain:
    return StaticPowertrain(dataset, esc, battery, units=4)


# ------------------------------------------------------------ interpolation


def test_knot_readback_within_half_percent(dataset):
    """M2 acceptance gate: every measured knot reproduced within 0.5 %."""
    result = benchmark_knot_readback(dataset, tolerance=0.005)
    assert result.status == "pass", result.metrics


def test_full_throttle_table_reproduction(dataset):
    result = benchmark_full_throttle_table(dataset, voltage=22.2)
    assert result.status == "pass", result.metrics


def test_thrust_cross_voltage_scatter_small(dataset):
    result = benchmark_thrust_voltage_scatter(dataset, tolerance_pct=5.0)
    assert result.status == "pass", result.metrics
    assert dataset.scatter_pct < 5.0


def test_thrust_monotone_in_rpm(dataset):
    rpms = np.linspace(2600, 5900, 67)
    thrusts = [dataset.thrust_gf(float(r)).value for r in rpms]
    assert np.all(np.diff(thrusts) >= -1e-9)


def test_current_interpolated_between_voltage_planes(dataset):
    """rpm 4000 is covered by both planes; 18.5 V sits between them."""
    lo = dataset.current_a(4000, 14.8).value
    hi = dataset.current_a(4000, 22.2).value
    mid = dataset.current_a(4000, 18.5)
    assert min(lo, hi) <= mid.value <= max(lo, hi)
    assert mid.voltage_corrected


def test_voltage_extrapolation_flagged(dataset):
    at_plane = dataset.current_a(4000, 22.2).value
    res = dataset.current_a(4000, 23.5)  # above the measured max plane
    assert res.voltage_extrapolated
    assert res.value < at_plane  # slope says current falls with V at fixed rpm


def test_voltage_beyond_excursion_refused(dataset):
    with pytest.raises(OutOfEnvelopeError):
        dataset.current_a(4000, 30.0)
    with pytest.raises(OutOfEnvelopeError):
        dataset.current_a(4000, 10.0)


def test_rpm_outside_envelope_refused(dataset):
    with pytest.raises(OutOfEnvelopeError):
        dataset.thrust_gf(2500.0)
    with pytest.raises(OutOfEnvelopeError):
        dataset.thrust_gf(6000.0)


def test_throttle_below_extrapolation_floor_refused(dataset):
    with pytest.raises(OutOfEnvelopeError):
        dataset.rpm_at_throttle(0.2, 22.2)


def test_throttle_extrapolation_flagged_not_silent(dataset):
    res = dataset.rpm_at_throttle(0.40, 22.2)
    assert res.throttle_extrapolated


def test_single_plane_dataset_refuses_other_voltage(motor):
    ds = PowertrainDataset(motor, "T-MOTOR 14*4.8CF")  # only a 22.2 V plane
    assert ds.current_a(5700.0, 22.2).value == pytest.approx(7.5, rel=0.005)
    with pytest.raises(OutOfEnvelopeError):
        ds.current_a(5700.0, 18.0)


def test_lumped_dc_crosscheck_is_reported_not_gated(dataset):
    result = benchmark_lumped_dc_crosscheck(dataset)
    assert result.status == "reported"
    assert "ke_eff_v_s_per_rad" in result.metrics
    assert "current_max_rel_err_pct" in result.metrics


def test_all_benchmarks_run(dataset):
    results = run_propulsion_benchmarks(dataset)
    assert len(results) == 4
    gated = [r for r in results if r.status in ("pass", "fail")]
    assert all(r.status == "pass" for r in gated)


# ---------------------------------------------------------------- battery


def test_battery_ocv_readback(battery):
    assert battery.ocv_pack(100.0) == pytest.approx(25.2, abs=1e-9)
    assert battery.ocv_pack(50.0) == pytest.approx(6 * 3.89, abs=1e-9)


def test_battery_sag(battery):
    assert battery.voltage_under_load(100.0, 0.0) == pytest.approx(25.2, abs=1e-9)
    assert battery.voltage_under_load(50.0, 10.0) == pytest.approx(6 * 3.89 - 0.2, abs=1e-9)


def test_battery_requires_resistance_for_load(library):
    spec = library.battery("generic_6s_lipo_16000mah").model_copy(deep=True)
    spec.internal_resistance_ohm = None
    pack = BatteryPack(spec)
    with pytest.raises(PowertrainError, match="internal resistance"):
        pack.voltage_under_load(50.0, 10.0)


def test_battery_soc_coulomb_counting(battery):
    assert battery.soc_after(100.0, 16.0, 3600.0) == pytest.approx(0.0, abs=1e-9)
    assert battery.soc_after(100.0, 16.0, 1800.0) == pytest.approx(50.0, abs=1e-9)


def test_battery_warning_and_cutoff(battery):
    ok = battery.status(100.0, 5.0)
    assert not ok.warning and not ok.cutoff
    drained = battery.status(2.0, 5.0)
    assert drained.warning
    assert battery.status(0.0, 5.0).cutoff


# ---------------------------------------------------------- static hover


def test_hover_point_plausible(powertrain):
    mass = 3.708
    target = mass * G
    throttle = powertrain.throttle_for_total_thrust(target, soc_pct=100.0)
    op = powertrain.operating_point(throttle, soc_pct=100.0)

    assert op.total_thrust_n == pytest.approx(target, rel=1e-4)
    # ~927 gf per rotor: within the 22.2 V plane's measured rpm range.
    assert 3800 <= op.per_unit.rpm <= 4800
    # Voltage-corrected hover current (flagged extrapolation above the 22.2 V
    # plane): ~2.5-6.5 A/rotor, i.e. ~65-260 W/rotor.
    assert 2.5 <= op.per_unit.current_a <= 6.5
    assert 10.0 <= op.total_current_a <= 26.0
    # Bus voltage sags below OCV but stays inside the allowed excursion.
    assert 22.0 <= op.v_bus <= 25.2


def test_thrust_inverse_roundtrip(powertrain):
    target = 3.708 * G
    throttle = powertrain.throttle_for_total_thrust(target, soc_pct=100.0)
    back = powertrain.operating_point(throttle, soc_pct=100.0).total_thrust_n
    assert back == pytest.approx(target, rel=1e-3)


def test_overload_fails_closed(powertrain):
    # 4 x 1880 gf = 73.8 N max; 100 N is far beyond -> refuse, don't fake.
    with pytest.raises(OutOfEnvelopeError):
        powertrain.throttle_for_total_thrust(100.0, soc_pct=100.0)


def test_hover_from_depleted_battery_fails_closed(powertrain):
    # A pack already at/below the cutoff cannot support hover -> refuse.
    with pytest.raises(PowertrainError, match="cutoff"):
        powertrain.static_hover(3.708, max_duration_s=60, dt_s=10.0, soc_start_pct=0.0)


def test_static_hover_endurance_plausible(powertrain):
    result = powertrain.static_hover(3.708, max_duration_s=7200, dt_s=10.0)
    # Hover thrust held at m*g throughout.
    assert result.hover_point.total_thrust_n == pytest.approx(3.708 * G, rel=1e-3)
    # Endurance to the 3.5 V/cell warning: 20–100 minutes for this pack/design.
    assert result.endurance_to_warning_s is not None
    assert 1200 <= result.endurance_to_warning_s <= 6000
    # Component limits respected in hover.
    assert result.limit_issues == []
    # Full-charge operation sits above the 22.2 V plane -> flagged, not silent.
    assert any("voltage_extrapolated" in f for f in result.envelope_flags)
    assert result.min_cell_voltage_v > 3.3  # never reaches the damage cutoff


@pytest.mark.parametrize("rating, failed", [(2.0, True), (8.0, False)])
def test_static_hover_checks_each_esc(esc, dataset, battery, rating, failed):
    controller = Esc(esc.spec.model_copy(update={"max_continuous_current_a": rating}))
    pt = StaticPowertrain(dataset, controller, battery, units=4)
    result = pt.static_hover(3.708, max_duration_s=60, dt_s=10.0)
    assert result.hover_point.total_current_a > rating
    assert (result.hover_point.per_unit.current_a > rating) == failed
    assert any("ESC over-current" in i for i in result.limit_issues) == failed
    if failed:
        assert len(result.samples) == 1 and result.energy_used_wh == 0
        assert result.endurance_to_warning_s is None


def test_esc_accepts_exact_ratings(esc):
    assert esc.check(esc.spec.max_continuous_current_a, esc.spec.max_voltage_v) == []
