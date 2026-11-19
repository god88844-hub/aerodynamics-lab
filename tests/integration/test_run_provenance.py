"""Installed data changes must change the saved model identity."""

from app.services import run_provenance


def test_component_revision_changes_fingerprint_and_embedded_data(tmp_path, monkeypatch):
    monkeypatch.setattr(run_provenance, "ROOT", tmp_path)
    components = tmp_path / "data/components"
    components.mkdir(parents=True)
    component = components / "battery.json"
    component.write_text('{"capacity_ah": 5}', encoding="utf-8")
    (tmp_path / "requirements.lock").write_text("numpy==1.0", encoding="utf-8")
    before = run_provenance.capture_provenance()
    assert before == run_provenance.capture_provenance()
    component.write_text('{"capacity_ah": 6}', encoding="utf-8")
    after = run_provenance.capture_provenance()
    assert before["sha256"] != after["sha256"]
    assert after["component_data"]["data/components/battery.json"]["capacity_ah"] == 6
    assert before["component_data"]["data/components/battery.json"]["capacity_ah"] == 5
