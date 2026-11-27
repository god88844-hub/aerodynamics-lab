"""P0B-010: Aerodynamic analysis job adapters, progress, cancellation, convergence, and VLM/CFD refusal."""

from __future__ import annotations

import pytest

from geometry.fixed_wing_cad import ParametricWingSpec
from physics.aerodynamics.fixed_wing import run_fixed_wing_analysis_job


def test_p0b_010_analysis_job_progress_convergence_and_cancellation():
    wing = ParametricWingSpec(name="JobWing", wingspan_m=1.8, root_chord_m=0.26, tip_chord_m=0.14)
    done = run_fixed_wing_analysis_job(wing, backend="lifting_line_prandtl_fourier", alpha_deg=4.0, airspeed_m_s=18.0)
    assert done["status"] == "completed"
    assert done["progress_log"] == [0.25, 0.65, 1.0]
    assert done["discretization_error_cl"] >= 0.0
    assert done["convergence"]["refinement_monotone"] is True
    assert done["physical_validation_status"] == "UNVALIDATED"

    cancelled = run_fixed_wing_analysis_job(wing, cancel_requested=True)
    assert cancelled["status"] == "cancelled"
    assert cancelled["progress_log"] == [0.25]
    assert cancelled["result"] is None


def test_p0b_010_planned_vlm_cfd_backends_cannot_execute_falsely():
    wing = ParametricWingSpec(name="BlockedWing", wingspan_m=1.8, root_chord_m=0.26, tip_chord_m=0.14)
    for backend in ("vlm", "rans_cfd"):
        with pytest.raises(NotImplementedError, match="planned/unimplemented"):
            run_fixed_wing_analysis_job(wing, backend=backend)
