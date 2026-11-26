"""Import, create, validate, package, version, recover, author, or simulate an Aerodynamics Lab project."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/api"), str(ROOT / "packages"), str(ROOT / "packages/shared-schemas")]

from aeroforge_schemas.project import EngineeringProject, import_legacy_project  # noqa: E402
from app.services.project_assets import copy_assets  # noqa: E402
from app.services.project_service import run_project  # noqa: E402
from desktop_worker.environment_authoring import author_test_ground  # noqa: E402
from desktop_worker.io import write_result, write_started  # noqa: E402
from desktop_worker.project_workflow import (  # noqa: E402
    ProjectWorkflowError,
    create_project_document,
    inspect_and_validate_project,
    list_project_versions,
    recover_last_valid_project,
    save_and_version_project,
    write_recovery_snapshot,
)
from physics.dynamics.assembly_layout import build_multirotor_layout_and_bom  # noqa: E402
from physics.propulsion.loader import ComponentLibrary  # noqa: E402
from physics.scenarios.mission_authoring import author_mission, run_authored_mission  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "import-legacy",
            "create",
            "validate",
            "package",
            "save-version",
            "list-versions",
            "recover",
            "layout-bom",
            "author-ground",
            "author-mission",
            "run-mission",
            "run",
        ),
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--error-output", type=Path)
    parser.add_argument("--completion-output", type=Path)
    parser.add_argument("--started-output", type=Path)
    parser.add_argument("--asset-root", type=Path)
    parser.add_argument("--restore-to", type=Path)
    parser.add_argument("--note", default="")
    args = parser.parse_args()
    paths = [path.resolve() for path in (args.input, args.output, args.error_output, args.completion_output, args.started_output) if path]
    if len(paths) != len(set(paths)):
        parser.error("input, output, error and completion paths must be separate")
    try:
        write_started(args.started_output)
        if args.command == "create":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            ref_path = spec.get("reference_design_path")
            project = create_project_document(
                spec.get("name", "New Flight Project"),
                aircraft_family=spec.get("aircraft_family", "multirotor"),
                template=spec.get("template", "assembly_empty"),
                reference_design_path=Path(ref_path) if ref_path else (ROOT / "data/designs/quad_mn3508_6s.json"),
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            payload = project.model_dump(mode="json")
            write_result(args.output, payload)
            write_recovery_snapshot(project, args.output, args.output.parent)
        elif args.command == "list-versions":
            payload = list_project_versions(args.input)
            write_result(args.output, payload)
        elif args.command == "recover":
            payload = recover_last_valid_project(args.input, restore_to=args.restore_to)
            write_result(args.output, payload)
        elif args.command == "layout-bom":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            library = ComponentLibrary(ROOT / "data" / "components")
            payload = build_multirotor_layout_and_bom(spec, library)
            write_result(args.output, payload)
        elif args.command == "author-ground":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            project = EngineeringProject.model_validate(spec["project"])
            updated = author_test_ground(project, spec["test_ground"])
            write_result(args.output, updated.model_dump(mode="json"))
        elif args.command == "author-mission":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            project = EngineeringProject.model_validate(spec["project"])
            updated = author_mission(project, spec["mission"])
            write_result(args.output, updated.model_dump(mode="json"))
        elif args.command == "run-mission":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            project = EngineeringProject.model_validate(spec["project"] if "project" in spec else spec)
            payload = run_authored_mission(
                project,
                mass_kg=float(spec.get("mass_kg", 1.5)) if isinstance(spec, dict) else 1.5,
                render_fps_hint=float(spec.get("render_fps_hint", 60.0)) if isinstance(spec, dict) else 60.0,
            )
            write_result(args.output, payload)
        elif args.command == "import-legacy":
            raw = json.loads(args.input.read_text(encoding="utf-8"))
            project = import_legacy_project(raw)
            payload = project.model_dump(mode="json")
            write_result(args.output, payload)
        else:
            asset_root = args.asset_root or args.input.parent
            raw_text = args.input.read_text(encoding="utf-8")
            project = inspect_and_validate_project(raw_text, asset_root)
            if args.command == "package":
                args.output.parent.mkdir(parents=True, exist_ok=True)
                copy_assets(project, asset_root, args.output)
                payload = project.model_dump(mode="json")
                write_result(args.output, payload)
                write_recovery_snapshot(project, args.output, asset_root)
            elif args.command == "save-version":
                result = save_and_version_project(project, asset_root, args.output, create_version=True, note=args.note)
                payload = result["project"]
            elif args.command == "run":
                payload = run_project(project)
                write_result(args.output, payload)
            else:
                payload = project.model_dump(mode="json")
                write_result(args.output, payload)
        if args.completion_output:
            write_result(args.completion_output, {"output_sha256": sha256(args.output.read_bytes()).hexdigest()})
    except ProjectWorkflowError as error:
        print(str(error), file=sys.stderr)
        if args.error_output:
            try:
                write_result(
                    args.error_output,
                    {"status": "failed", "category": error.category, "recoverable": error.recoverable, "error": str(error)},
                )
            except OSError as publication_error:
                print(str(publication_error), file=sys.stderr)
        return 2
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        if args.error_output:
            try:
                write_result(args.error_output, {"status": "failed", "category": "workflow_error", "recoverable": True, "error": str(error)})
            except OSError as publication_error:
                print(str(publication_error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
