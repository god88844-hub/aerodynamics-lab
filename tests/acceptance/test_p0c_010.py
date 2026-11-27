"""P0C-010: Detailed aerodynamic solver workers, license/mesh/boundary contracts, and refusal of unimplemented backends."""

from __future__ import annotations

import pytest

from physics.aerodynamics.rotorcraft_vtol import build_detailed_solver_contract, execute_detailed_solver_job


def test_p0c_010_detailed_solver_contracts_license_and_refusal():
    for solver in ("openfoam_rans", "calculix_fea", "xflr5_polar"):
        contract = build_detailed_solver_contract(
            solver_kind=solver, mesh_cell_count=250_000, estimated_ram_mb=2000, available_ram_mb=16000
        )
        assert contract["admission_status"] == "admitted"
        assert len(contract["contract_sha256"]) == 64

    with pytest.raises(PermissionError, match="reviewed license sign-off missing"):
        execute_detailed_solver_job(
            solver_kind="openfoam_rans", mesh_cell_count=100_000, estimated_ram_mb=1000, available_ram_mb=16000, license_reviewed=False
        )
    with pytest.raises(ValueError, match="Unsupported detailed solver"):
        build_detailed_solver_contract(solver_kind="proprietary_unlicensed_cfd", mesh_cell_count=1000, estimated_ram_mb=500, available_ram_mb=16000)
