"""A caller's unverified data labels must NEVER grant physical certification."""
import pytest

from physics.validation.credibility import Status, gate


@pytest.mark.parametrize("claimed_success", [True, False, None])
def test_spoofed_external_evidence_never_becomes_validated(claimed_success):
    report = gate(
        "unverified drone performance",
        independent_evidence=["synthetic fixture mislabeled independent physical measurement"],
        independent_error_within_tolerance=claimed_success,
        has_known_model_gaps=False,
    )
    assert report.status == Status.PROMISING
    assert report.status != Status.VALIDATED_FOR_THIS_DECISION
    assert "authenticity" in report.basis
    assert "independently authenticated original physical records" in report.missing_evidence


def test_numeric_claim_without_original_dataset_is_not_physically_validated():
    report = gate("hover accuracy", independent_error_within_tolerance=True)
    assert report.status == Status.PROMISING
    assert report.independent_evidence == []
    assert report.missing_evidence


def test_software_only_numeric_consistency_is_not_physical_validation():
    result = gate("static manufacturer readback", functional=True)
    assert result.status == Status.PROMISING
    assert result.summary()["measured_prediction_error"] is None
    assert result.summary()["validated_envelope"] is None


def test_nonfunctional_model_is_inconclusive():
    report = gate("unreliable controller", functional=False,
                  independent_evidence=["operator claimed test"],
                  independent_error_within_tolerance=True)
    assert report.status == Status.INCONCLUSIVE
    assert report.status != Status.VALIDATED_FOR_THIS_DECISION
