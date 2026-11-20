extends SceneTree


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	if not ClassDB.class_exists("LabEngineering"):
		push_error("Native engineering extension is unavailable")
		quit(1)
		return
	var core: RefCounted = ClassDB.instantiate("LabEngineering")
	var desktop_scene: PackedScene = load("res://main.tscn")
	var desktop: Control = desktop_scene.instantiate()
	get_root().add_child(desktop)
	var deadline: int = Time.get_ticks_msec() + 30000
	while desktop.get("project").is_empty() and Time.get_ticks_msec() < deadline:
		await process_frame
	if desktop.get("project").is_empty():
		push_error("Desktop did not load its project through the Python worker")
		quit(7)
		return
	var component_tree: Tree = desktop.get("components")
	component_tree.get_root().get_first_child().select(0)
	desktop.call("_select_component")
	desktop.get("project")["experiment"]["parameters"] = {"duration_s": 30.0}
	desktop.call("_run_experiment")
	var cancelled_pid: int = desktop.get("job_pid")
	var startup_deadline: int = Time.get_ticks_msec() + 20000
	while not FileAccess.file_exists(desktop.get("job_started")) and Time.get_ticks_msec() < startup_deadline:
		await process_frame
	var started: Variant = JSON.parse_string(FileAccess.get_file_as_string(desktop.get("job_started")))
	if not started is Dictionary or not _worker_alive(int(started.get("worker_pid", -1))):
		push_error("Cancellation check did not reach an active Python worker")
		quit(25)
		return
	var actual_worker_pid: int = int(started["worker_pid"])
	desktop.call("_cancel_job")
	if desktop.get("job_pid") != -1 or desktop.get("project").is_empty():
		push_error("Cancelling a worker lost the current project")
		quit(8)
		return
	var cancel_deadline: int = Time.get_ticks_msec() + 5000
	while (OS.is_process_running(cancelled_pid) or _worker_alive(actual_worker_pid)) and Time.get_ticks_msec() < cancel_deadline:
		await process_frame
	if OS.is_process_running(cancelled_pid) or _worker_alive(actual_worker_pid):
		push_error("Cancelled launcher or actual Python worker is still running")
		quit(9)
		return
	print("Cancellation verified for launcher %d and actual worker %d" % [cancelled_pid, actual_worker_pid])
	var properties: Dictionary = core.mass_properties([
		{"mass_kg": 2.0, "position_m": [0.0, 0.0, -1.0]},
		{"mass_kg": 1.0, "position_m": [3.0, 0.0, 2.0]}])
	if not properties.get("ok", false) or properties["center_of_mass_m"] != [1.0, 0.0, 0.0]:
		push_error("Native engineering result disagrees with the analytical reference")
		quit(2)
		return
	if core.mass_properties([{"mass_kg": -1.0, "position_m": [0, 0, 0]}]).get("ok", true):
		push_error("Invalid native mass was accepted")
		quit(3)
		return
	var root: String = ProjectSettings.globalize_path("res://").trim_suffix("/").get_base_dir().get_base_dir()
	var python: String = OS.get_environment("LAB_PYTHON")
	if python.is_empty():
		python = "python"
	var input: String = root.path_join("data/designs/quad_mn3508_6s.json")
	var project_path: String = ProjectSettings.globalize_path("user://smoke-project.json")
	var checked_path: String = ProjectSettings.globalize_path("user://smoke-checked.json")
	var run_path: String = ProjectSettings.globalize_path("user://smoke-run.json")
	var commands: Array = [
		["import-legacy", input, project_path],
		["validate", project_path, checked_path],
		["run", checked_path, run_path]]
	for command in commands:
		var arguments: PackedStringArray = [root.path_join("scripts/lab_project.py")]
		arguments.append_array(PackedStringArray(command))
		var output: Array = []
		var code: int = OS.execute(python, arguments, output, true, false)
		if code != 0:
			push_error("Project worker failed: " + str(output))
			quit(4)
			return
	var run: Variant = JSON.parse_string(FileAccess.get_file_as_string(run_path))
	if not run is Dictionary or run.get("result", {}).get("status") != "completed":
		push_error("Reference simulation did not complete")
		quit(5)
		return
	var project: Dictionary = run["project"]
	var expected: float = 0.0
	for part in project["vehicle"]["snapshot"]["parts"]:
		expected += float(part["mass_kg"])
	var combined: Dictionary = core.mass_properties(project["vehicle"]["snapshot"]["parts"])
	if not combined["ok"] or not is_equal_approx(combined["mass_kg"], expected):
		push_error("Native mass differs from the imported project")
		quit(6)
		return
	if OS.get_environment("LAB_TEST_CAD") == "1":
		desktop.call("_start_job", "build-blade", root.path_join("data/cad/blade-example.json"))
		if not await _wait_for_job(desktop):
			quit(10)
			return
		var reusable_pid: int = int(JSON.parse_string(FileAccess.get_file_as_string(desktop.get("job_started")))["worker_pid"])
		var reusable_session: String = desktop.get("cad_worker").get("session_id")
		var cad_project: Dictionary = desktop.get("project")
		var meshes: Array[Node] = desktop.get("aircraft").find_children("*", "MeshInstance3D", true, false)
		if cad_project["vehicle"]["format"] != "assembly_1" or meshes.size() != 1:
			push_error("CAD worker did not load an actual blade mesh")
			quit(11)
			return
		var blade: MeshInstance3D = meshes[0] as MeshInstance3D
		if blade.mesh.get_surface_count() != 1 or blade.get_meta("display_lod_count", 0) < 1:
			push_error("CAD display has no generated automatic LOD")
			quit(12)
			return
		var package_dir: String = ProjectSettings.globalize_path("user://package-%s" % Time.get_ticks_usec())
		DirAccess.make_dir_recursive_absolute(package_dir)
		var packaged: String = package_dir.path_join("project.json")
		desktop.call("_start_job", "package", desktop.call("_write_job_input"), packaged)
		if not await _wait_for_job(desktop) or desktop.get("project_asset_root") != package_dir:
			push_error("CAD project could not be saved with its geometry assets")
			quit(13)
			return
		desktop.call("_start_job", "validate", packaged)
		if not await _wait_for_job(desktop):
			quit(14)
			return
		var cad_input: String = desktop.call("_write_job_input")
		var refused: Array = []
		var refused_code: int = OS.execute(python, PackedStringArray([
			root.path_join("scripts/lab_project.py"), "run", cad_input,
			package_dir.path_join("unsupported-run.json")]), refused, true, false)
		if refused_code == 0 or FileAccess.file_exists(package_dir.path_join("unsupported-run.json")):
			push_error("CAD shape was incorrectly accepted as a qualified flight model")
			quit(15)
			return
		# Exercise the actual editor controls, rebuild, torque worker and CoG replay.
		desktop.call("_open_body_editor")
		desktop.get("body_dialog").hide()
		desktop.call("_rebuild_body")
		if not await _wait_for_job(desktop):
			quit(16)
			return
		desktop.call("_run_cad_torque")
		if not await _wait_for_job(desktop):
			quit(17)
			return
		var first_run: Dictionary = desktop.get("result")
		if first_run.get("experiment_kind") != "cad_torque_1" or first_run["result"]["status"] != "completed":
			push_error("Desktop did not run the exact geometry through the rigid-body backend")
			quit(18)
			return
		var first_speed: float = first_run["result"]["telemetry"]["omega_body_rad_s"][-1][2]
		var first_saved: String = package_dir.path_join("body-v1.json")
		desktop.call("_start_job", "package", desktop.call("_write_job_input"), first_saved)
		if not await _wait_for_job(desktop) or desktop.get("result").is_empty():
			push_error("Saving the project lost the current experiment preview")
			quit(26)
			return
		desktop.call("_seek", 1.0)
		var cad_aircraft: Node3D = desktop.get("aircraft")
		var center: Vector3 = desktop.call("_scene_position", first_run["mass_properties"]["center_of_mass_m"])
		if cad_aircraft.to_global(center).length() > 1e-5:
			push_error("CAD replay rotated the body around its datum instead of its CoG")
			quit(19)
			return
		desktop.get("body_fields")["width_m"].value = 0.3
		desktop.call("_rebuild_body")
		if not await _wait_for_job(desktop):
			quit(20)
			return
		desktop.call("_run_cad_torque")
		if not await _wait_for_job(desktop):
			quit(21)
			return
		var edited_run: Dictionary = desktop.get("result")
		if edited_run["result"]["telemetry"]["omega_body_rad_s"][-1][2] >= first_speed:
			push_error("Widening the body did not reduce spin-up under the same torque")
			quit(22)
			return
		var second_saved: String = package_dir.path_join("body-v2.json")
		desktop.call("_start_job", "package", desktop.call("_write_job_input"), second_saved)
		if not await _wait_for_job(desktop):
			push_error("Edited geometry could not be saved beside the prior project version")
			quit(27)
			return
		desktop.call("_start_job", "validate", first_saved)
		if not await _wait_for_job(desktop):
			quit(28)
			return
		desktop.call("_run_cad_torque")
		if not await _wait_for_job(desktop) or not is_equal_approx(desktop.get("result")["result"]["telemetry"]["omega_body_rad_s"][-1][2], first_speed):
			push_error("Saving an edited version changed the earlier version's physical inputs")
			quit(29)
			return
		desktop.get("density_enabled").button_pressed = false
		desktop.call("_rebuild_body")
		if not await _wait_for_job(desktop):
			quit(23)
			return
		desktop.call("_run_cad_torque")
		if not await _wait_for_job(desktop) or desktop.get("result")["result"]["status"] != "inconclusive":
			push_error("Unknown material density was incorrectly treated as a known rigid body")
			quit(24)
			return
		var reused_pid: int = int(JSON.parse_string(FileAccess.get_file_as_string(desktop.get("job_started")))["worker_pid"])
		if reused_pid != reusable_pid or desktop.get("cad_worker").get("session_id") != reusable_session:
			push_error("CAD editing and analysis did not reuse one isolated engine")
			quit(30)
			return
		# Cancel an active numerical job, then recover with a newly loaded engine.
		desktop.get("density_enabled").button_pressed = true
		desktop.call("_rebuild_body")
		if not await _wait_for_job(desktop):
			quit(31)
			return
		var retained: Dictionary = desktop.get("project").duplicate(true)
		desktop.get("torque_duration").value = 5.0
		desktop.get("torque_step").value = 0.001
		desktop.get("torque_z").value = 0.00001
		desktop.call("_run_cad_torque")
		var active_deadline: int = Time.get_ticks_msec() + 20000
		while not FileAccess.file_exists(desktop.get("job_started")) and Time.get_ticks_msec() < active_deadline:
			await process_frame
		if not _worker_alive(reusable_pid):
			push_error("Reusable-engine cancellation did not reach an active worker")
			quit(32)
			return
		var reusable_launcher: int = desktop.get("job_pid")
		desktop.call("_cancel_job")
		var stopped_deadline: int = Time.get_ticks_msec() + 5000
		while (OS.is_process_running(reusable_launcher) or _worker_alive(reusable_pid)) and Time.get_ticks_msec() < stopped_deadline:
			await process_frame
		if desktop.get("job_pid") != -1 or _worker_alive(reusable_pid) or desktop.get("project") != retained:
			push_error("Reusable cancellation left a running engine or lost the current project")
			quit(33)
			return
		desktop.get("torque_duration").value = 1.0
		desktop.get("torque_step").value = 0.005
		desktop.get("torque_z").value = 0.001
		desktop.call("_run_cad_torque")
		if not await _wait_for_job(desktop) or desktop.get("cad_worker").get("session_id") == reusable_session:
			push_error("CAD worker did not recover into a new session")
			quit(34)
			return
		if desktop.get("result")["result"]["status"] != "completed":
			push_error("Recovered CAD worker did not produce a completed numerical experiment")
			quit(35)
			return
		print("CAD engine reuse, active cancellation and fresh-session recovery checks passed")
	print("Desktop/native/worker smoke checks passed. Physical validation remains pending.")
	quit(0)


