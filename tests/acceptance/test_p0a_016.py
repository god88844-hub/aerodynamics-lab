"""P0A-016 acceptance tests: component provenance, operating limits, UNVERIFIED_ESTIMATE,
and fail-closed mass-property refusal when density or density source is missing.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aeroforge_schemas.component import (
    BatterySpec,
    EscSpec,
    MaterialRecord,
    MotorSpec,
    ParameterProvenance,
    PropellerSpec,
    SOURCED,
    SensorSpec,
    UNVERIFIED_ESTIMATE,
    WiringSpec,
    validate_component_record_acceptance,
)
from app.services.component_service import list_components
from geometry.cad_backend import require_solid_mass_properties, solid_mass_properties
from physics.dynamics.mass_properties import (
    part_from_material_volume,
    require_material_density_and_source,
)
from physics.propulsion.loader import ComponentLibrary
from physics.structures.materials import load_materials

ROOT = Path(__file__).resolve().parents[2]
DATA_COMPONENTS = ROOT / "data" / "components"
RESEARCH_REGISTRY = ROOT / "data" / "research" / "registry.json"
CANONICAL_REGISTRY = ROOT / "data" / "registry.json"


def test_all_committed_component_and_material_records_pass_acceptance():
    library = ComponentLibrary(DATA_COMPONENTS)
    audits = library.validate_all_records()

    kinds = {a["kind"] for a in audits}
    assert {"battery", "motor", "esc", "propeller", "wiring", "sensor", "material"} <= kinds
    assert all(a["accepted"] is True for a in audits)

    research = json.loads(RESEARCH_REGISTRY.read_text(encoding="utf-8"))
    evidence_registry = research["component_evidence_registry"]
    canonical = json.loads(CANONICAL_REGISTRY.read_text(encoding="utf-8"))
    canonical_artifacts = {a["artifact"] for a in canonical["component_calibration_inputs"]}

    for kind in ("battery", "motor", "esc", "propeller", "wiring", "sensor"):
        folder = DATA_COMPONENTS / {
            "battery": "batteries",
            "motor": "motors",
            "esc": "controllers",
            "propeller": "propellers",
            "wiring": "wiring",
            "sensor": "sensors",
        }[kind]
        for path in sorted(folder.glob("*.json")):
            rel = path.relative_to(ROOT).as_posix()
            assert rel in canonical_artifacts
            spec = library.load(kind, path.stem)
            assert spec.source.evidence_id in evidence_registry
            for param, prov in (spec.parameter_provenance or {}).items():
                assert prov.evidence_id in evidence_registry, f"{rel}:{param} missing registry evidence"
                assert prov.unit.strip()

    for mat in library.materials_catalog().materials:
        assert mat.evidence_id in evidence_registry
        for param, prov in mat.parameter_provenance.items():
            assert prov.evidence_id in evidence_registry, f"material {mat.id}:{param} missing registry evidence"


def test_unverified_estimate_flags_and_ui_export_surfacing():
    exported = list_components(DATA_COMPONENTS)
    assert set(exported) >= {"motors", "propellers", "batteries", "escs", "wiring", "sensors", "materials"}

    # Generic / placeholder entries must surface UNVERIFIED_ESTIMATE.
    bat = next(b for b in exported["batteries"] if b["id"] == "generic_6s_lipo_16000mah")
    assert bat["provenance_status"] == UNVERIFIED_ESTIMATE
    assert bat["has_unverified_estimates"] is True
    assert "internal_resistance_ohm" in bat["unverified_estimates"]
    assert bat["operating_limits"]["cutoff_cell_voltage_v"] == 3.3

    esc = next(e for e in exported["escs"] if e["id"] == "generic_esc_20a")
    assert esc["provenance_status"] == UNVERIFIED_ESTIMATE
    assert esc["estimated"] is True

    wire = next(w for w in exported["wiring"] if w["id"] == "silicone_awg12_bus")
    assert wire["provenance_status"] == UNVERIFIED_ESTIMATE
    assert "max_continuous_current_a" in wire["unverified_estimates"]
    assert wire["parameter_provenance"]["resistance_ohm_per_m"]["status"] == SOURCED

    sensor = next(s for s in exported["sensors"] if s["id"] == "icm42688p_imu")
    assert sensor["provenance_status"] == UNVERIFIED_ESTIMATE
    assert "latency_s" in sensor["unverified_estimates"]
    assert sensor["parameter_provenance"]["sample_rate_hz"]["status"] == SOURCED

    # T-Motor MN3508 is datasheet-sourced at record level while its unlisted thermal ceiling is flagged.
    motor = next(m for m in exported["motors"] if m["id"] == "tmotor_mn3508_kv380")
    assert motor["estimated"] is False
    assert motor["parameter_provenance"]["kv_rpm_per_v"]["status"] == SOURCED
    assert motor["parameter_provenance"]["max_winding_temp_c"]["status"] == UNVERIFIED_ESTIMATE
    assert "max_winding_temp_c" in motor["unverified_estimates"]

    # Materials with typical/assumed bands surface UNVERIFIED_ESTIMATE.
    alu = next(m for m in exported["materials"] if m["id"] == "alu_6061_t6")
    assert alu["has_unverified_estimates"] is True
    assert alu["provenance_status"] == UNVERIFIED_ESTIMATE
    cfrp = next(m for m in exported["materials"] if m["id"] == "cfrp_quasi_iso")
    assert cfrp["estimated"] is True
    assert cfrp["provenance_status"] == UNVERIFIED_ESTIMATE


def test_typical_or_assumed_parameter_cannot_claim_sourced():
    with pytest.raises(ValueError, match="UNVERIFIED_ESTIMATE"):
        ParameterProvenance(
            unit="kg",
            source="Typical mass estimate without datasheet",
            uncertainty_pct=15.0,
            estimated=False,
            status=SOURCED,
        )

    with pytest.raises(ValueError, match="UNVERIFIED_ESTIMATE"):
        ParameterProvenance(
            unit="degC",
            source="Assumed thermal limit",
            uncertainty_pct=10.0,
            estimated=True,
            status=SOURCED,
        )


def test_missing_limits_units_identity_or_provenance_refuse_acceptance():
    library = ComponentLibrary(DATA_COMPONENTS)
    bat = library.battery("generic_6s_lipo_16000mah")

    missing_limits = bat.model_copy(update={"operating_limits": {"cutoff_cell_voltage_v": 3.3}})
    with pytest.raises(ValueError, match="missing required operating limit"):
        validate_component_record_acceptance(missing_limits, "battery")

    missing_units = bat.model_copy(update={"units": None})
    with pytest.raises(ValueError, match="missing explicit SI units"):
        validate_component_record_acceptance(missing_units, "battery")

    missing_identity = bat.model_copy(update={"physical_identity": {}})
    with pytest.raises(ValueError, match="missing physical_identity"):
        validate_component_record_acceptance(missing_identity, "battery")

    reduced_prov = dict(bat.parameter_provenance or {})
    reduced_prov.pop("capacity_ah")
    missing_prov = bat.model_copy(update={"parameter_provenance": reduced_prov})
    with pytest.raises(ValueError, match="missing parameter provenance"):
        validate_component_record_acceptance(missing_prov, "battery")

    esc = library.esc("generic_esc_20a")
    bad_esc = esc.model_copy(update={"operating_limits": {**esc.operating_limits, "max_voltage_v": 0.0}})
    with pytest.raises(ValueError, match="must be > 0"):
        validate_component_record_acceptance(bad_esc, "esc")

    wire = library.wiring("silicone_awg12_bus")
    bad_wire = wire.model_copy(update={"operating_limits": {"max_continuous_current_a": 60.0}})
    with pytest.raises(ValueError, match="missing required operating limit"):
        validate_component_record_acceptance(bad_wire, "wiring")

    sensor = library.sensor("icm42688p_imu")
    bad_sensor = sensor.model_copy(update={"operating_limits": {**sensor.operating_limits, "min_voltage_v": 5.0, "max_voltage_v": 3.3}})
    with pytest.raises(ValueError, match="min_voltage_v must be < max_voltage_v"):
        validate_component_record_acceptance(bad_sensor, "sensor")


def test_mass_property_computation_refuses_missing_density_or_source(tmp_path):
    # 1. Physics helper fail-closed checks
    with pytest.raises(ValueError, match="density_kg_m3 is missing"):
        require_material_density_and_source(None, "ASM Handbook")
    with pytest.raises(ValueError, match="density source is missing"):
        require_material_density_and_source(2700.0, "")
    with pytest.raises(ValueError, match="density source is missing"):
        require_material_density_and_source(2700.0, None)
    with pytest.raises(ValueError, match="density source is missing"):
        part_from_material_volume("arm", 1e-4, [0.0, 0.0, 0.0], density_kg_m3=2700.0, density_source="   ")

    # Valid sourced density succeeds
    part = part_from_material_volume(
        "arm", 1e-4, [0.1, 0.0, 0.0], density_kg_m3=2700.0, density_source="ASM Metals Handbook 6061-T6"
    )
    assert part.mass_kg == pytest.approx(0.27)

    # 2. Material catalog loader fail-closed checks
    raw_materials = json.loads((DATA_COMPONENTS / "materials.json").read_text(encoding="utf-8"))
    no_source = deepcopy(raw_materials)
    no_source["materials"][0]["source"] = ""
    bad_source_file = tmp_path / "materials_no_source.json"
    bad_source_file.write_text(json.dumps(no_source), encoding="utf-8")
    with pytest.raises(ValueError, match="missing density/material source"):
        load_materials(bad_source_file)

    no_density = deepcopy(raw_materials)
    no_density["materials"][0]["density_kg_m3"] = None
    bad_density_file = tmp_path / "materials_no_density.json"
    bad_density_file.write_text(json.dumps(no_density), encoding="utf-8")
    with pytest.raises(ValueError, match="missing or non-positive density_kg_m3"):
        load_materials(bad_density_file)

    # 3. CAD solid_mass_properties fail-closed check (mocked solid checks gate without needing cadquery)
    fake_solid = SimpleNamespace(
        isValid=lambda: True,
        Solids=lambda: [object()],
        Volume=lambda: 1000.0,
        Center=lambda: SimpleNamespace(x=0.0, y=0.0, z=0.0),
    )
    with pytest.raises(ValueError, match="uniform density_kg_m3 is missing"):
        require_solid_mass_properties(fake_solid, None, "ASM Handbook")
    with pytest.raises(ValueError, match="density_source provenance is missing"):
        solid_mass_properties(fake_solid, 2700.0, density_source="", require_source=True)
