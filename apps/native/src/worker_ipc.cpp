#include "worker_ipc.hpp"

#include "lab/flight_rk4.hpp"

#include <chrono>
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
    cfg.max_total_thrust_n = cfg.mass_kg * 9.80665 * 2.15;
    cfg.cd_a_m2 = 0.06;
    cfg.wind_world_m_s = {params.wind_x_m_s, params.wind_y_m_s, 0.0};
    cfg.initial_altitude_m = 1.5;
    cfg.target_altitude_m = 4.5;
    cfg.dt_s = 0.01;
    cfg.duration_s = 2.4;

    const auto res = lab::run_multirotor_rk4(cfg);
    summary.has_trajectory = res.ok && !res.positions_m.empty();
    summary.playing = summary.has_trajectory;
    summary.playback_time_s = 0.0f;
    summary.duration_s = static_cast<float>(res.final_time_s);
    summary.max_altitude_m = res.max_altitude_m;
    summary.min_bus_voltage_v = res.min_bus_voltage_v;
    summary.traj_t_s = res.times_s;
    summary.traj_pos_m = res.positions_m;
    summary.traj_quat_wxyz = res.quaternions_wxyz;

    std::lock_guard lock(mu_);
    status_.last_ok = res.ok;
    status_.summary_line = "C++20 RK4 6-DoF complete: " + std::to_string(res.step_count) +
                           " steps, max Z=" + std::to_string(res.max_altitude_m).substr(0, 4) + " m";
    status_.log_lines.push_back(status_.summary_line);
}

std::string WorkerIPC::build_project_payload_json(const AircraftDesignParams &params) const {
    const char *fam = "multirotor";
    if (params.family == VehicleFamily::FixedWing) fam = "fixed_wing";
    else if (params.family == VehicleFamily::Helicopter) fam = "helicopter";
    else if (params.family == VehicleFamily::VTOL) fam = "vtol";

    std::ostringstream oss;
    oss << "{\n"
        << "  \"name\": \"" << params.project_name << "\",\n"
        << "  \"aircraft_family\": \"" << fam << "\",\n"
        << "  \"wingspan_m\": " << params.wingspan_m << ",\n"
        << "  \"root_chord_m\": " << params.root_chord_m << ",\n"
        << "  \"tip_chord_m\": " << params.tip_chord_m << ",\n"
        << "  \"sweep_deg\": " << params.sweep_deg << ",\n"
        << "  \"dihedral_deg\": " << params.dihedral_deg << ",\n"
        << "  \"twist_tip_deg\": " << params.twist_tip_deg << ",\n"
        << "  \"airfoil_code\": \"" << params.airfoil_code << "\",\n"
        << "  \"alpha_deg\": " << params.alpha_deg << ",\n"
        << "  \"airspeed_m_s\": " << params.airspeed_m_s << ",\n"
        << "  \"arm_length_m\": " << params.arm_length_m << ",\n"
        << "  \"n_rotors\": " << params.rotor_count << ",\n"
        << "  \"prop_diameter_m\": " << params.prop_diameter_m << "\n"
        << "}\n";
    return oss.str();
}

std::string WorkerIPC::build_part_payload_json(const AircraftDesignParams &params, const std::filesystem::path &export_dir) const {
    const char *kind = "rounded_plate";
    if (params.active_part.sketch_kind == SketchShapeKind::RingDuct) kind = "ring_duct";
    else if (params.active_part.sketch_kind == SketchShapeKind::AirfoilSection) kind = "airfoil_section";
    else if (params.active_part.sketch_kind == SketchShapeKind::HexMount) kind = "hex_mount";

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
        << "  \"export_dir\": \"" << export_dir.generic_string() << "\"\n"
        << "}\n";
    return oss.str();
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
        const int rc = std::system(shell.str().c_str());
        std::lock_guard lock(mu_);
        status_.running = false;
        status_.last_ok = (rc == 0);
        if (rc == 0) {
            status_.summary_line = "Worker finished: " + cmd + " -> " + out_file.filename().string();
        } else {
            status_.summary_line = "Worker exited (" + std::to_string(rc) + ") on " + cmd;
        }
        status_.log_lines.push_back(status_.summary_line);
        busy_.store(false);
    });
    return true;
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
