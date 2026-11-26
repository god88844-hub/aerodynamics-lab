"""Verify C++20 6-DoF RK4 native kernel parity/compilation and mobile visual-tier wiring."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENG_CORE = ROOT / "packages" / "engineering-core"


def test_mobile_graphics_presets_touch_gestures_and_gdextension_libraries():
    gd = (ROOT / "apps/desktop/main.gd").read_text(encoding="utf-8")
    for token in (
        "mobile_low",
        "forward_high",
        "forward_plus",
        "InputEventScreenDrag",
        "InputEventMagnifyGesture",
        "simulate_rk4",
        "_run_native_cpp_rk4",
    ):
        assert token in gd, f"missing {token} in main.gd"

    gde = (ROOT / "apps/desktop/lab_engineering.gdextension").read_text(encoding="utf-8")
    for target in ("android.debug.arm64", "android.release.arm64", "ios.release", "windows.release.x86_64", "linux.release.x86_64"):
        assert target in gde, f"missing GDExtension library mapping {target}"


def test_cpp20_core_builds_and_passes_native_rk4_ctest(tmp_path):
    cmake = shutil.which("cmake")
    if cmake is None:
        pytest.skip("cmake not installed on this host")
    build_dir = tmp_path / "cpp_build"
    cfg_cmd = [cmake, "-S", str(ENG_CORE), "-B", str(build_dir)]
    if shutil.which("ninja"):
        cfg_cmd.extend(["-G", "Ninja"])
    subprocess.run(cfg_cmd, check=True, cwd=ROOT)
    subprocess.run([cmake, "--build", str(build_dir), "--parallel", "2"], check=True, cwd=ROOT)
    ctest = shutil.which("ctest")
    assert ctest is not None
    subprocess.run([ctest, "--test-dir", str(build_dir), "--output-on-failure"], check=True, cwd=ROOT)
