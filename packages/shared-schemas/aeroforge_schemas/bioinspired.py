"""Versioned Phase 1 (Bio-Inspired Flight) geometry, kinematics, compliance, and provenance contracts.

Note: Separate from frozen WP1-WP3 foundation contracts (`foundation.py`, `project.py`, `cad.py`).
Validation of a schema document certifies structure and SI/frame conformance only; never physical acceptance.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, FiniteFloat, StrictBool, StrictInt, model_validator

from aeroforge_schemas.foundation import Digest, Frames, Positive
from aeroforge_schemas.project import Identifier, ProjectModel


class FlappingWingKinematics(ProjectModel):
    """Per-wing flapping stroke, deviation, and feathering kinematics in SI radians/Hz."""

    contract_version: Literal["bio_flapping_1"] = "bio_flapping_1"
    wing_span_r_m: Positive
    mean_chord_c_m: Positive
    flap_frequency_hz: FiniteFloat = Field(gt=0.0, le=350.0)
    stroke_amplitude_rad: FiniteFloat = Field(gt=0.0, le=1.65)
    stroke_plane_angle_rad: FiniteFloat = Field(ge=-1.571, le=1.571)
    feathering_amplitude_rad: FiniteFloat = Field(ge=0.0, le=1.45)
    deviation_amplitude_rad: FiniteFloat = Field(ge=0.0, le=0.6)
    r11_moment: FiniteFloat = Field(gt=0.0, le=1.0)
    r22_moment: FiniteFloat = Field(gt=0.0, le=1.0)
    r33_moment: FiniteFloat = Field(gt=0.0, le=1.0)
    frames: Frames = Field(default_factory=Frames)

    @model_validator(mode="after")
    def ordered_moments(self):
        if self.r33_moment > self.r22_moment or self.r22_moment > self.r11_moment:
            raise ValueError("Radial moments must satisfy 0 < r33 <= r22 <= r11 <= 1")
        return self


class MorphingWingState(ProjectModel):
    """Articulated shoulder/wrist/tail morphing configuration (SI, dimensionless 0..1 morph inputs)."""

    contract_version: Literal["bio_morphing_1"] = "bio_morphing_1"
    baseline_span_m: Positive
    baseline_area_m2: Positive
    wing_tuck_fraction: FiniteFloat = Field(ge=0.0, le=1.0)
    wing_asymmetry_diff: FiniteFloat = Field(ge=-0.5, le=0.5)
    tail_spread_fraction: FiniteFloat = Field(ge=0.0, le=1.0)
    tail_tilt_rad: FiniteFloat = Field(ge=-0.785, le=0.785)
    tail_elevator_rad: FiniteFloat = Field(ge=-0.65, le=0.65)
    frames: Frames = Field(default_factory=Frames)


class CompliantFlexureSpec(ProjectModel):
    """Compliant unibody flexure and Euler-Bernoulli flexible beam structural spec."""

    contract_version: Literal["bio_flexure_1"] = "bio_flexure_1"
    material_id: Identifier
    density_kg_m3: Positive
    density_source: str = Field(min_length=3, max_length=200)
    flexural_rigidity_ei_nm2: Positive
    torsional_rigidity_gj_nm2: Positive
    endurance_fatigue_limit_pa: Positive
    fatigue_safety_factor_min: FiniteFloat = Field(ge=1.0)
    max_cycle_count_budget: StrictInt = Field(ge=100)


class UnsteadyAeroEnvelope(ProjectModel):
    """Valid incompressible bio-inspired unsteady regime bounds (fail closed outside)."""

    max_tip_mach: FiniteFloat = Field(gt=0.0, le=0.25)
    reynolds_min: Positive
    reynolds_max: Positive
    strouhal_min: FiniteFloat = Field(ge=0.0, le=1.5)
    strouhal_max: FiniteFloat = Field(gt=0.0, le=2.5)
    max_reduced_freq_k: FiniteFloat = Field(gt=0.0, le=2.0)

    @model_validator(mode="after")
    def ordered_bounds(self):
        if self.reynolds_max < self.reynolds_min:
            raise ValueError("reynolds_max must be >= reynolds_min")
        if self.strouhal_max < self.strouhal_min:
            raise ValueError("strouhal_max must be >= strouhal_min")
        return self


class BioInspiredVehicleContract(ProjectModel):
    """Top-level Phase 1 contract uniting geometry/kinematics, compliance, and source status."""

    contract_version: Literal["bioinspired_vehicle_1"] = "bioinspired_vehicle_1"
    id: Identifier
    bio_mode: Literal["flapping_wing", "morphing_wing", "compliant_flex"]
    total_mass_kg: Positive
    flapping: FlappingWingKinematics | None = None
    morphing: MorphingWingState | None = None
    flexure: CompliantFlexureSpec
    envelope: UnsteadyAeroEnvelope
    reference_dataset_sha256: Digest | None = None
    biological_scaling_prohibited: StrictBool = True
    physical_validation_status: Literal["UNVALIDATED_BIOINSPIRED", "DEVELOPMENT"] = "UNVALIDATED_BIOINSPIRED"

    @model_validator(mode="after")
    def require_mode_spec(self):
        if self.bio_mode in ("flapping_wing", "compliant_flex") and self.flapping is None:
            raise ValueError("flapping_wing and compliant_flex require a FlappingWingKinematics block")
        if self.bio_mode == "morphing_wing" and self.morphing is None:
            raise ValueError("morphing_wing requires a MorphingWingState block")
        return self