func _wait_for_job(desktop: Control) -> bool:
	var deadline: int = Time.get_ticks_msec() + 60000
	while desktop.get("job_pid") > 0 and Time.get_ticks_msec() < deadline:
		await process_frame
	if desktop.get("job_pid") > 0 or FileAccess.file_exists(desktop.get("job_error")) or not desktop.call("_completed_output"):
		push_error("CAD integration job failed: " + str(desktop.get("status_label").text))
		return false
	# An old saved document cannot stand in for a completion receipt from this job.
	var receipt_path: String = desktop.get("job_completion")
	desktop.set("job_completion", receipt_path + "-missing")
	var accepted_without_receipt: bool = desktop.call("_completed_output")
	desktop.set("job_completion", receipt_path)
	if accepted_without_receipt:
		push_error("Desktop accepted an existing output without this job's completion receipt")
		return false
	if desktop.get("job_uses_reusable"):
		var client: RefCounted = desktop.get("cad_worker")
		var original: Dictionary = client.get("context").duplicate(true)
		client.get("context")["request_sha256"] = "0".repeat(64)
		var accepted_wrong_request: bool = desktop.call("_completed_output")
		client.set("context", original)
		if accepted_wrong_request:
			push_error("Desktop accepted a completion receipt for a different CAD request")
			return false
	return true


func _worker_alive(pid: int) -> bool:
	if pid <= 0:
		return false
	if OS.get_name() != "Windows":
		var posix_output: Array = []
		return OS.execute("kill", ["-0", str(pid)], posix_output, true, false) == 0
	# Godot's Windows API tracks only processes it created directly. The venv
	# interpreter is a descendant, so inspect it through the OS process inventory.
	var output: Array = []
	var code: int = OS.execute("tasklist", ["/FI", "PID eq %d" % pid, "/FO", "CSV", "/NH"], output, true, false)
	if code != 0:
		push_error("Could not inspect the actual worker process")
		return true  # never pass cancellation on an unavailable process inventory
	return not output.is_empty() and str(output[0]).contains('"%d"' % pid)
