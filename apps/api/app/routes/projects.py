"""Read-only project normalization and legacy import."""

import json

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, field_validator

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

    @field_validator("snapshot")
    @classmethod
    def finite_snapshot(cls, value):
        json.dumps(value.model_dump(mode="json"), allow_nan=False)
        return value


@router.post("/projects/import-legacy")
def import_legacy(body: LegacyImport) -> dict:
    project = import_legacy_project(body.snapshot.model_dump(mode="json"))
    return {"project": project.model_dump(mode="json"), "project_sha256": project.fingerprint()}
