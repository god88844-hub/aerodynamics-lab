"""API integration tests: designs CRUD, component listing, simulation runs.

Uses the ASGI TestClient with get_db overridden to a temporary SQLite DB."""

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

REPO_ROOT = Path(__file__).resolve().parents[2]
DESIGN_MN = REPO_ROOT / "data" / "designs" / "quad_mn3508_6s.json"


@pytest.fixture(scope="module")
def client():
    import sys

    sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))
    from fastapi.testclient import TestClient

    from app.main import app
    from app.persistence.database import Base, get_db

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    test_engine = create_engine(
        f"sqlite:///{tmp.name}", connect_args={"check_same_thread": False}, future=True
    )
    Base.metadata.create_all(test_engine)
    TestSession = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def design_payload() -> dict:
    import json

    return json.loads(DESIGN_MN.read_text(encoding="utf-8"))


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_cad_layout_revision_round_trip(client, design_payload):
    from copy import deepcopy
    from io import StringIO
    import ezdxf

    design = deepcopy(design_payload)
    battery = next(p for p in design["parts"] if p["name"] == "battery")
    battery["mount_id"] = "battery_mount"
    design["frame"]["mount_points"] = [{"id": "battery_mount", "position_m": battery["position_m"]}]
    saved = client.post("/api/designs", json={"snapshot": design}).json()
    revision = f"/api/designs/{saved['id']}/revisions/1"
    download = client.get(revision + "/layout.dxf")
    assert download.status_code == 200
    drawing = ezdxf.read(StringIO(download.content.decode("utf-8")))
    assert not drawing.audit().has_errors
    points = list(drawing.modelspace())
    assert len(points) == len(design["rotors"]) + len(design["parts"])
    preview = client.post(revision + "/layout-preview", content=download.content)
    assert preview.status_code == 200, preview.text
    assert preview.json()["snapshot"] == saved["snapshot"]
    assert preview.json()["changes"] == []

    mount = next(p for p in points if p.dxf.layer.startswith("AF_MOUNT_"))
    rotor = next(p for p in points if p.dxf.layer.startswith("AF_ROTOR_1_"))
    mount.dxf.location = (0.05, 0.0, -0.04)
    rotor.dxf.location = (0.3, 0.25, 0.02)

    def preview_drawing(path=revision):
        stream = StringIO()
        drawing.write(stream)
        return client.post(path + "/layout-preview", content=stream.getvalue().encode("utf-8"))

    result = preview_drawing()
    assert result.status_code == 200, result.text
    expected = deepcopy(saved["snapshot"])
    expected["frame"]["mount_points"][0]["position_m"] = [0.05, 0.0, -0.04]
    next(p for p in expected["parts"] if p["name"] == "battery")["position_m"] = [0.05, 0.0, -0.04]
    expected["rotors"][0]["position_m"] = [0.3, 0.25, 0.02]
    assert result.json()["snapshot"] == expected
    assert len(result.json()["changes"]) == 3
    assert client.get(revision).json()["snapshot"] == saved["snapshot"]

    assert client.put(f"/api/designs/{saved['id']}", json={"snapshot": expected}).status_code == 200
    assert preview_drawing(f"/api/designs/{saved['id']}/revisions/2").status_code == 422
    drawing.units = ezdxf.units.MM
    assert preview_drawing().status_code == 422
    drawing.units = ezdxf.units.M
    added = drawing.modelspace().add_line((0, 0), (1, 1))
    assert preview_drawing().status_code == 422
    drawing.modelspace().delete_entity(added)
    drawing.modelspace().delete_entity(rotor)
    assert preview_drawing().status_code == 422
    assert client.post(revision + "/layout-preview", content=b"broken DXF").status_code == 422
    assert client.post(revision + "/layout-preview", content=b"x" * (1024**2 + 1)).status_code == 413


