"""Engineering inputs for the bounded blade CAD prototype."""

from typing import Literal

from pydantic import Field, FiniteFloat, model_validator

from aeroforge_schemas.project import EngineeringProject, ProjectModel, Vector3


class BladeStation(ProjectModel):
    radius_m: FiniteFloat = Field(gt=0)
    chord_m: FiniteFloat = Field(gt=0)
    twist_deg: FiniteFloat = Field(ge=-89, le=89)
    thickness_to_chord: FiniteFloat = Field(default=0.12, gt=0, le=0.4)


class BladeRecipe(ProjectModel):
    name: str = Field(default="Custom blade", min_length=1, max_length=200)
    stations: list[BladeStation] = Field(min_length=2, max_length=16)
    profile_samples: int = Field(default=48, ge=16, le=128)
    mesh_deflection_m: FiniteFloat = Field(default=0.00025, ge=0.000001, le=0.01)
    material_density_kg_m3: FiniteFloat | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def ordered_stations(self):
        if any(right.radius_m <= left.radius_m for left, right in zip(self.stations, self.stations[1:])):
            raise ValueError("blade stations must have strictly increasing radii")
        return self


class BoxRecipe(ProjectModel):
    recipe_type: Literal["box_1"] = "box_1"
    name: str = Field(default="Constrained test body", min_length=1, max_length=200)
    # Bounds are the prototype's modeling domain, not material operating limits.
    width_m: FiniteFloat = Field(default=0.2, ge=0.001, le=5)
    height_m: FiniteFloat = Field(default=0.1, ge=0.001, le=5)
    depth_m: FiniteFloat = Field(default=0.02, ge=0.001, le=5)
    material_density_kg_m3: FiniteFloat | None = Field(default=None, gt=0)
    mesh_deflection_m: FiniteFloat = Field(default=0.00025, ge=0.000001, le=0.01)


class TorqueExperiment(ProjectModel):
    experiment_version: Literal["cad_torque_1"] = "cad_torque_1"
    torque_body_nm: Vector3 = (0.0, 0.0, 0.001)
    duration_s: FiniteFloat = Field(default=1.0, ge=0.01, le=10)
    step_s: FiniteFloat = Field(default=0.005, ge=0.0001, le=0.05)

    @model_validator(mode="after")
    def resource_budget(self):
        if self.duration_s / self.step_s > 5000:
            raise ValueError("torque experiment exceeds the 5000-step prototype budget")
        return self


class CadTorqueRequest(ProjectModel):
    project: EngineeringProject
    experiment: TorqueExperiment = Field(default_factory=TorqueExperiment)
