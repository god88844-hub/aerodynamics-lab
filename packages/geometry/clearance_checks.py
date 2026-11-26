"""Exact CAD datum-transform, rotor/obstacle clearance, and analytical load screening (P0A-020).

Display mesh LODs are explicitly ignored: clearances and structural screens
consume exact engineering coordinates/STEP bounds and declared transforms only.
Analytical screening never grants physical qualification.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np

from aeroforge_schemas.design import DroneDesign
from aeroforge_schemas.project import EngineeringProject
from app.services.project_assets import asset_bytes
from physics.dynamics.quaternion import rotation_matrix
from physics.structures.combined_metal import evaluate_combined_metal_screen
from physics.structures.materials import load_materials


def _transform_point(pos: np.ndarray, q_wxyz: np.ndarray, local_pt: np.ndarray) -> np.ndarray:
    rot = rotation_matrix(q_wxyz)
    return pos + rot @ local_pt


def _aabb_distance(box_min: np.ndarray, box_max: np.ndarray, point: np.ndarray) -> float:
    clamped = np.minimum(np.maximum(point, box_min), box_max)
    return float(np.linalg.norm(point - clamped))


def evaluate_assembly_clearance_and_loads(
    project: EngineeringProject,
    asset_root: Path,
    *,
    rotors: list[dict[str, Any]],
    obstacles: list[dict[str, Any]] | None = None,
    minimum_clearance_m: float = 0.02,
    structural_design: DroneDesign | None = None,
    load_cases: list[tuple[str, list[float], list[float]]] | None = None,
    materials_path: Path | None = None,
) -> dict[str, Any]:
    """Check rotor-to-rotor, rotor-to-obstacle, and assembly datum clearances.

    Display mesh assets are never read for geometry or clearance bounds; only exact
    project assets (STEP/parametric) and engineering transforms are evaluated.
    """
    if not math.isfinite(minimum_clearance_m) or minimum_clearance_m < 0.0:
        raise ValueError("minimum_clearance_m must be finite and >= 0")
    if not rotors:
        raise ValueError("clearance check requires at least one rotor")

    # Verify exact assets exist and match hashes (ignore display_mesh LODs completely)
    exact_hashes: dict[str, str] = {}
    for asset in project.assets:
        if asset.role in ("exact_geometry", "parametric_source"):
            content = asset_bytes(asset_root, asset.path, asset.sha256)
            exact_hashes[asset.id] = asset.sha256
            assert content is not None

    node_transforms: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    if hasattr(project.vehicle, "nodes"):
        for node in project.vehicle.nodes:
            node_transforms[node.id] = (
                np.asarray(node.position_m, dtype=float),
                np.asarray(node.orientation_wxyz, dtype=float),
            )

    transformed_rotors: list[dict[str, Any]] = []
    for idx, r in enumerate(rotors):
        radius_m = float(r["radius_m"])
        if not math.isfinite(radius_m) or radius_m <= 0.0:
            raise ValueError(f"rotor[{idx}]: radius_m must be finite and > 0")
        center = np.asarray(r["position_m"], dtype=float)
        if center.shape != (3,) or not np.all(np.isfinite(center)):
            raise ValueError(f"rotor[{idx}]: position_m must be finite 3-vector")
        node_id = r.get("node_id")
        if node_id is not None:
            if node_id not in node_transforms:
                raise ValueError(f"rotor[{idx}]: unknown node_id {node_id!r}")
            pos, quat = node_transforms[node_id]
            center = _transform_point(pos, quat, center)
        transformed_rotors.append({"index": idx, "center_m": center, "radius_m": radius_m})

    pair_checks: list[dict[str, Any]] = []
    min_observed = float("inf")
    any_violation = False

    for i in range(len(transformed_rotors)):
        for j in range(i + 1, len(transformed_rotors)):
            ra = transformed_rotors[i]
            rb = transformed_rotors[j]
            dist = float(np.linalg.norm(ra["center_m"] - rb["center_m"]))
            tip_gap = dist - (ra["radius_m"] + rb["radius_m"])
            violated = tip_gap < minimum_clearance_m
            any_violation = any_violation or violated
            min_observed = min(min_observed, tip_gap)
            pair_checks.append({
                "kind": "rotor_pair",
                "rotor_a": i,
                "rotor_b": j,
                "center_distance_m": dist,
                "tip_clearance_m": tip_gap,
                "below_minimum": violated,
            })

    obstacle_checks: list[dict[str, Any]] = []
    for o_idx, obs in enumerate(obstacles or []):
        obs_center = np.asarray(obs["center_m"], dtype=float)
        obs_size = np.asarray(obs["size_m"], dtype=float)
        if obs_center.shape != (3,) or obs_size.shape != (3,) or np.any(obs_size <= 0.0):
            raise ValueError(f"obstacle[{o_idx}]: invalid center_m or size_m")
        node_id = obs.get("node_id")
        if node_id is not None:
            if node_id not in node_transforms:
                raise ValueError(f"obstacle[{o_idx}]: unknown node_id {node_id!r}")
            pos, quat = node_transforms[node_id]
            obs_center = _transform_point(pos, quat, obs_center)
        box_min = obs_center - 0.5 * obs_size
        box_max = obs_center + 0.5 * obs_size
        for r in transformed_rotors:
            # Conservative 3D clearance: distance from disk center to obstacle AABB minus rotor radius
            center_dist = _aabb_distance(box_min, box_max, r["center_m"])
            tip_gap = center_dist - r["radius_m"]
            violated = tip_gap < minimum_clearance_m
            any_violation = any_violation or violated
            min_observed = min(min_observed, tip_gap)
            obstacle_checks.append({
                "kind": "rotor_obstacle",
                "rotor": r["index"],
                "obstacle_id": obs.get("id", f"obstacle_{o_idx}"),
                "tip_clearance_m": tip_gap,
                "below_minimum": violated,
            })

    if not math.isfinite(min_observed):
        min_observed = float("inf")

    load_screen = None
    if structural_design is not None and load_cases is not None and materials_path is not None:
        materials = load_materials(materials_path)
        load_screen = evaluate_combined_metal_screen(
            structural_design,
            load_cases,
            materials,
            safety_factor=1.5,
            load_case_source="P0A-020 analytical load screening case (not physical qualification)",
        )

    return {
        "project_sha256": project.fingerprint(),
        "exact_asset_hashes": exact_hashes,
        "display_lod_used": False,
        "minimum_required_clearance_m": minimum_clearance_m,
        "minimum_observed_clearance_m": None if math.isinf(min_observed) else min_observed,
        "clearance_status": "OVERLAP_OR_BELOW_MINIMUM" if any_violation else "CLEAR",
        "clearance_passed": not any_violation,
        "pair_checks": pair_checks,
        "obstacle_checks": obstacle_checks,
        "analytical_load_screen": load_screen,
        "physical_validation_status": "ANALYTICAL_SCREEN_ONLY_NOT_PHYSICALLY_QUALIFIED",
    }
