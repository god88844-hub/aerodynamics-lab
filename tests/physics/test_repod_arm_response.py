"""Synthetic regression tests for the arm-response benchmark."""
from pathlib import Path
import runpy

import pytest

bench = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/benchmark_repod_arm_response.py"))


def test_calibration_parser_skips_held_out_numeric_cells(tmp_path):
    path = tmp_path / "example.csv"
    rows = [",".join(bench["HEADER"])]
    for material, infill in bench["CONFIGURATIONS"]:
        for stroke in bench["STROKES"]:
            rows.extend(f"{material},{infill},1,{stroke},{stroke},unused,{2 * stroke}" for _ in range(30))
    rows.append("PLA,100%,4,1,unopened,unused,unopened")
    path.write_text("\n".join(rows) + "\n")
    records = bench["read_strokes"](path, (1,))
    assert len(records) == 20
    assert bench["stiffness"](records) == pytest.approx(2)
    with pytest.raises(ValueError):
        bench["read_strokes"](path, (4,))


def test_missing_stroke_is_an_error(tmp_path):
    path = tmp_path / "example.csv"
    path.write_text(",".join(bench["HEADER"]) + "\nPLA,100%,1,1,1,unused,1\n")
    with pytest.raises(ValueError, match="complete measured stroke"):
        bench["read_strokes"](path, (1,))
