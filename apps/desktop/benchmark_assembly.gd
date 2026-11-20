extends SceneTree

var desktop: Control
var report_path: String
var fixture_path: String
var frames: int = 600
var interactive: bool = false
var report: Dictionary = {"report_version": "assembly_viewport_1", "physical_validation_status": "unvalidated",
	"hardware_tier_acceptance": "pending", "frame_target_ms": 1000.0 / 30.0,
	"scope": "200-part viewport orbit/selection, save/reopen, then single-solid worker build/torque. Geometry editing of the complete assembly remains pending."}


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument == "--interactive":
			interactive = true
		if argument.begins_with("--report="):
			report_path = argument.trim_prefix("--report=")
		if argument.begins_with("--frames="):
			frames = int(argument.trim_prefix("--frames="))
	if not report_path.is_absolute_path() or FileAccess.file_exists(report_path) or frames < 120 or frames > 3600 or DisplayServer.get_name() == "headless":
		push_error("Use a new absolute report path, graphical renderer and 120–3600 frames")
		quit(1)
		return
	var repository: String = ProjectSettings.globalize_path("res://").trim_suffix("/").get_base_dir().get_base_dir()
	fixture_path = repository.path_join("data/benchmarks/assembly-200/project.json")
	report["fixture_sha256"] = FileAccess.get_sha256(fixture_path)
	report["observer_sha256"] = FileAccess.get_sha256(ProjectSettings.globalize_path("res://benchmark_assembly.gd"))
	report["godot"] = Engine.get_version_info()
	report["desktop_pid"] = OS.get_process_id()
	report["os"] = OS.get_name()
	report["cpu"] = OS.get_processor_name()
	report["driver"] = Array(OS.get_video_adapter_driver_info())
	report["system_memory"] = OS.get_memory_info()
	report["generated_at_utc"] = Time.get_datetime_string_from_system(true)
	report["renderer"] = ProjectSettings.get_setting("rendering/renderer/rendering_method")
	report["vsync_mode"] = DisplayServer.window_get_vsync_mode()
	report["max_fps"] = Engine.max_fps
	var scene: PackedScene = load("res://main.tscn")
	desktop = scene.instantiate()
	get_root().add_child(desktop)
	if not await _wait():
		_finish(1, "Initial project failed")
		return
	_write_record(report_path.get_basename() + "-startup.json", {"desktop_pid": OS.get_process_id(), "ready_usec": Time.get_ticks_usec(), "utc": Time.get_datetime_string_from_system(true)})
	var start: int = Time.get_ticks_usec()
	desktop.call("_start_job", "validate", fixture_path)
	if not await _wait():
		_finish(1, "Assembly import failed")
		return
	await RenderingServer.frame_post_draw
	report["import_s"] = (Time.get_ticks_usec() - start) / 1000000.0
	var meshes: Array[Node] = desktop.get("aircraft").find_children("*", "MeshInstance3D", true, false)
	if meshes.size() != 200:
		_finish(1, "Expected 200 geometry-bearing parts")
		return
	var mesh_resources: Dictionary = {}
	var source_triangles: int = 0
	var generated_lods: int = 0
	for item in meshes:
		var mesh: MeshInstance3D = item as MeshInstance3D
		mesh_resources[mesh.mesh.get_instance_id()] = true
		source_triangles += mesh.mesh.surface_get_array_index_len(0) / 3
		generated_lods += int(mesh.get_meta("display_lod_count", 0))
	report["part_count"] = meshes.size()
	report["mesh_resource_count"] = mesh_resources.size()
	report["source_triangle_instances"] = source_triangles
	report["generated_lod_instances"] = generated_lods
	report["window_size"] = [get_root().size.x, get_root().size.y]
	report["viewport_size"] = [desktop.get("viewport").size.x, desktop.get("viewport").size.y]
	# Warm the complete scene before the timed camera/selection sequence.
	for index in range(90):
		await RenderingServer.frame_post_draw
	var samples: Array[float] = []
	var selection_samples: Array[float] = []
	var tree: Tree = desktop.get("components")
	var selected: TreeItem = tree.get_root().get_first_child()
	var initial_yaw: float = desktop.get("yaw")
	var focused_frames: int = 0
	if interactive:
		desktop.set("qualification_orbit_left", true)
		desktop.get("status_label").text = "QUALIFICATION: press Space, then drag the assembly with the left mouse button. Recording 1800 rendered frames."
		var input_deadline: int = Time.get_ticks_msec() + 180000
		while desktop.get("qualification_started_usec") == 0 and Time.get_ticks_msec() < input_deadline:
			await process_frame
		if desktop.get("qualification_started_usec") == 0:
			_finish(1, "No real input started the interactive recording")
			return
	var previous: int = Time.get_ticks_usec()
	var beginning: int = previous
	for index in range(frames):
		if not interactive:
			desktop.set("yaw", 0.7 + (Time.get_ticks_usec() - beginning) / 1000000.0 * 0.4)
			desktop.call("_update_camera")
		var selecting: bool = not interactive and index % 30 == 0
		if get_root().has_focus():
			focused_frames += 1
		var selection_start: int = Time.get_ticks_usec()
		if selecting:
			selected.select(0)
			desktop.call("_select_component")
			selected = selected.get_next() if selected.get_next() != null else tree.get_root().get_first_child()
		await RenderingServer.frame_post_draw
		var now: int = Time.get_ticks_usec()
		samples.append((now - previous) / 1000.0)
		if selecting:
			selection_samples.append((now - selection_start) / 1000.0)
		previous = now
	report["frame_intervals_ms"] = samples
	report["selection_to_frame_ms"] = selection_samples
	report["mean_fps"] = frames / ((previous - beginning) / 1000000.0)
	var sorted: Array[float] = samples.duplicate()
	sorted.sort()
	report["p50_ms"] = sorted[int(ceil(0.50 * frames)) - 1]
	report["p95_ms"] = sorted[int(ceil(0.95 * frames)) - 1]
	report["p99_ms"] = sorted[int(ceil(0.99 * frames)) - 1]
	report["max_ms"] = sorted[-1]
	report["p95_frame_equivalent_fps"] = 1000.0 / report["p95_ms"]
	report["p99_frame_equivalent_fps"] = 1000.0 / report["p99_ms"]
	report["interactive"] = interactive
	report["focused_frames"] = focused_frames
	report["recorded_frames"] = frames
	if interactive:
		report["input_events"] = desktop.get("qualification_events")
		report["yaw_change_rad"] = float(desktop.get("yaw")) - initial_yaw
		var drag_events: int = 0
		for event in report["input_events"]:
			if event["kind"] == "motion" and int(event["buttons"]) & MOUSE_BUTTON_MASK_LEFT:
				drag_events += 1
		report["drag_motion_events"] = drag_events
		report["interactive_input_verified"] = drag_events > 0 and absf(report["yaw_change_rad"]) > 0.01
	report["viewport_target_met"] = report["p95_ms"] <= report["frame_target_ms"] and report["mean_fps"] >= 30.0
	report["rendered_objects_monitor"] = Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME)
	report["draw_calls_monitor"] = Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)
	var saved: String = report_path.get_basename() + "-saved/project.json"
	DirAccess.make_dir_recursive_absolute(saved.get_base_dir())
	start = Time.get_ticks_usec()
	desktop.call("_save_project")
	desktop.get("file_dialog").file_selected.emit(saved)
	desktop.get("file_dialog").hide()
	if not await _wait():
		_finish(1, "Assembly save failed")
		return
	report["save_s"] = (Time.get_ticks_usec() - start) / 1000000.0
	start = Time.get_ticks_usec()
	desktop.call("_start_job", "validate", saved)
	if not await _wait() or desktop.get("project") != JSON.parse_string(FileAccess.get_file_as_string(fixture_path)):
		_finish(1, "Saved project changed or failed to reopen")
		return
	report["reopen_s"] = (Time.get_ticks_usec() - start) / 1000000.0
	# Exercise real CAD worker memory after measuring the assembly viewport.
	desktop.call("_rebuild_body")
	var cad_ok: bool = await _wait()
	if cad_ok:
		desktop.call("_run_cad_torque")
		cad_ok = await _wait()
		if cad_ok:
			cad_ok = desktop.get("result")["result"]["status"] == "completed"
	report["cad_worker_exercise_passed"] = cad_ok
	if not cad_ok:
		report["cad_worker_refusal"] = desktop.get("status_label").text
	# Measure a real active application job even when local CAD admission refuses.
	# Keep CAD and legacy results separate; one cannot stand in for the other.
	if cad_ok:
		desktop.get("torque_duration").value = 5.0
		desktop.get("torque_step").value = 0.001
		desktop.get("torque_z").value = 0.00001
		desktop.call("_run_cad_torque")
		report["active_cad_cancel"] = await _measure_cancel()
	desktop.call("_load_reference")
	if not await _wait():
		_finish(1, "Reference reload for cancellation failed")
		return
	var cancellation_project: Dictionary = desktop.get("project").duplicate(true)
	cancellation_project["experiment"]["parameters"] = {"duration_s": 30.0}
	desktop.call("_start_job", "validate", desktop.call("_write_payload", cancellation_project))
	if not await _wait():
		_finish(1, "Cancellation input validation failed")
		return
	desktop.call("_run_experiment")
	report["active_legacy_cancel"] = await _measure_cancel()
	var passed: bool = report["viewport_target_met"] and cad_ok and report["active_legacy_cancel"]["project_preserved"]
	if interactive:
		passed = passed and report["interactive_input_verified"] and focused_frames == frames
	_finish(0 if passed else 2)


