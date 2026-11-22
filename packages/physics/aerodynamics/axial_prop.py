"""Canonical signed axial-flow propeller regime (P0A-009).

Model of record for the M24 UIUC axial sweeps: the frozen coefficient-space
protocol (linear interpolation of the publisher's signed CT/CP columns in J
per calibration plane, blended linearly by RPM) lifted into exact SI space:

    J = V_a / (n D)          n = rpm / 60   [rev/s],  D [m]
    T = rho * n^2 * D^4 * CT(J, RPM)        [N]      (signed: CT < 0 = windmilling)
    Q = rho * n^2 * D^5 * CP(J, RPM) / (2 pi)  [N m]
    P = 2 pi n Q = rho * n^3 * D^5 * CP     [W]

Signs are preserved end to end (hover/climb CT > 0; windmilling CT < 0 gives
negative thrust; CP stays positive while the shaft absorbs power). The
body-frame force is the signed thrust projected on the declared rotor axis.

Fail-closed envelope contract: any query outside the supported signed regime
is refused with a typed error — nonpositive speed (n <= 0), reverse/vortex-ring
axial inflow (V_a < 0, unmodeled), RPM outside the calibration planes, or J
outside the calibration J support. ``classify`` provides the explicit
non-fatal OUT_OF_ENVELOPE labeling when a caller declares it wants names, not
refusals.

MODEL STATUS: interpolation of measured wind-tunnel coefficients inside the
measured envelope; no blade-element physics, no Reynolds/Mach correction, no
off-axis or installed-interference behavior. Results outside the declared
envelope are refused, not extrapolated.
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from math import isfinite, pi, sqrt

import numpy as np


class AxialEnvelopeError(ValueError):
    """The requested operating point lies outside the supported signed
    axial-flow regime — refused, not extrapolated (P0A-009)."""


@dataclass(frozen=True)
class PlaneKnots:
    """One measured calibration plane: (J, CT, CP) knots, J strictly
    increasing, values finite. The publisher's own signed coefficients."""

    knots: tuple[tuple[float, float, float], ...]

    def __post_init__(self) -> None:
        knots = self.knots
        if len(knots) < 2:
            raise ValueError("a calibration plane needs >= 2 knots")
        for j, ct, cp in knots:
            if not (isfinite(j) and isfinite(ct) and isfinite(cp)):
                raise ValueError("plane knots must be finite")
        if any(a[0] >= b[0] for a, b in zip(knots, knots[1:])):
            raise ValueError("plane knots must be strictly increasing in J")

    @property
    def j_support(self) -> tuple[float, float]:
        return (self.knots[0][0], self.knots[-1][0])

    def interpolate(self, j: float) -> tuple[float, float]:
        """Linear interpolation in J (the frozen M24 protocol's exact form)."""
        lo, hi = self.j_support
        if not lo <= j <= hi:
            raise AxialEnvelopeError(
                f"J {j:.6g} outside the measured plane support [{lo:.6g}, {hi:.6g}]")
        upper = max(1, bisect_left(self.knots, j, key=lambda row: row[0]))
        j_lo, ct_lo, cp_lo = self.knots[upper - 1]
        j_hi, ct_hi, cp_hi = self.knots[upper]
        weight = (j - j_lo) / (j_hi - j_lo)
        return (ct_lo + weight * (ct_hi - ct_lo),
                cp_lo + weight * (cp_hi - cp_lo))


@dataclass(frozen=True)
class AxialEnvelope:
    """The supported signed regime, declared by the caller from frozen
    calibration evidence (never hardcoded per propeller in this module)."""

    rpm_min: float
    rpm_max: float
    j_min: float
    j_max: float
    provenance: str

    def __post_init__(self) -> None:
        for name, value in (("rpm_min", self.rpm_min), ("rpm_max", self.rpm_max),
                            ("j_min", self.j_min), ("j_max", self.j_max)):
            if not isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and > 0")
        if self.rpm_min > self.rpm_max or self.j_min > self.j_max:
            raise ValueError("envelope bounds are inverted")

    def violation(self, rpm: float, j: float) -> str | None:
        if not self.rpm_min <= rpm <= self.rpm_max:
            return (f"RPM {rpm:.6g} outside the calibration envelope "
                    f"[{self.rpm_min:.6g}, {self.rpm_max:.6g}]")
        if not self.j_min <= j <= self.j_max:
            return (f"J {j:.6g} outside the calibration envelope "
                    f"[{self.j_min:.6g}, {self.j_max:.6g}]")
        return None


@dataclass(frozen=True)
class AxialLoad:
    """One SI-space axial operating point (all signed quantities)."""

    rpm: float
    n_rev_s: float
    axial_speed_m_s: float
    j: float
    ct: float
    cp: float
    thrust_n: float
    torque_n_m: float
    power_w: float
    air_density_kg_m3: float
    diameter_m: float


