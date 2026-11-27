"""P0A-036: Standalone offline Windows package staging, license/notices, and atomic recovery."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import shutil
from typing import Any

from desktop_worker.project_workflow import recover_last_valid_project

ROOT = Path(__file__).resolve().parents[2]

PACKAGE_TREE_ITEMS = (
    "apps/native/CMakeLists.txt",
    "apps/native/src",
    "apps/desktop/main.gd",
    "apps/desktop/cad_worker.gd",
    "apps/desktop/project.godot",
    "apps/desktop/lab_engineering.gdextension",
    "apps/desktop/requirements-cad.lock",
    "apps/api/app/services",
    "apps/api/requirements.lock",
    "packages/engineering-core",
    "packages/desktop_worker",
    "packages/physics",
    "packages/geometry",
    "packages/optimization",
    "packages/shared-schemas/aeroforge_schemas",
    "scripts/lab_project.py",
    "scripts/lab_worker.py",
    "scripts/lab_cad_analysis.py",
    "scripts/export_sbom.py",
    "data/airfoils",
    "data/components",
    "data/designs",
    "data/research/frozen_protocols.json",
    "LICENSE",
)

NOTICE_TEXT = (
    "Aerodynamics Lab Standalone Offline Desktop Distribution\n"
    "- Zero third-party game engine or HTTP server required.\n"
    "- Bundles native C++20/OpenGL workbench sources (plus built AerodynamicsLab.exe when present), Open CASCADE/Python worker scripts, shared schemas, and reference component/design data.\n"
    "- See LICENSE for Apache-2.0 repository terms; external benchmark sources retain their declared licenses.\n"
)


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def stage_standalone_package(target_dir: Path, *, repo_root: Path = ROOT) -> dict[str, Any]:
    """Assemble a clean-user standalone offline distribution without HTTP/dev dependencies."""
    target_dir = Path(target_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    staged_files: list[dict[str, str]] = []
    for rel in PACKAGE_TREE_ITEMS:
        src = repo_root / rel
        if not src.exists():
            raise FileNotFoundError(f"Required package payload missing: {rel}")
        dst = target_dir / rel
        if src.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(
                src,
                dst,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".godot"),
            )
            for item in sorted(dst.rglob("*")):
                if item.is_file():
                    staged_files.append({"path": item.relative_to(target_dir).as_posix(), "sha256": _file_sha256(item)})
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            staged_files.append({"path": rel, "sha256": _file_sha256(dst)})

    native_exe = repo_root / "apps/native/build/AerodynamicsLab.exe"
    if native_exe.is_file():
        dst_exe = target_dir / "AerodynamicsLab.exe"
        shutil.copy2(native_exe, dst_exe)
        staged_files.append({"path": "AerodynamicsLab.exe", "sha256": _file_sha256(dst_exe)})

    notice_path = target_dir / "NOTICE_STANDALONE.txt"
    notice_path.write_text(NOTICE_TEXT, encoding="utf-8")
    staged_files.append({"path": "NOTICE_STANDALONE.txt", "sha256": _file_sha256(notice_path)})

    manifest = {
        "schema_version": "1.0",
        "package_mode": "standalone_offline_desktop",
        "http_server_required": False,
        "file_count": len(staged_files),
        "files": staged_files,
    }
    manifest_path = target_dir / "package_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"target_dir": str(target_dir), "manifest_path": str(manifest_path), "file_count": len(staged_files)}


def safe_stage_update_or_rollback(
    staging_source: Path,
    install_dir: Path,
    *,
    simulate_failure: bool = False,
) -> dict[str, Any]:
    """Atomically apply an update to install_dir without losing prior install or user data."""
    install_dir = Path(install_dir).resolve()
    backup_dir = install_dir.parent / f".{install_dir.name}.backup"
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    had_existing = install_dir.exists()
    if had_existing:
        shutil.copytree(install_dir, backup_dir)
    try:
        if simulate_failure:
            raise OSError("Simulated interrupted install/update failure")
        stage_standalone_package(install_dir, repo_root=staging_source)
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        return {"status": "updated", "rolled_back": False, "install_dir": str(install_dir)}
    except OSError as exc:
        if install_dir.exists():
            shutil.rmtree(install_dir)
        if had_existing and backup_dir.exists():
            shutil.move(str(backup_dir), str(install_dir))
        return {"status": "failed_rolled_back", "rolled_back": True, "error": str(exc), "install_dir": str(install_dir)}


def recover_user_project_after_corruption(project_path: Path) -> dict[str, Any]:
    """Recover the last valid user project snapshot after a corrupt project write."""
    return recover_last_valid_project(project_path, restore_to=project_path)
