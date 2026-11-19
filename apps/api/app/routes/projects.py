"""Read-only project normalization and legacy import."""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from aeroforge_schemas.design import DroneDesign
from aeroforge_schemas.project import EngineeringProject, import_legacy_project

router = APIRouter(tags=["projects"])


@router.get("/projects/schema")
def project_schema() -> dict:
    return EngineeringProject.model_json_schema()


@router.post("/projects/validate")
def validate_project(project: EngineeringProject) -> dict:
    return {"project": project.model_dump(mode="json"), "project_sha256": project.fingerprint()}


class LegacyImport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    snapshot: DroneDesign


@router.post("/projects/import-legacy")
def import_legacy(body: LegacyImport) -> dict:
    project = import_legacy_project(body.snapshot.model_dump(mode="json"))
    return {"project": project.model_dump(mode="json"), "project_sha256": project.fingerprint()}
