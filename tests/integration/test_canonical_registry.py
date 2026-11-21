"""Protect source coverage, content drift and inspected-evidence roles."""
from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("reconcile_registry", ROOT / "scripts/reconcile_registry.py")
registry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(registry)


def test_complete_source_registry_matches_current_artifacts_and_catalogs():
    actual = registry.read(ROOT, "data/registry.json")
    assert actual == registry.generated()
    registry.validate(actual)
    baseline_results = {p.stem.removesuffix("_results").removesuffix("_holdout")
                        for p in (ROOT / "docs/campaigns").glob("*.json")
                        if p.stem.endswith(("_results", "_holdout"))}
    assert {c["id"] for c in actual["campaigns"]} == baseline_results


@pytest.mark.parametrize("role,acceptance", [("CONFIRMATORY", "UNVALIDATED"), ("DEVELOPMENT", "ACCEPTED")])
def test_inspected_campaign_cannot_be_relabelled_as_blind_acceptance(role, acceptance):
    value = deepcopy(registry.read(ROOT, "data/registry.json"))
    value["campaigns"][0].update(policy_role=role, physical_acceptance=acceptance)
    with pytest.raises(ValueError, match="cannot be promoted"):
        registry.validate(value)


def test_missing_license_is_not_silently_replaced_with_project_license():
    value = deepcopy(registry.read(ROOT, "data/registry.json"))
    value["sources"][0]["license"] = None
    with pytest.raises(ValueError, match="explicit license"):
        registry.validate(value)


def test_text_hash_declares_normalization_and_original_bytes_are_exact(tmp_path):
    file = tmp_path / "source.json"
    file.write_bytes(b'{"x":1}\r\n')
    first = registry.artifact(tmp_path, "source.json")
    file.write_bytes(b'{"x":1}\n')
    assert first == registry.artifact(tmp_path, "source.json")
    original = tmp_path / "BATT.csv"
    original.write_bytes(b"x\r\n")
    before = registry.artifact(tmp_path, "BATT.csv")
    original.write_bytes(b"x\n")
    after = registry.artifact(tmp_path, "BATT.csv")
    assert before["hash_semantics"] == "EXACT_ORIGINAL_BYTES"
    assert before["sha256"] != after["sha256"]
