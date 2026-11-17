"""M28.10 full-interval rotor-rotor outer-sphere clearance under hard speed bounds.

Even for arbitrary axis orientation, each declared maximum swept cylindrical
rotor envelope fits an enclosing sphere. This screen establishes only a
sufficient geometric separation *conditional on truthful upper bounds*.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from aeroforge_schemas.design import DroneDesign
from physics.structures.swept_cylinder_clearance import _finite, _vector, _source


def _xyz(raw: object) -> tuple[float, float, float]:
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence) or len(raw) != 3:
        raise ValueError("each rotor center must contain three finite coordinates")
    xyz = []
    for x in raw:
        if isinstance(x, bool) or not isinstance(x, (int, float)):
            raise ValueError("each rotor center must contain three finite coordinates")
        try:
            z = float(x)
        except (ValueError, OverflowError) as exc:
            raise ValueError("each rotor center must contain three finite coordinates") from exc
        if not math.isfinite(z):
            raise ValueError("each rotor center must contain three finite coordinates")
        xyz.append(z)
    return tuple(xyz)


def screen_continuous_rotor_pair_clearance(
    design: DroneDesign,
    *,
    installed_rotor_diameters_m: Sequence[float],
    maximum_swept_heights_m: Sequence[float],
    diameter_hard_bounds_m: Sequence[float],
    center_position_hard_bounds_m: Sequence[float],
    center_speed_hard_bounds_m_per_s: Sequence[float],
    time_samples: Sequence[Mapping],
    minimum_declared_pair_gap_m: float,
    trajectory_source: str,
    geometry_hard_bound_source: str,
    rotor_center_speed_source: str,
) -> dict:
    """Lower bound every instant, not only recorded sample instants.

    If |relative center speed| <= v_i+v_j over interval dt, each interior
    point is at most dt/2 away from one endpoint, and distance >=
    min(D_start,D_end) - (v_i+v_j)*dt/2.
    Subtract entire enclosing sphere radii and both hard center position
    error bounds, without interpolation or extrapolation.
    """
    n = len(design.rotors)
    if not 2 <= n <= 32:
        raise ValueError("2–32 rotors required")
    trajectory_source = _source(trajectory_source, "trajectory_source")
    geometry_hard_bound_source = _source(geometry_hard_bound_source, "geometry_hard_bound_source")
    rotor_center_speed_source = _source(rotor_center_speed_source, "rotor_center_speed_source")
    gap = _finite(minimum_declared_pair_gap_m, "minimum_declared_pair_gap_m")
    d = _vector(installed_rotor_diameters_m, n, "installed_rotor_diameters_m", strictly_positive=True)
    h = _vector(maximum_swept_heights_m, n, "maximum_swept_heights_m", strictly_positive=True)
    du = _vector(diameter_hard_bounds_m, n, "diameter_hard_bounds_m")
    cu = _vector(center_position_hard_bounds_m, n, "center_position_hard_bounds_m")
    v = _vector(center_speed_hard_bounds_m_per_s, n, "center_speed_hard_bounds_m_per_s")
    radii = []
    for i in range(n):
        max_d = d[i] + du[i]
        if not math.isfinite(max_d):
            raise ValueError("rotor diameter hard bound accumulation overflow")
        r = math.hypot(max_d/2, h[i]/2)
        if not math.isfinite(r):
            raise ValueError("rotor outer sphere radius overflow")
        radii.append(r)
    if isinstance(time_samples, (str, bytes)) or not isinstance(time_samples, Sequence) or not 2 <= len(time_samples) <= 500:
        raise ValueError("2–500 time samples required")
    timeline = []
    prev = -1.
    for entry in time_samples:
        if not isinstance(entry, Mapping) or set(entry) != {"time_s", "rotor_centers_m"}:
            raise ValueError("time sample requires exact timestamp and rotor centers")
        t = _finite(entry["time_s"], "time_s")
        if t <= prev or (prev < 0 and t != 0):
            raise ValueError("time starts at zero and strictly increases")
        centers = entry["rotor_centers_m"]
        if isinstance(centers, (str, bytes)) or not isinstance(centers, Sequence) or len(centers) != n:
            raise ValueError("exactly one 3D center per rotor required")
        timeline.append((t, [_xyz(p) for p in centers]))
        prev = t
    # Detect an internally impossible set of supplied center trajectories,
    # allowing both endpoint-position hard errors in the speed feasibility.
    for k in range(len(timeline)-1):
        t0, c0 = timeline[k]
        t1, c1 = timeline[k+1]
        dt = t1-t0
        for i in range(n):
            displacement = math.dist(c0[i], c1[i])
            possible = v[i]*dt + 2*cu[i]
            if not math.isfinite(displacement) or not math.isfinite(possible):
                raise ValueError("rotor center speed arithmetic overflow")
            if displacement > possible+1e-12:
                raise ValueError("rotor center movement contradicts declared speed hard bound")
    pairs = []
    min_all = math.inf
    for i in range(n):
        for j in range(i+1,n):
            min_pair = math.inf
            governing = -1
            for k in range(len(timeline)-1):
                t0, c0 = timeline[k]
                t1, c1 = timeline[k+1]
                dt = t1-t0
                dist0 = math.dist(c0[i], c0[j])
                dist1 = math.dist(c1[i], c1[j])
                travel = (v[i]+v[j])*dt/2
                extent = radii[i]+radii[j]+cu[i]+cu[j]
                if not all(math.isfinite(x) for x in (dist0,dist1,travel,extent)):
                    raise ValueError("rotor pair motion hard bound accumulation overflow")
                separation = max(0.,min(dist0,dist1)-travel-extent)
                if separation < min_pair:
                    min_pair = separation
                    governing = k
            meets = min_pair>0 and min_pair>=gap
            min_all = min(min_all,min_pair)
            pairs.append({
                "rotor_a":i,"rotor_b":j,
                "minimum_conservative_full_interval_pair_gap_m":min_pair,
                "governing_time_interval_index":governing,
                "possible_pair_contact_or_interference":not meets,
                "declared_continuous_time_pair_gap_met":meets,
            })
    passed = all(p["declared_continuous_time_pair_gap_met"] for p in pairs)
    return {
        "status":("ANALYTICAL_CONTINUOUS_ROTOR_PAIR_SEPARATION_ASSUMPTIONS_ONLY"
                  if passed else "CONTINUOUS_ROTOR_PAIR_CLEARANCE_NOT_ESTABLISHED"),
        "design_name":design.name,
        "time_horizon_s":timeline[-1][0],
        "time_sample_count":len(timeline),
        "pair_count":len(pairs),
        "minimum_analytical_full_interval_gap_m":min_all,
        "pairs":pairs,
        "analytical_screen_passed":passed,
        "trajectory_source_operator_declared":trajectory_source,
        "geometry_hard_bound_source_operator_declared":geometry_hard_bound_source,
        "rotor_center_speed_source_operator_declared":rotor_center_speed_source,
        "continuous_rotor_motion_bounds_independently_authenticated":False,
        "actual_rotor_dynamic_collision_test_passed":False,
        "real_world_flightworthiness_established":False,
        "flight_release_authorized":False,
        "limitations":[
            "Rotor actual shape, flex, center travel and speeds are not independently measured",
            "Outer-sphere overlap means insufficient analytical evidence, not proven blade impact",
            "Only declared rotor pairs/time horizon checked; no airframe/obstacle collisions",
            "Physical interference and flight approval require independent actual aircraft evidence",
        ],
    }