def test_components_listed(client):
    r = client.get("/api/components")
    assert r.status_code == 200
    body = r.json()
    assert any(m["id"] == "tmotor_mn3508_kv380" for m in body["motors"])
    assert any(p["id"] == "tmotor_p15x5_cf" for p in body["propellers"])
    assert any(m["id"] == "cfrp_quasi_iso" for m in body["materials"])
    motor = next(m for m in body["motors"] if m["id"] == "tmotor_mn3508_kv380")
    assert motor["estimated"] is False and motor["source"]


def test_design_crud_cycle(client, design_payload):
    r = client.post("/api/designs", json={"snapshot": design_payload})
    assert r.status_code == 200
    design_id = r.json()["id"]

    r = client.get(f"/api/designs/{design_id}")
    assert r.status_code == 200
    assert r.json()["snapshot"]["name"] == "quad_mn3508_6s_15x5"

    modified = {**design_payload, "name": "quad_mn3508_6s_15x5_v2"}
    r = client.put(f"/api/designs/{design_id}", json={"snapshot": modified})
    assert r.status_code == 200
    assert r.json()["snapshot"]["name"].endswith("_v2")

    r = client.get("/api/designs")
    assert any(d["id"] == design_id for d in r.json())

    r = client.delete(f"/api/designs/{design_id}")
    assert r.status_code == 200
    assert client.get(f"/api/designs/{design_id}").status_code == 404


def test_invalid_snapshot_rejected(client):
    r = client.post("/api/designs", json={"snapshot": {"name": "broken", "parts": []}})
    assert r.status_code == 422
    assert "invalid design snapshot" in r.json()["detail"]


def test_design_history_is_immutable_across_saves_and_restore(client, design_payload):
    from hashlib import sha256
    import json

    created = client.post("/api/designs", json={"snapshot": design_payload}).json()
    path = f"/api/designs/{created['id']}"
    initial = client.get(f"{path}/revisions/1").json()
    exact = json.dumps(initial["snapshot"], sort_keys=True, separators=(",", ":")).encode()
    assert initial["snapshot_sha256"] == sha256(exact).hexdigest()

    update = {**created["snapshot"], "name": "Revised airframe"}
    for _ in range(2):
        assert client.put(path, json={"snapshot": update}).json()["snapshot"] == update
    assert [row["number"] for row in client.get(f"{path}/revisions").json()] == [2, 1]
    assert client.get(f"{path}/revisions/1").json() == initial
    assert client.post(f"{path}/revisions/99/restore").status_code == 404
    for _ in range(2):
        assert client.post(f"{path}/revisions/1/restore").json() == created
    history = client.get(f"{path}/revisions").json()
    assert [row["number"] for row in history] == [3, 2, 1]
    assert history[0]["snapshot_sha256"] == history[2]["snapshot_sha256"]


def test_concurrent_design_saves_keep_both_revisions(client, design_payload):
    from concurrent.futures import ThreadPoolExecutor

    created = client.post("/api/designs", json={"snapshot": design_payload}).json()
    path = f"/api/designs/{created['id']}"
    names = ("Concurrent A", "Concurrent B")

    def save(name):
        return client.put(path, json={"snapshot": {**created["snapshot"], "name": name}})

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert [result.status_code for result in pool.map(save, names)] == [200, 200]

    history = client.get(f"{path}/revisions").json()
    assert [row["number"] for row in history] == [3, 2, 1]
    assert {row["name"] for row in history[:2]} == set(names)
    assert client.get(path).json()["snapshot"]["name"] == history[0]["name"]


def test_preview_returns_mass_properties(client, design_payload):
    r = client.post("/api/designs/preview", json={"snapshot": design_payload})
    assert r.status_code == 200
    body = r.json()
    assert body["mass_kg"] == pytest.approx(3.708, abs=1e-6)
    assert len(body["principal_axes"]) == 3
    assert body["hover_trim_error"] is None


