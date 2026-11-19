# Desktop foundation prototype

This checkout contains the first Godot desktop shell, a C++ engineering library and a Python project worker. It loads and saves project document 1.0, lists/selects schematic components, computes native mass/CoG and runs/replays the existing reference simulation. Right-drag orbits and the mouse wheel zooms.

The full prototype acceptance gate in [the product specification](../../docs/PRODUCT_SPEC.md) also requires constrained CAD, custom blade generation and the recorded performance target. Those requirements remain open in [desktop issue #100](https://github.com/god88844-hub/aerodynamics-lab/issues/100).

## Windows

Install Python 3.11, CMake, Ninja and a C++20 compiler in the developer environment. From the repository root, run the following.

```powershell
.\scripts\build_desktop.ps1 -Launch
```

The script downloads pinned Godot 4.7.2 and godot-cpp source archives, checks SHA-256, creates a local Python environment with the locked API dependencies, builds the extension and runs integration checks before launching. Downloaded tools and build state live in the checkout's ignored desktop cache. An existing compatible Python environment can be supplied through `-PythonPath`.

## Linux

```sh
python -m pip install --require-hashes --only-binary=:all: -r apps/api/requirements.lock
cmake -S packages/engineering-core -B packages/engineering-core/build -DLAB_BUILD_GDEXTENSION=ON -DCMAKE_BUILD_TYPE=Release
cmake --build packages/engineering-core/build --parallel 2
ctest --test-dir packages/engineering-core/build --output-on-failure
export LAB_PYTHON="$(command -v python)"
godot --headless --path apps/desktop --editor --import --quit
godot --headless --path apps/desktop --script smoke_test.gd
godot --path apps/desktop
```

Use Godot 4.7.2. The C++ bindings are pinned to the 4.5 stable source commit and use its compatible extension API. CI downloads and verifies the exact Linux Godot release.

## Model and job behavior

The application starts the existing Python project worker as a separate process. It polls atomic output files and can terminate that process through Cancel job or on application exit. Reference replay interpolates stored position and attitude. Display coordinates map engineering `(x, y, z)` to Godot `(x, z, -y)`.

The native library combines supplied part masses and coordinates using double precision. Rendered markers represent component positions. Source geometry, calibrated component behavior and validation limits remain recorded in the project/backend inputs.

The legacy backend explicitly refuses changed environment settings and generic assembly documents. Other family identities are available for project authoring while their physical backends are implemented. The worker reports failed operations separately from saved projects.

Godot and godot-cpp use the MIT license. The extension build copies the bindings' full license notice into its output directory. Source archive URLs and checksums are pinned in the build definitions.
