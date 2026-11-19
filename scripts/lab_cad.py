"""Build a new blade CAD project from a declared recipe."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/api"), str(ROOT / "packages"), str(ROOT / "packages/shared-schemas")]

from aeroforge_schemas.cad import BladeRecipe, BoxRecipe  # noqa: E402
from geometry.cad_backend import build_blade_project, build_box_project  # noqa: E402
from lab_project import write_result, write_started  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--error-output", type=Path)
    parser.add_argument("--completion-output", type=Path)
    parser.add_argument("--started-output", type=Path)
    args = parser.parse_args()
    paths = [args.input.resolve(), args.output.resolve()]
    if args.error_output:
        paths.append(args.error_output.resolve())
    if args.completion_output:
        paths.append(args.completion_output.resolve())
    if args.started_output:
        paths.append(args.started_output.resolve())
    if len(paths) != len(set(paths)):
        parser.error("input, output, error and completion paths must be separate")
    try:
        raw = json.loads(args.input.read_bytes())
        write_started(args.started_output)
        directory = args.output.parent / (args.output.stem + "-cad")
        result = (build_box_project(BoxRecipe.model_validate(raw), directory)
                  if raw.get("recipe_type") == "box_1"
                  else build_blade_project(BladeRecipe.model_validate(raw), directory))
        write_result(args.output, result)
        if args.completion_output:
            write_result(args.completion_output, {"output_sha256": sha256(args.output.read_bytes()).hexdigest()})
    except Exception as error:
        # Native geometry/constraint failures must reach the desktop as failed jobs.
        if args.error_output:
            write_result(args.error_output, {"status": "failed", "error": str(error)})
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
