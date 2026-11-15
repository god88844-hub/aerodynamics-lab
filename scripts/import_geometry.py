"""CLI utility for importing external geometry (STL/OBJ/glTF) into AeroForge.

Milestone 0 placeholder: the import/validation pipeline (scale check,
manifoldness, watertightness, inertia computation from mesh) is implemented
when the editor needs it (M5). Imports are validated for scale and
manifoldness per the build specification before they may enter a design.
"""

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(description="Import and validate external geometry.")
    parser.add_argument("file", help="STL/OBJ/glTF file to import.")
    args = parser.parse_args()
    print(f"Geometry import for {args.file!r} lands with Milestone 5 (editor).")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
