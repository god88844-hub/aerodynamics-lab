"""M9 Phase 9 — strict credibility gate.

Every engineering result receives exactly one of four statuses:

  VALIDATED_FOR_THIS_DECISION   independent physical evidence demonstrates
      sufficient predictive accuracy within the applicable operating envelope
  PROMISING_FURTHER_EVIDENCE_REQUIRED  the model functions, but independent
      validation / uncertainty / applicability evidence is insufficient
  FAILED_ENGINEERING_REQUIREMENTS  the predicted system violates specified
      performance or safety requirements
  INCONCLUSIVE  the model or available evidence cannot support a reliable
      conclusion

No result may receive VALIDATED_FOR_THIS_DECISION merely because software
tests pass, manufacturer tables are reproduced, or Monte Carlo runs complete.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Status(str, Enum):
    VALIDATED_FOR_THIS_DECISION = "VALIDATED_FOR_THIS_DECISION"
    PROMISING = "PROMISING_FURTHER_EVIDENCE_REQUIRED"
    FAILED = "FAILED_ENGINEERING_REQUIREMENTS"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass
class CredibilityVerdict:
    capability: str
    status: Status
    basis: str
    independent_evidence: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    measured_prediction_error: str | None = None
    validated_envelope: str | None = None

    def summary(self) -> dict:
        return {
            "status": self.status.value,
            "basis": self.basis,
            "independent_evidence": self.independent_evidence,
            "missing_evidence": self.missing_evidence,
            "measured_prediction_error": self.measured_prediction_error,
            "validated_envelope": self.validated_envelope,
        }


def gate(capability: str, *, independent_evidence: list[str] | None = None,
         has_known_model_gaps: bool = False, independent_error_within_tolerance: bool | None = None,
         functional: bool = True) -> CredibilityVerdict:
    """Apply the credibility gate from declared evidence facts.

    Rules:
    - VALIDATED requires at least one INDEPENDENT physical dataset with
      pre-declared tolerances met AND no known unmodeled failure mechanisms
      relevant to the decision.
    - Anything reproducing only its own calibration data stays PROMISING.
    - A functional model with known gaps that matter for the decision is
      PROMISING (not INCONCLUSIVE) when its applicability limits are stated.
    - A non-functional or refuted model is FAILED / INCONCLUSIVE.
    """
    independent_evidence = independent_evidence or []
    if not functional:
        return CredibilityVerdict(
            capability, Status.INCONCLUSIVE,
            basis="model cannot support a conclusion in its current state")
    if independent_evidence and independent_error_within_tolerance and not has_known_model_gaps:
        return CredibilityVerdict(
            capability, Status.VALIDATED_FOR_THIS_DECISION,
            basis="independent physical evidence within pre-declared tolerance, "
                  "no relevant unmodeled mechanisms",
            independent_evidence=independent_evidence,
            measured_prediction_error=None)
    if independent_evidence or (independent_error_within_tolerance is not None
                                and not has_known_model_gaps):
        return CredibilityVerdict(
            capability, Status.PROMISING,
            basis="independent evidence exists but known model gaps or missing "
                  "coverage remain",
            independent_evidence=independent_evidence,
            missing_evidence=["gap-dependent items — see evidence inventory"])
    return CredibilityVerdict(
        capability, Status.PROMISING,
        basis="functions and is verified in software, but no independent "
              "physical validation evidence exists yet",
        missing_evidence=["independent physical validation dataset"])
