"""Public contract entry points, invalid boundaries and source-controlled locks."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest
from pydantic import ValidationError

from aeroforge_schemas.foundation import AeroSurface, EvidenceRecord, Frames, JobRecord, ResourceLimits
from desktop_worker.resources import ResourceBudget

ROOT = Path(__file__).resolve().parents[2]
DIGEST = "a" * 64


def surface():
    return {"id": "blade", "kind": "rotating_blade",
        "geometry": {"id": "exact", "path": "blade.step", "sha256": DIGEST, "role": "exact_geometry"},
        "reference_area_m2": .01, "reference_span_m": .2, "reference_chord_m": .05,
        "moment_datum_body_m": [0,0,0], "execution_backend": "bemt_planned",
        "stations": [{"span_or_radius_m": radius, "chord_m": .05, "twist_rad": .1,
                      "leading_edge_surface_m": [0,radius,0], "polar_asset_id": "polar"} for radius in (.02,.2)],
        "polars": [{"asset": {"id": "polar", "path": "polar.json", "sha256": DIGEST, "role": "parametric_source"},
                    "source_class": "synthetic", "envelope": {"reynolds_min": 10000, "reynolds_max": 20000,
                        "mach_min": 0, "mach_max": .1, "alpha_min_rad": -.2, "alpha_max_rad": .2}}]}


def cli(tmp_path, contract, document, executable=False):
    source = tmp_path / "in.json"
    output = tmp_path / "out.json"
    source.write_text(json.dumps(document), encoding="utf-8")
    if output.exists():
        output.unlink()
    command = [sys.executable, str(ROOT / "scripts/lab_contract.py"), contract, str(source), str(output)]
    if executable:
        command.append("--require-executable")
    return subprocess.run(command, capture_output=True, text=True), output


def test_surface_contract_roundtrip_does_not_invent_an_execution_backend(tmp_path):
    result, path = cli(tmp_path, "geometry_aero", surface())
    assert result.returncode == 0, result.stderr
    normalized = json.loads(path.read_bytes())
    assert normalized["document"] == AeroSurface.model_validate(surface()).model_dump(mode="json")
    assert normalized["physical_validation_status"] == "unvalidated"
    result, path = cli(tmp_path, "geometry_aero", surface(), executable=True)
    assert result.returncode == 2 and "UNSUPPORTED" in result.stderr
    assert not path.exists()


@pytest.mark.parametrize("case", ["display", "missing_polar", "nonfinite", "degrees", "left_handed", "station_order", "quaternion", "accepted"])
def test_surface_rejects_invalid_engineering_boundaries(case):
    document = surface()
    if case == "display": document["geometry"]["role"] = "display_mesh"
    if case == "missing_polar": document["polars"] = []
    if case == "nonfinite": document["reference_area_m2"] = float("nan")
    if case == "degrees": document["frames"] = {"angles": "deg"}
    if case == "left_handed": document["frames"] = {"world": "left_handed_y_up"}
    if case == "station_order": document["stations"].reverse()
    if case == "quaternion": document["placement"] = {"rotation_surface_to_body_wxyz": [2,0,0,0]}
    if case == "accepted": document["physical_validation_status"] = "validated"
    with pytest.raises(ValidationError):
        AeroSurface.model_validate(document)


def test_cli_refuses_wrong_units_without_publishing_success(tmp_path):
    result, output = cli(tmp_path, "frames", {"units": "imperial"})
    assert result.returncode == 2 and not output.exists()


@pytest.mark.parametrize("change", [{}, {"memory_bytes": True}, {"memory_bytes": "1048576"},
    {"wall_time_s": True}, {"workspace_bytes": 0}, {"wall_time_s": float("inf")}, {"extra": 1}])
def test_stdlib_supervisor_and_shared_resource_contract_agree(change):
    outcomes = []
    documents = []
    for validate in (ResourceBudget.from_dict, ResourceLimits.model_validate):
        try:
            result = validate(deepcopy(change))
            documents.append(result.document() if isinstance(result, ResourceBudget) else result.model_dump(mode="json"))
            outcomes.append(True)
        except (ValueError, TypeError):
            outcomes.append(False)
    assert outcomes[0] == outcomes[1]
    if outcomes[0]: assert documents[0] == documents[1]


def test_evidence_data_cannot_assert_acceptance_or_relabel_revealed_data():
    document = {"dataset_sha256": DIGEST, "source_url": "https://example.org/original",
                "license": "CC0", "source_class": "independent_measurement", "role": "development",
                "experiment_ids": ["flight1"], "previously_revealed": True}
    assert EvidenceRecord.model_validate(document).physical_validation_status == "unvalidated"
    with pytest.raises(ValidationError):
        EvidenceRecord.model_validate({**document, "role": "confirmatory"})
    with pytest.raises(ValidationError):
        EvidenceRecord.model_validate({**document, "physical_validation_status": "accepted"})
    with pytest.raises(ValidationError):
        EvidenceRecord.model_validate({**document, "role": "confirmatory", "previously_revealed": False})


def test_successful_job_requires_both_output_and_resource_approval():
    solver = {"backend_id": "cad_torque_1", "algorithm": "rk4_fixed_step", "step_s": .005,
              "model": {"model_id": "rigid_body", "version": "1", "source_sha256": DIGEST,
                        "environment_sha256": DIGEST, "parameter_sha256": DIGEST}}
    document = {"job_id": "1"*32, "state": "succeeded", "request_sha256": DIGEST,
                "solver": solver, "resources": {}}
    with pytest.raises(ValidationError):
        JobRecord.model_validate(document)
    assert JobRecord.model_validate({**document, "output_sha256": DIGEST, "resource_approval_sha256": DIGEST})


def test_machine_contracts_and_policy_match_frozen_exports():
    result = subprocess.run([sys.executable, str(ROOT / "scripts/export_contracts.py"), "--check"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    policy = json.loads((ROOT / "docs/contracts/wp1-wp3-1/validation-policy.json").read_bytes())
    assert set(policy["criteria"]) == {"M"+str(x) for x in range(21,28)}
    assert policy["historical_campaign_role"] == "DEVELOPMENT"
    assert policy["criteria"]["M27"]["coverage_unit"] == "whole_flight_joint_all_critical_outputs_and_times"
