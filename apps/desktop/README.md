# Standalone 3D desktop application

The [200-part viewport and memory benchmark](../../docs/prototypes/ASSEMBLY_BENCHMARK.md) publishes a frozen workload, reproduction commands, successful/failed receipts and the remaining hardware acceptance limits. Verified project JSON remains authoritative for saving and analysis; the rendering dictionary is a display representation.

This checkout contains the standalone Godot 3D application, a C++ engineering library and a Python project worker. It loads and saves project document 1.0, lists/selects schematic components, computes native mass/CoG and runs/replays the existing reference simulation. Right-drag orbits and the mouse wheel zooms.

The CAD worker builds a sample or user-supplied blade recipe into a valid Open CASCADE solid, STEP, a hash-bound display mesh and a portable project. Procedural display meshes generate automatic Godot LODs. Foundation qualification passed. Full software execution is defined by the numbered [master plan](../../docs/MASTER_PLAN.md), with CAD and wider hardware/physical acceptance tracked separately. This is the primary product; the web client is frozen legacy.

## Windows

Install Python 3.11, CMake, Ninja and a C++20 compiler in the developer environment. Close running desktop instances before rebuilding the native extension. Apply the [local workspace/state settings](../../docs/WORKSPACE.md), then run from the repository root.

```powershell
.\scripts\build_desktop.ps1 -Launch
```

The script downloads pinned Godot 4.7.2 and godot-cpp source archives, checks SHA-256, creates a local Python environment with the locked API and CAD dependencies, builds the extension and runs integration checks before launching. CAD uses prebuilt pinned binary wheels. Downloaded tools and build state live in the checkout's ignored desktop cache. An existing Python environment containing `requirements-cad.lock` can be supplied through `-PythonPath`.

Windows editor import runs with a hidden Compatibility-renderer window and retains its exit-code gate. A fresh headless editor import reproduced an access violation during recorded qualification; the hidden graphical cold import completed successfully. Runtime integration checks still run headless. The project configuration targets the pinned 4.7 application; the native bindings retain the tested 4.5 extension API.

## Linux

```sh
python -m pip install --require-hashes --only-binary=:all: -r apps/desktop/requirements-cad.lock
cmake -S packages/engineering-core -B packages/engineering-core/build -DLAB_BUILD_GDEXTENSION=ON -DCMAKE_BUILD_TYPE=Release
cmake --build packages/engineering-core/build --parallel 2
ctest --test-dir packages/engineering-core/build --output-on-failure
export LAB_PYTHON="$(command -v python)"
export LAB_CAD_PYTHON="$LAB_PYTHON"
export LAB_TEST_CAD=1
xvfb-run -a godot --rendering-method gl_compatibility --path apps/desktop --editor --import --quit
godot --headless --path apps/desktop --script smoke_test.gd
godot --path apps/desktop
```

Use Godot 4.7.2. The C++ bindings are pinned to the 4.5 stable source commit and use its compatible extension API. CI downloads and verifies the exact Linux Godot release.

Linux editor import uses a virtual X display with Xvfb. Godot's upstream headless GDExtension import/shutdown issue affects cold-cache editor initialization. The subsequent runtime checks run headless and retain their exit-code gate. [Upstream issue](https://github.com/godotengine/godot/issues/111645)

## Model and job behavior

The application starts the existing Python project worker as a separate process. It requires a per-job completion receipt matching the output hash, so an old saved file cannot stand in for a successful worker. Cancel job and application exit stop the launched Windows process tree, including the virtual-environment child interpreter. Current Linux project workers run as a single direct process. Future detached solver groups need their own supervised lifetime contract. Reference replay interpolates stored position and attitude. Display coordinates map engineering `(x, y, z)` to Godot `(x, z, -y)`.

CAD builds and applied-torque experiments now use a reusable engine behind a separate lightweight supervisor. Libraries stay loaded between requests; each job still constructs its own geometry or imports its own frozen STEP bytes. The local protocol binds session/job/request/result identities, retires failed or changed-model sessions, and stops the engine on owner exit or a deadline. Cancel retains the project and a later CAD operation starts a fresh session. Application exit stops idle CAD workers too. See [the reusable worker contract and lifecycle checks](../../docs/prototypes/REUSABLE_CAD_WORKER.md).

