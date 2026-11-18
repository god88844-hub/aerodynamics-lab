"""Synthetic regressions for source pinning and interpolation boundaries."""
from hashlib import sha256
from pathlib import Path
import runpy

import pytest

bench = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/benchmark_uiuc_axial_sweeps.py"))


def test_interpolation_rejects_extrapolation_and_preserves_signed_thrust():
    curve = [(0.2, 0.03, 0.05), (0.6, -0.01, 0.01)]
    assert bench["interpolate"](curve, 0.2) == pytest.approx((0.03, 0.05))
    assert bench["interpolate"](curve, 0.4) == pytest.approx((0.01, 0.03))
    assert bench["interpolate"](curve, 0.6) == pytest.approx((-0.01, 0.01))
    with pytest.raises(ValueError, match="outside"):
        bench["interpolate"](curve, 0.61)


def test_sweep_requires_pinned_source_and_increasing_advance_ratio(tmp_path):
    file = tmp_path / "sweep.txt"
    data = b"J CT CP eta\n0.2 0.03 0.05 0.12\n0.1 0.02 0.04 0.05\n"
    file.write_bytes(data)
    with pytest.raises(ValueError, match="SHA-256"):
        bench["read_table"](file, "bad checksum", ("J", "CT", "CP", "eta"))
    with pytest.raises(ValueError, match="increasing"):
        bench["read_table"](file, sha256(data).hexdigest(), ("J", "CT", "CP", "eta"))
