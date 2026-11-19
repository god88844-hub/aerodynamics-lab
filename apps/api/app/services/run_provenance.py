"""Fingerprint installed model files and record the numerical environment."""

from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import platform

ROOT = Path(__file__).resolve().parents[4]


def capture_provenance() -> dict:
    files = [
        *ROOT.glob("packages/**/*.py"),
        *ROOT.glob("apps/api/app/**/*.py"),
        *ROOT.glob("data/components/**/*.json"),
    ]
    lock = ROOT / "apps/api/requirements.lock"
    if not lock.is_file():
        lock = ROOT / "requirements.lock"  # packaged API location
    record = {
        "files_sha256": {
            path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
            for path in sorted(files)
        },
        "component_data": {
            path.relative_to(ROOT).as_posix(): json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(ROOT.glob("data/components/**/*.json"))
        },
        "dependency_lock_sha256": sha256(lock.read_bytes()).hexdigest(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "operating_system": platform.system(),
        "machine": platform.machine(),
        "package_versions": {
            name: version(name)
            for name in ("numpy", "scipy", "pydantic", "fastapi", "sqlalchemy", "ezdxf")
        },
    }
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return {"sha256": sha256(canonical.encode("utf-8")).hexdigest(), **record}
