"""Tests for unified Virtual-vs-Real Evidence Scorecard classification."""

from __future__ import annotations

import pytest

from physics.validation.virtual_evidence_scorecard import compute_virtual_evidence_scorecard


def test_scorecard_development_when_parity_and_envelope_pass() -> None:
    card = compute_virtual_evidence_scorecard(
        vehicle_family="multirotor",
        cpp_mass_kg=3.512,
        python_mass_kg=3.512,
        clearance_ok=True,
        mach=0.05,
        alpha_deg=5.0,
        has_custom_modified_part=False,
        benchmark_twin_percent=94.2,
    )
    assert card["numerical_verification"]["parity_pass"] is True
    assert card["overall_status"] == "DEVELOPMENT"
    assert card["physical_acceptance_granted"] is False


def test_scorecard_fails_closed_on_clearance_or_stall_or_mach() -> None:
    bad = compute_virtual_evidence_scorecard(
        vehicle_family="fixed_wing",
        cpp_mass_kg=2.2,
        python_mass_kg=2.2,
        clearance_ok=False,
        mach=0.35,
        alpha_deg=16.0,
    )
    assert bad["overall_status"] == "FAIL"
    assert len(bad["envelope_failures"]) == 3


def test_scorecard_marks_custom_part_unvalidated() -> None:
    custom = compute_virtual_evidence_scorecard(
        vehicle_family="multirotor",
        cpp_mass_kg=3.6,
        python_mass_kg=3.6,
        clearance_ok=True,
        mach=0.04,
        alpha_deg=4.0,
        has_custom_modified_part=True,
    )
    assert custom["overall_status"] == "UNVALIDATED_CUSTOM"


def test_scorecard_rejects_nonfinite() -> None:
    with pytest.raises(ValueError, match="finite"):
        compute_virtual_evidence_scorecard(
            vehicle_family="vtol",
            cpp_mass_kg=float("nan"),
            python_mass_kg=1.0,
            clearance_ok=True,
            mach=0.1,
            alpha_deg=2.0,
        )
