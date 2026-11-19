"""Run an isolated torque experiment from frozen CAD project and settings."""

import argparse
from hashlib import sha256
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/api"), str(ROOT / "packages"), str(ROOT / "packages/shared-schemas")]

from aeroforge_schemas.cad import CadTorqueRequest  # noqa: E402
from geometry.cad_dynamics import run_cad_torque  # noqa: E402
from lab_project import write_result  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--asset-root", type=Path, required=True)
    parser.add_argument("--error-output", type=Path)
    parser.add_argument("--completion-output", type=Path)
    args = parser.parse_args()
    paths = [path.resolve() for path in (args.input, args.output, args.error_output, args.completion_output) if path]
    if len(paths) != len(set(paths)):
        parser.error("input, output, error and completion paths must be separate")
    try:
        request = CadTorqueRequest.model_validate_json(args.input.read_bytes())
        asset_paths = {(args.asset_root / asset.path).resolve() for asset in request.project.assets}
        if any(path.resolve() in asset_paths for path in (args.output, args.error_output, args.completion_output) if path):
            parser.error("Output paths must not replace a project asset")
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