def test_flight_simulation_end_to_end(client, design_payload):
    r = client.post("/api/designs", json={"snapshot": design_payload})
    design_id = r.json()["id"]

    r = client.post(f"/api/designs/{design_id}/simulate",
                    json={"scenario": "flight", "params": {}})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["mission"]["aborted"] is False
    assert body["results"]["time_to_5m_s"] is not None
    assert body["results"]["energy_used_wh"] > 0
    assert body["success"]["reached_5m"] is True
    # Telemetry decimated but present.
    assert len(body["telemetry"]["t"]) > 10
    assert len(body["telemetry"]["motor_current_a"]) == len(body["telemetry"]["t"])

    # Stored and retrievable.
    r = client.get(f"/api/simulations/{body['simulation_id']}")
    assert r.status_code == 200
    assert "flight" in r.json()["scenario"]

    r = client.get(f"/api/designs/{design_id}/simulations")
    assert len(r.json()) == 1


def test_hover_static_end_to_end(client, design_payload):
    r = client.post("/api/designs", json={"snapshot": design_payload})
    design_id = r.json()["id"]
    r = client.post(f"/api/designs/{design_id}/simulate",
                    json={"scenario": "hover-static", "params": {"max_duration_s": 7200}})
    body = r.json()
    assert body["status"] == "completed"
    assert body["endurance"]["to_warning_s"] > 1200
    assert body["limits"] == {"verdict": "INCONCLUSIVE", "issues": []}
    benchmarks = {b["name"]: b["status"] for b in body["benchmarks"]}
    assert "pass" in benchmarks.values()


def test_static_hover_saves_esc_failure_without_endurance(client, design_payload, monkeypatch):
    from physics.propulsion.loader import ComponentLibrary

    load_esc = ComponentLibrary.esc
    def weak_esc(library, component_id):
        return load_esc(library, component_id).model_copy(update={"max_continuous_current_a": 2.0})
    monkeypatch.setattr(ComponentLibrary, "esc", weak_esc)
    design_id = client.post("/api/designs", json={"snapshot": design_payload}).json()["id"]
    response = client.post(f"/api/designs/{design_id}/simulate",
                           json={"scenario": "hover-static", "params": {"max_duration_s": 60}})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["limits"]["verdict"] == "FAIL"
    assert "ESC over-current" in body["limits"]["issues"][0]
    assert body["endurance"]["to_warning_s"] is None
    saved = client.get(f"/api/simulations/{body['simulation_id']}").json()
    assert saved["limits"] == body["limits"]


def test_saved_run_inputs_survive_design_edits(client, design_payload):
    from hashlib import sha256

    original = {**design_payload, "name": "original frozen test"}
    created = client.post("/api/designs", json={"snapshot": original}).json()
    design_id = created["id"]
    response = client.post(f"/api/designs/{design_id}/simulate", json={
        "scenario": "hover-ideal",
        "params": {"duration_s": "0.02"},
    })
    assert response.status_code == 200, response.text
    run = response.json()
    assert run["status"] == "completed"
    path = f"/api/simulations/{run['simulation_id']}/inputs"
    frozen = client.get(path)
    assert frozen.status_code == 200, frozen.text
    assert run["input_sha256"] == sha256(frozen.content).hexdigest()
    assert frozen.headers["x-aeroforge-input-sha256"] == run["input_sha256"]
    assert frozen.json()["design"] == created["snapshot"]
    assert frozen.json()["scenario"] == "hover-ideal"
    assert frozen.json()["requested_parameters"] == {"duration_s": "0.02"}
    assert frozen.json()["effective_parameters"] == {
        "duration_s": 0.02, "dt_s": 0.002, "solver": "rk4",
    }

    edited_parts = [*original["parts"]]
    edited_parts[0] = {**edited_parts[0], "mass_kg": edited_parts[0]["mass_kg"] + 0.1}
    updated = client.put(f"/api/designs/{design_id}", json={"snapshot": {
        **original, "name": "edited after the simulation", "parts": edited_parts,
    }})
    assert updated.status_code == 200, updated.text
    assert client.get(path).content == frozen.content
    assert client.get(f"/api/simulations/{run['simulation_id']}").json()["input_sha256"] == run["input_sha256"]
    assert client.delete(f"/api/designs/{design_id}").status_code == 200
    assert client.get(path).status_code == 404


