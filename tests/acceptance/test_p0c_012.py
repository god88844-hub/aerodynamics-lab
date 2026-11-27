"""P0C-012: Budgeted local & remote detailed-job execution, cancellation, OOM refusal, and equivalence."""

from __future__ import annotations

import pytest

from physics.aerodynamics.rotorcraft_vtol import execute_detailed_solver_job


def test_p0c_012_budget_refusal_cancellation_and_local_remote_equivalence():
    oom = execute_detailed_solver_job(
        solver_kind="openfoam_rans", mesh_cell_count=8_000_000, estimated_ram_mb=24_000, available_ram_mb=16_000, execution_target="local"
    )
    assert oom["job_status"] == "refused_budget"
    assert oom["solution_cl"] is None
    assert oom["cleaned_up"] is True

    cancelled = execute_detailed_solver_job(
        solver_kind="calculix_fea", mesh_cell_count=200_000, estimated_ram_mb=2000, available_ram_mb=16_000, cancel_requested=True
    )
    assert cancelled["job_status"] == "cancelled"
    assert cancelled["cleaned_up"] is True

    local_ok = execute_detailed_solver_job(
        solver_kind="xflr5_polar", mesh_cell_count=150_000, estimated_ram_mb=1500, available_ram_mb=16_000, execution_target="local"
    )
    remote_ok = execute_detailed_solver_job(
        solver_kind="xflr5_polar", mesh_cell_count=150_000, estimated_ram_mb=1500, available_ram_mb=64_000, execution_target="remote"
    )
    assert local_ok["converged_metric"] == pytest.approx(remote_ok["converged_metric"], abs=1e-9)
