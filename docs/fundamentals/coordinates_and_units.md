# Coordinates, units and time

Canonical conventions for the frozen [WP1–WP3 contracts](../contracts/README.md).
These describe the existing engineering implementation; source data must carry its own
declared conversion. A matching field name is insufficient to infer a frame.

## Engineering and display

Store SI: m, kg, s, N, N·m, Pa, V, A, J, K and radians. Explicit legacy boundaries
include CAD `twist_deg`, telemetry RPM and battery Ah: rad = deg·π/180,
rad/s = RPM·2π/60, C = Ah·3600. Celsius needs a 273.15 offset for absolute K;
temperature differences have the same numerical size. Preserve original units too.

World **E** is local right-handed Z-up; body **B** is X-forward/Y-left/Z-up (FLU).
Z-up alone does not establish geodetic ENU: register origin, heading and gravity.
The 13-state rigid body is `[r_E(3), v_E(3), q_EB(4), omega_B(3)]`.
`q_EB = [w,x,y,z]` is an active Hamilton unit quaternion: `v_E = R(q_EB) v_B`.
Hamilton multiplication applies the right operand first. `q` and `−q` are the same
orientation; compare shortest rotation angle, not component signs or wrapped Euler angles.

For geodetically aligned source axes, these matrices map column vectors:

```text
ENU from NED: N = [[0,1,0], [1,0,0], [0,0,-1]]
FLU from FRD: B = [[1,0,0], [0,-1,0], [0,0,-1]]
Godot from E: S = [[1,0,0], [0,0,1], [0,-1,0]]
```

All are proper orthogonal rotations; inverse = transpose, determinant +1. Thus
Godot position/force is `(x,z,−y)`. Godot stores quaternion components `xyzw`:
the existing adapter maps engineering `(w,x,y,z)` to `(x,z,−y,w)`.
This is basis conjugation `R_G = S R_EB Sᵀ`, with both world and body bases changed.
For a NED/FRD source, the general rule is `R_new = A R_old B⁻¹`, using the
separately declared world and body changes. Do not apply a vector permutation to
four quaternion components or assume a source's active/passive convention.
Transform covariance as `C_new = T C_old Tᵀ`, including cross blocks consistently.

Godot Y-up and quaternion storage are documented in the
[Godot transforms guide](https://docs.godotengine.org/en/stable/tutorials/3d/using_transforms.html)
and [Quaternion API](https://docs.godotengine.org/en/stable/classes/class_quaternion.html).
PX4's [frame conversion implementation](https://github.com/PX4/px4_ros_com/blob/main/include/px4_ros_com/frame_transforms.h)
provides an independent NED/ENU and FRD/FLU reference; its message semantics must
still be checked for each imported stream.

## Clocks and measurements

Declare simulation time, controller/sample time, wall clock, epoch, sample interval,
gaps, synchronization and clock uncertainty. Specific force is not inertial acceleration:
the source attitude/gravity convention must be known before conversion. No fitted
time shifts, guessed timestamps, silent axis alignment or reconstructed missing channels.
Unknown origin, calibration, frame or time basis makes the affected comparison inconclusive.

## Executable verification

Existing implementation: `packages/physics/dynamics/quaternion.py`, `rigid_body.py`,
`apps/desktop/main.gd` (assembly/telemetry quaternion construction and vector adapters).
[Coordinate round trips](../../tests/physics/test_coordinate_contract.py) verify basis,
NED/ENU gravity, Hamilton composition, Godot quaternion conjugation and inverse round trips.
[Quaternion tests](../../tests/physics/test_quaternion.py) verify analytic rotations;
[rigid-body tests](../../tests/physics/test_rigid_body.py) verify dynamics.
These are code verification, not instrument calibration or physical validation.
