"""Authoritative multirotor layout, component selection, BOM, and mass properties (P0A-019)."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np

from aeroforge_schemas.component import SOURCED, UNVERIFIED_ESTIMATE, collect_unverified_estimates
from geometry.primitives import box_inertia, cylinder_inertia_z
from physics.dynamics.mass_properties import (
    MassProperties,
    Part,
    assemble_mass_properties,
    require_material_density_and_source,
)
from physics.propulsion.loader import ComponentLibrary
from physics.structures.materials import load_materials


def build_multirotor_layout_and_bom(
    layout_spec: dict[str, Any],
    library: ComponentLibrary,
) -> dict[str, Any]:
    """Assemble mass, CoG, inertia, powertrain summary, and BOM from arbitrary rotor layout & components.

    Fails closed (raises ValueError) if any structural frame/custom volume part is missing
    material density or density provenance source, or if selected components lack required mass.
    """
    rotors_spec = layout_spec.get("rotors") or []
    if not rotors_spec:
        raise ValueError("multirotor layout requires at least one rotor")

    motor_id = str(layout_spec["motor_id"])
    prop_id = str(layout_spec["propeller_id"])
    esc_id = str(layout_spec["esc_id"])
    battery_id = str(layout_spec["battery_id"])
    wiring_id = layout_spec.get("wiring_id")
    wiring_length_m = float(layout_spec.get("wiring_length_m", 0.0))
    sensor_ids = [str(s) for s in (layout_spec.get("sensor_ids") or [])]

    motor = library.motor(motor_id)
    prop = library.propeller(prop_id)
    esc = library.esc(esc_id)
    battery = library.battery(battery_id)
    wiring = library.wiring(str(wiring_id)) if wiring_id else None
    sensors = [library.sensor(sid) for sid in sensor_ids]

    for label, comp in (("motor", motor), ("propeller", prop), ("esc", esc), ("battery", battery)):
        if getattr(comp, "mass_kg", None) is None or float(comp.mass_kg) <= 0.0:
            raise ValueError(f"{label}/{comp.id}: missing positive mass_kg")

    materials_path = library.data_dir / "materials.json"
    materials = load_materials(materials_path) if materials_path.is_file() else {}

    parts: list[Part] = []
    bom: list[dict[str, Any]] = []
    n_rotors = len(rotors_spec)

    # Frame / structural body parts: require explicit density + density_source (fail closed!)
    frame_parts = layout_spec.get("frame_parts") or []
    if not frame_parts:
        raise ValueError("layout requires at least one frame_parts entry with material/density provenance")

    for fp in frame_parts:
        fp_name = str(fp.get("name", "frame_part"))
        pos = np.asarray(fp.get("position_m", [0.0, 0.0, 0.0]), dtype=float)
        mat_id = fp.get("material_id")
        if mat_id is not None:
            if mat_id not in materials:
                raise ValueError(f"frame part {fp_name!r}: unknown material_id {mat_id!r}")
            mat = materials[mat_id]
            density, d_source = require_material_density_and_source(mat.density_kg_m3, mat.source)
            mat_status = mat.status
        else:
            density, d_source = require_material_density_and_source(
                fp.get("density_kg_m3"), fp.get("density_source")
            )
            mat_status = UNVERIFIED_ESTIMATE

        dims = fp.get("dimensions_m")
        shape = fp.get("shape", "box")
        if dims is not None:
            x, y, z = [float(v) for v in dims]
            if any(not math.isfinite(v) or v <= 0.0 for v in (x, y, z)):
                raise ValueError(f"frame part {fp_name!r}: dimensions_m must be finite and > 0")
            if shape == "cylinder":
                volume_m3 = math.pi * (0.5 * x) ** 2 * z
                mass_kg = volume_m3 * density
                own_inertia = cylinder_inertia_z(mass_kg, 0.5 * x, z)
            elif shape == "box":
                volume_m3 = x * y * z
                mass_kg = volume_m3 * density
                own_inertia = box_inertia(mass_kg, x, y, z)
            else:
                raise ValueError(f"unsupported frame shape {shape!r}")
        elif fp.get("volume_m3") is not None:
            volume_m3 = float(fp["volume_m3"])
            if not math.isfinite(volume_m3) or volume_m3 <= 0.0:
                raise ValueError(f"frame part {fp_name!r}: volume_m3 must be finite and > 0")
            mass_kg = volume_m3 * density
            own_inertia = None
        else:
            raise ValueError(f"frame part {fp_name!r}: requires dimensions_m or volume_m3")

        parts.append(Part(name=fp_name, mass_kg=mass_kg, position_m=pos, inertia_about_own_cog=own_inertia))
        bom.append({
            "kind": "structure",
            "id": mat_id or fp_name,
            "name": fp_name,
            "quantity": 1,
            "unit_mass_kg": mass_kg,
            "total_mass_kg": mass_kg,
            "source": d_source,
            "provenance_status": mat_status,
        })

    # Rotors: each rotor places 1 motor + 1 propeller + 1 ESC
    validated_rotors: list[dict[str, Any]] = []
    for idx, r in enumerate(rotors_spec):
        r_pos = np.asarray(r["position_m"], dtype=float)
        spin = int(r.get("spin_direction", 1 if idx % 2 == 0 else -1))
        if spin not in (1, -1):
            raise ValueError(f"rotor[{idx}]: spin_direction must be 1 or -1")
        parts.append(Part(name=f"motor_{idx + 1}", mass_kg=float(motor.mass_kg), position_m=r_pos))
        parts.append(Part(name=f"prop_{idx + 1}", mass_kg=float(prop.mass_kg), position_m=r_pos))
        esc_pos = np.asarray(r.get("esc_position_m", r_pos * 0.5), dtype=float)
        parts.append(Part(name=f"esc_{idx + 1}", mass_kg=float(esc.mass_kg), position_m=esc_pos))
        validated_rotors.append({
            "index": idx,
            "position_m": r_pos.tolist(),
            "spin_direction": spin,
            "motor_id": motor.id,
            "propeller_id": prop.id,
            "esc_id": esc.id,
        })

    # Battery
    bat_pos = np.asarray(layout_spec.get("battery_position_m", [0.0, 0.0, 0.0]), dtype=float)
    parts.append(Part(name=f"battery_{battery.id}", mass_kg=float(battery.mass_kg), position_m=bat_pos))

    # Optional wiring harness
    if wiring is not None:
        if not math.isfinite(wiring_length_m) or wiring_length_m <= 0.0:
            raise ValueError("wiring_length_m must be finite and > 0 when wiring_id is selected")
        wire_mass = float(wiring.mass_kg_per_m) * wiring_length_m
        wire_pos = np.asarray(layout_spec.get("wiring_position_m", [0.0, 0.0, 0.0]), dtype=float)
        parts.append(Part(name=f"wiring_{wiring.id}", mass_kg=wire_mass, position_m=wire_pos))

    # Optional sensors
    for s_idx, sensor in enumerate(sensors):
        s_pos = np.asarray(layout_spec.get("sensor_position_m", [0.0, 0.0, 0.02]), dtype=float)
        parts.append(Part(name=f"sensor_{s_idx + 1}_{sensor.id}", mass_kg=float(sensor.mass_kg), position_m=s_pos))

    mass_props: MassProperties = assemble_mass_properties(parts)

    def _status(spec) -> str:
        return UNVERIFIED_ESTIMATE if collect_unverified_estimates(spec) else SOURCED

    bom.extend([
        {
            "kind": "motor",
            "id": motor.id,
            "name": motor.name,
            "quantity": n_rotors,
            "unit_mass_kg": float(motor.mass_kg),
            "total_mass_kg": float(motor.mass_kg) * n_rotors,
            "source": motor.source.source,
            "provenance_status": _status(motor),
        },
        {
            "kind": "propeller",
            "id": prop.id,
            "name": prop.name,
            "quantity": n_rotors,
            "unit_mass_kg": float(prop.mass_kg),
            "total_mass_kg": float(prop.mass_kg) * n_rotors,
            "source": prop.source.source,
            "provenance_status": _status(prop),
        },
        {
            "kind": "esc",
            "id": esc.id,
            "name": esc.name,
            "quantity": n_rotors,
            "unit_mass_kg": float(esc.mass_kg),
            "total_mass_kg": float(esc.mass_kg) * n_rotors,
            "source": esc.source.source,
            "provenance_status": _status(esc),
        },
        {
            "kind": "battery",
            "id": battery.id,
            "name": battery.name,
            "quantity": 1,
            "unit_mass_kg": float(battery.mass_kg),
            "total_mass_kg": float(battery.mass_kg),
            "source": battery.source.source,
            "provenance_status": _status(battery),
        },
    ])
    if wiring is not None:
        bom.append({
            "kind": "wiring",
            "id": wiring.id,
            "name": wiring.name,
            "quantity": wiring_length_m,
            "quantity_unit": "m",
            "unit_mass_kg": float(wiring.mass_kg_per_m),
            "total_mass_kg": float(wiring.mass_kg_per_m) * wiring_length_m,
            "source": wiring.source.source,
            "provenance_status": _status(wiring),
        })
    for sensor in sensors:
        bom.append({
            "kind": "sensor",
            "id": sensor.id,
            "name": sensor.name,
            "quantity": 1,
            "unit_mass_kg": float(sensor.mass_kg),
            "total_mass_kg": float(sensor.mass_kg),
            "source": sensor.source.source,
            "provenance_status": _status(sensor),
        })

    return {
        "n_rotors": n_rotors,
        "rotors": validated_rotors,
        "powertrain": {
            "motor_id": motor.id,
            "propeller_id": prop.id,
            "esc_id": esc.id,
            "battery_id": battery.id,
            "wiring_id": wiring.id if wiring else None,
            "wiring_length_m": wiring_length_m if wiring else 0.0,
            "sensor_ids": [s.id for s in sensors],
        },
        "mass_properties": {
            "units": {"mass_kg": "kg", "cog_m": "m", "inertia_about_cog_kg_m2": "kg*m^2"},
            "mass_kg": mass_props.mass_kg,
            "cog_m": mass_props.cog_m.tolist(),
            "inertia_about_cog_kg_m2": mass_props.inertia_about_cog.tolist(),
            "principal_moments_kg_m2": mass_props.principal_moments.tolist(),
        },
        "bom": bom,
        "unverified_bom_items": [item["id"] for item in bom if item["provenance_status"] == UNVERIFIED_ESTIMATE],
        "physical_validation_status": "unvalidated",
    }
