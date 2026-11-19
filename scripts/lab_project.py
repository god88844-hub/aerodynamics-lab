"""Import, validate or simulate an Aerodynamics Lab project from a file."""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/api"), str(ROOT / "packages"), str(ROOT / "packages/shared-schemas")]

from aeroforge_schemas.project import EngineeringProject, import_legacy_project  # noqa: E402
from app.services.project_service import run_project  # noqa: E402


def write_result(destination: Path, payload: dict) -> None:
    """Replace an output atomically after serialization completes."""
    content = json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n"
    descriptor, temporary = tempfile.mkstemp(prefix=".lab-output-", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("import-legacy", "validate", "run"))
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("choose an output path separate from the input project")
    try:
        raw = json.loads(args.input.read_text(encoding="utf-8"))
        project = import_legacy_project(raw) if args.command == "import-legacy" else EngineeringProject.model_validate(raw)
        payload = run_project(project) if args.command == "run" else project.model_dump(mode="json")
        write_result(args.output, payload)
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
