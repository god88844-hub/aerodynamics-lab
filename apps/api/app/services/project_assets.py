"""Verify and copy declared project assets without replacing conflicting bytes."""

from hashlib import sha256
import os
from pathlib import Path
import tempfile

from aeroforge_schemas.project import EngineeringProject

MAX_ASSET_BYTES = 256 * 1024 * 1024


def asset_bytes(root: Path, relative_path: str, expected_sha256: str) -> bytes:
    root = root.resolve(strict=True)
    path = (root / relative_path).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Asset must be a regular file inside its project directory")
    with path.open("rb") as source:
        content = source.read(MAX_ASSET_BYTES + 1)
    if len(content) > MAX_ASSET_BYTES:
        raise ValueError("Asset exceeds the prototype's 256 MiB file-work limit")
    if sha256(content).hexdigest() != expected_sha256:
        raise ValueError(f"Asset SHA-256 mismatch for {relative_path}")
    return content


def verify_assets(project: EngineeringProject, root: Path) -> None:
    for asset in project.assets:
        asset_bytes(root, asset.path, asset.sha256)


def copy_assets(project: EngineeringProject, source_root: Path, destination: Path) -> None:
    destination_root = destination.parent.resolve(strict=True)
    for asset in project.assets:
        content = asset_bytes(source_root, asset.path, asset.sha256)
        target = destination_root / asset.path
        if target.resolve() == destination.resolve():
            raise ValueError("The project document path conflicts with an asset")
        if not target.resolve().is_relative_to(destination_root):
            raise ValueError("Destination asset escapes the project directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            asset_bytes(destination_root, asset.path, asset.sha256)
            continue
        descriptor, name = tempfile.mkstemp(prefix=".lab-asset-", dir=target.parent)
        staged = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            try:
                os.link(staged, target)
            except FileExistsError:
                asset_bytes(destination_root, asset.path, asset.sha256)
        finally:
            staged.unlink(missing_ok=True)
