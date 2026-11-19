"""Engineering inputs for the bounded blade CAD prototype."""

from pydantic import Field, FiniteFloat, model_validator

from aeroforge_schemas.project import ProjectModel


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
