"""Pytest configuration: make the monorepo's Python packages importable.

Mirrors the `pythonpath` setting in pyproject.toml so tests also pass when
invoked from tools that ignore the repo-level ini (IDE runners etc.).
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
for _p in (
    REPO_ROOT / "packages",
    REPO_ROOT / "packages" / "shared-schemas",
    REPO_ROOT / "apps" / "api",
):
    _s = str(_p)
    if _p.is_dir() and _s not in sys.path:
        sys.path.insert(0, _s)
