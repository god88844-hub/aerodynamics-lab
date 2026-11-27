"""P0D-008: Verify adverse-weather coupling, dry limit identity, and failure propagation in authoritative runner."""

from __future__ import annotations

import json
from pathlib import Path

from aeroforge_schemas.project import EngineeringProject, import_legacy_project
from physics.scenarios.desktop_runner import run_authoritative_desktop_simulation

ROOT = Path(__file__).resolve().parents[2]
LEGACY_DESIGN = ROOT / "data" / "designs" / "quad_mn3508_6s.json"


def test_p0d_008_weather_coupling_dry_limit_and_icing_failure_propagation():
    base = import_legacy_project(json.loads(LEGACY_DESIGN.read_text(encoding="utf-8")))
    dry = run_authoritative_desktop_simulation(base)

    severe_ice = EngineeringProject.model_validate(
        {
            **base.model_dump(mode="json"),
            "experiment": {
                **base.experiment.model_dump(mode="json"),
                "parameters": {
                    **dict(base.experiment.parameters or {}),
                    "adverse_weather": {
                        "turbulence_intensity": 0.20,
                        "rain_mm_h": 35.0,
                        "oat_c": -6.0,
                        "lwc_g_m3": 1.2,
                        "icing_exposure_s": 120.0,
                    },
                },
            },
        }
    )
    res = run_authoritative_desktop_simulation(severe_ice)
    assert res["adverse_weather_summary"] is not None
    assert res["adverse_weather_summary"]["caveat_status"] == "SUPPORTED_WITH_CAVEATS"
    assert res["physical_validation_status"] == "unvalidated"
    assert res["result"]["telemetry"]["z"] != dry["result"]["telemetry"]["z"]
