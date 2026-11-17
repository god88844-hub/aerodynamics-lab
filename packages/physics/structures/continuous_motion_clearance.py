"""M28.9 continuous-time rotor/obstacle clearance lower bound from sampled centers.

A nearest-endpoint bound guarantees separation throughout each time interval
ONLY IF the declared Euclidean center speeds actually hard-bound all motion
between samples. Original trajectory and speed bounds are not authenticated.
This is not a CAD collision solver, flight test, or airworthiness evidence.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence

from aeroforge_schemas.design import DroneDesign
from physics.structures.swept_cylinder_clearance import _finite, _vector, _source

_ID = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


def _xyz(value: object, name: str) -> tuple[float, float, float]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != 3:
        raise ValueError(f"{name}: finite 3D center required")
    numbers = []
    for entry in value:
        if isinstance(entry, bool) or not isinstance(entry, (int, float)):
            raise ValueError(f"{name}: finite 3D center required")
        try:
            x = float(entry)
        except (ValueError, OverflowError) as exc:
            raise ValueError(f"{name}: finite 3D center required") from exc
        if not math.isfinite(x):
            raise ValueError(f"{name}: finite 3D center required")
        numbers.append(x)
    return (numbers[0], numbers[1], numbers[2])


def screen_continuous_motion_clearance(
    design: DroneDesign,
    *,
    rotor_diameters_m: Sequence[float],
    rotor_swept_heights_m: Sequence[float],
    rotor_diameter_hard_bounds_m: Sequence[float],
    rotor_center_position_hard_bounds_m: Sequence[float],
    rotor_center_speed_hard_bounds_m_per_s: Sequence[float],
    obstacle_envelopes: Sequence[Mapping],
    time_samples: Sequence[Mapping],
    minimum_declared_clearance_m: float,
    trajectory_source: str,
    hard_bounds_source: str,
    obstacle_inventory_source: str,
) -> dict:
    """Conservative union-of-spheres pair gap over a declared sampled timeline.

    For rotor i and obstacle j in interval [t0,t1], define nominal endpoint
    distances D0,D1 and full relative-center Lipschitz hard bound V_i+V_j.
    Each unknown time is within dt/2 of at least one endpoint, so the
    continuous distance is no less than min(D0,D1) - (V_i+V_j)*dt/2.
    Subtract both entire object sphere radii and hard position/radius bounds.
    """
    n = len(design.rotors)
    if not 2 <= n <= 32:
        raise ValueError("2–32 rotors required")
    trajectory_source = _source(trajectory_source, "trajectory_source")
    hard_bounds_source = _source(hard_bounds_source, "hard_bounds_source")
    obstacle_inventory_source = _source(obstacle_inventory_source, "obstacle_inventory_source")
    clearance = _finite(minimum_declared_clearance_m, "minimum_declared_clearance_m")
    d = _vector(rotor_diameters_m, n, "rotor_diameters_m", strictly_positive=True)
    h = _vector(rotor_swept_heights_m, n, "rotor_swept_heights_m", strictly_positive=True)
    du = _vector(rotor_diameter_hard_bounds_m, n, "rotor_diameter_hard_bounds_m")
    rcu = _vector(rotor_center_position_hard_bounds_m, n, "rotor_center_position_hard_bounds_m")
    rv = _vector(rotor_center_speed_hard_bounds_m_per_s, n, "rotor_center_speed_hard_bounds_m_per_s")
    radii = []
    for i in range(n):
        outer_d = d[i] + du[i]
        if not math.isfinite(outer_d):
            raise ValueError("rotor max diameter overflow")
        radius = math.hypot(outer_d / 2, h[i] / 2)
        if not math.isfinite(radius):
            raise ValueError("rotor swept radius overflow")
        radii.append(radius)
    if isinstance(obstacle_envelopes, (str, bytes)) or not isinstance(obstacle_envelopes, Sequence) or not 1 <= len(obstacle_envelopes) <= 128:
        raise ValueError("1–128 declared obstacle envelopes required")
    obstacle_data = []
    seen = set()
    required = {
        "obstacle_id", "outer_radius_m", "outer_radius_hard_bound_m",
        "center_position_hard_bound_m", "center_speed_hard_bound_m_per_s",
    }
    for obj in obstacle_envelopes:
        if not isinstance(obj, Mapping) or set(obj) != required:
            raise ValueError("obstacle envelopes require exact dimension/motion hard bounds")
        oid = obj["obstacle_id"]
        if not isinstance(oid, str) or not _ID.fullmatch(oid) or oid in seen:
            raise ValueError("invalid or duplicate obstacle ID")
        seen.add(oid)
        radius = _finite(obj["outer_radius_m"], "outer_radius_m")
        if radius <= 0:
            raise ValueError("obstacle radius must be positive")
        radius_u = _finite(obj["outer_radius_hard_bound_m"], "outer_radius_hard_bound_m")
        center_u = _finite(obj["center_position_hard_bound_m"], "center_position_hard_bound_m")
        velocity = _finite(obj["center_speed_hard_bound_m_per_s"], "center_speed_hard_bound_m_per_s")
        full_radius = radius + radius_u
        if not math.isfinite(full_radius):
            raise ValueError("obstacle dimension overflow")
        obstacle_data.append((oid, full_radius, center_u, velocity))
    m = len(obstacle_data)
    if isinstance(time_samples, (str, bytes)) or not isinstance(time_samples, Sequence) or not 2 <= len(time_samples) <= 500:
        raise ValueError("2–500 exact time samples required")
    samples = []
    last_t = -1.
    for sample in time_samples:
        if not isinstance(sample, Mapping) or set(sample) != {"time_s", "rotor_centers_m", "obstacle_centers_m"}:
            raise ValueError("time samples require exact time and all object centers")
        t = _finite(sample["time_s"], "time_s")
        if t <= last_t:
            raise ValueError("sample timestamps must strictly increase")
        if not samples and t != 0:
            raise ValueError("trajectory must begin at time zero")
        last_t = t
        rc, oc = sample["rotor_centers_m"], sample["obstacle_centers_m"]
        if isinstance(rc, (str, bytes)) or not isinstance(rc, Sequence) or len(rc) != n:
            raise ValueError("every timeline sample requires exactly one center per rotor")
        if isinstance(oc, (str, bytes)) or not isinstance(oc, Sequence) or len(oc) != m:
            raise ValueError("every timeline sample requires exactly one center per declared obstacle")
        samples.append((t, [_xyz(v, "rotor center") for v in rc],
                        [_xyz(v, "obstacle center") for v in oc]))
    # The declared speed hard bound must at least make adjacent reported
    # endpoint centers feasible after allowing both hard position errors.
    for k in range(len(samples) - 1):
        t0, r0, o0 = samples[k]
        t1, r1, o1 = samples[k+1]
        dt = t1-t0
        for i in range(n):
            displacement = math.dist(r0[i], r1[i])
            feasible = rv[i]*dt + 2*rcu[i]
            if not math.isfinite(displacement) or not math.isfinite(feasible):
                raise ValueError("rotor displacement/speed accumulation overflow")
            if displacement > feasible + 1e-12:
                raise ValueError("rotor declared center speed bound contradicts sampled endpoints")
        for j, (_, _, center_u, velocity) in enumerate(obstacle_data):
            displacement = math.dist(o0[j], o1[j])
            feasible = velocity*dt + 2*center_u
            if not math.isfinite(displacement) or not math.isfinite(feasible):
                raise ValueError("obstacle displacement/speed accumulation overflow")
            if displacement > feasible + 1e-12:
                raise ValueError("obstacle declared center speed bound contradicts sampled endpoints")
    pair_summaries = []
    worst = math.inf
    for i in range(n):
        for j, (name, obstacle_radius, center_u, speed_u) in enumerate(obstacle_data):
            pair_min = math.inf
            pair_worst_interval = -1
            for k in range(len(samples) - 1):
                ta, ra, oa = samples[k]
                tb, rb, ob = samples[k+1]
                dt = tb-ta
                first = math.dist(ra[i], oa[j])
                last = math.dist(rb[i], ob[j])
                rel_speed = rv[i] + speed_u
                travel = rel_speed * dt/2
                extent = radii[i] + obstacle_radius + rcu[i] + center_u
                if not all(math.isfinite(x) for x in (first, last, rel_speed, travel, extent)):
                    raise ValueError("continuous clearance hard-bound arithmetic overflow")
                lower = max(0., min(first, last) - travel - extent)
                if lower < pair_min:
                    pair_min = lower
                    pair_worst_interval = k
            worst = min(worst, pair_min)
            meets = pair_min > 0 and pair_min >= clearance
            pair_summaries.append({
                "rotor_index": i, "obstacle_id": name,
                "minimum_analytical_continuous_gap_lower_m": pair_min,
                "governing_interval_index": pair_worst_interval,
                "declared_full_interval_clearance_met": meets,
                "collision_or_contact_cannot_be_excluded": not meets,
            })
    passed = all(p["declared_full_interval_clearance_met"] for p in pair_summaries)
    return {
        "status": ("ANALYTICAL_DECLARED_CONTINUOUS_TRAJECTORY_NONINTERSECTION_ONLY"
                   if passed else "DECLARED_CONTINUOUS_TRAJECTORY_CLEARANCE_NOT_ESTABLISHED"),
        "design_name": design.name,
        "time_span_s": samples[-1][0],
        "sample_count": len(samples),
        "declared_obstacle_count": m,
        "minimum_continuous_analytical_gap_lower_m": worst,
        "analytical_screen_passed": passed,
        "pair_summaries": pair_summaries,
        "trajectory_source_operator_declared": trajectory_source,
        "hard_bounds_source_operator_declared": hard_bounds_source,
        "obstacle_inventory_source_operator_declared": obstacle_inventory_source,
        "continuous_speed_hard_bounds_independently_verified": False,
        "actual_airframe_obstacle_inventory_authenticated": False,
        "real_world_dynamic_collision_validation_established": False,
        "flight_release_authorized": False,
        "limitations": [
            "Full-time clearance valid only if declared speed/radius/center error bounds enclose all motion",
            "The sampled trajectory, obstacle count and finite time horizon are operator supplied",
            "Bounding spheres are conservative; missing actual hardware and changing shape are unmodeled",
            "No independent physical clearance tests, qualified CAD or aircraft flightworthiness assessment",
        ],
    }
