"""Exercise the flight report with its real structural monitor and a short mission."""
from pathlib import Path

import pytest

from aeroforge_schemas.design import DroneDesign
from physics.scenarios import service


@pytest.mark.parametrize("configuration,status", [("default", "INCONCLUSIVE"), ("absent", "INCONCLUSIVE"), ("thin", "FAIL")])
def test_saved_flight_structure_verdict(monkeypatch, configuration, status):
    design = DroneDesign.model_validate_json(
        (Path(__file__).resolve().parents[2] / "data/designs/quad_mn3508_6s.json").read_bytes()
    )
    if configuration == "absent":
        design.frame = None
    elif configuration == "thin":
        design.frame = design.frame.model_copy(update={"tube_od_m": 0.003, "tube_id_m": 0.0025})
    original = service.run_scenario

    def short_mission(design, scenario, library):
        scenario.duration_s = 0.04
        return original(design, scenario, library)

    monkeypatch.setattr(service, "run_scenario", short_mission)
    result = service.run_flight(design)
    assert result["trustworthiness"]["structure"]["status"] == status
    assert any("structural" in note for note in result["model_notes"])
    assert result["mission"]["aborted"] == (status == "FAIL")
    assert (result["results"]["structural_margin_min"] is None) == (configuration == "absent")
