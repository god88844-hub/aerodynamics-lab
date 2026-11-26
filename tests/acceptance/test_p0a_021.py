"""P0A-021 acceptance tests: repeatable engineering test-ground authoring,
save/reload serialization identity, and fail-closed refusal of unsupported weather/contact.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from aeroforge_schemas.project import EngineeringProject
from desktop_worker.environment_authoring import author_test_ground, validate_supported_environment

ROOT = Path(__file__).resolve().parents[2]
LAB_PROJECT = ROOT / "scripts" / "lab_project.py"
REFERENCE_DESIGN = ROOT / "data" / "designs" / "quad_mn3508_6s.json"


def test_test_ground_authoring_save_reload_identity(tmp_path):
    imported = tmp_path / "base.json"
    subprocess.run(
        [sys.executable, str(LAB_PROJECT), "import-legacy", str(REFERENCE_DESIGN), str(imported)],
        cwd=ROOT, check=True,
    )
    base_doc = json.loads(imported.read_text(encoding="utf-8"))

    ground_spec = {
        "terrain_kind": "graded_pad",
        "wind_world_m_s": [3.5, -1.2, 0.0],
        "temperature_k": 295.15,
        "pressure_pa": 99500.0,
        "relative_humidity": 0.45,
        "landing_surfaces": [
            {"id": "helipad_a", "center_m": [0.0, 0.0, 0.0], "size_m": [3.0, 3.0], "friction_coeff": 0.85}
        ],
        "obstacles": [
            {"id": "tower_1", "center_m": [5.0, 2.0, 1.5], "size_m": [1.0, 1.0, 3.0]}
        ],
    }
    req = tmp_path / "author_req.json"
    authored = tmp_path / "authored.json"
    req.write_text(json.dumps({"project": base_doc, "test_ground": ground_spec}), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(LAB_PROJECT), "author-ground", str(req), str(authored)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr

    # Save -> reload identity
    saved = tmp_path / "saved" / "project.json"
    reloaded = tmp_path / "reloaded.json"
    subprocess.run([sys.executable, str(LAB_PROJECT), "package", str(authored), str(saved)], cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(LAB_PROJECT), "validate", str(saved), str(reloaded)], cwd=ROOT, check=True)

    proj_saved = EngineeringProject.model_validate_json(saved.read_text(encoding="utf-8"))
    proj_reloaded = EngineeringProject.model_validate_json(reloaded.read_text(encoding="utf-8"))
    assert proj_saved.fingerprint() == proj_reloaded.fingerprint()
    assert proj_reloaded.environment.wind_world_m_s == (3.5, -1.2, 0.0)
    assert proj_reloaded.environment.temperature_k == 295.15
    assert proj_reloaded.environment.pressure_pa == 99500.0
    assert proj_reloaded.environment.relative_humidity == 0.45
    tg = proj_reloaded.experiment.parameters["test_ground"]
    assert tg["units"] == "SI"
    assert tg["world_frame"] == "local_right_handed_z_up"
    assert len(tg["obstacles"]) == 1


@pytest.mark.parametrize(
    "bad_patch,match",
    [
        ({"rain_mm_h": 4.0}, "rain/wet operation"),
        ({"snow_water_equivalent_mm_h": 2.0}, "snow accumulation"),
        ({"icing_requested": True}, "icing"),
        ({"landing_surfaces": [{"id": "bad", "contact_model": "mud_bog"}]}, "rigid_plane"),
    ],
)
def test_unsupported_atmospheric_and_contact_mechanisms_fail_closed(tmp_path, bad_patch, match):
    imported = tmp_path / "base.json"
    subprocess.run(
        [sys.executable, str(LAB_PROJECT), "import-legacy", str(REFERENCE_DESIGN), str(imported)],
        cwd=ROOT, check=True,
    )
    proj = EngineeringProject.model_validate_json(imported.read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match=match):
        author_test_ground(proj, bad_patch)
    if "rain_mm_h" in bad_patch:
        with pytest.raises(ValueError, match="rain"):
            validate_supported_environment(proj.environment.model_copy(update=bad_patch))


def test_desktop_wires_test_ground_authoring():
    main_gd = (ROOT / "apps" / "desktop" / "main.gd").read_text(encoding="utf-8")
    for sym in ("_open_test_ground_dialog", "_apply_test_ground", "author-ground"):
        assert sym in main_gd
