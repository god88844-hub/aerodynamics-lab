"""Exact blade construction through CadQuery's C++ Open CASCADE bindings."""

from __future__ import annotations

from hashlib import sha256
from importlib.metadata import version
import json
import math
from pathlib import Path
from uuid import uuid4

from aeroforge_schemas.cad import BladeRecipe, BoxRecipe
from aeroforge_schemas.project import AssemblyNode, AssemblyVehicle, EngineeringProject, GeometryAsset


def _rectangle_sketch(width_m: float, height_m: float):
    """Check the experimental sketch solver against independently checked dimensions."""
    import cadquery as cq

    if not all(math.isfinite(value) and value > 0 for value in (width_m, height_m)):
        raise ValueError("Sketch dimensions must be finite and positive")
    width, height = width_m * 1000, height_m * 1000
    sketch = (cq.Sketch()
              .segment((0, 0), (0.9 * width, 0), "a")
              .segment((0.9 * width, 0), (0.9 * width, 0.9 * height), "b")
              .segment((0.9 * width, 0.9 * height), (0, 0.9 * height), "c")
              .segment((0, 0.9 * height), (0, 0), "d"))
    for tag, orientation, length in (
        ("a", (1, 0), width), ("b", (0, 1), height),
        ("c", (-1, 0), width), ("d", (0, -1), height),
    ):
        sketch = sketch.constrain(tag, "Orientation", orientation).constrain(tag, "Length", length)
    sketch = sketch.constrain("a", "FixedPoint", 0)
    for first, second in (("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")):
        sketch = sketch.constrain(first, second, "Coincident", None)
    sketch = sketch.solve()
    lengths = [sketch._tags[tag][0].Length() for tag in "abcd"]
    expected = [width, height, width, height]
    if any(abs(actual - target) > 1e-5 for actual, target in zip(lengths, expected)):
        raise ValueError("Sketch constraints did not converge to the requested dimensions")
    sketch = sketch.assemble()
    area_mm2 = sketch.val().Area()
    if not math.isclose(area_mm2, width * height, rel_tol=1e-7, abs_tol=1e-7):
        raise ValueError("Solved sketch area disagrees with the dimensional reference")
    return sketch, {"width_m": width_m, "height_m": height_m, "area_m2": area_mm2 * 1e-6,
                    "solver_cost": float(sketch._solve_status["cost"])}


def constrained_rectangle(width_m: float, height_m: float) -> dict:
    return _rectangle_sketch(width_m, height_m)[1]


def solid_mass_properties(shape, density_kg_m3: float | None) -> dict:
    """OCCT central tensor in fixed CAD axes; geometry units are millimetres."""
    import cadquery as cq
    import numpy as np
    from physics.dynamics.rigid_body import RigidBody

    if not shape.isValid() or len(shape.Solids()) != 1 or shape.Volume() <= 0:
        raise ValueError("Mass properties require one valid positive-volume solid")
    center = shape.Center()
    volume = shape.Volume() * 1e-9
    mass, inertia = None, None
    if density_kg_m3 is not None:
        if not math.isfinite(density_kg_m3) or density_kg_m3 <= 0:
            raise ValueError("Uniform density must be finite and positive")
        # Unit-density volume inertia has dimensions length^5, not length^2.
        inertia = np.asarray(cq.Shape.matrixOfInertia(shape)) * density_kg_m3 * 1e-15
        mass = volume * density_kg_m3
        RigidBody(mass, inertia)  # reject nonfinite or non-positive-definite inputs
    return {"assumption": "homogeneous_uniform_density", "frame": "local_right_handed_z_up",
            "volume_m3": volume, "material_density_kg_m3": density_kg_m3,
            "center_of_mass_m": [center.x / 1000, center.y / 1000, center.z / 1000],
            "mass_kg": mass, "inertia_about_cog_kg_m2": inertia.tolist() if inertia is not None else None,
            "physical_validation_status": "unvalidated"}


def blade_solid(recipe: BladeRecipe):
    import cadquery as cq

    profiles = []
    for station in recipe.stations:
        upper, lower = [], []
        angle = math.radians(station.twist_deg)
        for index in range(recipe.profile_samples + 1):
            u = 0.5 * (1 - math.cos(math.pi * index / recipe.profile_samples))
            thickness = 5 * station.thickness_to_chord * (
                0.2969 * math.sqrt(u) - 0.1260 * u - 0.3516 * u**2
                + 0.2843 * u**3 - 0.1036 * u**4)
            if index in (0, recipe.profile_samples):
                thickness = 0
            chord_position = (u - 0.25) * station.chord_m
            for sign, destination in ((1, upper), (-1, lower)):
                height = sign * thickness * station.chord_m
                y = chord_position * math.cos(angle) - height * math.sin(angle)
                z = chord_position * math.sin(angle) + height * math.cos(angle)
                destination.append(cq.Vector(station.radius_m * 1000, y * 1000, z * 1000))
        profiles.append(cq.Wire.assembleEdges([
            cq.Edge.makeSpline(upper), cq.Edge.makeSpline(list(reversed(lower))),
        ]))
    solid = cq.Solid.makeLoft(profiles, ruled=False)
    if not solid.isValid() or len(solid.Solids()) != 1 or solid.Volume() <= 0:
        raise ValueError("Blade loft did not produce one valid positive-volume solid")
    return solid


