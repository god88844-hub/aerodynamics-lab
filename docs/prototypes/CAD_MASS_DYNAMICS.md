# Constrained geometry to rigid-body response

20 November 2026. Related: #100, #101 and #110. This extends the exact-CAD prototype with a supported mathematical geometry-to-physics path. It does not qualify a new aircraft or supply its aerodynamic coefficients.

## Normal workflow

In the desktop, choose **New / edit test body**. Width and height constrain an actual rectangular sketch; depth extrudes the solved face. Optional homogeneous density is an explicit assumption. Rebuild produces a new project and exact/display/recipe assets. This is a bounded parametric-body editor; a general sketch/history editor remains open.

Choose the applied body-Z torque, duration and integration step, then **Run applied-torque experiment**. The worker reads and hashes the project assets once, imports the frozen STEP bytes and recomputes mass, centre of mass and the full central inertia tensor. Stored mass-property caches do not drive the physics. A single placed/rotated solid is supported; multiple-body assemblies and arbitrary recipe adapters are refused.

The existing Python `RigidBody` and RK4 modules integrate the response. This experiment starts at rest at the CoG, with constant body-frame torque and gravity disabled. Aerodynamics, motors, flight control, contact, structural failure and thermal effects are outside this experiment. The ordinary flight-run command still refuses a generic CAD project.

Replay rotates about the computed CoG while retaining the CAD datum. Missing density gives an INCONCLUSIVE result and no invented mass/inertia/trajectory. Known density produces a uniform-density estimate with physical status **unvalidated**.

## Numerical and source contract

OCCT uses millimetres in this adapter. Solid volume scales by `1e-9` into cubic metres. Its unit-density central volume inertia has dimension length to the fifth power, so the SI mass tensor is `I_mm5 * density_kg_m3 * 1e-15`. Tensor axes stay parallel to the CAD axes, and node placement rotates the tensor into assembly axes. Translation moves the CoG without adding a parallel-axis term to a tensor already expressed about that CoG.

The primary [OCCT GProp_GProps reference](https://occt3d.com/dev/doc/refman/html/class_g_prop___g_props.html) specifies the central tensor frame and density/unit consistency. The pinned CadQuery/OCP implementation is checked against analytical box inertia, including a rotated and translated solid. The CadQuery helper's dimensional prose is not used as the unit-conversion specification.

The report freezes the project and experiment and includes source hashes, component data, numerical platform/package versions, CAD package versions and the CAD dependency-lock hash. Changes in the installed model environment during execution cause a refusal. Asset bytes are imported from a temporary frozen copy.

The prototype admits at most 5,000 requested RK4 steps, checks a conservative angular step bound and repeats the integration at half the step. Endpoint angular-velocity and quaternion-component differences must each be at most `1e-6`. These are numerical consistency thresholds for this prototype, not physical measurement tolerances or a calibrated uncertainty interval. Cross-platform bit identity is not claimed.

## Verification and remaining gate

Focused local checks passed for the constrained solid's analytic mass/inertia and principal-axis torque solution, tensor rotation/translation, geometry edits changing actual response, packaged assets, repeatability, unknown density, unsupported environment, tampering, source changes, CLI receipts and failure preservation. The actual desktop smoke edits the width, rebuilds, reruns and requires slower spin-up under the same torque. It also verifies CoG-centred replay and an inconclusive missing-density run.

The initial example is 0.2 × 0.1 × 0.02 m at an assumed 500 kg/m³. Its mass is 0.2 kg and central `Izz` is 0.000833333… kg·m². A 0.001 N·m Z torque for one second gives 1.2 rad/s from rest. Widening to 0.3 m gives 0.3 kg, `Izz = 0.0025` kg·m² and 0.4 rad/s. These are independent closed-form checks, not measured test results.

The prototype still needs the hardware compatibility matrix, representative 200-part responsiveness and memory/recovery measurements. The two-second geometry/physics interaction goal has not been measured. Full CAD, flight/aerodynamic bridges and physical qualification remain open. See [the hardware contract](../HARDWARE_AND_FIDELITY.md) and [acceptance ledger](../ACCEPTANCE.md).

Windows lifecycle checks additionally cover a cold graphical editor import and cancellation of both the environment launcher and actual worker interpreter. The former cold headless import failed with an access violation; it is not counted as a passing installation check. The Windows entry point now uses hidden graphical import with the exit code enforced. Cancellation checks inspect the actual child PID through the OS inventory and require both processes to stop. Aggregate memory reclamation and future detached solver groups remain unmeasured.

For headless use, build a body with `scripts/lab_cad.py data/cad/body-example.json result.json`. Supply `scripts/lab_cad_analysis.py` a JSON object containing `project` and `experiment`, an output path and `--asset-root` pointing to the generated project folder. The experiment uses version `cad_torque_1`, `torque_body_nm`, `duration_s` and `step_s`. Output/receipt/error paths cannot replace a declared project asset.
