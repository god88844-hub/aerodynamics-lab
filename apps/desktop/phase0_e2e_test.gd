extends SceneTree


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	if not ClassDB.class_exists("LabEngineering"):
		push_error("Native LabEngineering GDExtension is unavailable")
		quit(1)
		return

	var desktop_scene: PackedScene = load("res://main.tscn")
	var desktop: Control = desktop_scene.instantiate()
	get_root().add_child(desktop)

	var deadline: int = Time.get_ticks_msec() + 30000
	while desktop.get("project").is_empty() and Time.get_ticks_msec() < deadline:
		await process_frame
	if desktop.get("project").is_empty():
		push_error("Desktop failed to load reference project on startup | status=%s | job_pid=%s | job_err=%s | repo=%s | py=%s" % [
			str(desktop.get("status_label").text), str(desktop.get("job_pid")), str(desktop.get("job_error")), str(desktop.call("repository_root")), str(desktop.call("python_command"))])
		quit(2)
		return

	# 1. Native C++20 6-DoF RK4 Kernel
	desktop.call("_run_native_cpp_rk4")
	var native_res: Dictionary = desktop.get("result")
	if native_res.get("experiment_kind") != "native_cpp_rk4_1":
		push_error("Native C++20 RK4 execution failed: " + str(desktop.get("status_label").text))
		quit(3)
		return
	print("[PASS] C++20 Native RK4 kernel executed in-process")

	# 2. Visual Profiles & Touch Gestures (Tier 0 Mobile -> Forward+ Ultra)
	for _i in range(5):
		desktop.call("_cycle_visual_profile")
	desktop.call("_toggle_lighting_mode")
	var drag := InputEventScreenDrag.new()
	drag.relative = Vector2(24.0, 10.0)
	desktop.call("_viewport_input", drag)
	var pinch := InputEventMagnifyGesture.new()
	pinch.factor = 1.15
	desktop.call("_viewport_input", pinch)
	print("[PASS] Visual tier cycling, HDRI lighting toggle, and mobile touch/pinch navigation")

	# 3. Layout / BOM -> 6-rotor hexacopter 3D mesh check
	desktop.get("layout_fields")["n_rotors"].value = 6
	desktop.call("_apply_layout_bom")
	if not await _wait_job(desktop):
		quit(4)
		return
	var hex_meshes: Array[Node] = desktop.get("aircraft").find_children("*", "MeshInstance3D", true, false)
	if hex_meshes.size() < 7:
		push_error("Layout BOM did not render 6 rotor meshes + hub (got %d)" % hex_meshes.size())
		quit(5)
		return
	print("[PASS] Layout/BOM 6-rotor CFRP hexacopter + 3D rotor disc update")

	# 4. Clearance Check, Test Ground, Mission Authoring & Authoritative RK4 Sim
	desktop.call("_run_clearance_check")
	if not await _wait_job(desktop) or not "CLEAR" in str(desktop.get("status_label").text):
		push_error("Clearance check failed: " + str(desktop.get("status_label").text))
		quit(6)
		return

	desktop.get("ground_fields")["wind_x"].value = 2.5
	desktop.call("_apply_test_ground")
	if not await _wait_job(desktop):
		quit(7)
		return

	desktop.get("mission_fields")["hover_alt_m"].value = 4.0
	desktop.get("mission_fields")["hover_s"].value = 0.5
	desktop.call("_run_authored_mission")
	if not await _wait_job(desktop):
		quit(8)
		return

	desktop.call("_run_authoritative_sim")
	if not await _wait_job(desktop):
		quit(9)
		return
	if desktop.get("result").get("result", {}).get("status") != "completed":
		push_error("Authoritative simulation did not complete cleanly")
		quit(10)
		return
	desktop.call("_step_replay")
	desktop.call("_open_twin_dialog")
	desktop.get("twin_dialog").hide()
	desktop.call("_open_fidelity_dialog")
	desktop.get("fidelity_dialog").hide()
	print("[PASS] Clearance, TestGround, Mission Authoring, Authoritative Sim, Twin %, Fidelity dialogs")

	# 5. Protocols, Guided Experiment, Bounded Sweep & Help Dialog
	desktop.call("_open_protocol_catalog")
	if not await _wait_job(desktop):
		quit(11)
		return
	desktop.get("protocol_dialog").hide()

	desktop.call("_run_guided_experiment")
	if not await _wait_job(desktop):
		quit(12)
		return

	desktop.call("_run_bounded_sweep")
	if not await _wait_job(desktop):
		quit(13)
		return

	desktop.call("_open_help_dialog")
	desktop.get("help_dialog").hide()
	desktop.call("_on_ribbon_tab_changed", 3)
	desktop.call("_toggle_flow_overlay")
	desktop.call("_toggle_stress_map")
	desktop.call("_snap_view", 0.72, 0.48)
	desktop.call("_on_ribbon_tab_changed", 2)
	desktop.call("_toggle_blueprint_balloons")
	desktop.call("_export_active_drawing")
	if not await _wait_job(desktop):
		quit(27)
		return
	desktop.call("_on_ribbon_tab_changed", 0)
	print("[PASS] Protocols, Guided Experiment, Sweep, Flow Streamlines, Stress Colormap & 2D Blueprint Export")

	# 6. Multi-Family Simulation Workflows & 3D Viewport Animations
	desktop.call("_run_fixed_wing_vlm")
	if not await _wait_job(desktop):
		quit(14)
		return
	desktop.call("_seek", 0.5)
	if desktop.get("aircraft").get_child_count() < 2:
		push_error("Fixed-wing 3D geometry not built")
		quit(15)
		return

	desktop.call("_run_vtol_transition")
	if not await _wait_job(desktop):
		quit(16)
		return
	desktop.call("_seek", float(desktop.get("timeline").max_value))
	var nac_node: Node = desktop.get("aircraft").find_child("nacelle_left", true, false)
	if nac_node == null:
		push_error("VTOL tilting nacelle mesh missing")
		quit(17)
		return

	desktop.call("_run_adverse_weather")
	if not await _wait_job(desktop):
		quit(18)
		return

	desktop.call("_run_helicopter_autorotation")
	if not await _wait_job(desktop):
		quit(25)
		return
	desktop.call("_seek", float(desktop.get("timeline").max_value) * 0.5)

	desktop.call("_run_sitl_mission")
	if not await _wait_job(desktop):
		quit(26)
		return

	desktop.call("_run_swarm_sim")
	if not await _wait_job(desktop):
		quit(19)
		return
	desktop.call("_seek", 1.0)
	if desktop.get("aircraft").find_child("swarm_agent_0", true, false) == null:
		push_error("Swarm 3D agents missing after swarm-sim")
		quit(20)
		return
	print("[PASS] Fixed-Wing 3D, VTOL Tilting Nacelles, Adverse Weather & Animated Swarm Sim")

	# 7. Project Save, Versioning & Recovery
	var ver_dir: String = ProjectSettings.globalize_path("user://e2e-ver-%s" % Time.get_ticks_usec())
	DirAccess.make_dir_recursive_absolute(ver_dir)
	var ver_proj: String = ver_dir.path_join("project.json")
	desktop.set("current_project_path", ver_proj)
	desktop.call("_start_job", "package", desktop.call("_write_job_input"), ver_proj)
	if not await _wait_job(desktop):
		quit(21)
		return
	desktop.call("_save_version")
	if not await _wait_job(desktop):
		quit(22)
		return
	desktop.call("_open_versions_dialog")
	if not await _wait_job(desktop):
		quit(23)
		return
	desktop.get("versions_dialog").hide()
	desktop.call("_recover_last_valid")
	if not await _wait_job(desktop):
		quit(24)
		return
	print("[PASS] Project save, versioning & last-valid recovery")
	print("=== ALL PHASE 0 DESKTOP END-TO-END WORKFLOWS PASSED ===")
	quit(0)


func _wait_job(desktop: Control) -> bool:
	var deadline: int = Time.get_ticks_msec() + 45000
	while desktop.get("job_pid") > 0 and Time.get_ticks_msec() < deadline:
		await process_frame
	if desktop.get("job_pid") > 0 or FileAccess.file_exists(desktop.get("job_error")) or not desktop.call("_completed_output"):
		push_error("Desktop worker failed (%s): %s" % [str(desktop.get("job_action")), str(desktop.get("status_label").text)])
		return false
	return true
