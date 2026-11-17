"""Signed energy and data quality checks using miniature synthetic exports."""
from pathlib import Path
import runpy
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[2]
bench = runpy.run_path(str(ROOT / "scripts/benchmark_m100_planned_energy.py"))


@pytest.mark.parametrize(("time", "current", "status"), [
    ("2", "-1", "SCORED"),
    ("1", "-1", "CLOCK_OR_GAP_REJECTION"),
    ("2", "201", "OUTSIDE_DOCUMENTED_METER_RANGE"),
])
def test_source_signed_energy_and_clock_gate(tmp_path, time, current, status):
    flight = bench["Mission"](1, "2019-05-01", 4, 25, 0)
    path = tmp_path / "synthetic.zip"
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "flights/1.csv",
            f"time,battery_voltage,battery_current\n0,24,2\n1,24,2\n{time},24,{current}\n3,24,2\n4,24,2\n",
        )
    with ZipFile(path) as archive:
        result = bench["metered_record"](archive, flight)
    assert result["status"] == status
    if status == "SCORED":
        assert result["measured_energy_wh"] == pytest.approx(24 * 5 / 3600)
