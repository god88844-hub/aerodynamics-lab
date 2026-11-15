"""AeroForge API application package.

This package's __init__ makes the monorepo's simulation packages importable
(``physics``, ``aeroforge_schemas``) so the API can be run directly with
uvicorn from ``apps/api`` without an editable install.
"""

from __future__ import annotations

import sys
from pathlib import Path

_API_DIR = Path(__file__).resolve().parent.parent  # apps/api
_REPO_ROOT = _API_DIR.parent.parent  # aeroforge/

for _pkg_dir in (_REPO_ROOT / "packages", _REPO_ROOT / "packages" / "shared-schemas"):
    _pkg_str = str(_pkg_dir)
    if _pkg_dir.is_dir() and _pkg_str not in sys.path:
        sys.path.insert(0, _pkg_str)
