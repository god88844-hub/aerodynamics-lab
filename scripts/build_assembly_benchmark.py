"""Publish a new 200-part CAD display workload, never a validated aircraft."""

from collections import Counter
from hashlib import sha256
import argparse
import json
import math
from pathlib import Path
import sys
import tempfile
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/api"), str(ROOT / "packages"), str(ROOT / "packages/shared-schemas")]

from aeroforge_schemas.cad import BladeRecipe, BoxRecipe
from aeroforge_schemas.project import AssemblyNode, AssemblyVehicle, EngineeringProject, GeometryAsset
from app.services.project_assets import verify_assets
from desktop_worker.io import json_bytes, write_result
from geometry.cad_backend import build_blade_project, build_box_project


def build(destination: Path) -> EngineeringProject:
    destination.mkdir(parents=True, exist_ok=False)
    boxes = {
        "plate": (0.4, 0.3, 0.006, 1600), "arm": (0.55, 0.035, 0.035, 1600),
        "motor": (0.055, 0.055, 0.045, 2700), "pack": (0.10, 0.05, 0.035, 2000),
        "board": (0.035, 0.025, 0.003, 1850), "fastener": (0.004, 0.004, 0.014, 7800),
    }
    recipes = {key: BoxRecipe(name=f"Benchmark {key}", width_m=w, height_m=h, depth_m=d,
                              material_density_kg_m3=rho) for key, (w, h, d, rho) in boxes.items()}
    recipes["blade"] = BladeRecipe.model_validate_json((ROOT / "data/cad/blade-example.json").read_bytes())
    assets, meshes, recipe_ids = [], {}, {}
    with tempfile.TemporaryDirectory(prefix="lab-assembly-") as scratch:
        for kind, recipe in recipes.items():
            builder = build_blade_project if kind == "blade" else build_box_project
            result = builder(recipe, Path(scratch) / kind)
            old = result["project"]["assets"]
            identities = {item["id"]: f"{kind}_{item['id']}" for item in old}
            for item in old:
                source = Path(result["project_path"]).parent / item["path"]
                content = source.read_bytes()
                if item["role"] != "exact_geometry":
                    document = json.loads(content)
                    reference = "source_asset_id" if item["role"] == "display_mesh" else "exact_geometry_asset_id"
                    document[reference] = identities[document[reference]]
                    content = json_bytes(document)
                digest = sha256(content).hexdigest()
                relative = f"assets/{digest}/{source.name}"
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
                identity = identities[item["id"]]
                assets.append(GeometryAsset(id=identity, path=relative, sha256=digest, role=item["role"]))
                if item["role"] == "display_mesh":
                    meshes[kind] = identity
                if item["role"] == "parametric_source":
                    recipe_ids[kind] = identity
    nodes = []

    def add(kind, position, angle=0):
        nodes.append(AssemblyNode(id=f"part_{len(nodes):03d}", name=f"{kind} {len(nodes):03d}",
                     geometry_asset_id=meshes[kind], component_reference="cad-recipe:" + recipe_ids[kind],
                     position_m=position, orientation_wxyz=(math.cos(angle / 2), 0, 0, math.sin(angle / 2))))

    for height in (0, 0.05):
        add("plate", (-0.2, -0.15, height))
    for index in range(6):
        angle = index * math.tau / 6
        radial = lambda radius: (radius * math.cos(angle), radius * math.sin(angle))
        x, y = radial(0.1)
        add("arm", (x, y, 0.015), angle)
        x, y = radial(0.65)
        add("motor", (x - 0.0275, y - 0.0275, 0.05))
        for opposite in (0, math.pi):
            add("blade", (x, y, 0.10), angle + opposite)
        add("pack", (-0.15 + (index % 3) * 0.10, -0.07 + (index // 3) * 0.08, -0.04))
    for index in range(8):
        add("board", (-0.08 + (index % 4) * 0.045, -0.035 + (index // 4) * 0.05, 0.06))
    for layer in range(2):
        for row in range(8):
            for column in range(10):
                add("fastener", (-0.18 + column * 0.039, -0.13 + row * 0.037, layer * 0.05))
    project = EngineeringProject(id=uuid5(NAMESPACE_URL, "aerodynamics-lab:assembly-benchmark-200:1"),
               name="200-part conceptual hexacopter display benchmark", aircraft_family="multirotor",
               vehicle=AssemblyVehicle(nodes=nodes), assets=assets)
    verify_assets(project, destination)
    write_result(destination / "fixture.json", {"fixture_version": "assembly_200_1", "part_count": len(nodes),
        "categories": dict(Counter(node.name.split()[0] for node in nodes)),
        "project_sha256": project.fingerprint(), "generator_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "recipes": {key: recipe.model_dump(mode="json") for key, recipe in recipes.items()},
        "physical_validation_status": "unvalidated",
        "scope": "Constructed editor workload. Box proxies, assumed materials and placements; no flight, clearance, assembly mass or hardware validation."})
    (destination / "project.json").write_bytes(project.canonical_bytes())
    return project


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, help="New directory; existing data are never replaced")
    print(build(parser.parse_args().destination).fingerprint())
