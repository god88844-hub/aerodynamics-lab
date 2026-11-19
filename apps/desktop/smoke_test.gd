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
	desktop.call("_run_experiment")
	var cancelled_pid: int = desktop.get("job_pid")
	desktop.call("_cancel_job")
	if desktop.get("job_pid") != -1 or desktop.get("project").is_empty():
		push_error("Cancelling a worker lost the current project")
		quit(8)
		return
	var cancel_deadline: int = Time.get_ticks_msec() + 5000
	while cancelled_pid > 0 and OS.is_process_running(cancelled_pid) and Time.get_ticks_msec() < cancel_deadline:
		await process_frame
	if cancelled_pid > 0 and OS.is_process_running(cancelled_pid):
		push_error("Cancelled worker is still running")
		quit(9)
		return
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
	print("Desktop/native/worker smoke checks passed. Physical validation remains pending.")
	quit(0)
