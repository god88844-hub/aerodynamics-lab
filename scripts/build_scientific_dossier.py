"""P0D-028: Build and verify the deterministic Numerical and Scientific Dossier from live repository artifacts."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "packages"), str(ROOT / "packages/shared-schemas"), str(ROOT / "apps/api")]

from desktop_worker.learning_experiments import EQUATIONS_AND_ASSUMPTIONS  # noqa: E402
from export_sbom import build_sbom  # noqa: E402
from physics.validation.protocol_registry import load_frozen_protocol_catalog  # noqa: E402


def render_scientific_dossier(repo_root: Path = ROOT) -> str:
    """Assemble the reproducible scientific & numerical verification dossier without inflating physical status."""
    reg = json.loads((repo_root / "data" / "registry.json").read_text(encoding="utf-8"))
    frozen_base = load_frozen_protocol_catalog(repo_root / "data" / "research" / "frozen_protocols.json")
    frozen_ext = load_frozen_protocol_catalog(repo_root / "data" / "research" / "extended_protocols.json")
    airfoil_manifest = json.loads((repo_root / "data" / "airfoils" / "airfoil_manifest.json").read_text(encoding="utf-8"))
    sbom = build_sbom(repo_root)

    n_sources = len(reg.get("sources", []))
    n_campaigns = len(reg.get("campaigns", []))
    base_ids = [p["protocol_id"] for p in frozen_base["protocols"]]
    ext_ids = [p["protocol_id"] for p in frozen_ext["protocols"]]

    lines = [
        "# Numerical and Scientific Verification Dossier",
        "",
        "> **Status Notice:** All simulation solvers, CAD transformations, and protocol templates below are software-verified.",
        "> Physical acceptance remains **UNVALIDATED / DEVELOPMENT** pending sealed custodian experimental recordings (`P0A-027`..`P0D-020`), external reviewer sign-offs (`P0A-033`..`P0D-029`), multi-machine hardware qualification (`P0A-038`, `P0D-022`, `P0D-027`), and owner Phase 0 exit (`P0D-032`).",
        "",
        "## 1. Authoritative Registry & Open-Data Provenance",
        "",
        f"- **Registered external sources:** `{n_sources}` (`data/registry.json`)",
        f"- **Tracked empirical campaigns:** `{n_campaigns}` (all `DEVELOPMENT`; zero physical acceptance claims)",
        f"- **Clean-room Apache-2.0 airfoil coordinate sets bundled:** `{len(airfoil_manifest.get('airfoils', []))}` (`data/airfoils/airfoil_manifest.json`)",
        f"- **CycloneDX-subset SBOM components:** `{sbom['counts']['total']}` (PyPI backend `{sbom['counts']['pypi_backend']}`, PyPI CAD `{sbom['counts']['pypi_cad']}`, npm web `{sbom['counts']['npm_web']}`)",
        "",
        "## 2. Core Physics & Estimation Kernels (Strict SI, Right-Handed Z-Up, Hamilton `wxyz`)",
        "",
        "| Domain | Module | Method / Solver | Physical Scope & Caveats |",
        "| --- | --- | --- | --- |",
        "| C++20 Native Core | `packages/engineering-core/` | Exact parallel-axis mass/inertia & float64 RK4 (`simulate_rk4`) | Zero-dependency Godot GDExtension + CTest parity |",
        "| Multirotor Flight | `packages/physics/scenarios/desktop_runner.py` | Double-precision RK4 + prop/motor lookup + density/weather coupling | Incompressible low-Mach; coupled weather marked `SUPPORTED_WITH_CAVEATS` |",
        "| Atmosphere | `packages/physics/environment/isa_atmosphere.py` | US Standard Atmosphere 1976 (Troposphere & Lower Stratosphere) + Sutherland viscosity | Dry & moist ideal-gas regime up to 32 km |",
        "| Fixed-Wing Aero | `packages/physics/aerodynamics/fixed_wing.py` & `sixdof_fixed_wing.py` | Prandtl Fourier lifting-line + Re polar coupling + 13-state 6-DoF FRD/Z-up derivatives | Fails closed above Mach 0.30 or stall AoA |",
        "| Rotorcraft & VTOL | `packages/physics/aerodynamics/rotorcraft_vtol.py` & `pitt_peters_inflow.py` | Annular BEMT + Cheeseman-Bennett IGE + Pitt-Peters 3-state inflow + autorotation flare + aero-thermo-structural coupling | Fails closed in deep vortex-ring (`climb < -8 m/s`) or `z/R <= 0.35` |",
        "| Propulsion Battery | `packages/physics/propulsion/thevenin_battery.py` | 2-RC polarization equivalent circuit + lumped thermal capacitance | Fails closed on cutoff sag voltage & thermal runaway |",
        "| Autonomy & Vision | `packages/physics/autonomy/ekf_estimator.py` & `sitl_and_swarms.py` | 6-state ES-EKF + ArduPilot/PX4 lock-step + synthetic LiDAR/A*/swarm/AprilTag PnP | Virtual/synthetic (`SYNTHETIC`); real HIL gated at `P0D-018` |",
        "| CAD & 2D Drawings | `packages/geometry/fixed_wing_cad.py` | Undoable sketch/extrude/revolve/boolean stack, Steiner assembly, 3-view SVG/DXF (`ezdxf`) | Fail-closed missing material density |",
        "",
        "## 3. Governing Equations & Assumptions Catalog",
        "",
    ]
    for item in EQUATIONS_AND_ASSUMPTIONS:
        lines.append(f"- **{item['topic']}:** `{item['equation']}` — _{item['assumptions']}_")

    lines.extend(
        [
            "",
            "## 4. Frozen Validation Protocols (Pre-Registered, Unapproved)",
            "",
            f"- **Core component & multirotor (`data/research/frozen_protocols.json`):** {', '.join(f'`{x}`' for x in base_ids)}",
            f"- **Extended 4-family & weather/autonomy (`data/research/extended_protocols.json`):** {', '.join(f'`{x}`' for x in ext_ids)}",
            "",
        ]
    )
    payload = "\n".join(lines)
    digest = sha256(payload.encode("utf-8")).hexdigest()[:16]
    return payload + f"<!-- dossier_sha256_prefix: {digest} -->\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if docs/SCIENTIFIC_DOSSIER.md is stale")
    args = parser.parse_args()
    out_path = ROOT / "docs" / "SCIENTIFIC_DOSSIER.md"
    rendered = render_scientific_dossier(ROOT)
    if args.check:
        if not out_path.is_file() or out_path.read_text(encoding="utf-8") != rendered:
            print("docs/SCIENTIFIC_DOSSIER.md is out of date; run python scripts/build_scientific_dossier.py", file=sys.stderr)
            return 1
        print("Scientific dossier matches repository state.")
        return 0
    out_path.write_text(rendered, encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
