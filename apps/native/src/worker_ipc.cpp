#include "worker_ipc.hpp"

#include "lab/flight_rk4.hpp"

#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <sstream>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <commdlg.h>
#endif

namespace aerolab {

std::filesystem::path detect_repo_root() {
    std::error_code ec;
    auto cur = std::filesystem::current_path(ec);
    for (int i = 0; i < 6; ++i) {
        if (std::filesystem::exists(cur / "scripts" / "lab_project.py", ec)) {
            return cur;
        }
        if (!cur.has_parent_path() || cur == cur.parent_path()) break;
        cur = cur.parent_path();
    }
    return std::filesystem::current_path(ec);
}

WorkerIPC::WorkerIPC(std::filesystem::path repo_root)
    : repo_root_(std::move(repo_root)), tmp_dir_(repo_root_ / ".local" / "tmp" / "native_ipc") {
    std::error_code ec;
    std::filesystem::create_directories(tmp_dir_, ec);
    append_log("Aerodynamics Lab C++20 engine initialized. Repo: " + repo_root_.string());
}

WorkerIPC::~WorkerIPC() {
    if (worker_thread_.joinable()) {
        worker_thread_.join();
    }
}

void WorkerIPC::append_log(const std::string &line) {
    std::lock_guard lock(mu_);
    status_.log_lines.push_back(line);
    if (status_.log_lines.size() > 200) {
        status_.log_lines.erase(status_.log_lines.begin());
    }
}

WorkerJobStatus WorkerIPC::snapshot_status() const {
    std::lock_guard lock(mu_);
    return status_;
}

void WorkerIPC::run_cpp_rk4_multirotor(const AircraftDesignParams &params, LiveEvidenceSummary &summary) {
    lab::MultirotorSimConfig cfg;
    cfg.mass_kg = std::max(0.2, summary.total_mass_kg > 0.1 ? summary.total_mass_kg : 2.5);
    cfg.n_rotors = std::clamp(params.rotor_count, 3, 8);
    const double rho = (summary.air_density_kg_m3 > 0.2) ? summary.air_density_kg_m3 : 1.225;
    cfg.air_density_kg_m3 = rho;
    const double rho_ratio = std::max(0.25, rho / 1.225);
    const double effective_tw = std::max(0.05, summary.thrust_to_weight > 0.01 ? summary.thrust_to_weight : 2.0);
    // flight_rk4 scales max_total_thrust_n by (rho / 1.225); divide here so density is applied once cleanly.
    cfg.max_total_thrust_n = (cfg.mass_kg * 9.80665 * effective_tw) / rho_ratio;
    cfg.cd_a_m2 = 0.06;
    const double gust_gain = 1.0 + 0.5 * std::clamp(static_cast<double>(params.turbulence_pct) / 100.0, 0.0, 0.6);
    cfg.wind_world_m_s = {params.wind_x_m_s * gust_gain, params.wind_y_m_s * gust_gain, 0.0};
    cfg.min_bus_voltage_v = (summary.cutoff_voltage_v > 5.0) ? summary.cutoff_voltage_v : 19.2;
    cfg.initial_altitude_m = 1.5;
    cfg.target_altitude_m = 4.5;
    cfg.dt_s = 0.01;
    cfg.duration_s = 2.4;

    const auto res = lab::run_multirotor_rk4(cfg);
    summary.has_trajectory = res.ok && !res.positions_m.empty();
    summary.playing = summary.has_trajectory && !res.aborted;
    summary.playback_time_s = 0.0f;
    summary.duration_s = static_cast<float>(res.final_time_s);
    summary.max_altitude_m = res.max_altitude_m;
    summary.min_bus_voltage_v = res.min_bus_voltage_v;
    summary.traj_t_s = res.times_s;
    summary.traj_pos_m = res.positions_m;
    summary.traj_quat_wxyz = res.quaternions_wxyz;

    std::lock_guard lock(mu_);
    status_.last_ok = res.ok && !res.aborted;
    if (res.aborted) {
        status_.summary_line = "6-DoF ABORTED at t=" + std::to_string(res.final_time_s).substr(0, 4) +
                               " s: " + res.error_or_reason;
        summary.validation_status = "FAIL";
        summary.predicted_readiness_pct = 0.0;
        summary.status_detail = "6-DoF Sim Aborted: " + res.error_or_reason;
    } else {
        status_.summary_line = "C++20 RK4 6-DoF complete: " + std::to_string(res.step_count) +
                               " steps, max Z=" + std::to_string(res.max_altitude_m).substr(0, 4) + " m";
    }
    status_.log_lines.push_back(status_.summary_line);
}

std::string WorkerIPC::build_project_payload_json(const AircraftDesignParams &params) const {
    const char *fam = "multirotor";
    if (params.family == VehicleFamily::FixedWing) fam = "fixed_wing";
    else if (params.family == VehicleFamily::Helicopter) fam = "helicopter";
    else if (params.family == VehicleFamily::VTOL) fam = "vtol";
    else if (params.family == VehicleFamily::CustomPart) fam = "custom_part";

    const char *kind = "rounded_plate";
    if (params.active_part.sketch_kind == SketchShapeKind::RingDuct) kind = "ring_duct";
    else if (params.active_part.sketch_kind == SketchShapeKind::AirfoilSection) kind = "airfoil_section";
    else if (params.active_part.sketch_kind == SketchShapeKind::HexMount) kind = "hex_mount";
    else if (params.active_part.sketch_kind == SketchShapeKind::CustomPropeller) kind = "custom_propeller";
    else if (params.active_part.sketch_kind == SketchShapeKind::CustomBodyShell) kind = "custom_body_shell";

    const double est_mass = params.frame_mass_kg + params.battery_mass_kg + params.payload_mass_kg +
                            params.motor_mass_kg * std::clamp(params.rotor_count, 1, 8);

    std::ostringstream oss;
    oss << "{\n"
        << "  \"name\": \"" << params.project_name << "\",\n"
        << "  \"aircraft_family\": \"" << fam << "\",\n"
        << "  \"mass_kg\": " << est_mass << ",\n"
        << "  \"wingspan_m\": " << params.wingspan_m << ",\n"
        << "  \"root_chord_m\": " << params.root_chord_m << ",\n"
        << "  \"tip_chord_m\": " << params.tip_chord_m << ",\n"
        << "  \"sweep_deg\": " << params.sweep_deg << ",\n"
        << "  \"dihedral_deg\": " << params.dihedral_deg << ",\n"
        << "  \"twist_tip_deg\": " << params.twist_tip_deg << ",\n"
        << "  \"vtol_tilt_deg\": " << params.vtol_tilt_deg << ",\n"
        << "  \"airfoil_code\": \"" << params.airfoil_code << "\",\n"
        << "  \"alpha_deg\": " << params.alpha_deg << ",\n"
        << "  \"airspeed_m_s\": " << params.airspeed_m_s << ",\n"
        << "  \"arm_length_m\": " << params.arm_length_m << ",\n"
        << "  \"n_rotors\": " << params.rotor_count << ",\n"
        << "  \"prop_diameter_m\": " << params.prop_diameter_m << ",\n"
        << "  \"prop_pitch_deg\": " << params.prop_pitch_deg << ",\n"
        << "  \"prop_blades\": " << params.prop_blades << ",\n"
        << "  \"main_rotor_diameter_m\": " << params.main_rotor_diameter_m << ",\n"
        << "  \"tail_boom_length_m\": " << params.tail_boom_length_m << ",\n"
        << "  \"battery_mass_kg\": " << params.battery_mass_kg << ",\n"
        << "  \"payload_mass_kg\": " << params.payload_mass_kg << ",\n"
        << "  \"battery_cells_s\": " << params.battery_cells_s << ",\n"
        << "  \"battery_capacity_ah\": " << params.battery_capacity_ah << ",\n"
        << "  \"battery_r0_ohm\": " << params.battery_r0_ohm << ",\n"
        << "  \"rotor_rpm\": " << params.rotor_rpm << ",\n"
        << "  \"wind_x_m_s\": " << params.wind_x_m_s << ",\n"
        << "  \"wind_y_m_s\": " << params.wind_y_m_s << ",\n"
        << "  \"turbulence_pct\": " << params.turbulence_pct << ",\n"
        << "  \"mfg_tolerance_pct\": " << params.mfg_tolerance_pct << ",\n"
        << "  \"altitude_asl_m\": " << params.altitude_asl_m << ",\n"
        << "  \"motor_cooling_grade\": " << params.motor_cooling_grade << ",\n"
        << "  \"rain_mm_h\": " << params.rain_mm_h << ",\n"
        << "  \"oat_c\": " << params.oat_c << ",\n"
        << "  \"attach_custom_part\": " << (params.attach_custom_part ? "true" : "false") << ",\n"
        << "  \"part_name\": \"" << params.active_part.part_name << "\",\n"
        << "  \"sketch_kind\": \"" << kind << "\",\n"
        << "  \"part_width_m\": " << params.active_part.width_m << ",\n"
        << "  \"part_length_m\": " << params.active_part.length_m << ",\n"
        << "  \"part_thickness_m\": " << params.active_part.thickness_m << ",\n"
        << "  \"part_hole_radius_m\": " << params.active_part.hole_radius_m << ",\n"
        << "  \"part_revolve_360\": " << (params.active_part.revolve_360 ? "true" : "false") << ",\n"
        << "  \"part_circular_pattern_count\": " << params.active_part.circular_pattern_count << ",\n"
        << "  \"motor_id\": \"tmotor_mn3508_kv380\",\n"
        << "  \"propeller_id\": \"tmotor_p15x5_cf\",\n"
        << "  \"esc_id\": \"generic_esc_20a\",\n"
        << "  \"battery_id\": \"generic_6s_lipo_16000mah\",\n"
        << "  \"frame_parts\": [\n"
        << "    {\"name\": \"center_frame_plate\", \"material_id\": \"cfrp_quasi_iso\", \"dimensions_m\": ["
        << params.frame_width_m << ", " << (params.frame_width_m * 1.15f) << ", " << (params.hub_height_m * 0.45f)
        << "], \"shape\": \"box\", \"position_m\": [0.0, 0.0, 0.0]}\n"
        << "  ],\n"
        << "  \"rotors\": [\n";
    const int nr = std::clamp(params.rotor_count, 3, 8);
    constexpr double kPiD = 3.14159265358979323846;
    for (int i = 0; i < nr; ++i) {
        const double ang = (kPiD / static_cast<double>(nr)) + 2.0 * kPiD * static_cast<double>(i) / static_cast<double>(nr);
        const double rx = params.arm_length_m * std::cos(ang);
        const double ry = params.arm_length_m * std::sin(ang);
        oss << "    {\"position_m\": [" << rx << ", " << ry << ", 0.015], \"spin_direction\": " << (i % 2 == 0 ? 1 : -1)
            << "}" << (i + 1 < nr ? "," : "") << "\n";
    }
    oss << "  ]\n"
        << "}\n";
    return oss.str();
}

std::string WorkerIPC::build_part_payload_json(const AircraftDesignParams &params, const std::filesystem::path &export_dir) const {
    const char *kind = "rounded_plate";
    if (params.active_part.sketch_kind == SketchShapeKind::RingDuct) kind = "ring_duct";
    else if (params.active_part.sketch_kind == SketchShapeKind::AirfoilSection) kind = "airfoil_section";
    else if (params.active_part.sketch_kind == SketchShapeKind::HexMount) kind = "hex_mount";
    else if (params.active_part.sketch_kind == SketchShapeKind::CustomPropeller) kind = "custom_propeller";
    else if (params.active_part.sketch_kind == SketchShapeKind::CustomBodyShell) kind = "custom_body_shell";

    std::ostringstream oss;
    oss << "{\n"
        << "  \"part_name\": \"" << params.active_part.part_name << "\",\n"
        << "  \"sketch_kind\": \"" << kind << "\",\n"
        << "  \"width_m\": " << params.active_part.width_m << ",\n"
        << "  \"length_m\": " << params.active_part.length_m << ",\n"
        << "  \"thickness_m\": " << params.active_part.thickness_m << ",\n"
        << "  \"hole_radius_m\": " << params.active_part.hole_radius_m << ",\n"
        << "  \"revolve_360\": " << (params.active_part.revolve_360 ? "true" : "false") << ",\n"
        << "  \"circular_pattern_count\": " << params.active_part.circular_pattern_count << ",\n"
        << "  \"density_kg_m3\": " << params.active_part.density_kg_m3 << ",\n"
        << "  \"density_source\": \"builtin_material_library\",\n"
        << "  \"airfoil_code\": \"" << params.airfoil_code << "\",\n"
        << "  \"export_dir\": \"" << export_dir.generic_string() << "\"\n"
        << "}\n";
    return oss.str();
}

std::string WorkerIPC::build_drawing_payload_json(const AircraftDesignParams &params, const std::filesystem::path &export_dir) const {
    const auto svg = (export_dir / "wing_drawing.svg").generic_string();
    const auto dxf = (export_dir / "wing_drawing.dxf").generic_string();
    std::ostringstream oss;
    oss << "{\n"
        << "  \"name\": \"" << params.project_name << "\",\n"
        << "  \"wingspan_m\": " << params.wingspan_m << ",\n"
        << "  \"root_chord_m\": " << params.root_chord_m << ",\n"
        << "  \"tip_chord_m\": " << params.tip_chord_m << ",\n"
        << "  \"airfoil_code\": \"" << params.airfoil_code << "\",\n"
        << "  \"svg_path\": \"" << svg << "\",\n"
        << "  \"dxf_path\": \"" << dxf << "\"\n"
        << "}\n";
    return oss.str();
}

std::string WorkerIPC::build_compare_payload_json(const AircraftDesignParams &params, const LiveEvidenceSummary &summary) const {
    const double hover_ref = (summary.total_mass_kg > 0.1) ? summary.loaded_bus_voltage_v : 22.7;
    std::ostringstream oss;
    oss << "{\n"
        << "  \"channel\": \"bus_voltage\",\n"
        << "  \"unit\": \"V\",\n"
        << "  \"tolerance_abs\": 0.8,\n"
        << "  \"frozen_run\": {\n"
        << "    \"t_s\": [0.0, 0.5, 1.0],\n"
        << "    \"bus_voltage\": [" << hover_ref << ", " << (hover_ref - 0.15) << ", " << (hover_ref - 0.30) << "]\n"
        << "  },\n"
        << "  \"source_record\": {\n"
        << "    \"source_id\": \"" << (params.attach_custom_part ? "custom_physics_only" : "pinned_sit_uiuc_dev") << "\",\n"
        << "    \"t_s\": [0.0, 0.5, 1.0],\n"
        << "    \"bus_voltage\": [" << (hover_ref + 0.1) << ", " << (hover_ref - 0.08) << ", " << (hover_ref - 0.22) << "]\n"
        << "  }\n"
        << "}\n";
    return oss.str();
}

bool WorkerIPC::load_project_payload_json(const std::string &json_text, AircraftDesignParams &params) {
    auto find_val = [&](const char *key) -> std::string {
        const std::string pat = std::string("\"") + key + "\"";
        const auto kp = json_text.find(pat);
        if (kp == std::string::npos) return {};
        const auto colon = json_text.find(':', kp + pat.size());
        if (colon == std::string::npos) return {};
        auto vs = json_text.find_first_not_of(" \t\r\n", colon + 1);
        if (vs == std::string::npos) return {};
        if (json_text[vs] == '"') {
            const auto ve = json_text.find('"', vs + 1);
            return (ve != std::string::npos) ? json_text.substr(vs + 1, ve - vs - 1) : std::string{};
        }
        const auto ve = json_text.find_first_of(",}\r\n", vs);
        return json_text.substr(vs, ve == std::string::npos ? std::string::npos : ve - vs);
    };
    auto read_f = [&](const char *key, float &dst) {
        const auto s = find_val(key);
        if (!s.empty()) dst = static_cast<float>(std::atof(s.c_str()));
    };
    auto read_i = [&](const char *key, int &dst) {
        const auto s = find_val(key);
        if (!s.empty()) dst = std::atoi(s.c_str());
    };

    const auto fam = find_val("aircraft_family");
    if (fam.empty()) return false;
    if (fam == "multirotor") params.family = VehicleFamily::Multirotor;
    else if (fam == "fixed_wing") params.family = VehicleFamily::FixedWing;
    else if (fam == "helicopter") params.family = VehicleFamily::Helicopter;
    else if (fam == "vtol") params.family = VehicleFamily::VTOL;
    else if (fam == "custom_part") params.family = VehicleFamily::CustomPart;

    if (const auto n = find_val("name"); !n.empty()) params.project_name = n;
    if (const auto af = find_val("airfoil_code"); !af.empty()) params.airfoil_code = af;
    read_f("wingspan_m", params.wingspan_m);
    read_f("root_chord_m", params.root_chord_m);
    read_f("tip_chord_m", params.tip_chord_m);
    read_f("sweep_deg", params.sweep_deg);
    read_f("dihedral_deg", params.dihedral_deg);
    read_f("twist_tip_deg", params.twist_tip_deg);
    read_f("vtol_tilt_deg", params.vtol_tilt_deg);
    read_f("alpha_deg", params.alpha_deg);
    read_f("airspeed_m_s", params.airspeed_m_s);
    read_f("arm_length_m", params.arm_length_m);
    read_i("n_rotors", params.rotor_count);
    read_f("prop_diameter_m", params.prop_diameter_m);
    read_f("prop_pitch_deg", params.prop_pitch_deg);
    read_i("prop_blades", params.prop_blades);
    read_f("main_rotor_diameter_m", params.main_rotor_diameter_m);
    read_f("tail_boom_length_m", params.tail_boom_length_m);
    read_f("battery_mass_kg", params.battery_mass_kg);
    read_f("payload_mass_kg", params.payload_mass_kg);
    read_i("battery_cells_s", params.battery_cells_s);
    read_f("battery_capacity_ah", params.battery_capacity_ah);
    read_f("battery_r0_ohm", params.battery_r0_ohm);
    read_f("rotor_rpm", params.rotor_rpm);
    read_f("wind_x_m_s", params.wind_x_m_s);
    read_f("wind_y_m_s", params.wind_y_m_s);
    read_f("turbulence_pct", params.turbulence_pct);
    read_f("mfg_tolerance_pct", params.mfg_tolerance_pct);
    read_f("altitude_asl_m", params.altitude_asl_m);
    read_i("motor_cooling_grade", params.motor_cooling_grade);
    read_f("rain_mm_h", params.rain_mm_h);
    read_f("oat_c", params.oat_c);
    if (const auto ac = find_val("attach_custom_part"); !ac.empty()) params.attach_custom_part = (ac == "true");
    if (const auto pn = find_val("part_name"); !pn.empty()) params.active_part.part_name = pn;
    if (const auto sk = find_val("sketch_kind"); !sk.empty()) {
        if (sk == "ring_duct") params.active_part.sketch_kind = SketchShapeKind::RingDuct;
        else if (sk == "airfoil_section") params.active_part.sketch_kind = SketchShapeKind::AirfoilSection;
        else if (sk == "hex_mount") params.active_part.sketch_kind = SketchShapeKind::HexMount;
        else if (sk == "custom_propeller") params.active_part.sketch_kind = SketchShapeKind::CustomPropeller;
        else if (sk == "custom_body_shell") params.active_part.sketch_kind = SketchShapeKind::CustomBodyShell;
        else params.active_part.sketch_kind = SketchShapeKind::RoundedPlate;
    }
    read_f("part_width_m", params.active_part.width_m);
    read_f("part_length_m", params.active_part.length_m);
    read_f("part_thickness_m", params.active_part.thickness_m);
    read_f("part_hole_radius_m", params.active_part.hole_radius_m);
    if (const auto rv = find_val("part_revolve_360"); !rv.empty()) params.active_part.revolve_360 = (rv == "true");
    read_i("part_circular_pattern_count", params.active_part.circular_pattern_count);
    return true;
}

bool WorkerIPC::launch_python_command(const std::string &cmd, const std::string &input_json, const std::string &note) {
    if (busy_.exchange(true)) {
        return false;
    }
    if (worker_thread_.joinable()) {
        worker_thread_.join();
    }
    {
        std::lock_guard lock(mu_);
        status_.running = true;
        status_.active_command = cmd;
        status_.summary_line = "Running local worker: " + cmd + "...";
        status_.log_lines.push_back("> python scripts/lab_project.py " + cmd);
    }

    worker_thread_ = std::thread([this, cmd, input_json, note]() {
        std::error_code ec;
        std::filesystem::create_directories(tmp_dir_, ec);
        std::filesystem::create_directories(repo_root_ / ".local" / "tmp" / "native_exports", ec);
        const auto in_file = tmp_dir_ / "job_in.json";
        const auto out_file = tmp_dir_ / "job_out.json";
        const auto err_file = tmp_dir_ / "job_err.json";
        {
            std::ofstream ofs(in_file, std::ios::binary);
            ofs << input_json;
        }
        const char *py_env = std::getenv("LAB_PYTHON");
        const std::string py = (py_env && *py_env) ? std::string(py_env) : "python";
        const std::string script = (repo_root_ / "scripts" / "lab_project.py").string();
        std::ostringstream shell;
        shell << "\"" << py << "\" \"" << script << "\" " << cmd << " \"" << in_file.string() << "\" \""
              << out_file.string() << "\" --error-output \"" << err_file.string() << "\"";
        if (!note.empty()) {
            shell << " --note \"" << note << "\"";
        }
        int rc = -1;
#ifdef _WIN32
        STARTUPINFOA si{};
        PROCESS_INFORMATION pi{};
        si.cb = sizeof(si);
        std::string cmdline = shell.str();
        if (CreateProcessA(nullptr, cmdline.data(), nullptr, nullptr, FALSE, CREATE_NO_WINDOW, nullptr,
                           repo_root_.string().c_str(), &si, &pi)) {
            WaitForSingleObject(pi.hProcess, 120000);
            DWORD exit_code = 1;
            GetExitCodeProcess(pi.hProcess, &exit_code);
            rc = static_cast<int>(exit_code);
            CloseHandle(pi.hThread);
            CloseHandle(pi.hProcess);
        }
#else
        rc = std::system(shell.str().c_str());
#endif
        std::lock_guard lock(mu_);
        status_.running = false;
        status_.last_ok = (rc == 0);
        if (rc == 0) {
            status_.summary_line = "Worker finished: " + cmd + " -> " + out_file.filename().string();
            pending_result_.store(true);
        } else {
            status_.summary_line = "Worker exited (" + std::to_string(rc) + ") on " + cmd;
        }
        status_.log_lines.push_back(status_.summary_line);
        busy_.store(false);
    });
    return true;
}

bool WorkerIPC::poll_completed_results(LiveEvidenceSummary &summary) {
    if (!pending_result_.exchange(false)) {
        return false;
    }
    const auto out_file = tmp_dir_ / "job_out.json";
    std::ifstream ifs(out_file);
    if (!ifs) return false;
    std::string text((std::istreambuf_iterator<char>(ifs)), std::istreambuf_iterator<char>());
    auto parse_triples = [&](const char *key) -> std::vector<std::array<double, 3>> {
        std::vector<std::array<double, 3>> pts;
        const auto kpos = text.find(key);
        if (kpos == std::string::npos) return pts;
        auto pos = text.find('[', kpos);
        if (pos == std::string::npos) return pts;
        int depth = 0;
        for (std::size_t i = pos; i < text.size(); ++i) {
            if (text[i] == '[') {
                ++depth;
                if (depth == 2) {
                    double x = 0, y = 0, z = 0;
                    if (std::sscanf(text.c_str() + i + 1, "%lf , %lf , %lf", &x, &y, &z) == 3) {
                        pts.push_back({x, y, z});
                    }
                }
            } else if (text[i] == ']') {
                --depth;
                if (depth <= 0) break;
            }
        }
        return pts;
    };
    auto pts = parse_triples("\"positions_m\"");
    if (pts.empty()) pts = parse_triples("\"trajectory_positions_m\"");
    if (!pts.empty()) {
        summary.has_trajectory = true;
        summary.playing = true;
        summary.playback_time_s = 0.0f;
        summary.duration_s = 2.5f;
        summary.traj_pos_m = std::move(pts);
        summary.traj_t_s.resize(summary.traj_pos_m.size());
        summary.traj_quat_wxyz.assign(summary.traj_pos_m.size(), {1.0, 0.0, 0.0, 0.0});
        for (std::size_t i = 0; i < summary.traj_pos_m.size(); ++i) {
            summary.traj_t_s[i] = (summary.traj_pos_m.size() > 1)
                                      ? (summary.duration_s * static_cast<double>(i) / static_cast<double>(summary.traj_pos_m.size() - 1))
                                      : 0.0;
        }
        return true;
    }
    return false;
}

std::string native_open_file_dialog(const char *filter_desc, const char *ext) {
#ifdef _WIN32
    wchar_t file_buf[MAX_PATH] = L"";
    wchar_t filter_w[128] = L"All Files (*.*)\0*.*\0";
    (void)filter_desc;
    (void)ext;
    OPENFILENAMEW ofn{};
    ofn.lStructSize = sizeof(ofn);
    ofn.lpstrFilter = filter_w;
    ofn.lpstrFile = file_buf;
    ofn.nMaxFile = MAX_PATH;
    ofn.Flags = OFN_PATHMUSTEXIST | OFN_FILEMUSTEXIST | OFN_NOCHANGEDIR;
    if (GetOpenFileNameW(&ofn)) {
        int len = WideCharToMultiByte(CP_UTF8, 0, file_buf, -1, nullptr, 0, nullptr, nullptr);
        std::string out(len > 0 ? len - 1 : 0, '\0');
        WideCharToMultiByte(CP_UTF8, 0, file_buf, -1, out.data(), len, nullptr, nullptr);
        return out;
    }
#else
    (void)filter_desc;
    (void)ext;
#endif
    return {};
}

std::string native_save_file_dialog(const char *default_name, const char *filter_desc, const char *ext) {
#ifdef _WIN32
    wchar_t file_buf[MAX_PATH] = L"";
    MultiByteToWideChar(CP_UTF8, 0, default_name, -1, file_buf, MAX_PATH);
    wchar_t filter_w[128] = L"All Files (*.*)\0*.*\0";
    (void)filter_desc;
    (void)ext;
    OPENFILENAMEW ofn{};
    ofn.lStructSize = sizeof(ofn);
    ofn.lpstrFilter = filter_w;
    ofn.lpstrFile = file_buf;
    ofn.nMaxFile = MAX_PATH;
    ofn.Flags = OFN_OVERWRITEPROMPT | OFN_NOCHANGEDIR;
    if (GetSaveFileNameW(&ofn)) {
        int len = WideCharToMultiByte(CP_UTF8, 0, file_buf, -1, nullptr, 0, nullptr, nullptr);
        std::string out(len > 0 ? len - 1 : 0, '\0');
        WideCharToMultiByte(CP_UTF8, 0, file_buf, -1, out.data(), len, nullptr, nullptr);
        return out;
    }
#else
    (void)default_name;
    (void)filter_desc;
    (void)ext;
#endif
    return {};
}

} // namespace aerolab
