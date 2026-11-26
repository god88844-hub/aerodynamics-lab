"""Standalone desktop project lifecycle: create, import, validate, version, recover.

All operations run locally with zero HTTP server dependency. Corrupt/missing assets
and incompatible document versions fail closed without overwriting valid projects.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from pydantic import ValidationError

from aeroforge_schemas.project import (
    AssemblyVehicle,
    EngineeringProject,
    Family,
    import_legacy_project,
)
from app.services.project_assets import asset_bytes, copy_assets, verify_assets
from desktop_worker.io import write_result

SUPPORTED_DOCUMENT_VERSION = "1.0"
RECOVERY_DIR = ".aerolab-recovery"
VERSIONS_DIR = "versions"


class ProjectWorkflowError(ValueError):
    """Typed failure carrying machine-readable category for desktop UI recovery."""

    def __init__(self, category: str, message: str, *, recoverable: bool = True) -> None:
        super().__init__(message)
        self.category = category
        self.recoverable = recoverable


def create_project_document(
    name: str,
    *,
    aircraft_family: Family = "multirotor",
    template: str = "assembly_empty",
    reference_design_path: Path | None = None,
) -> EngineeringProject:
    clean_name = name.strip()
    if not clean_name:
        raise ProjectWorkflowError("invalid_input", "Project name must be non-empty", recoverable=False)
    if template == "legacy_reference":
        if aircraft_family != "multirotor":
            raise ProjectWorkflowError(
                "invalid_input",
                "Legacy reference template is only valid for multirotor family",
                recoverable=False,
            )
        if reference_design_path is None or not reference_design_path.is_file():
            raise ProjectWorkflowError(
                "missing_asset",
                "Reference multirotor design file is missing",
                recoverable=False,
            )
        raw = json.loads(reference_design_path.read_text(encoding="utf-8"))
        project = import_legacy_project(raw)
        return project.model_copy(update={"name": clean_name})
    if template != "assembly_empty":
        raise ProjectWorkflowError("invalid_input", f"Unsupported project template: {template!r}", recoverable=False)
    identity = sha256(f"{aircraft_family}:{clean_name}".encode("utf-8")).hexdigest()
    return EngineeringProject(
        id=uuid5(NAMESPACE_URL, "aerodynamics-lab:project:" + identity),
        name=clean_name,
        aircraft_family=aircraft_family,
        vehicle=AssemblyVehicle(),
    )


def inspect_and_validate_project(raw_text: str, asset_root: Path) -> EngineeringProject:
    try:
        parsed = json.loads(raw_text, parse_constant=_reject_nonfinite)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ProjectWorkflowError("corrupt_document", f"Malformed project JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ProjectWorkflowError("corrupt_document", "Project document must be a JSON object")
    doc_ver = parsed.get("document_version")
    if doc_ver != SUPPORTED_DOCUMENT_VERSION:
        raise ProjectWorkflowError(
            "incompatible_version",
            f"Unsupported project document_version {doc_ver!r}; supported version is {SUPPORTED_DOCUMENT_VERSION!r}",
        )
    try:
        project = EngineeringProject.model_validate(parsed)
    except ValidationError as exc:
        raise ProjectWorkflowError("invalid_project", f"Project schema validation failed: {exc}") from exc
    _verify_assets_classified(project, asset_root)
    return project


def _reject_nonfinite(constant: str) -> None:
    raise ValueError(f"Nonfinite JSON constant {constant!r} is forbidden")


def _verify_assets_classified(project: EngineeringProject, asset_root: Path) -> None:
    for asset in project.assets:
        try:
            asset_bytes(asset_root, asset.path, asset.sha256)
        except FileNotFoundError as exc:
            raise ProjectWorkflowError("missing_asset", f"Missing project asset {asset.path}: {exc}") from exc
        except ValueError as exc:
            raise ProjectWorkflowError("corrupt_asset", f"Corrupt or invalid asset {asset.path}: {exc}") from exc


def write_recovery_snapshot(project: EngineeringProject, project_path: Path, source_root: Path) -> Path:
    """Persist an atomic last-valid recovery snapshot alongside the saved project."""
    recovery_root = project_path.parent / RECOVERY_DIR
    recovery_root.mkdir(parents=True, exist_ok=True)
    snapshot_path = recovery_root / "last-valid.json"
    copy_assets(project, source_root, snapshot_path)
    write_result(snapshot_path, project.model_dump(mode="json"))
    manifest = {
        "project_path": project_path.name,
        "project_sha256": project.fingerprint(),
        "saved_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    write_result(recovery_root / "manifest.json", manifest)
    return snapshot_path


def save_and_version_project(
    project: EngineeringProject,
    source_root: Path,
    destination: Path,
    *,
    create_version: bool = True,
    note: str = "",
) -> dict[str, Any]:
    """Verify source assets, publish project + recovery snapshot, and optionally append a version."""
    _verify_assets_classified(project, source_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    copy_assets(project, source_root, destination)
    write_result(destination, project.model_dump(mode="json"))
    recovery_path = write_recovery_snapshot(project, destination, source_root)

    version_entry = None
    if create_version:
        versions_root = destination.parent / VERSIONS_DIR
        versions_root.mkdir(parents=True, exist_ok=True)
        index_path = versions_root / "index.json"
        existing: list[dict[str, Any]] = []
        if index_path.is_file():
            try:
                loaded = json.loads(index_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict) and isinstance(loaded.get("versions"), list):
                    existing = list(loaded["versions"])
            except json.JSONDecodeError:
                existing = []
        next_num = (max((int(item.get("version", 0)) for item in existing), default=0) + 1)
        fp = project.fingerprint()
        rel_dir = f"v{next_num:04d}_{fp[:12]}"
        version_dir = versions_root / rel_dir
        version_dir.mkdir(parents=True, exist_ok=True)
        version_file = version_dir / "project.json"
        copy_assets(project, source_root, version_file)
        write_result(version_file, project.model_dump(mode="json"))
        version_entry = {
            "version": next_num,
            "id": rel_dir,
            "path": f"{VERSIONS_DIR}/{rel_dir}/project.json",
            "project_sha256": fp,
            "parent_sha256": existing[-1]["project_sha256"] if existing else None,
            "saved_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "note": note,
        }
        existing.append(version_entry)
        write_result(index_path, {"project_name": project.name, "versions": existing})

    return {
        "project": project.model_dump(mode="json"),
        "project_path": str(destination),
        "project_sha256": project.fingerprint(),
        "recovery_path": str(recovery_path),
        "version": version_entry,
    }


def list_project_versions(project_path: Path) -> dict[str, Any]:
    root = project_path if project_path.is_dir() else project_path.parent
    index_path = root / VERSIONS_DIR / "index.json"
    versions: list[dict[str, Any]] = []
    if index_path.is_file():
        data = json.loads(index_path.read_text(encoding="utf-8"))
        versions = list(data.get("versions", []))
    recovery_manifest = root / RECOVERY_DIR / "manifest.json"
    recovery = None
    if recovery_manifest.is_file() and (root / RECOVERY_DIR / "last-valid.json").is_file():
        recovery = json.loads(recovery_manifest.read_text(encoding="utf-8"))
    return {"versions": versions, "recovery": recovery}


def recover_last_valid_project(project_path: Path, restore_to: Path | None = None) -> dict[str, Any]:
    root = project_path if project_path.is_dir() else project_path.parent
    recovery_root = root / RECOVERY_DIR
    snapshot_path = recovery_root / "last-valid.json"
    manifest_path = recovery_root / "manifest.json"
    if not snapshot_path.is_file():
        raise ProjectWorkflowError("missing_recovery", "No last-valid recovery snapshot exists", recoverable=False)
    project = inspect_and_validate_project(snapshot_path.read_text(encoding="utf-8"), recovery_root)
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected_sha = manifest.get("project_sha256")
        if expected_sha and project.fingerprint() != expected_sha:
            raise ProjectWorkflowError("corrupt_recovery", "Recovery snapshot failed integrity check", recoverable=False)
    if restore_to is not None:
        copy_assets(project, recovery_root, restore_to)
        write_result(restore_to, project.model_dump(mode="json"))
    return {
        "recovered": True,
        "project": project.model_dump(mode="json"),
        "project_sha256": project.fingerprint(),
        "restored_to": str(restore_to) if restore_to else None,
    }