class AxialPropellerModel:
    """Signed axial-flow regime: two calibration planes blended by RPM.

    Exactly two planes, matching the frozen M24 protocol (linear in J per
    plane, linear in RPM between planes). The envelope and the diameter are
    declared caller inputs bound to frozen calibration evidence.
    """

    def __init__(
        self,
        planes: tuple[tuple[float, PlaneKnots], tuple[float, PlaneKnots]],
        diameter_m: float,
        envelope: AxialEnvelope,
    ) -> None:
        rpms = tuple(sorted(rpm for rpm, _ in planes))
        if len(set(rpms)) != 2:
            raise ValueError("exactly two distinct calibration planes are required")
        self._low_rpm, self._high_rpm = rpms
        self._planes = dict(planes)
        if not isfinite(diameter_m) or diameter_m <= 0.0:
            raise ValueError("diameter_m must be finite and > 0")
        self._diameter_m = float(diameter_m)
        if not isinstance(envelope, AxialEnvelope):
            raise ValueError("envelope must be an AxialEnvelope")
        # The declared envelope must sit inside BOTH planes' measured support.
        for rpm, knots in planes:
            lo, hi = knots.j_support
            if not (lo <= envelope.j_min and envelope.j_max <= hi):
                raise ValueError(
                    f"declared J envelope [{envelope.j_min:.6g}, {envelope.j_max:.6g}] "
                    f"is not inside the measured support of the {rpm:g} RPM plane "
                    f"[{lo:.6g}, {hi:.6g}]")
        self._envelope = envelope
        # The RPM blend weight must be well defined inside the envelope.
        if self._high_rpm == self._low_rpm:
            raise ValueError("calibration planes must differ in RPM")

    @property
    def envelope(self) -> AxialEnvelope:
        return self._envelope

    @property
    def diameter_m(self) -> float:
        return self._diameter_m

    def _blend_weight(self, rpm: float) -> float:
        return (rpm - self._low_rpm) / (self._high_rpm - self._low_rpm)

    def coefficients(self, j: float, rpm: float) -> tuple[float, float]:
        """Signed coefficients at (J, RPM): envelope-checked, no extrapolation."""
        if not (isfinite(j) and isfinite(rpm)):
            raise AxialEnvelopeError("J and RPM must be finite")
        violation = self._envelope.violation(rpm, j)
        if violation is not None:
            raise AxialEnvelopeError(violation)
        lo_ct, lo_cp = self._planes[self._low_rpm].interpolate(j)
        hi_ct, hi_cp = self._planes[self._high_rpm].interpolate(j)
        weight = self._blend_weight(rpm)
        return (lo_ct + weight * (hi_ct - lo_ct),
                lo_cp + weight * (hi_cp - lo_cp))

    def classify(self, rpm: float, axial_speed_m_s: float,
                 air_density_kg_m3: float) -> str:
        """Non-fatal labeling: 'supported' or 'out_of_envelope: <reason>'.

        Declared refusal reasons: n <= 0, reverse/vortex-ring axial inflow
        (V_a < 0 — unmodeled), RPM or J outside the calibration envelope.
        """
        try:
            self.evaluate(rpm, axial_speed_m_s, air_density_kg_m3)
        except AxialEnvelopeError as exc:
            return f"out_of_envelope: {exc}"
        return "supported"

    def evaluate(self, rpm: float, axial_speed_m_s: float,
                 air_density_kg_m3: float) -> AxialLoad:
        """One SI-space operating point through the exact signed equations."""
        if not (isfinite(rpm) and isfinite(axial_speed_m_s)
                and isfinite(air_density_kg_m3)):
            raise AxialEnvelopeError("rpm, axial speed and density must be finite")
        if rpm <= 0.0:
            raise AxialEnvelopeError(
                f"n <= 0 unsupported (rpm {rpm:.6g}) — the signed regime is "
                "declared for positive rotation speed only")
        if axial_speed_m_s < 0.0:
            raise AxialEnvelopeError(
                f"negative axial inflow V_a {axial_speed_m_s:.6g} m/s unsupported "
                "— reverse/vortex-ring regime is unmodeled; refused, not "
                "extrapolated")
        if air_density_kg_m3 <= 0.0:
            raise AxialEnvelopeError("air density must be > 0")
        n_rev_s = rpm / 60.0
        j = axial_speed_m_s / (n_rev_s * self._diameter_m)
        violation = self._envelope.violation(rpm, j)
        if violation is not None:
            raise AxialEnvelopeError(violation)
        ct, cp = self.coefficients(j, rpm)
        thrust_n = air_density_kg_m3 * n_rev_s ** 2 * self._diameter_m ** 4 * ct
        torque_n_m = (air_density_kg_m3 * n_rev_s ** 2 * self._diameter_m ** 5 * cp
                      / (2.0 * pi))
        power_w = 2.0 * pi * n_rev_s * torque_n_m
        return AxialLoad(
            rpm=rpm, n_rev_s=n_rev_s, axial_speed_m_s=axial_speed_m_s, j=j,
            ct=ct, cp=cp, thrust_n=thrust_n, torque_n_m=torque_n_m,
            power_w=power_w, air_density_kg_m3=air_density_kg_m3,
            diameter_m=self._diameter_m)


def body_frame_force(load: AxialLoad, axis_body: np.ndarray) -> np.ndarray:
    """Signed thrust projected on the declared body-frame rotor axis.

    The axis must be a finite nonzero vector; it is normalized, so only its
    orientation matters. F_body = T * axis: flipping the axis flips the
    force; CT < 0 flips the thrust along the same axis (P0A-009 sign
    contract)."""
    axis = np.asarray(axis_body, dtype=float)
    if axis.shape != (3,) or not np.all(np.isfinite(axis)):
        raise ValueError("axis_body must be a finite 3-vector")
    norm = float(np.linalg.norm(axis))
    if norm <= 0.0 or not isfinite(norm):
        raise ValueError("axis_body must be nonzero")
    return (load.thrust_n / norm) * axis


def body_frame_torque(load: AxialLoad, axis_body: np.ndarray) -> np.ndarray:
    """Shaft torque about the declared body-frame rotation axis (same
    normalization contract as ``body_frame_force``)."""
    axis = np.asarray(axis_body, dtype=float)
    if axis.shape != (3,) or not np.all(np.isfinite(axis)):
        raise ValueError("axis_body must be a finite 3-vector")
    norm = float(np.linalg.norm(axis))
    if norm <= 0.0 or not isfinite(norm):
        raise ValueError("axis_body must be nonzero")
    return (load.torque_n_m / norm) * axis
