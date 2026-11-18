"""Regressions for MODERA command matching and group holdout isolation."""
from pathlib import Path
import runpy

import pytest

bench = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/benchmark_modera_vertical_force.py"))


def test_command_loader_canonicalizes_and_rejects_duplicates():
    header = ",".join(bench["HEADER"])
    supported = "0.85,0.850000000000001,0.1,1.0,0,0,1,0,0,0"
    unsupported = "0.01,0.85,0.1,1.0,0,0,1,0,0,0"
    loader = bench["read_commands"]
    assert loader(f"{header}\n{supported}\n{unsupported}\n") == ({(0.85, 0.85, 0.1, 1.0): "1"}, 1)
    with pytest.raises(ValueError, match="Duplicate canonical"):
        loader(f"{header}\n{supported}\n{supported}\n")


def test_fit_never_parses_vertical_force_for_reserved_pairs():
    headings = bench["ANGLES"]
    records = {(t,) * 4: dict.fromkeys(headings, str(4 * t)) for t in bench["THROTTLES"]}
    records[(0.25, 0.25, 0.10, 0.10)] = dict.fromkeys(headings, "0.72")
    records[(0.25, 0.10, 0.25, 0.10)] = dict.fromkeys(headings, "0.69")
    records[(0.55, 0.55, 0.10, 0.10)] = dict.fromkeys(headings, "unopened")
    fit = bench["fit"](records)
    assert fit["calibration_mixed_configurations"] == {"adjacent": 1, "diagonal": 1}
    assert fit["quadratic_throttle_difference_coefficient_n"] == pytest.approx({
        "adjacent": -4 / 9, "diagonal": 8 / 9, "pooled": 2 / 9
    })
