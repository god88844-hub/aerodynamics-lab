"""Run an isolated torque experiment or clearance/load check from frozen CAD project and settings."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/api"), str(ROOT / "packages"), str(ROOT / "packages/shared-schemas")]

from aeroforge_schemas.cad import CadTorqueRequest  # noqa: E402
from aeroforge_schemas.design import DroneDesign  # noqa: E402
from aeroforge_schemas.project import EngineeringProject  # noqa: E402
from desktop_worker.io import write_result, write_started  # noqa: E402
from geometry.cad_dynamics import run_cad_torque  # noqa: E402
from geometry.clearance_checks import evaluate_assembly_clearance_and_loads  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--asset-root", type=Path, required=True)
    parser.add_argument("--clearance", action="store_true", help="Evaluate datum-transformed clearance and load screen")
    parser.add_argument("--error-output", type=Path)
    parser.add_argument("--completion-output", type=Path)
    parser.add_argument("--started-output", type=Path)
    args = parser.parse_args()
    paths = [path.resolve() for path in (args.input, args.output, args.error_output, args.completion_output, args.started_output) if path]
    if len(paths) != len(set(paths)):
        parser.error("input, output, error and completion paths must be separate")
    try:
        if args.clearance:
            payload = json.loads(args.input.read_text(encoding="utf-8"))
            project = EngineeringProject.model_validate(payload["project"])
            asset_paths = {(args.asset_root / asset.path).resolve() for asset in project.assets}
            if any(path.resolve() in asset_paths for path in (args.output, args.error_output, args.completion_output, args.started_output) if path):
                parser.error("Output paths must not replace a project asset")
            write_started(args.started_output)
            design = DroneDesign.model_validate(payload["structural_design"]) if payload.get("structural_design") else None
            load_cases = [tuple(c) for c in payload["load_cases"]] if payload.get("load_cases") else None
            result = evaluate_assembly_clearance_and_loads(
                project,
                args.asset_root,
                rotors=payload["rotors"],
                obstacles=payload.get("obstacles"),
                minimum_clearance_m=float(payload.get("minimum_clearance_m", 0.02)),
                structural_design=design,
                load_cases=load_cases,
                materials_path=(ROOT / "data/components/materials.json") if design is not None else None,
            )
        else:
            request = CadTorqueRequest.model_validate_json(args.input.read_bytes())
            asset_paths = {(args.asset_root / asset.path).resolve() for asset in request.project.assets}
            if any(path.resolve() in asset_paths for path in (args.output, args.error_output, args.completion_output, args.started_output) if path):
                parser.error("Output paths must not replace a project asset")
            write_started(args.started_output)
            result = run_cad_torque(request, args.asset_root)
        write_result(args.output, result)
        if args.completion_output:
            write_result(args.completion_output, {"output_sha256": sha256(args.output.read_bytes()).hexdigest()})
    except Exception as error:
        if args.error_output:
            write_result(args.error_output, {"status": "failed", "error": str(error)})
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
