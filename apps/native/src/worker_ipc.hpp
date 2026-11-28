#pragma once

#include "cad_types.hpp"

#include <atomic>
#include <filesystem>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace aerolab {

struct WorkerJobStatus {
    bool running = false;
    bool last_ok = true;
    std::string active_command;
    std::string summary_line = "Ready (local C++20 lab_core + Python worker)";
    std::vector<std::string> log_lines;
};

class WorkerIPC {
public:
    explicit WorkerIPC(std::filesystem::path repo_root);
    ~WorkerIPC();

    bool is_busy() const { return busy_.load(); }
    WorkerJobStatus snapshot_status() const;

    // Direct zero-latency pure C++20 lab_core 6-DoF RK4 run
    void run_cpp_rk4_multirotor(const AircraftDesignParams &params, LiveEvidenceSummary &summary);

    // Poll async Python solver output into trajectory/metrics when finished
    bool poll_completed_results(LiveEvidenceSummary &summary);
    bool consume_pending_occt_mesh(FreeformBrepCache &cache);
    bool consume_pending_cfd_fea(EmbeddedCfdFeaCache &cache);
    const std::filesystem::path &tmp_dir() const { return tmp_dir_; }

    // Background subprocess invocation of scripts/lab_project.py
    bool launch_python_command(const std::string &cmd, const std::string &input_json, const std::string &note = "");

    std::string build_project_payload_json(const AircraftDesignParams &params) const;
    std::string build_part_payload_json(const AircraftDesignParams &params, const std::filesystem::path &export_dir) const;
    std::string build_drawing_payload_json(const AircraftDesignParams &params, const std::filesystem::path &export_dir) const;
    std::string build_compare_payload_json(const AircraftDesignParams &params, const LiveEvidenceSummary &summary) const;
    static bool load_project_payload_json(const std::string &json_text, AircraftDesignParams &params);

private:
    void append_log(const std::string &line);

    std::filesystem::path repo_root_;
    std::filesystem::path tmp_dir_;
    std::atomic<bool> busy_{false};
    std::atomic<bool> pending_result_{false};
    std::atomic<bool> pending_occt_mesh_{false};
    std::atomic<bool> pending_cfd_fea_{false};
    mutable std::mutex mu_;
    WorkerJobStatus status_;
    std::thread worker_thread_;
};

std::filesystem::path detect_repo_root();
std::string native_open_file_dialog(const char *filter_desc, const char *ext);
std::string native_save_file_dialog(const char *default_name, const char *filter_desc, const char *ext);

} // namespace aerolab