def test_simulation_failure_is_reported_not_crashing(client):
    """A design that physics refuses (no powertrain + flight) returns a
    failed-status result with the error message — an engineering outcome."""
    r = client.post("/api/designs", json={"snapshot": {
        "schema_version": "0.1", "name": "no_powertrain",
        "parts": [{"name": "frame", "mass_kg": 1.0, "position_m": [0, 0, 0]}],
        "rotors": [{"position_m": [0.25, 0, 0]}],
    }})
    design_id = r.json()["id"]
    r = client.post(f"/api/designs/{design_id}/simulate",
                    json={"scenario": "flight", "params": {}})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "failed"
    assert "powertrain" in body["error"]


@pytest.mark.parametrize(("scenario", "options", "solver"), [
    ("hover-ideal", {"duration_s": 0.02}, "run_hover_ideal"),
    ("hover-ideal", {"duration_s": 0.10, "dt_s": 1, "solver": "ivp"}, "run_hover_ideal"),
    ("hover-static", {"max_duration_s": 20}, "run_hover_static"),
    ("hover-hold", {"duration_s": 0.02}, "run_hover_hold"),
])
def test_simulation_work_limit_records_refusal_before_solver(client, design_payload, monkeypatch, scenario, options, solver):
    from app.services import simulation_service

    monkeypatch.setitem(simulation_service.SIMULATION_STEP_LIMITS, scenario, 1)
    monkeypatch.setattr(simulation_service.service, solver, lambda *a, **kw: pytest.fail("Solver started"))
    saved = client.post("/api/designs", json={"snapshot": design_payload}).json()
    reply = client.post(f"/api/designs/{saved['id']}/simulate", json={
        "scenario": scenario, "params": options,
    })
    assert reply.status_code == 200, reply.text
    report = reply.json()
    assert report["status"] == "failed"
    assert report["error_code"] == "simulation_work_limit"
    assert report["telemetry"] is None
    recorded = client.get(f"/api/simulations/{report['simulation_id']}/inputs").json()
    assert recorded["requested_parameters"] == options
    assert recorded["execution_limits"]["steps"] == 1


@pytest.mark.parametrize("solver", ["rk4", "ivp"])
def test_simulation_deadline_stops_integrator_and_releases_slot(client, design_payload, monkeypatch, solver):
    from physics.integration import runtime_limit

    clock = iter((0.0, 46.0))
    monkeypatch.setattr(runtime_limit, "monotonic", lambda: next(clock, 46.0))
    saved = client.post("/api/designs", json={"snapshot": design_payload}).json()
    path = f"/api/designs/{saved['id']}/simulate"
    payload = {"scenario": "hover-ideal", "params": {"duration_s": 0.02, "solver": solver}}
    reply = client.post(path, json=payload)
    assert reply.status_code == 200, reply.text
    report = reply.json()
    assert report["status"] == "failed"
    assert report["error_code"] == "simulation_time_limit"
    assert report["telemetry"] is None
    assert client.get(f"/api/simulations/{report['simulation_id']}/inputs").status_code == 200
    assert client.post(path, json=payload).json()["status"] == "completed"


def test_adaptive_solver_enforces_its_evaluation_limit(client, design_payload, monkeypatch):
    from app.services import simulation_service

    monkeypatch.setattr(simulation_service, "SIMULATION_MAX_ADAPTIVE_EVALUATIONS", 1)
    saved = client.post("/api/designs", json={"snapshot": design_payload}).json()
    response = client.post(f"/api/designs/{saved['id']}/simulate", json={
        "scenario": "hover-ideal", "params": {"duration_s": 0.02, "solver": "ivp"},
    })
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["status"] == "failed"
    assert report["error_code"] == "simulation_work_limit"
    frozen = client.get(f"/api/simulations/{report['simulation_id']}/inputs").json()
    assert frozen["effective_parameters"]["max_evaluations"] == 1


