"""A DXF model-space point for each independently located item of a saved design."""
from __future__ import annotations

from io import StringIO
import math
import re

import ezdxf
from ezdxf import units
from ezdxf.lldxf.const import DXFError

from aeroforge_schemas.design import DroneDesign

APPID = "AEROFORGE_LAYOUT_V1"
MAX_DRAWING_BYTES = 1024 * 1024


def _items(design: DroneDesign):
    # Layer numbers uniquely identify items even where names or coordinates coincide.
    for i, part in enumerate(design.parts):
        if part.mount_id is None:
            yield f"PART_{i+1}", part.name, part, 3
    for i, rotor in enumerate(design.rotors):
        yield f"ROTOR_{i+1}", "thrust_center", rotor, 1
    if design.frame:
        for i, mount in enumerate(design.frame.mount_points):
            yield f"MOUNT_{i+1}", mount.id, mount, 5


def _layer(key: str, name: str) -> str:
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)[:64]
    return f"AF_{key}_{safe_name}".upper()


def export_layout(design: DroneDesign, digest: str) -> bytes:
    doc = ezdxf.new("R2010", units=units.M)
    doc.appids.new(APPID)
    doc.header["$PDMODE"] = 35
    doc.header["$PDSIZE"] = -2.0
    for key, name, item, color in _items(design):
        layer = _layer(key, name)
        doc.layers.new(layer, dxfattribs={"color": color})
        point = doc.modelspace().add_point(item.position_m, dxfattribs={"layer": layer})
        point.set_xdata(APPID, [(1000, digest), (1000, key)])
    stream = StringIO()
    doc.write(stream)
    data = stream.getvalue().encode("utf-8")
    if len(data) > MAX_DRAWING_BYTES:
        raise ValueError("This layout exceeds the 1 MiB CAD exchange limit")
    return data


def import_layout(design: DroneDesign, digest: str, data: bytes) -> tuple[DroneDesign, list[dict]]:
    if len(data) > MAX_DRAWING_BYTES:
        raise ValueError("DXF exceeds the 1 MiB exchange limit")
    try:
        doc = ezdxf.read(StringIO(data.decode("utf-8-sig")))
        if doc.units != units.M:
            raise ValueError("Drawing units must be metres")
        edited = design.model_copy(deep=True)
        items = {key: (name, item) for key, name, item, _ in _items(edited)}
        changes = []
        for entity in doc.modelspace():
            if entity.dxftype() != "POINT" or not entity.has_xdata(APPID):
                raise ValueError("Every model-space entity must be an exported AeroForge POINT")
            tags = entity.get_xdata(APPID)
            if len(tags) != 2 or tags[0] != (1000, digest) or tags[1].code != 1000:
                raise ValueError("Drawing points must belong to the selected design revision")
            key = tags[1].value
            if key not in items:
                raise ValueError(f"Unexpected or duplicate layout point {key!r}")
            name, item = items.pop(key)
            if entity.dxf.layer.upper() != _layer(key, name):
                raise ValueError(f"Unexpected layer for {key}")
            if not entity.dxf.hasattr("location"):
                raise ValueError(f"Missing coordinates for {key}")
            position = tuple(entity.dxf.location)
            if not all(math.isfinite(v) for v in position):
                raise ValueError(f"Nonfinite coordinates for {key}")
            if position != item.position_m:
                changes.append({"item": key, "name": name, "from_m": item.position_m, "to_m": position})
                item.position_m = position
        if items:
            raise ValueError(f"Missing layout points: {', '.join(items)}")
        if edited.frame and design.frame:
            moved = {new.id: new.position_m for old, new in
                     zip(design.frame.mount_points, edited.frame.mount_points)
                     if old.position_m != new.position_m}
            for part in edited.parts:
                if part.mount_id in moved:
                    target = moved[part.mount_id]
                    changes.append({"item": "ATTACHED_PART", "name": part.name,
                                    "from_m": part.position_m, "to_m": target})
                    part.position_m = target
        return DroneDesign.model_validate(edited.model_dump()), changes
    except (DXFError, UnicodeError, IndexError, TypeError, OverflowError) as exc:
        raise ValueError("Could not read the CAD layout as a UTF-8 text DXF") from exc
