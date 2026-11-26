"""P0A-017 acceptance tests: standalone desktop project workflow, versioning, recovery,
numeric round-trip preservation, and Forward+ PBR / gl_compatibility visual profile.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
LAB_PROJECT = ROOT / "scripts" / "lab_project.py"
REFERENCE_DESIGN = ROOT / "data" / "designs" / "quad_mn3508_6s.json"
ASSEMBLY_200 = ROOT / "data" / "benchmarks" / "assembly-200"


def _run_worker(command: str, inp: Path, out: Path, *extra: str) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    err = out.with_name(out.stem + "-error.json")
    comp = out.with_name(out.stem + "-complete.json")
    cmd = [
        sys.executable,
        str(LAB_PROJECT),
        command,
        str(inp),
        str(out),
        "--error-output",
        str(err),
        "--completion-output",
        str(comp),
        *extra,
    ]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    return proc, err, comp


def test_create_import_package_version_reopen_and_run_preserve_numeric_identity(tmp_path):
    # 1. Create a fresh assembly project via worker (no HTTP server)
    spec_path = tmp_path / "create-spec.json"
    spec_path.write_text(
        json.dumps({"name": "P0A017 Quad Concept", "aircraft_family": "multirotor", "template": "assembly_empty"}),
        encoding="utf-8",
    )
    created_path = tmp_path / "created" / "project.json"
    proc, err, comp = _run_worker("create", spec_path, created_path)
    assert proc.returncode == 0, proc.stderr
    assert not err.exists()
    assert comp.is_file()
    created_doc = json.loads(created_path.read_text(encoding="utf-8"))
    assert created_doc["document_version"] == "1.0"
    assert created_doc["aircraft_family"] == "multirotor"

    # 2. Import legacy design -> package -> save-version v1 -> edit -> save-version v2 -> reopen v1
    imported_path = tmp_path / "imported.json"
    proc, _, _ = _run_worker("import-legacy", REFERENCE_DESIGN, imported_path)
    assert proc.returncode == 0, proc.stderr

    ws = tmp_path / "workspace"
    v1_target = ws / "project.json"
    proc, _, _ = _run_worker("save-version", imported_path, v1_target, "--note", "v1 baseline")
    assert proc.returncode == 0, proc.stderr
    v1_bytes = v1_target.read_bytes()
    v1_sha = sha256(v1_bytes).hexdigest()

    # Edit scenario duration and save v2
    edited_in = tmp_path / "edited_in.json"
    edited = json.loads(v1_bytes.decode("utf-8"))
    edited["experiment"]["parameters"] = {"duration_s": 2.0}
    edited_in.write_text(json.dumps(edited), encoding="utf-8")
    proc, _, _ = _run_worker("save-version", edited_in, v1_target, "--note", "v2 2s duration")
    assert proc.returncode == 0, proc.stderr
    v2_sha = sha256(v1_target.read_bytes()).hexdigest()
    assert v2_sha != v1_sha

    # List versions and verify both v1 and v2 plus recovery snapshot exist
    versions_out = tmp_path / "versions.json"
    proc, _, _ = _run_worker("list-versions", v1_target, versions_out)
    assert proc.returncode == 0, proc.stderr
    versions_info = json.loads(versions_out.read_text(encoding="utf-8"))
    assert len(versions_info["versions"]) == 2
    assert versions_info["recovery"] is not None

    # Reopen v1 and verify exact numeric/SHA-256 identity preserved
    reopened_v1 = ws / versions_info["versions"][0]["path"]
    validated_v1 = tmp_path / "validated_v1.json"
    proc, _, _ = _run_worker("validate", reopened_v1, validated_v1)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(validated_v1.read_bytes()) == json.loads(v1_bytes)

    # Run reopened v1 through authoritative simulation worker
    run_out = tmp_path / "run_v1.json"
    proc, _, _ = _run_worker("run", validated_v1, run_out)
    assert proc.returncode == 0, proc.stderr
    run_payload = json.loads(run_out.read_text(encoding="utf-8"))
    assert run_payload["result"]["status"] == "completed"
    assert run_payload["project"] == json.loads(v1_bytes)


def test_corrupt_missing_assets_incompatible_version_and_recovery(tmp_path):
    # Copy the 200-part asset-bearing assembly fixture into tmp_path
    proj_dir = tmp_path / "proj"
    shutil.copytree(ASSEMBLY_200, proj_dir)
    proj_file = proj_dir / "project.json"
    saved_dir = tmp_path / "saved"
    saved_file = saved_dir / "project.json"

    proc, _, _ = _run_worker("package", proj_file, saved_file, "--asset-root", proj_dir)
    assert proc.returncode == 0, proc.stderr
    good_bytes = saved_file.read_bytes()
    good_doc = json.loads(good_bytes.decode("utf-8"))

    # 1. Corrupt asset SHA-256 mismatch
    first_asset = saved_dir / good_doc["assets"][0]["path"]
    original_asset_bytes = first_asset.read_bytes()
    first_asset.write_bytes(original_asset_bytes + b"tampered")
    out_bad = tmp_path / "bad_corrupt_out.json"
    proc, err, _ = _run_worker("validate", saved_file, out_bad, "--asset-root", saved_dir)
    assert proc.returncode == 2
    err_data = json.loads(err.read_text(encoding="utf-8"))
    assert err_data["category"] == "corrupt_asset"
    assert err_data["recoverable"] is True

    # 2. Missing asset
    first_asset.unlink()
    proc, err2, _ = _run_worker("validate", saved_file, tmp_path / "bad_missing_out.json", "--asset-root", saved_dir)
    assert proc.returncode == 2
    assert json.loads(err2.read_text(encoding="utf-8"))["category"] == "missing_asset"

    # 3. Incompatible document_version does not overwrite saved_file
    incompat = dict(good_doc, document_version="2.0")
    incompat_in = tmp_path / "incompat.json"
    incompat_in.write_text(json.dumps(incompat), encoding="utf-8")
    proc, err3, _ = _run_worker("package", incompat_in, saved_file, "--asset-root", proj_dir)
    assert proc.returncode == 2
    assert json.loads(err3.read_text(encoding="utf-8"))["category"] == "incompatible_version"
    assert saved_file.read_bytes() == good_bytes

    # 4. Corrupt project JSON on disk -> recover restores last-valid project & assets cleanly
    saved_file.write_text("{corrupt json", encoding="utf-8")
    proc, err4, _ = _run_worker("validate", saved_file, tmp_path / "bad_json_out.json", "--asset-root", saved_dir)
    assert proc.returncode == 2
    assert json.loads(err4.read_text(encoding="utf-8"))["category"] == "corrupt_document"

    rec_out = tmp_path / "recovered.json"
    proc, rec_err, _ = _run_worker("recover", saved_file, rec_out, "--restore-to", str(saved_file))
    assert proc.returncode == 0, proc.stderr
    assert not rec_err.exists()
    rec_payload = json.loads(rec_out.read_text(encoding="utf-8"))
    assert rec_payload["recovered"] is True
    assert first_asset.read_bytes() == original_asset_bytes
    proc, _, _ = _run_worker("validate", saved_file, tmp_path / "revalidated.json", "--asset-root", saved_dir)
    assert proc.returncode == 0, proc.stderr


def test_godot_desktop_exposes_workflow_and_dual_visual_profile_without_http():
    main_gd = (ROOT / "apps" / "desktop" / "main.gd").read_text(encoding="utf-8")
    for required_symbol in (
        "_open_new_project_dialog",
        "_create_new_project",
        "_import_design",
        "_open_project",
        "_save_project",
        "_save_version",
        "_open_versions_dialog",
        "_reopen_selected_version",
        "_recover_last_valid",
        "_apply_visual_profile",
        "TONE_MAPPER_ACES",
        "ProceduralSkyMaterial",
        "RenderingServer.get_rendering_device()",
    ):
        assert required_symbol in main_gd

    # Standalone offline guarantee: desktop scripts must not call localhost/HTTP API servers
    for gd_path in (ROOT / "apps" / "desktop").glob("*.gd"):
        text = gd_path.read_text(encoding="utf-8")
        assert "http://" not in text and "https://" not in text

    project_godot = (ROOT / "apps" / "desktop" / "project.godot").read_text(encoding="utf-8")
    assert 'renderer/rendering_method="gl_compatibility"' in project_godot