func _measure_cancel() -> Dictionary:
	var deadline: int = Time.get_ticks_msec() + 20000
	while not FileAccess.file_exists(desktop.get("job_started")) and desktop.get("job_pid") > 0 and Time.get_ticks_msec() < deadline:
		await process_frame
	if not FileAccess.file_exists(desktop.get("job_started")):
		return {"failure": "No active worker receipt"}
	await create_timer(0.3).timeout
	if desktop.get("job_pid") <= 0 or FileAccess.file_exists(desktop.get("job_completion")):
		return {"failure": "Job completed before active cancellation"}
	var started: Variant = JSON.parse_string(FileAccess.get_file_as_string(desktop.get("job_started")))
	var frozen: String = desktop.get("project_document_json")
	# External observer sees this marker while sampling the actual process tree.
	var action_usec: int = Time.get_ticks_usec()
	_write_record(report_path.get_basename() + "-cancel-" + ("cad" if desktop.get("job_uses_reusable") else "legacy") + ".json",
		{"action_usec": action_usec, "worker_pid": started["worker_pid"], "desktop_pid": OS.get_process_id(), "completion": desktop.get("job_completion")})
	desktop.call("_cancel_job")
	return {"worker_pid": started["worker_pid"], "action_usec": action_usec,
		"application_cancel_return_s": (Time.get_ticks_usec() - action_usec) / 1000000.0,
		"project_preserved": desktop.get("project_document_json") == frozen,
		"completion_published": FileAccess.file_exists(desktop.get("job_completion"))}


func _write_record(path: String, data: Dictionary) -> void:
	var output: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	output.store_string(JSON.stringify(data, "\t", true, true))
	output.close()


func _wait() -> bool:
	var deadline: int = Time.get_ticks_msec() + 95000
	while desktop.get("job_pid") > 0 and Time.get_ticks_msec() < deadline:
		await process_frame
	return desktop.get("job_pid") == -1 and desktop.call("_completed_output") and not FileAccess.file_exists(desktop.get("job_error"))


func _finish(code: int, failure: String = "") -> void:
	if not failure.is_empty():
		report["failure"] = failure
		report["desktop_status"] = desktop.get("status_label").text
	if desktop != null and desktop.get("cad_worker") != null:
		report["worker_stopped"] = desktop.get("cad_worker").stop()
		if not report["worker_stopped"]:
			code = 1
	var file: FileAccess = FileAccess.open(report_path, FileAccess.WRITE)
	file.store_string(JSON.stringify(report, "\t"))
	file.close()
	print("Assembly benchmark: " + report_path)
	quit(code)