The [rendered interaction benchmark](../../docs/prototypes/REUSABLE_CAD_WORKER.md#rendered-interaction-benchmark) measures one bounded editing/torque case with cold and warm results separated. It does not establish a hardware-tier or complete hardware-matrix acceptance. The density control uses a 0.001 kg/m³ increment aligned with its minimum, preserving an entered/default value of 500 rather than snapping it to 500.001.

Workers publish an optional atomic startup receipt with the actual interpreter PID. The cancellation smoke waits for an active worker and checks both it and the launcher after cancellation. Windows process inspection uses the system inventory because Godot's process tracker covers directly created processes. [Windows process-tree termination](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/taskkill).

The native library combines supplied part masses and coordinates using double precision. Rendered markers represent component positions. Source geometry, calibrated component behavior and validation limits remain recorded in the project/backend inputs.

New project runs freeze their input document and capture Python model/component file hashes, the component data, the dependency-lock hash and numerical package/platform versions. A changed model environment during execution causes a refusal. The record supports reproducing the selected reference backend.

The legacy backend explicitly refuses changed environment settings and generic assembly documents. Other family identities are available for project authoring while their physical backends are implemented. The worker reports failed operations separately from saved projects.

Godot and godot-cpp use the MIT license. The extension build copies the bindings' full license notice into its output directory. Source archive URLs and checksums are pinned in the build definitions.

## CAD prototype scope

Choose **Build blade example** or **Build blade recipe**. The recipe declares station radii, chords, twist, thickness ratio, spline sampling and display tolerance in SI units. The example is conceptual geometry with no claimed aerodynamic performance. Edit its JSON recipe and rebuild to change the solid. A full interactive sketcher, history editor and arbitrary geometry-to-flight model remain future CAD work.

The worker uses CadQuery 2.8.0 and cadquery-ocp 7.9.3.1.1. A separate constrained rectangle demonstration exercises the experimental sketch solver and checks actual edge lengths and enclosed area. The blade loft itself uses declared section coordinates, with a symmetric four-digit thickness distribution and a closed trailing edge. These operations do not establish a general constrained sketcher or a validated propeller design.

The kernel works in millimetres and exports STEP in millimetres. Display vertices use metres and an explicit right-handed Z-up frame. STEP import/export must preserve a valid positive-volume solid and its volume. Optional density produces a uniform-density mass estimate. Missing density leaves mass unknown. The generic CAD project has no assigned flight backend; Run refuses it until an applicable physical adapter exists.

Save project copies all declared, SHA-256-verified assets to the destination. Newly generated assets use `assets/<sha256>/<filename>`, so rebuilt geometry can be saved in the same folder as earlier project versions. Old asset bytes remain available; opening either project verifies its own references. Conflicting bytes at an existing declared path are refused before project publication. Previous flat asset paths remain supported. The desktop bounds each display file at 16 MiB and 100,000 triangles; the worker bounds generated mesh counts and the packaging worker bounds individual asset reads at 256 MiB. These are current current implementation limits, with [measured hardware tiers](../../docs/HARDWARE_AND_FIDELITY.md) defining the delivery target. They are not OS memory admission or complete large-assembly protection.

The display path explicitly generates LODs through ImporterMesh because these procedural JSON meshes bypass Godot scene import. Exact geometry and engineering inputs retain their original hashes. Headless acceptance requires actual generated LODs, a mesh resource, a save/reopen round trip and refusal of an unsupported CAD flight run.

For headless use:

```sh
python scripts/lab_cad.py data/cad/blade-example.json blade-result.json --error-output blade-error.json
python scripts/lab_project.py package blade-result-cad/project.json saved/project.json
```

Create the `saved` destination directory first. The CAD output directory must be new. Failed/cancelled builds may leave incomplete assets; the project manifest is published last. `LAB_CAD_PYTHON` can select a dedicated locked CAD environment. Launch arguments after `--` accept `--open-project=/absolute/project.json`.

CadQuery is Apache-2.0. Its OCCT binding and kernel retain their LGPL/exception notices and distribution obligations. The worker environment also includes other dependencies. This source distribution does not establish installer license acceptance. [CadQuery source/license](https://github.com/CadQuery/cadquery/tree/v2.8.0), [OCP](https://github.com/CadQuery/OCP).

## Constrained body and applied-torque experiment

**New / edit test body** exposes width, height, extrusion depth and optional assumed uniform density. Rebuild uses the solved sketch to construct the actual solid. **Run applied-torque experiment** recomputes mass and full central inertia from frozen STEP bytes, then runs the existing rigid-body/RK4 engine with body-Z torque and gravity disabled. Choose the integration step explicitly. Play/seek shows rotation about the computed CoG.

Saving an unchanged project retains its current experiment preview. Save named project files in the same folder to retain earlier geometry versions; generated assets are copied under their content hashes. A rebuild changes the project and clears the previous preview until a new experiment is run.

Missing density returns INCONCLUSIVE. A completed mathematical experiment remains physically unvalidated. The current implementation supports one solid and explicit node placement; multiple-body assembly and aircraft/propeller aerodynamics need separate adapters. Ordinary flight runs still refuse generic CAD. See [the mass/dynamics evidence and headless interface](../../docs/prototypes/CAD_MASS_DYNAMICS.md).
