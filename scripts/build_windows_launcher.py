"""Compile a branded console-free Windows AerodynamicsLab.exe launcher with custom app icon."""

from __future__ import annotations

from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def write_ico_from_png(png_path: Path, ico_path: Path) -> None:
    """Wrap an existing square RGBA PNG inside a standard Windows ICO container."""
    png_bytes = png_path.read_bytes()
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", 128, 128, 0, 0, 1, 32, len(png_bytes), 22)
    ico_path.write_bytes(header + entry + png_bytes)


def build_launcher() -> Path:
    out_dir = ROOT / ".local" / "release"
    out_dir.mkdir(parents=True, exist_ok=True)
    ico_path = out_dir / "aerodynamics_lab.ico"
    rc_path = out_dir / "launcher.rc"
    res_path = out_dir / "launcher.res"
    cpp_path = out_dir / "launcher.cpp"
    exe_path = out_dir / "AerodynamicsLab.exe"

    write_ico_from_png(ROOT / "apps" / "desktop" / "icon.png", ico_path)
    rc_path.write_text('1 ICON "aerodynamics_lab.ico"\n', encoding="utf-8")
    cpp_path.write_text(
        r'''#include <windows.h>
#include <string>

int WINAPI WinMain(HINSTANCE, HINSTANCE, LPSTR, int) {
    wchar_t exeBuf[MAX_PATH];
    GetModuleFileNameW(nullptr, exeBuf, MAX_PATH);
    std::wstring dir(exeBuf);
    dir = dir.substr(0, dir.find_last_of(L"\\/"));
    std::wstring root = dir + L"\\..\\..";
    std::wstring godot = root + L"\\.local\\tools\\godot\\Godot_v4.7.2-stable_win64.exe";
    std::wstring desk = root + L"\\apps\\desktop";
    std::wstring cmd = L"\"" + godot + L"\" --path \"" + desk + L"\" --rendering-driver vulkan --rendering-method forward_plus";
    STARTUPINFOW si{};
    si.cb = sizeof(si);
    PROCESS_INFORMATION pi{};
    if (!CreateProcessW(nullptr, cmd.data(), nullptr, nullptr, FALSE, 0, nullptr, root.c_str(), &si, &pi)) {
        MessageBoxW(nullptr, L"Could not launch Aerodynamics Lab runtime.", L"Aerodynamics Lab", MB_ICONERROR);
        return 1;
    }
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
    return 0;
}
''',
        encoding="utf-8",
    )
    subprocess.run(["windres", str(rc_path), "-O", "coff", "-o", str(res_path)], check=True, cwd=out_dir)
    subprocess.run(["g++", "-O2", "-mwindows", "-static", str(cpp_path), str(res_path), "-o", str(exe_path)], check=True, cwd=out_dir)
    return exe_path


if __name__ == "__main__":
    built = build_launcher()
    print(f"Built {built} ({built.stat().st_size} bytes)")
