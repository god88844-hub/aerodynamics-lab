"""Frozen exact geometry to an isolated, no-gravity rigid-body torque experiment."""

from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import tempfile

import numpy as np

from aeroforge_schemas.cad import BladeRecipe, BoxRecipe, CadTorqueRequest
from aeroforge_schemas.project import AssemblyVehicle, Environment, Experiment
from app.services.project_assets import asset_bytes
from app.services.run_provenance import capture_provenance
from geometry.cad_backend import solid_mass_properties
from physics.dynamics.quaternion import rotation_matrix
from physics.dynamics.rigid_body import RigidBody, make_state, normalize_state
from physics.integration.rk4 import integrate_fixed

ROOT = Path(__file__).resolve().parents[2]


def _identity() -> dict:
    return {"model": capture_provenance(),
            "cadquery_version": version("cadquery"), "ocp_version": version("cadquery-ocp"),
            "cad_lock_sha256": sha256((ROOT / "apps/desktop/requirements-cad.lock").read_bytes()).hexdigest()}


def _frozen_solid_properties(request: CadTorqueRequest, asset_root: Path) -> dict:
    import cadquery as cq

    project = request.project
    if not isinstance(project.vehicle, AssemblyVehicle) or len(project.vehicle.nodes) != 1:
        raise ValueError("CAD torque prototype requires exactly one solid assembly node")
    if project.environment != Environment() or project.experiment != Experiment():
        raise ValueError("CAD torque prototype requires the default environment and an unassigned flight backend")
    node = project.vehicle.nodes[0]
    if not node.component_reference or not node.component_reference.startswith("cad-recipe:"):
        raise ValueError("CAD node needs a supported parametric recipe reference")
    assets = {asset.id: asset for asset in project.assets}
    # Read and verify once. The kernel uses these frozen bytes, never a later reread.
    frozen = {key: asset_bytes(asset_root, asset.path, asset.sha256) for key, asset in assets.items()}
    recipe_id = node.component_reference.removeprefix("cad-recipe:")
    if recipe_id not in assets or assets[recipe_id].role != "parametric_source":
        raise ValueError("CAD recipe asset is missing")
    metadata = json.loads(frozen[recipe_id])
    recipe_type = metadata.get("recipe_type", "blade_1")  # previous blade adapter
    if recipe_type == "box_1":
        recipe = BoxRecipe.model_validate(metadata["recipe"])
    elif recipe_type == "blade_1":
        recipe = BladeRecipe.model_validate(metadata["recipe"])
    else:
        raise ValueError("Unsupported CAD recipe version")
    exact_id = metadata.get("exact_geometry_asset_id", "blade_exact")
    if exact_id not in assets or assets[exact_id].role != "exact_geometry":
        raise ValueError("Exact geometry asset is missing")
    if node.geometry_asset_id not in assets or assets[node.geometry_asset_id].role != "display_mesh":
        raise ValueError("CAD node needs its linked display geometry")
    display = json.loads(frozen[node.geometry_asset_id])
    if display.get("source_asset_id") != exact_id or display.get("source_sha256") != assets[exact_id].sha256:
        raise ValueError("Display and exact geometry do not share the declared source identity")
    with tempfile.TemporaryDirectory(prefix="lab-solid-") as folder:
        path = Path(folder) / "solid.step"
        path.write_bytes(frozen[exact_id])
        shape = cq.importers.importStep(str(path)).val()
        properties = solid_mass_properties(shape, recipe.material_density_kg_m3)
    # A placed single solid has its tensor rotated, with the CoG translated.
    rotation = rotation_matrix(np.asarray(node.orientation_wxyz))
    properties["center_of_mass_m"] = (
        np.asarray(node.position_m) + rotation @ np.asarray(properties["center_of_mass_m"])).tolist()
    if properties["inertia_about_cog_kg_m2"] is not None:
        tensor = np.asarray(properties["inertia_about_cog_kg_m2"])
        properties["inertia_about_cog_kg_m2"] = (rotation @ tensor @ rotation.T).tolist()
    properties["source_asset_id"] = exact_id
    properties["source_sha256"] = assets[exact_id].sha256
    return properties


def run_cad_torque(request: CadTorqueRequest, asset_root: Path) -> dict:
    # Freeze caller-owned models, and refuse a changing installed model environment.
    request = CadTorqueRequest.model_validate_json(request.model_dump_json())
    identity = _identity()
    properties = _frozen_solid_properties(request, asset_root)
    experiment = request.experiment
    report = {"experiment_kind": "cad_torque_1", "project": request.project.model_dump(mode="json"),
              "project_sha256": request.project.fingerprint(), "experiment": experiment.model_dump(mode="json"),
              "mass_properties": properties, "model_provenance": identity,
              "physical_validation_status": "unvalidated",
              "assumptions": ["homogeneous declared density", "constant rigid solid",
                              "starts at rest at its centre of mass", "constant body-frame applied torque",
                              "gravity disabled", "no aerodynamic, thermal, structural or actuator model"]}
    if properties["mass_kg"] is None:
        report["result"] = {"status": "inconclusive", "reason": "Uniform density is missing; mass and inertia are unknown"}
    else:
        tensor = np.asarray(properties["inertia_about_cog_kg_m2"])
        body = RigidBody(properties["mass_kg"], tensor)
        torque = np.asarray(experiment.torque_body_nm)
        speed_bound = np.linalg.norm(torque) * experiment.duration_s / np.linalg.eigvalsh(tensor)[0]
        if not np.isfinite(speed_bound) or speed_bound * experiment.step_s > 0.1:
            raise ValueError("Requested step is too large for this torque/inertia; reduce step, torque or duration")
        initial = make_state(np.zeros(3), np.zeros(3), [1, 0, 0, 0], np.zeros(3))
        derivative = lambda t, state: body.derivs(state, np.zeros(3), torque, gravity=False)
        times, states = integrate_fixed(derivative, initial, 0, experiment.duration_s,
                                        experiment.step_s, post_step=normalize_state)
        _, fine = integrate_fixed(derivative, initial, 0, experiment.duration_s,
                                  experiment.step_s / 2, post_step=normalize_state)
        if not np.all(np.isfinite(states)) or not np.all(np.isfinite(fine)):
            raise ValueError("Rigid-body integration produced nonfinite state")
        angular_delta = float(np.linalg.norm(states[-1, 10:13] - fine[-1, 10:13]))
        quaternion_delta = float(np.linalg.norm(states[-1, 6:10] - fine[-1, 6:10]))
        if angular_delta > 1e-6 or quaternion_delta > 1e-6:
            raise ValueError("Step-halving agreement exceeds the prototype's 1e-6 numerical thresholds")
        report["numerical_check"] = {"method": "RK4 step halving; endpoint comparison",
                                     "angular_velocity_delta_rad_s": angular_delta,
                                     "quaternion_component_l2_delta": quaternion_delta,
                                     "agreement_threshold": 1e-6,
                                     "note": "numerical consistency, not a physical uncertainty bound"}
        report["result"] = {"status": "completed", "telemetry": {
            "t": times.tolist(), "x": states[:, 0].tolist(), "y": states[:, 1].tolist(),
            "z": states[:, 2].tolist(), "q_wxyz": states[:, 6:10].tolist(),
            "omega_body_rad_s": states[:, 10:13].tolist()}}
    if identity != _identity():
        raise ValueError("Model environment changed during the CAD experiment")
    return report
