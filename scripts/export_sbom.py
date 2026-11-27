"""Generate deterministic CycloneDX-style SBOM & license inventory from pinned lockfiles (P0D-025)."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _parse_pip_lock(lock_path: Path, group: str) -> list[dict[str, Any]]:
    components = []
    if not lock_path.is_file():
        return components
    pattern = re.compile(r"^([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+)")
    for raw_line in lock_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        m = pattern.match(line)
        if m:
            components.append({"name": m.group(1), "version": m.group(2), "ecosystem": "pypi", "lock_group": group})
    return components


def _parse_npm_lock(lock_path: Path) -> list[dict[str, Any]]:
    components = []
    if not lock_path.is_file():
        return components
    data = json.loads(lock_path.read_text(encoding="utf-8"))
    packages = data.get("packages") or {}
    for pkg_path, info in sorted(packages.items()):
        if not pkg_path or not isinstance(info, dict):
            continue
        name = pkg_path.split("node_modules/")[-1]
        version = info.get("version")
        if version:
            components.append(
                {
                    "name": name,
                    "version": str(version),
                    "ecosystem": "npm",
                    "license": info.get("license", "UNKNOWN"),
                    "dev": bool(info.get("dev", False)),
                }
            )
    return components


def build_sbom(repo_root: Path = ROOT) -> dict[str, Any]:
    api_deps = _parse_pip_lock(repo_root / "apps/api/requirements.lock", "backend_api_worker")
    cad_deps = _parse_pip_lock(repo_root / "apps/desktop/requirements-cad.lock", "cad_worker")
    web_deps = _parse_npm_lock(repo_root / "apps/web/package-lock.json")

    license_file = repo_root / "LICENSE"
    notices = ["LICENSE"]
    if (repo_root / "apps/desktop/bin/godot-cpp-LICENSE.txt").is_file():
        notices.append("apps/desktop/bin/godot-cpp-LICENSE.txt")

    all_components = api_deps + cad_deps + web_deps
    doc = {
        "bomFormat": "CycloneDX-Subset",
        "specVersion": "1.5",
        "project": "Aerodynamics Lab",
        "project_license": "Apache-2.0",
        "license_sha256": sha256(license_file.read_bytes()).hexdigest() if license_file.is_file() else None,
        "notice_files": notices,
        "counts": {
            "total": len(all_components),
            "pypi_backend": len(api_deps),
            "pypi_cad": len(cad_deps),
            "npm_web": len(web_deps),
        },
        "components": all_components,
    }
    doc["sbom_sha256"] = sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return doc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    args = parser.parse_args()
    sbom = build_sbom(ROOT)
    text = json.dumps(sbom, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(json.dumps(sbom["counts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
