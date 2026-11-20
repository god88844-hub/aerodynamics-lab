"""Versioned, bounded requests for the local single-engine CAD worker."""

from typing import Literal

from pydantic import Field, JsonValue, model_validator

from aeroforge_schemas.cad import BladeRecipe, BoxRecipe, CadTorqueRequest
from aeroforge_schemas.project import ProjectModel

PROTOCOL = "desktop_worker_1"
MAX_REQUEST_BYTES = 16 * 1024 * 1024


class WorkerRequest(ProjectModel):
    protocol: Literal["desktop_worker_1"] = PROTOCOL
    session_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    job_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    operation: Literal["build-body", "build-blade", "cad-torque"]
    payload: dict[str, JsonValue]
    asset_root: str | None = Field(default=None, min_length=1, max_length=4096)

    @model_validator(mode="after")
    def supported_payload(self):
        models = {"build-body": BoxRecipe, "build-blade": BladeRecipe, "cad-torque": CadTorqueRequest}
        self.payload = models[self.operation].model_validate(self.payload).model_dump(mode="json")
        if self.operation == "cad-torque" and self.asset_root is None:
            raise ValueError("CAD torque requires an asset root")
        if self.operation != "cad-torque" and self.asset_root is not None:
            raise ValueError("Only CAD torque accepts an asset root")
        return self
