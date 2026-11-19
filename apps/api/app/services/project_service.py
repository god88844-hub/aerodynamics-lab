"""Project validation and explicitly supported reference simulation."""

from hashlib import sha256

from aeroforge_schemas.project import EngineeringProject, Environment, LegacyMultirotorVehicle
from app.services.simulation_service import run_simulation
from app.services.run_provenance import capture_provenance


def run_project(project: EngineeringProject) -> dict:
    """Execute one declared backend without implying physical validation."""
    project = EngineeringProject.model_validate_json(project.canonical_bytes())
    if project.experiment.backend_id != "legacy_python":
        raise ValueError("This project has no implemented simulation backend")
    if not isinstance(project.vehicle, LegacyMultirotorVehicle):
        raise ValueError("The legacy backend requires a legacy multirotor snapshot")
    if project.environment != Environment():
        raise ValueError("The legacy backend supports only its fixed default environment")
    if project.experiment.seed != 0:
        raise ValueError("The legacy backend has no configurable random-seed adapter")
    model_environment = capture_provenance()
    report, inputs = run_simulation(
        project.vehicle.snapshot.model_dump(mode="json"),
        project.experiment.scenario, project.experiment.parameters,
    )
    if capture_provenance()["sha256"] != model_environment["sha256"]:
        raise ValueError("Model files, components or numerical environment changed during the run")
    return {
        "document_version": "1.0",
        "project": project.model_dump(mode="json"),
        "project_sha256": sha256(project.canonical_bytes()).hexdigest(),
        "backend_id": "legacy_python",
        "model_environment": model_environment,
        "physical_validation_status": "unvalidated",
        "inputs": inputs,
        "result": report,
    }
