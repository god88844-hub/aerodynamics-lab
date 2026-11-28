"""Import, create, validate, package, version, recover, author, or simulate an Aerodynamics Lab project."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/api"), str(ROOT / "packages"), str(ROOT / "packages/shared-schemas")]

from aeroforge_schemas.project import EngineeringProject, import_legacy_project  # noqa: E402
from app.services.project_assets import copy_assets  # noqa: E402
from app.services.project_service import run_project  # noqa: E402
from desktop_worker.environment_authoring import author_test_ground  # noqa: E402
from desktop_worker.io import write_result, write_started  # noqa: E402
from desktop_worker.learning_experiments import create_guided_experiment_bundle, save_and_reproduce_experiment  # noqa: E402
from desktop_worker.project_workflow import (  # noqa: E402
    ProjectWorkflowError,
    create_project_document,
    inspect_and_validate_project,
    list_project_versions,
    recover_last_valid_project,
    save_and_version_project,
    write_recovery_snapshot,
)
from desktop_worker.twin_comparison import compare_frozen_run_and_source, export_labeled_comparison  # noqa: E402
from geometry.fixed_wing_cad import ParametricWingSpec, compute_wing_geometry_properties, export_2d_engineering_drawing_svg_dxf  # noqa: E402
from geometry.part_designer import CustomPartRecipe, build_custom_part, swap_assembly_part  # noqa: E402
from geometry.freeform_cad import build_freeform_cad_model, solve_freeform_sketch  # noqa: E402
from optimization.bounded_sweep import run_bounded_sweep  # noqa: E402
from physics.validation.virtual_evidence_scorecard import compute_virtual_evidence_scorecard  # noqa: E402
from physics.aerodynamics.fixed_wing import run_fixed_wing_mission  # noqa: E402
from physics.aerodynamics.aeroacoustics_and_vrs import (  # noqa: E402
    evaluate_helicopter_vrs_and_asymmetry,
    evaluate_hydro_cavitation,
    evaluate_rf_and_rcs,
    evaluate_rotor_and_jet_aeroacoustics,
)
from physics.aerodynamics.rockets_and_cfd import evaluate_multistage_rocket, export_and_run_detailed_cfd_fea  # noqa: E402
from physics.aerodynamics.embedded_3d_cfd_fea import run_embedded_3d_cfd_fea  # noqa: E402
from physics.aerodynamics.rotorcraft_vtol import run_helicopter_autorotation_mission, run_vtol_transition_corridor  # noqa: E402
from physics.aerodynamics.sixdof_fixed_wing import build_derivatives_from_wing, simulate_6dof_fixed_wing  # noqa: E402
from physics.autonomy.sitl_and_swarms import run_multi_drone_swarm, run_sitl_closed_loop_mission  # noqa: E402
from physics.dynamics.assembly_layout import build_multirotor_layout_and_bom  # noqa: E402
from physics.dynamics.slung_load_and_tailsitter import evaluate_failure_atlas_cases, import_electrophysics_powerpack  # noqa: E402
from physics.environment.adverse_weather import evaluate_icing_and_shedding, evaluate_rain_wet_effects  # noqa: E402
from physics.propulsion.loader import ComponentLibrary  # noqa: E402
from physics.scenarios.desktop_runner import run_authoritative_desktop_simulation  # noqa: E402
from physics.scenarios.mission_authoring import author_mission, run_authored_mission  # noqa: E402
from physics.validation.phase1_dataset_eval import evaluate_all_phase1_datasets  # noqa: E402
from physics.aerodynamics.phase3_phase4_eval import evaluate_all_phase3_and_phase4_benchmarks  # noqa: E402
from physics.validation.protocol_registry import load_frozen_protocol_catalog, register_validation_protocol  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "import-legacy",
            "create",
            "validate",
            "package",
            "save-version",
            "list-versions",
            "recover",
            "layout-bom",
            "author-ground",
            "author-mission",
            "run-mission",
            "simulate",
            "compare-source",
            "register-protocol",
            "guided-experiment",
            "bounded-sweep",
            "fixed-wing-sim",
            "6dof-fixed-wing",
            "export-drawing",
            "vtol-transition",
            "autorotation-sim",
            "adverse-weather",
            "swarm-sim",
            "sitl-mission",
            "build-custom-part",
            "swap-assembly-part",
            "solve-sketch",
            "freeform-cad",
            "evidence-scorecard",
            "phase1-eval",
            "failure-atlas",
            "load-powerpack",
            "multiphysics-audit",
            "rocket-sim",
            "cfd-fea-export",
            "embedded-cfd-fea",
            "phase3-4-eval",
            "run",
        ),
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--error-output", type=Path)
    parser.add_argument("--completion-output", type=Path)
    parser.add_argument("--started-output", type=Path)
    parser.add_argument("--asset-root", type=Path)
    parser.add_argument("--restore-to", type=Path)
    parser.add_argument("--note", default="")
    args = parser.parse_args()
    paths = [path.resolve() for path in (args.input, args.output, args.error_output, args.completion_output, args.started_output) if path]
    if len(paths) != len(set(paths)):
        parser.error("input, output, error and completion paths must be separate")
    try:
        write_started(args.started_output)
        if args.command == "create":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            ref_path = spec.get("reference_design_path")
            project = create_project_document(
                spec.get("name", "New Flight Project"),
                aircraft_family=spec.get("aircraft_family", "multirotor"),
                template=spec.get("template", "assembly_empty"),
                reference_design_path=Path(ref_path) if ref_path else (ROOT / "data/designs/quad_mn3508_6s.json"),
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            payload = project.model_dump(mode="json")
            write_result(args.output, payload)
            write_recovery_snapshot(project, args.output, args.output.parent)
        elif args.command == "list-versions":
            payload = list_project_versions(args.input)
            write_result(args.output, payload)
        elif args.command == "recover":
            payload = recover_last_valid_project(args.input, restore_to=args.restore_to)
            write_result(args.output, payload)
        elif args.command == "layout-bom":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            library = ComponentLibrary(ROOT / "data" / "components")
            payload = build_multirotor_layout_and_bom(spec, library)
            write_result(args.output, payload)
        elif args.command == "author-ground":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            project = EngineeringProject.model_validate(spec["project"])
            updated = author_test_ground(project, spec["test_ground"])
            write_result(args.output, updated.model_dump(mode="json"))
        elif args.command == "author-mission":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            project = EngineeringProject.model_validate(spec["project"])
            updated = author_mission(project, spec["mission"])
            write_result(args.output, updated.model_dump(mode="json"))
        elif args.command == "run-mission":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            project = EngineeringProject.model_validate(spec["project"] if "project" in spec else spec)
            payload = run_authored_mission(
                project,
                mass_kg=float(spec.get("mass_kg", 1.5)) if isinstance(spec, dict) else 1.5,
                render_fps_hint=float(spec.get("render_fps_hint", 60.0)) if isinstance(spec, dict) else 60.0,
            )
            write_result(args.output, payload)
        elif args.command == "simulate":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            proj_obj = spec["project"] if isinstance(spec, dict) and "project" in spec else spec
            dt_val = spec.get("dt_s") if isinstance(spec, dict) else None
            payload = run_authoritative_desktop_simulation(
                proj_obj,
                dt_s=float(dt_val) if dt_val is not None else None,
            )
            write_result(args.output, payload)
        elif args.command == "compare-source":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            payload = compare_frozen_run_and_source(
                spec["frozen_run"],
                spec["source_record"],
                channel=str(spec.get("channel", "z")),
                unit=str(spec.get("unit", "m")),
                tolerance_abs=float(spec.get("tolerance_abs", 0.25)),
            )
            if spec.get("export_csv_path"):
                csv_out = Path(spec["export_csv_path"])
                payload["exported"] = export_labeled_comparison(payload, args.output, csv_out)
            write_result(args.output, payload)
        elif args.command == "register-protocol":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            if spec.get("catalog_path"):
                payload = load_frozen_protocol_catalog(Path(spec["catalog_path"]))
            else:
                payload = register_validation_protocol(
                    spec["protocol"],
                    tolerance_bindings=spec.get("tolerance_bindings", {}),
                    frozen_sha256=spec.get("frozen_sha256"),
                )
            write_result(args.output, payload)
        elif args.command == "guided-experiment":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            proj = EngineeringProject.model_validate(spec["project"])
            bundle = create_guided_experiment_bundle(
                proj,
                hypothesis=str(spec.get("hypothesis", "Higher target altitude increases hover climb demand")),
                target_altitude_m=float(spec.get("target_altitude_m", 3.5)),
                hover_duration_s=float(spec.get("hover_duration_s", 0.3)),
                wind_world_m_s=tuple(float(v) for v in spec.get("wind_world_m_s", [0.0, 0.0, 0.0])),
                seed=int(spec.get("seed", 42)),
            )
            if spec.get("save_bundle_path"):
                bundle["reproduction_check"] = save_and_reproduce_experiment(bundle, Path(spec["save_bundle_path"]))
            write_result(args.output, bundle)
        elif args.command == "bounded-sweep":
            from aeroforge_schemas.design import DroneDesign
            from physics.structures.materials import load_materials

            spec = json.loads(args.input.read_text(encoding="utf-8"))
            design_path = ROOT / "data" / "designs" / "quad_mn3508_6s.json"
            if spec.get("project") and spec["project"].get("vehicle", {}).get("format") == "legacy_multirotor_0.1":
                design = DroneDesign.model_validate(spec["project"]["vehicle"]["snapshot"])
            else:
                design = DroneDesign.model_validate_json(design_path.read_bytes())
            library = ComponentLibrary(ROOT / "data" / "components")
            mat_id = spec.get("material_id", "cfrp_quasi_iso")
            mat = load_materials(ROOT / "data" / "components" / "materials.json").get(mat_id)
            grid_spec = spec.get(
                "grid_spec",
                {"battery_capacity_ah": [10.0, 16.0], "rotor_count": [4], "arm_length_m": [0.25, 0.35], "payload_kg": [0.0, 2.0]},
            )
            payload = run_bounded_sweep(
                design,
                library,
                grid_spec,
                material=mat,
                constraints=spec.get("constraints"),
                seed=int(spec.get("seed", 42)),
            )
            write_result(args.output, payload)
        elif args.command == "fixed-wing-sim":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            wing = ParametricWingSpec(
                name=str(spec.get("name", "Fixed-Wing Aircraft")),
                wingspan_m=float(spec.get("wingspan_m", 1.8)),
                root_chord_m=float(spec.get("root_chord_m", 0.28)),
                tip_chord_m=float(spec.get("tip_chord_m", 0.16)),
                airfoil_code=str(spec.get("airfoil_code", "2412")),
            )
            payload = {
                "geometry": compute_wing_geometry_properties(wing),
                "mission": run_fixed_wing_mission(
                    wing,
                    mass_kg=float(spec.get("mass_kg", 2.2)),
                    duration_s=float(spec.get("duration_s", 6.0)),
                ),
            }
            write_result(args.output, payload)
        elif args.command == "vtol-transition":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            payload = run_vtol_transition_corridor(
                mass_kg=float(spec.get("mass_kg", 3.0)),
                wing_area_m2=float(spec.get("wing_area_m2", 0.45)),
                max_rotor_thrust_n=float(spec.get("max_rotor_thrust_n", 45.0)),
                max_cruise_thrust_n=float(spec.get("max_cruise_thrust_n", 25.0)),
            )
            write_result(args.output, payload)
        elif args.command == "adverse-weather":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            payload = {
                "rain": evaluate_rain_wet_effects(rain_mm_h=float(spec.get("rain_mm_h", 0.0))),
                "icing": evaluate_icing_and_shedding(
                    oat_c=float(spec.get("oat_c", 5.0)),
                    lwc_g_m3=float(spec.get("lwc_g_m3", 0.0)),
                    exposure_s=float(spec.get("exposure_s", 0.0)),
                ),
            }
            write_result(args.output, payload)
        elif args.command == "swarm-sim":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            payload = run_multi_drone_swarm(
                initial_positions_m=[tuple(float(v) for v in p) for p in spec["initial_positions_m"]],
                target_positions_m=[tuple(float(v) for v in p) for p in spec["target_positions_m"]],
                min_separation_m=float(spec.get("min_separation_m", 1.0)),
            )
            write_result(args.output, payload)
        elif args.command == "export-drawing":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            wing = ParametricWingSpec(
                name=str(spec.get("name", "FixedWing")),
                wingspan_m=float(spec.get("wingspan_m", 1.8)),
                root_chord_m=float(spec.get("root_chord_m", 0.26)),
                tip_chord_m=float(spec.get("tip_chord_m", 0.14)),
                airfoil_code=str(spec.get("airfoil_code", "2412")),
            )
            payload = export_2d_engineering_drawing_svg_dxf(
                wing,
                svg_path=Path(spec["svg_path"]) if spec.get("svg_path") else None,
                dxf_path=Path(spec["dxf_path"]) if spec.get("dxf_path") else None,
            )
            write_result(args.output, payload)
        elif args.command == "6dof-fixed-wing":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            wing = ParametricWingSpec(
                name=str(spec.get("name", "FixedWing")),
                wingspan_m=float(spec.get("wingspan_m", 1.8)),
                root_chord_m=float(spec.get("root_chord_m", 0.26)),
                tip_chord_m=float(spec.get("tip_chord_m", 0.14)),
                airfoil_code=str(spec.get("airfoil_code", "2412")),
            )
            payload = simulate_6dof_fixed_wing(
                aero=build_derivatives_from_wing(wing),
                mass_kg=float(spec.get("mass_kg", 2.2)),
                thrust_n=float(spec.get("thrust_n", 3.5)),
                duration_s=float(spec.get("duration_s", 1.2)),
            )
            write_result(args.output, payload)
        elif args.command == "autorotation-sim":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            payload = run_helicopter_autorotation_mission(
                flare_altitude_m=float(spec.get("flare_altitude_m", 8.0)),
                min_safe_rpm=float(spec.get("min_safe_rpm", 950.0)),
            )
            write_result(args.output, payload)
        elif args.command == "sitl-mission":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            payload = run_sitl_closed_loop_mission(firmware_kind=str(spec.get("firmware_kind", "ardupilot")))
            write_result(args.output, payload)
        elif args.command == "build-custom-part":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            recipe = CustomPartRecipe(
                part_name=str(spec["part_name"]),
                sketch_kind=str(spec.get("sketch_kind", "rounded_plate")),
                width_m=float(spec.get("width_m", 0.048)),
                length_m=float(spec.get("length_m", 0.240)),
                thickness_m=float(spec.get("thickness_m", 0.012)),
                hole_radius_m=float(spec.get("hole_radius_m", 0.008)),
                revolve_360=bool(spec.get("revolve_360", False)),
                circular_pattern_count=int(spec.get("circular_pattern_count", 1)),
                density_kg_m3=float(spec.get("density_kg_m3", 1580.0)),
                density_source=str(spec.get("density_source", "")),
                airfoil_code=str(spec.get("airfoil_code", "2412")),
            )
            export_dir = Path(spec["export_dir"]) if spec.get("export_dir") else None
            payload = build_custom_part(recipe, export_dir=export_dir)
            write_result(args.output, payload)
        elif args.command == "swap-assembly-part":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            rep = spec["replacement"]
            recipe = CustomPartRecipe(
                part_name=str(rep["part_name"]),
                sketch_kind=str(rep.get("sketch_kind", "rounded_plate")),
                width_m=float(rep.get("width_m", 0.048)),
                length_m=float(rep.get("length_m", 0.240)),
                thickness_m=float(rep.get("thickness_m", 0.012)),
                hole_radius_m=float(rep.get("hole_radius_m", 0.008)),
                revolve_360=bool(rep.get("revolve_360", False)),
                circular_pattern_count=int(rep.get("circular_pattern_count", 1)),
                density_kg_m3=float(rep.get("density_kg_m3", 1580.0)),
                density_source=str(rep.get("density_source", "")),
            )
            pos = tuple(float(v) for v in spec["replacement_position_m"]) if spec.get("replacement_position_m") else None
            payload = swap_assembly_part(
                list(spec["parts"]),
                target_part_name=str(spec["target_part_name"]),
                replacement=recipe,
                replacement_position_m=pos,
            )
            write_result(args.output, payload)
        elif args.command == "evidence-scorecard":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            payload = compute_virtual_evidence_scorecard(
                vehicle_family=str(spec.get("vehicle_family", "multirotor")),
                cpp_mass_kg=float(spec["cpp_mass_kg"]),
                python_mass_kg=float(spec["python_mass_kg"]),
                clearance_ok=bool(spec.get("clearance_ok", True)),
                mach=float(spec.get("mach", 0.05)),
                alpha_deg=float(spec.get("alpha_deg", 5.0)),
                has_custom_modified_part=bool(spec.get("has_custom_modified_part", False)),
                benchmark_twin_percent=spec.get("benchmark_twin_percent"),
            )
            write_result(args.output, payload)
        elif args.command == "phase1-eval":
            payload = evaluate_all_phase1_datasets()
            write_result(args.output, payload)
        elif args.command == "failure-atlas":
            payload = evaluate_failure_atlas_cases()
            write_result(args.output, payload)
        elif args.command == "load-powerpack":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            bat = import_electrophysics_powerpack(spec)
            write_result(args.output, bat.model_dump(mode="json"))
        elif args.command == "multiphysics-audit":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            payload = {
                "aeroacoustics": evaluate_rotor_and_jet_aeroacoustics(
                    is_jet=bool(spec.get("aircraft_family") == "jet"),
                    rotor_rpm=float(spec.get("rotor_rpm", 4800.0)),
                    jet_mach=float(spec.get("airspeed_m_s", 92.0)) / 340.3,
                ),
                "helicopter_highspeed": evaluate_helicopter_vrs_and_asymmetry(
                    horizontal_speed_m_s=float(spec.get("airspeed_m_s", 12.0)),
                ),
                "cavitation": evaluate_hydro_cavitation(prop_rpm=float(spec.get("rotor_rpm", 3800.0))),
                "rf_rcs": evaluate_rf_and_rcs(
                    sweep_deg=float(spec.get("sweep_deg", 26.0)),
                    rain_mm_h=float(spec.get("rain_mm_h", 0.0)),
                ),
            }
            write_result(args.output, payload)
        elif args.command == "rocket-sim":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            payload = evaluate_multistage_rocket(
                payload_mass_kg=float(spec.get("payload_mass_kg", 250.0)),
                target_altitude_m=float(spec.get("altitude_asl_m", 220000.0)) if float(spec.get("altitude_asl_m", 0.0)) > 50000.0 else 220000.0,
            )
            write_result(args.output, payload)
        elif args.command == "cfd-fea-export":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            export_dir = Path(spec.get("export_dir", str(args.output.parent / "cfd_fea_export")))
            payload = export_and_run_detailed_cfd_fea(
                project_name=str(spec.get("name", "AerodynamicsLabDesign")),
                airspeed_m_s=float(spec.get("airspeed_m_s", 18.0)),
                wingspan_m=float(spec.get("wingspan_m", 1.65)),
                root_chord_m=float(spec.get("root_chord_m", 0.28)),
                mass_kg=float(spec.get("mass_kg", 3.1)),
                output_dir=export_dir,
            )
            write_result(args.output, payload)
        elif args.command == "embedded-cfd-fea":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            exp_dir = Path(spec["export_dir"]) if spec.get("export_dir") else None
            write_result(args.output, run_embedded_3d_cfd_fea(spec, export_dir=exp_dir))
        elif args.command == "phase3-4-eval":
            write_result(args.output, evaluate_all_phase3_and_phase4_benchmarks())
        elif args.command == "solve-sketch":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            write_result(args.output, solve_freeform_sketch(spec))
        elif args.command == "freeform-cad":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            exp_dir = Path(spec["export_dir"]) if spec.get("export_dir") else None
            write_result(args.output, build_freeform_cad_model(spec, export_dir=exp_dir))
        elif args.command == "import-legacy":
            raw = json.loads(args.input.read_text(encoding="utf-8"))
            project = import_legacy_project(raw)
            payload = project.model_dump(mode="json")
            write_result(args.output, payload)
        else:
            asset_root = args.asset_root or args.input.parent
            raw_text = args.input.read_text(encoding="utf-8")
            project = inspect_and_validate_project(raw_text, asset_root)
            if args.command == "package":
                args.output.parent.mkdir(parents=True, exist_ok=True)
                copy_assets(project, asset_root, args.output)
                payload = project.model_dump(mode="json")
                write_result(args.output, payload)
                write_recovery_snapshot(project, args.output, asset_root)
            elif args.command == "save-version":
                result = save_and_version_project(project, asset_root, args.output, create_version=True, note=args.note)
                payload = result["project"]
            elif args.command == "run":
                payload = run_project(project)
                write_result(args.output, payload)
            else:
                payload = project.model_dump(mode="json")
                write_result(args.output, payload)
        if args.completion_output:
            write_result(args.completion_output, {"output_sha256": sha256(args.output.read_bytes()).hexdigest()})
    except ProjectWorkflowError as error:
        print(str(error), file=sys.stderr)
        if args.error_output:
            try:
                write_result(
                    args.error_output,
                    {"status": "failed", "category": error.category, "recoverable": error.recoverable, "error": str(error)},
                )
            except OSError as publication_error:
                print(str(publication_error), file=sys.stderr)
        return 2
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        if args.error_output:
            try:
                write_result(args.error_output, {"status": "failed", "category": "workflow_error", "recoverable": True, "error": str(error)})
            except OSError as publication_error:
                print(str(publication_error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