def test_simulation_capacity_keeps_reads_available(client, design_payload, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from app.services import simulation_service

    started = Event()
    release = Event()
    original = simulation_service.service.run_hover_ideal

    def wait_in_solver(*args, **kwargs):
        started.set()
        assert release.wait(10), "The test did not release the first request."
        return original(*args, **kwargs)

    monkeypatch.setattr(simulation_service.service, "run_hover_ideal", wait_in_solver)
    saved = client.post("/api/designs", json={"snapshot": design_payload}).json()
    path = f"/api/designs/{saved['id']}/simulate"
    payload = {"scenario": "hover-ideal", "params": {"duration_s": 0.02}}
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(client.post, path, json=payload)
        try:
            assert started.wait(10), "The first request did not start."
            busy = client.post(path, json=payload)
            assert busy.status_code == 503, busy.text
            assert busy.headers["retry-after"] == "1"
            assert client.get("/api/health").status_code == 200
            assert client.get(f"/api/designs/{saved['id']}/simulations").json() == []
        finally:
            release.set()
        assert pending.result(timeout=10).json()["status"] == "completed"
    assert client.post(path, json=payload).json()["status"] == "completed"


def test_structural_envelope_returns_auditable_per_rotor_loads(client, design_payload):
    r = client.post("/api/designs/structural-envelope", json={
        "snapshot": design_payload,
        "cases": [
            {"name": "static_hover_user_defined", "thrusts_n": [9.1] * 4},
            {"name": "asymmetric_user_defined", "thrusts_n": [10, 12, 8, 9]},
        ],
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["cases"]) == 2
    assert all(len(case["rotors"]) == 4 for case in data["cases"])
    assert data["governing"]["case"] == "asymmetric_user_defined"
    assert data["governing"]["rotor_index"] == 1
    assert data["governing"]["span_m"] > design_payload["frame"]["arm_length_m"]
    assert "static" in data["failure_threshold"]
    assert data["verdict"] in ("ANALYTICAL_STATIC_SCREEN_ONLY",
                               "EXCEEDS_DECLARED_ALLOWABLE")


def test_structural_envelope_rejects_bad_cases_and_missing_frame(client, design_payload):
    invalid = client.post("/api/designs/structural-envelope", json={
        "snapshot": design_payload,
        "cases": [{"name": "wrong_size", "thrusts_n": [1, 2]}],
    })
    assert invalid.status_code == 422
    without_frame = dict(design_payload)
    without_frame.pop("frame")
    missing = client.post("/api/designs/structural-envelope", json={
        "snapshot": without_frame,
        "cases": [{"name": "hover", "thrusts_n": [1, 1, 1, 1]}],
    })
    assert missing.status_code == 422


def test_structural_envelope_opt_in_torsion_and_joints(client, design_payload):
    r = client.post("/api/designs/structural-envelope", json={
        "snapshot": design_payload,
        "cases": [{"name": "joint_screen", "thrusts_n": [4, 5, 6, 7],
                   "axial_torques_n_m": [0.3, 0.2, -0.3, 0.1]}],
        "shear_allowable_pa": 30e6,
        "shear_allowable_source": "operator-entered report",
        "joint_allowables": {
            "bending_moment_n_m": 4.0, "axial_torque_n_m": .5,
            "evidence_source": "user supplied joint test",
        },
    })
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["advanced_loads"]["axial_torque_cases_with_data"] == 1
    assert result["advanced_loads"]["combined_interaction"] == "NOT_MODELED"
    assert result["cases"][0]["rotors"][2]["arm_axial_torque_n_m"] == -0.3
    assert result["advanced_loads"]["screening_verdict"] == "INCOMPLETE_EVIDENCE"


def test_structural_envelope_omitted_torque_stays_unknown(client, design_payload):
    r = client.post("/api/designs/structural-envelope", json={
        "snapshot": design_payload,
        "cases": [{"name": "legacy", "thrusts_n": [4, 5, 6, 7]}],
    })
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["advanced_loads"]["axial_torque_cases_with_data"] == 0
    assert result["cases"][0]["rotors"][0]["arm_axial_torque_n_m"] is None
    assert result["advanced_loads"]["joint_bending_screen"] is None


def test_structural_envelope_rejects_bad_joint_capacity_and_wrong_torque_count(client, design_payload):
    base = {"snapshot": design_payload, "cases": [
        {"name": "bad", "thrusts_n": [1, 1, 1, 1], "axial_torques_n_m": [1, 2]}]}
    assert client.post("/api/designs/structural-envelope", json=base).status_code == 422
    base["cases"][0]["axial_torques_n_m"] = [1, 1, 1, 1]
    base["joint_allowables"] = {
        "bending_moment_n_m": 0, "axial_torque_n_m": 1,
        "evidence_source": "fixture",
    }
    assert client.post("/api/designs/structural-envelope", json=base).status_code == 422


def test_battery_evidence_api_reports_holdout_without_mutating_component(client):
    from physics.propulsion.loader import ComponentLibrary
    from physics.propulsion.battery import BatteryPack

    lib = ComponentLibrary(REPO_ROOT / "data" / "components")
    spec = lib.battery("generic_6s_lipo_16000mah")
    pack = BatteryPack(spec)
    def sample(id, split, soc, current):
        return {
            "id": id, "split": split, "soc_pct": soc, "current_a": current,
            "terminal_voltage_v": pack.ocv_pack(soc) - .024 * current,
        }
    body = {
        "battery_id": spec.id,
        "dataset_kind": "synthetic_fixture",
        "calibration_run_id": "math_fixture_A",
        "heldout_run_id": "math_fixture_B",
        "calibration_source": "Synthetic OCV minus constant I*R voltage",
        "heldout_source": "Separate synthetic points for code verification",
        "predeclared_max_abs_percentage_error_pct": 1.0,
        "samples": [
            sample("c1", "calibration", 40, 10),
            sample("c2", "calibration", 50, 20),
            sample("c3", "calibration", 60, 30),
            sample("h1", "held_out", 45, 15),
            sample("h2", "held_out", 55, 25),
        ],
    }
    response = client.post("/api/components/battery-evidence", json=body)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["fit"]["fitted_pack_resistance_ohm"] == pytest.approx(.024, rel=1e-10)
    assert result["verdict"] == "SYNTHETIC_VERIFICATION_ONLY"
    assert len(result["heldout"]["rows"]) == 2
    assert not result["simulation_battery_modified"]
    assert lib.battery(spec.id).internal_resistance_ohm == .020


def test_battery_evidence_rejects_fake_data_and_unknown_pack(client):
    incomplete = {
        "battery_id": "generic_6s_lipo_16000mah",
        "dataset_kind": "physical_measurements",
        "calibration_run_id": "one", "heldout_run_id": "one",
        "calibration_source": "operator", "heldout_source": "operator",
        "predeclared_max_abs_percentage_error_pct": 10,
        "samples": [],
    }
    assert client.post("/api/components/battery-evidence", json=incomplete).status_code == 422
    incomplete["battery_id"] = "../../escape"
    assert client.post("/api/components/battery-evidence", json=incomplete).status_code == 422


def test_battery_evidence_unknown_battery_returns_404(client):
    from physics.propulsion.loader import ComponentLibrary
    from physics.propulsion.battery import BatteryPack

    spec = ComponentLibrary(REPO_ROOT / "data" / "components").battery("generic_6s_lipo_16000mah")
    pack = BatteryPack(spec)
    samples = []
    for i, (split, soc, current) in enumerate([
        ("calibration", 40, 10), ("calibration", 50, 20),
        ("calibration", 60, 30), ("held_out", 45, 15), ("held_out", 55, 25),
    ]):
        samples.append({"id": f"r{i}", "split": split, "soc_pct": soc,
                        "current_a": current,
                        "terminal_voltage_v": pack.ocv_pack(soc) - .02 * current})
    payload = {
        "battery_id": "nonexistent_pack",
        "dataset_kind": "synthetic_fixture",
        "calibration_run_id": "A", "heldout_run_id": "B",
        "calibration_source": "synthetic fixture",
        "heldout_source": "synthetic fixture",
        "predeclared_max_abs_percentage_error_pct": 1,
        "samples": samples,
    }
    assert client.post("/api/components/battery-evidence", json=payload).status_code == 404