def build_blade_project(recipe: BladeRecipe, directory: Path) -> dict:
    """Create a new project directory and publish its manifest after all assets exist."""
    shape = blade_solid(recipe)
    sketch_check = constrained_rectangle(recipe.stations[0].chord_m, recipe.stations[-1].chord_m)
    return _publish_solid(shape, recipe, directory, "blade", sketch_check,
                          "symmetric four-digit thickness distribution with closed trailing edge, spline sampled")


def build_box_project(recipe: BoxRecipe, directory: Path) -> dict:
    import cadquery as cq

    sketch, check = _rectangle_sketch(recipe.width_m, recipe.height_m)
    # Extrude the solved face itself, so the constraints actually feed the solid.
    shape = cq.Solid.extrudeLinear(sketch.val(), cq.Vector(0, 0, recipe.depth_m * 1000))
    return _publish_solid(shape, recipe, directory, "body", check, "extruded constrained rectangle")


def _publish_solid(shape, recipe, directory: Path, stem: str, sketch_check: dict, profile: str) -> dict:
    import cadquery as cq

    properties = solid_mass_properties(shape, recipe.material_density_kg_m3)
    directory.mkdir(parents=True, exist_ok=False)
    assets_dir = directory / "assets"
    assets_dir.mkdir()
    step_path = assets_dir / f"{stem}.step"
    cq.Workplane(obj=shape).export(str(step_path), unit="MM")
    imported = cq.importers.importStep(str(step_path)).val()
    if not imported.isValid() or not math.isclose(imported.Volume(), shape.Volume(), rel_tol=1e-7):
        raise ValueError("STEP round trip changed the solid's volume")
    vertices, triangles = shape.tessellate(recipe.mesh_deflection_m * 1000, 0.1)
    if len(triangles) > 100000 or len(vertices) > 100000:
        raise ValueError("Tessellation exceeds the CAD prototype display budget; choose a coarser mesh")
    mesh = {
        "units": "m", "frame": "local_right_handed_z_up",
        "source_asset_id": f"{stem}_exact", "source_sha256": sha256(step_path.read_bytes()).hexdigest(),
        "chordal_deflection_m": recipe.mesh_deflection_m, "angular_deflection_rad": 0.1,
        "vertices_m": [[point.x / 1000, point.y / 1000, point.z / 1000] for point in vertices],
        "triangles": [list(face) for face in triangles],
    }
    volume_m3 = shape.Volume() * 1e-9
    repository = Path(__file__).resolve().parents[2]
    metadata = {
        "recipe": recipe.model_dump(mode="json"),
        "profile": profile, "recipe_type": "box_1" if isinstance(recipe, BoxRecipe) else "blade_1",
        "exact_geometry_asset_id": f"{stem}_exact", "mass_properties": properties,
        "source_length_unit": "m", "cad_kernel_length_unit": "mm",
        "volume_m3": volume_m3,
        "uniform_density_mass_estimate_kg": (
            volume_m3 * recipe.material_density_kg_m3 if recipe.material_density_kg_m3 else None),
        "cadquery_version": version("cadquery"), "ocp_version": version("cadquery-ocp"),
        "adapter_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "dependency_lock_sha256": sha256((repository / "apps/desktop/requirements-cad.lock").read_bytes()).hexdigest(),
        "constraint_check": sketch_check, "physical_validation_status": "unvalidated",
    }
    mesh_path, recipe_path = assets_dir / f"{stem}.mesh.json", assets_dir / f"{stem}.recipe.json"
    mesh_path.write_text(json.dumps(mesh, allow_nan=False, separators=(",", ":")), encoding="utf-8")
    recipe_path.write_text(json.dumps(metadata, allow_nan=False, indent=2) + "\n", encoding="utf-8")
    assets = []
    for identity, path, role in (
        (f"{stem}_exact", step_path, "exact_geometry"),
        (f"{stem}_mesh", mesh_path, "display_mesh"),
        (f"{stem}_recipe", recipe_path, "parametric_source"),
    ):
        digest = sha256(path.read_bytes()).hexdigest()
        # Generated revisions can share a destination without replacing earlier bytes.
        stored = assets_dir / digest / path.name
        stored.parent.mkdir(exist_ok=True)
        path.replace(stored)
        assets.append(GeometryAsset(id=identity, path=stored.relative_to(directory).as_posix(),
                                    sha256=digest, role=role))
    project = EngineeringProject(
        id=uuid4(), name=recipe.name, aircraft_family="multirotor",
        vehicle=AssemblyVehicle(nodes=[
            AssemblyNode(id=stem, name=recipe.name, geometry_asset_id=f"{stem}_mesh",
                         component_reference=f"cad-recipe:{stem}_recipe")]),
        assets=assets,
    )
    project_path = directory / "project.json"
    temporary = directory / ".project.json.tmp"
    temporary.write_bytes(project.canonical_bytes())
    temporary.replace(project_path)
    return {"project": project.model_dump(mode="json"), "project_path": str(project_path.resolve()),
            "project_sha256": project.fingerprint(), "geometry": metadata}
