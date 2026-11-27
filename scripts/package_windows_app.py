"""CLI entry point to stage a standalone offline Aerodynamics Lab package & reproducible installer archive."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "packages"), str(ROOT / "packages/shared-schemas"), str(ROOT / "apps/api")]

from desktop_worker.windows_packaging import stage_standalone_package  # noqa: E402
from export_sbom import build_sbom  # noqa: E402


def create_reproducible_installer_archive(package_dir: Path, archive_path: Path) -> dict[str, object]:
    """Pack a staged standalone desktop package into a deterministic, timestamp-normalized ZIP archive."""
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    fixed_date = (2026, 11, 27, 0, 0, 0)
    files = sorted(p for p in package_dir.rglob("*") if p.is_file())
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file_path in files:
            rel = file_path.relative_to(package_dir).as_posix()
            info = zipfile.ZipInfo(filename=rel, date_time=fixed_date)
            info.external_attr = 0o644 << 16
            zf.writestr(info, file_path.read_bytes())
    digest = sha256(archive_path.read_bytes()).hexdigest()
    return {
        "archive_path": str(archive_path),
        "archive_sha256": digest,
        "file_count": len(files),
        "size_bytes": os.path.getsize(archive_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target_dir", type=Path)
    parser.add_argument("--zip", dest="zip_path", type=Path, help="Optional reproducible standalone ZIP archive path")
    args = parser.parse_args()
    summary = stage_standalone_package(args.target_dir, repo_root=ROOT)
    sbom = build_sbom(ROOT)
    sbom_path = Path(args.target_dir) / "SBOM_CycloneDX.json"
    sbom_path.write_text(json.dumps(sbom, indent=2) + "\n", encoding="utf-8")
    summary["sbom_path"] = str(sbom_path)
    summary["sbom_sha256"] = sbom["sbom_sha256"]
    if args.zip_path is not None:
        summary["installer_archive"] = create_reproducible_installer_archive(Path(args.target_dir), args.zip_path)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
