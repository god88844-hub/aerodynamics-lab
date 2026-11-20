extends SceneTree

# Manual rendered benchmark. CI exercises correctness and lifecycle without
# asserting machine-dependent latency. The predeclared warm target is 2 seconds.
var desktop: Control
var report_path: String = ""
var context_path: String = ""
var sample_count: int = 5
var report: Dictionary = {"report_version": "cad_worker_timing_1", "warm_target_s": 2.0,
	"physical_validation_status": "unvalidated", "hardware_tier_acceptance": "pending",
	"scope": "One constrained solid, build plus torque response plus rendered frame. Does not measure 200-part FPS or process memory."}
var engine_pid: int = -1


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--report="):
			report_path = argument.trim_prefix("--report=")
		if argument.begins_with("--context="):
			context_path = argument.trim_prefix("--context=")
		if argument.begins_with("--samples="):
			sample_count = int(argument.trim_prefix("--samples="))
	if report_path.is_empty() or not report_path.is_absolute_path() or report_path.get_extension() != "json" or FileAccess.file_exists(report_path):
		push_error("Choose a new absolute JSON report path")
		quit(1)
		return
	if sample_count < 3 or sample_count > 20 or DisplayServer.get_name() == "headless":
		push_error("Use a graphical renderer and between 3 and 20 warm samples")
		quit(1)
		return
	if not context_path.is_empty():
		var context: Variant = JSON.parse_string(FileAccess.get_file_as_string(context_path))
		if not context is Dictionary:
			push_error("Benchmark context must be a JSON object")
			quit(1)
			return
		report["external_context"] = context
	report["godot"] = Engine.get_version_info()
	report["os"] = OS.get_name()
	report["cpu"] = OS.get_processor_name()
	report["logical_processors"] = OS.get_processor_count()
	report["system_memory_info"] = OS.get_memory_info()
	report["display_server"] = DisplayServer.get_name()
	report["driver_info"] = Array(OS.get_video_adapter_driver_info())
	report["renderer_setting"] = ProjectSettings.get_setting("rendering/renderer/rendering_method")
	report["generated_at_utc"] = Time.get_datetime_string_from_system(true)
	var revision: Array = []
	var repository: String = ProjectSettings.globalize_path("res://").trim_suffix("/").get_base_dir().get_base_dir()
	if OS.execute("git", ["-C", repository, "rev-parse", "HEAD"], revision, true, false) == 0:
		report["commit_sha"] = str(revision[0]).strip_edges()
	report["benchmark_sha256"] = FileAccess.get_sha256(ProjectSettings.globalize_path("res://benchmark_worker.gd"))
	var scene: PackedScene = load("res://main.tscn")
	desktop = scene.instantiate()
	get_root().add_child(desktop)
	if not await _wait():
		_finish(1, "Reference project did not load")
		return
	report["window_size"] = [get_root().size.x, get_root().size.y]
	report["viewport_size"] = [desktop.get("viewport").size.x, desktop.get("viewport").size.y]
	var cold: Dictionary = await _cycle(0.2)
	if cold.is_empty():
		_finish(1, "Cold CAD cycle failed")
		return
	report["cold_cycle"] = cold
	var warm: Array = []
	var latencies: Array[float] = []
	for index in range(sample_count):
		var sample: Dictionary = await _cycle(0.2 + 0.01 * (index % 2))
		if sample.is_empty():
			_finish(1, "Warm CAD cycle failed")
			return
		warm.append(sample)
		latencies.append(sample["total_s"])
	latencies.sort()
	report["warm_cycles"] = warm
	var middle: int = latencies.size() / 2
	report["warm_median_s"] = latencies[middle] if latencies.size() % 2 else (latencies[middle - 1] + latencies[middle]) / 2.0
	report["warm_max_s"] = latencies[-1]
	report["warm_target_met"] = latencies[-1] <= 2.0
	_finish(0 if report["warm_target_met"] else 2)


func _wait() -> bool:
	var deadline: int = Time.get_ticks_msec() + 95000
	while desktop.get("job_pid") > 0 and Time.get_ticks_msec() < deadline:
		await process_frame
	return desktop.get("job_pid") == -1 and desktop.call("_completed_output") and not FileAccess.file_exists(desktop.get("job_error"))


func _cycle(width: float) -> Dictionary:
	desktop.get("body_fields")["width_m"].value = width
	desktop.get("body_fields")["height_m"].value = 0.1
	desktop.get("body_fields")["depth_m"].value = 0.02
	desktop.get("body_fields")["material_density_kg_m3"].value = 500.0
	desktop.get("density_enabled").button_pressed = true
	desktop.get("torque_z").value = 0.001
	desktop.get("torque_duration").value = 1.0
	desktop.get("torque_step").value = 0.005
	var start: int = Time.get_ticks_usec()
	desktop.call("_rebuild_body")
	if not await _wait():
		report["failed_stage"] = "build"
		report["worker_status"] = desktop.get("status_label").text
		return {}
	var built: int = Time.get_ticks_usec()
	desktop.call("_run_cad_torque")
	if not await _wait():
		report["failed_stage"] = "analysis"
		report["worker_status"] = desktop.get("status_label").text
		return {}
	var calculated: int = Time.get_ticks_usec()
	await RenderingServer.frame_post_draw
	var finished: int = Time.get_ticks_usec()
	var result: Dictionary = desktop.get("result")
	var mass: float = 500.0 * width * 0.1 * 0.02
	var inertia: float = mass * (width * width + 0.1 * 0.1) / 12.0
	var expected_speed: float = 0.001 / inertia
	var actual_mass: float = result["mass_properties"]["mass_kg"]
	var speed: float = result["result"]["telemetry"]["omega_body_rad_s"][-1][2]
	var started: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(desktop.get("job_started")))
	var current_pid: int = int(started["worker_pid"])
	if engine_pid < 0:
		engine_pid = current_pid
	if current_pid != engine_pid or absf(actual_mass - mass) > 1e-7 or absf(speed - expected_speed) > 1e-6:
		report["failed_stage"] = "independent analytic check or engine identity"
		report["failed_case"] = {"actual_mass": actual_mass, "expected_mass": mass,
			"actual_speed": speed, "expected_speed": expected_speed, "worker_pid": current_pid}
		return {}
	return {"width_m": width, "height_m": 0.1, "depth_m": 0.02, "density_kg_m3": 500.0,
		"torque_z_nm": 0.001, "duration_s": 1.0, "step_s": 0.005,
		"build_s": (built - start) / 1000000.0, "analysis_s": (calculated - built) / 1000000.0,
		"render_wait_s": (finished - calculated) / 1000000.0, "total_s": (finished - start) / 1000000.0,
		"mass_kg": actual_mass, "omega_z_rad_s": speed, "expected_omega_z_rad_s": expected_speed,
		"worker_pid": current_pid}


func _finish(code: int, failure: String = "") -> void:
	if not failure.is_empty():
		report["failure"] = failure
	if desktop != null and desktop.get("cad_worker") != null:
		var start: int = Time.get_ticks_usec()
		report["worker_stopped"] = desktop.get("cad_worker").stop()
		report["stop_s"] = (Time.get_ticks_usec() - start) / 1000000.0
		if not report["worker_stopped"]:
			code = 1
	DirAccess.make_dir_recursive_absolute(report_path.get_base_dir())
	var file: FileAccess = FileAccess.open(report_path, FileAccess.WRITE)
	if file == null:
		push_error("Cannot publish the benchmark report")
		quit(1)
		return
	file.store_string(JSON.stringify(report, "\t"))
	file.close()
	print("CAD worker benchmark result: " + report_path)
	quit(code)
