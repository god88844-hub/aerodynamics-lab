"""P0C-005: Author VTOL tilt and lift-plus-cruise configurations, round-trip, and mechanism refusal."""

from __future__ import annotations

import json

import pytest

from physics.aerodynamics.rotorcraft_vtol import VtolConfigurationSpec, author_vtol_configuration


def test_p0c_005_vtol_tilt_and_lpc_configuration_roundtrip():
    tilt = VtolConfigurationSpec(
        name="TiltVTOL-2100",
        architecture="tilt_rotor",
        mass_kg=3.2,
        wing_area_m2=0.45,
        max_hover_thrust_n=52.0,
        mass_provenance="MEASURED_BILL_OF_MATERIALS",
    )
    doc = author_vtol_configuration(tilt)
    assert doc["hover_thrust_weight_ratio"] > 1.5
    assert doc["physical_validation_status"] == "UNVALIDATED"
    reloaded = json.loads(json.dumps(doc))
    assert reloaded["config_sha256"] == doc["config_sha256"]

    lpc = author_vtol_configuration(
        VtolConfigurationSpec(name="LPC-2000", architecture="lift_plus_cruise", mass_kg=3.4, wing_area_m2=0.52, max_hover_thrust_n=56.0, mass_provenance="SPEC")
    )
    assert lpc["architecture"] == "lift_plus_cruise"


def test_p0c_005_invalid_vtol_mechanism_rejected():
    with pytest.raises(ValueError, match="VTOL invalid"):
        VtolConfigurationSpec(name="Underpowered", architecture="tilt_rotor", mass_kg=5.0, max_hover_thrust_n=25.0, mass_provenance="SPEC")
    with pytest.raises(ValueError, match="tilt mechanism"):
        VtolConfigurationSpec(name="BadTilt", architecture="tilt_rotor", mass_kg=3.0, max_hover_thrust_n=48.0, tilt_min_deg=60.0, tilt_max_deg=45.0, mass_provenance="SPEC")
