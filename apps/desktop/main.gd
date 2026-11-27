extends Control

var project: Dictionary = {}
var project_document_json: String = ""
var project_document_view: Dictionary = {}
var result: Dictionary = {}
var engineering: RefCounted
var components: Tree
var status_label: Label
var project_label: Label
var metrics_label: Label
var timeline: HSlider
var viewport: SubViewport
var world: Node3D
var aircraft: Node3D
var camera: Camera3D
var file_dialog: FileDialog
var job_pid: int = -1
var job_action: String = ""
var job_output: String = ""
var job_error: String = ""
var job_completion: String = ""
var job_started: String = ""
var job_started_ms: int = 0
var playing: bool = false
var replay_time: float = 0.0
var yaw: float = 0.7
var elevation: float = 0.5
var distance_m: float = 1.4
var capture_path: String = ""
var capture_view: String = ""
var capture_frames: int = 0
var project_asset_root: String = ""
var job_asset_root: String = ""
var scope_label: Label
var view_center: Vector3 = Vector3.ZERO
var body_dialog: AcceptDialog
var body_fields: Dictionary = {}
var density_enabled: CheckButton
var torque_z: SpinBox
var torque_duration: SpinBox
var torque_step: SpinBox
var cad_worker: RefCounted
var job_uses_reusable: bool = false
var last_worker_check_ms: int = 0
var limits_dialog: AcceptDialog
var limits_fields: Dictionary = {}
var limits_status: Label
var new_project_dialog: AcceptDialog
var new_project_name: LineEdit
var new_project_family: OptionButton
var new_project_template: OptionButton
var versions_dialog: AcceptDialog
var versions_tree: Tree
var versions_status: Label
var visual_profile_button: Button
var visual_profile: String = "auto"
var lighting_mode: String = "studio"
var lighting_button: Button
var cad_material_select: OptionButton
var cad_material_preset: String = "anodized_blue"
var blade_dialog: AcceptDialog
var blade_fields: Dictionary = {}
var blade_density_enabled: CheckButton
var transform_dialog: AcceptDialog
var transform_fields: Dictionary = {}
var undo_stack: Array = []
var redo_stack: Array = []
var layout_dialog: AcceptDialog
var layout_fields: Dictionary = {}
var layout_material_select: OptionButton
var layout_motor_select: OptionButton
var ground_dialog: AcceptDialog
var ground_fields: Dictionary = {}
var ground_rain_check: CheckButton
var mission_dialog: AcceptDialog
var mission_fields: Dictionary = {}
var twin_dialog: AcceptDialog
var twin_report_label: Label
var fidelity_dialog: AcceptDialog
var fidelity_report_label: Label
var protocol_dialog: AcceptDialog
var protocol_report_label: Label
var learning_dialog: AcceptDialog
var hypothesis_input: LineEdit
var learning_fields: Dictionary = {}
var sweep_dialog: AcceptDialog
var sweep_fields: Dictionary = {}
var help_dialog: AcceptDialog
var playback_state: String = "IDLE"
var world_env: WorldEnvironment
var ground_props: Node3D
var grid_group: Node3D
var overlay_group: Node3D
var key_light: DirectionalLight3D
var fill_light: DirectionalLight3D
var ribbon_tabs: TabBar
var ribbon_panels: Array[HFlowContainer] = []
var viewport_container: SubViewportContainer
var blueprint_canvas: WorkbenchControls.BlueprintSheetCanvas
var telemetry_plot: WorkbenchControls.TelemetryPlotCanvas
var colorbar_legend: WorkbenchControls.ColorbarLegend
var viewport_hud_label: Label
var show_inertia_rings: bool = true
var show_flow_overlay: bool = false
var show_stress_map: bool = false
var hud_timer: float = 0.0
var last_rotor_scene_positions: Array = []
var current_project_path: String = ""
var last_valid_project_path: String = ""
var qualification_orbit_left: bool = false
var qualification_started_usec: int = 0
var qualification_events: Array = []


func repository_root() -> String:
	return ProjectSettings.globalize_path("res://").trim_suffix("/").get_base_dir().get_base_dir()


func python_command() -> String:
	var configured: String = OS.get_environment("LAB_PYTHON")
	if not configured.is_empty():
		return configured
	var win_venv: String = repository_root().path_join(".venv/Scripts/python.exe")
	if FileAccess.file_exists(win_venv):
		return win_venv
	var posix_venv: String = repository_root().path_join(".venv/bin/python")
	if FileAccess.file_exists(posix_venv):
		return posix_venv
	return "python"


func _ready() -> void:
	_build_interface()
	if not ClassDB.class_exists("LabEngineering"):
		status_label.text = "Build the native engineering extension before loading a project."
		return
	engineering = ClassDB.instantiate("LabEngineering")
	var cad_python: String = OS.get_environment("LAB_CAD_PYTHON")
	var worker_script: GDScript = load("res://cad_worker.gd")
	cad_worker = worker_script.new(repository_root(), cad_python if not cad_python.is_empty() else python_command())
	var initial_project: String = ""
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--capture="):
			capture_path = argument.trim_prefix("--capture=")
		if argument.begins_with("--demo-view="):
			capture_view = argument.trim_prefix("--demo-view=")
		if argument.begins_with("--open-project="):
			initial_project = argument.trim_prefix("--open-project=")
		if argument.begins_with("--visual-tier="):
			visual_profile = argument.trim_prefix("--visual-tier=")
	_apply_visual_profile()
	if initial_project.is_empty():
		_load_reference()
	else:
		current_project_path = initial_project
		_start_job("validate", initial_project)


func _add_button(parent: Node, title: String, action: Callable) -> void:
	var button: Button = Button.new()
	button.text = title
	button.pressed.connect(action)
	parent.add_child(button)


func _build_interface() -> void:
	var margin: MarginContainer = MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 10)
	add_child(margin)
	var layout: VBoxContainer = VBoxContainer.new()
	layout.add_theme_constant_override("separation", 6)
	margin.add_child(layout)
	# --- Clean Fusion 360 / Onshape Top Workbench Header Bar ---
	var header: HBoxContainer = HBoxContainer.new()
	header.add_theme_constant_override("separation", 10)
	layout.add_child(header)
	var title: Label = Label.new()
	title.text = "AERODYNAMICS LAB"
	title.add_theme_font_size_override("font_size", 18)
	title.add_theme_color_override("font_color", Color(0.45, 0.80, 1.0))
	header.add_child(title)
	project_label = Label.new()
	project_label.text = "Standalone CAD & 6-DoF Flight Workbench"
	project_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(project_label)
	cad_material_select = OptionButton.new()
	cad_material_select.add_item("Mat: Anodized Blue")
	cad_material_select.add_item("Mat: Alu 6061-T6")
	cad_material_select.add_item("Mat: CFRP Quasi-Iso")
	cad_material_select.add_item("Mat: PA12 Nylon")
	cad_material_select.item_selected.connect(_on_cad_material_selected)
	header.add_child(cad_material_select)
	lighting_button = Button.new()
	lighting_button.text = "Light: Studio"
	lighting_button.pressed.connect(_toggle_lighting_mode)
	header.add_child(lighting_button)
	visual_profile_button = Button.new()
	visual_profile_button.text = "Visual: Auto"
	visual_profile_button.pressed.connect(_cycle_visual_profile)
	header.add_child(visual_profile_button)
	_add_button(header, "? Help", _open_help_dialog)
	# --- Contextual Workspace Ribbon Tabs (NO button wall clutter!) ---
	ribbon_tabs = TabBar.new()
	for tab_title in ["Design CAD", "Assembly & BOM", "2D Blueprint", "Aero & Flow", "Flight & Swarm", "Verify & Env"]:
		ribbon_tabs.add_tab(tab_title)
	ribbon_tabs.tab_changed.connect(_on_ribbon_tab_changed)
	layout.add_child(ribbon_tabs)
	var ribbon_box := PanelContainer.new()
	layout.add_child(ribbon_box)
	var ribbon_holder := MarginContainer.new()
	for s in ["left", "right", "top", "bottom"]:
		ribbon_holder.add_theme_constant_override("margin_" + s, 6)
	ribbon_box.add_child(ribbon_holder)
	ribbon_panels.clear()
	for idx in range(6):
		var rp := HFlowContainer.new()
		rp.visible = (idx == 0)
		ribbon_panels.append(rp)
		ribbon_holder.add_child(rp)
	# Tab 0: Design CAD
	_add_button(ribbon_panels[0], "New Project", _open_new_project_dialog)
	_add_button(ribbon_panels[0], "Import Design", _import_design)
	_add_button(ribbon_panels[0], "Load Reference", _load_reference)
	_add_button(ribbon_panels[0], "Open Project", _open_project)
	_add_button(ribbon_panels[0], "Build Blade", func():
		_start_job("build-blade", repository_root().path_join("data/cad/blade-example.json")))
	_add_button(ribbon_panels[0], "Blade Recipe", _open_blade_recipe)
	_add_button(ribbon_panels[0], "Edit Blade", _open_blade_editor)
	_add_button(ribbon_panels[0], "Edit Body", _open_body_editor)
	_add_button(ribbon_panels[0], "Transform", _open_transform_editor)
	_add_button(ribbon_panels[0], "Undo", _undo_edit)
	_add_button(ribbon_panels[0], "Redo", _redo_edit)
	# Tab 1: Assembly & BOM
	_add_button(ribbon_panels[1], "Layout / BOM", _open_layout_editor)
	_add_button(ribbon_panels[1], "Rotor Clearance", _run_clearance_check)
	_add_button(ribbon_panels[1], "Toggle CoG & Inertia Rings", _toggle_inertia_rings)
	_add_button(ribbon_panels[1], "Save Project", _save_project)
	_add_button(ribbon_panels[1], "Save Version", _save_version)
	_add_button(ribbon_panels[1], "Versions / Recover", _open_versions_dialog)
	# Tab 2: 2D Blueprint
	_add_button(ribbon_panels[2], "Toggle 2D Sheet / 3D", func(): _toggle_blueprint_view(true))
	_add_button(ribbon_panels[2], "Toggle Balloons", _toggle_blueprint_balloons)
	_add_button(ribbon_panels[2], "Export DXF + SVG", _export_active_drawing)
	# Tab 3: Aero & Flow
	_add_button(ribbon_panels[3], "Fixed-Wing VLM", _run_fixed_wing_vlm)
	_add_button(ribbon_panels[3], "Toggle Airflow Streamlines", _toggle_flow_overlay)
	_add_button(ribbon_panels[3], "Toggle Wing Stress Map", _toggle_stress_map)
	_add_button(ribbon_panels[3], "Adverse Weather", _run_adverse_weather)
	_add_button(ribbon_panels[3], "Bounded Sweep", _open_sweep_dialog)
	# Tab 4: Flight & Swarm
	_add_button(ribbon_panels[4], "Test Ground", _open_test_ground_dialog)
	_add_button(ribbon_panels[4], "Mission / Seeds", _open_mission_dialog)
	_add_button(ribbon_panels[4], "Run authoritative", _run_authoritative_sim)
	_add_button(ribbon_panels[4], "Run C++ Kernel", _run_native_cpp_rk4)
	_add_button(ribbon_panels[4], "VTOL Transition", _run_vtol_transition)
	_add_button(ribbon_panels[4], "Heli Autorotation", _run_helicopter_autorotation)
	_add_button(ribbon_panels[4], "Swarm Sim", _run_swarm_sim)
	_add_button(ribbon_panels[4], "SITL Autonomy", _run_sitl_mission)
	_add_button(ribbon_panels[4], "Applied Torque", _run_cad_torque)
	_add_button(ribbon_panels[4], "Reference Flight", _run_experiment)
	# Tab 5: Verify & Env
	_add_button(ribbon_panels[5], "Twin % / Compare", _open_twin_dialog)
	_add_button(ribbon_panels[5], "Fidelity / Budgets", _open_fidelity_dialog)
	_add_button(ribbon_panels[5], "Validation Protocols", _open_protocol_catalog)
	_add_button(ribbon_panels[5], "Learn / Invent", _open_learning_dialog)
	_add_button(ribbon_panels[5], "Worker Limits", _open_limits)
	_add_button(ribbon_panels[5], "Cancel Job", _cancel_job)
	help_dialog = AcceptDialog.new()
	help_dialog.title = "Physics Equations, Units Contract & Accessibility Shortcuts"
	var help_lbl: Label = Label.new()
	help_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	help_lbl.custom_minimum_size = Vector2(540, 240)
	help_lbl.text = (
		"CONVENTIONS: Right-handed Z-up body/world (m, kg, s, N, rad) | Hamilton wxyz quaternions | Strict SI.\n\n"
		+ "EQUATIONS & ASSUMPTIONS (All virtual results remain UNVALIDATED until physical custody/review receipts):\n"
		+ "1) 6-DoF RK4: m*dv/dt = R(q_bw)*f_body + m*g; dq/dt = 0.5 * q (*) [0, omega].\n"
		+ "2) ISA 1976 & Drag: rho = P / (R_air * T); F_drag = -0.5 * rho * CdA * |v_rel| * v_rel.\n"
		+ "3) Fixed-Wing Lifting-Line: CL = pi * AR * A1; CDi = CL^2 / (pi * AR * e); Mach <= 0.30.\n"
		+ "4) Rotorcraft BEMT + Cheeseman-Bennett IGE + Pitt-Peters 3-State Dynamic Inflow.\n"
		+ "5) 2-RC Thevenin Battery + ES-EKF State Estimation (IMU + Baro/GPS).\n\n"
		+ "SHORTCUTS & MOBILE TOUCH: Drag/Touch-Drag=Orbit | Shift+Drag=Pan | Wheel/Pinch=Zoom | Tab=Focus UI Controls."
	)
	help_dialog.add_child(help_lbl)
	add_child(help_dialog)
	var split: HSplitContainer = HSplitContainer.new()
	split.size_flags_vertical = Control.SIZE_EXPAND_FILL
	layout.add_child(split)
	var inspector: VBoxContainer = VBoxContainer.new()
	inspector.custom_minimum_size.x = 290
	split.add_child(inspector)
	var section: Label = Label.new()
	section.text = "Assembly components"
	inspector.add_child(section)
	components = Tree.new()
	components.hide_root = true
	components.item_selected.connect(_select_component)
	components.size_flags_vertical = Control.SIZE_EXPAND_FILL
	inspector.add_child(components)
	metrics_label = Label.new()
	metrics_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	inspector.add_child(metrics_label)
	var torque_title: Label = Label.new()
	torque_title.text = "Rigid-body experiment (no flight forces)"
	inspector.add_child(torque_title)
	torque_z = _numeric_field(inspector, "Body Z torque (N·m)", -1, 1, 0.001, 0.001)
	torque_z.step = 0.0001
	torque_duration = _numeric_field(inspector, "Duration (s)", 0.01, 10, 0.01, 1.0)
	torque_step = _numeric_field(inspector, "Integration step (s)", 0.0001, 0.05, 0.0001, 0.005)
	var viewport_stage := Control.new()
	viewport_stage.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	viewport_stage.size_flags_vertical = Control.SIZE_EXPAND_FILL
	split.add_child(viewport_stage)
	viewport_container = SubViewportContainer.new()
	viewport_container.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	viewport_container.stretch = true
	viewport_container.mouse_filter = Control.MOUSE_FILTER_STOP
	viewport_container.gui_input.connect(_viewport_input)
	viewport_stage.add_child(viewport_container)
	viewport = SubViewport.new()
	viewport.size = Vector2i(960, 540)
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	viewport.own_world_3d = true
	viewport_container.add_child(viewport)
	blueprint_canvas = WorkbenchControls.BlueprintSheetCanvas.new()
	blueprint_canvas.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	blueprint_canvas.visible = false
	viewport_stage.add_child(blueprint_canvas)
	# Top-Left NVIDIA Isaac-Sim style Physics & Performance HUD
	var hud_panel := PanelContainer.new()
	hud_panel.position = Vector2(12, 12)
	hud_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	viewport_container.add_child(hud_panel)
	var hud_pad := MarginContainer.new()
	for s in ["left", "right", "top", "bottom"]:
		hud_pad.add_theme_constant_override("margin_" + s, 8)
	hud_pad.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hud_panel.add_child(hud_pad)
	viewport_hud_label = Label.new()
	viewport_hud_label.text = "FPS: -- | Engine Ready\nMass & CoG: loading..."
	viewport_hud_label.add_theme_font_size_override("font_size", 11)
	viewport_hud_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hud_pad.add_child(viewport_hud_label)
	# Top-Right Interactive Onshape / Fusion 360 ViewCube Quick-Snap Controls
	var viewcube := HBoxContainer.new()
	viewcube.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT)
	viewcube.offset_left = -255
	viewcube.offset_top = 12
	viewcube.offset_right = -12
	viewcube.offset_bottom = 42
	viewport_container.add_child(viewcube)
	_add_button(viewcube, "ISO", func(): _snap_view(0.72, 0.48))
	_add_button(viewcube, "TOP", func(): _snap_view(0.0, 1.38))
	_add_button(viewcube, "FRONT", func(): _snap_view(0.0, 0.08))
	_add_button(viewcube, "SIDE", func(): _snap_view(PI * 0.5, 0.10))
	_add_button(viewcube, "FIT", _fit_camera)
	# Bottom-Right SOLIDWORKS Flow / Onshape FEA Colorbar Scale Legend
	colorbar_legend = WorkbenchControls.ColorbarLegend.new()
	colorbar_legend.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_RIGHT)
	colorbar_legend.offset_left = -210
	colorbar_legend.offset_top = -72
	colorbar_legend.offset_right = -12
	colorbar_legend.offset_bottom = -12
	colorbar_legend.visible = false
	colorbar_legend.mouse_filter = Control.MOUSE_FILTER_IGNORE
	viewport_container.add_child(colorbar_legend)
	world = Node3D.new()
	viewport.add_child(world)
	aircraft = Node3D.new()
	world.add_child(aircraft)
	camera = Camera3D.new()
	camera.current = true
	camera.fov = 45.0
	world.add_child(camera)
	key_light = DirectionalLight3D.new()
	key_light.rotation_degrees = Vector3(-40, -25, 0)
	key_light.light_energy = 1.25
	world.add_child(key_light)
	fill_light = DirectionalLight3D.new()
	fill_light.rotation_degrees = Vector3(-25, 145, 0)
	fill_light.light_energy = 0.45
	fill_light.light_color = Color(0.75, 0.85, 1.0)
	world.add_child(fill_light)
	world_env = WorldEnvironment.new()
	world_env.environment = Environment.new()
	world.add_child(world_env)
	var ground: MeshInstance3D = MeshInstance3D.new()
	var ground_mesh: PlaneMesh = PlaneMesh.new()
	ground_mesh.size = Vector2(12, 12)
	ground.mesh = ground_mesh
	var ground_material: StandardMaterial3D = StandardMaterial3D.new()
	ground_material.albedo_color = Color(0.08, 0.11, 0.15)
	ground_material.roughness = 0.88
	ground_material.metallic = 0.05
	ground.material_override = ground_material
	ground.position.y = -0.12
	world.add_child(ground)
	grid_group = WorkbenchMeshes.build_cad_grid_and_axes(6.0, 0.5, true)
	world.add_child(grid_group)
	overlay_group = Node3D.new()
	aircraft.add_child(overlay_group)
	ground_props = Node3D.new()
	world.add_child(ground_props)
	var replay: HBoxContainer = HBoxContainer.new()
	layout.add_child(replay)
	_add_button(replay, "Play / pause", _toggle_play_pause)
	_add_button(replay, "Step +dt", _step_replay)
	timeline = HSlider.new()
	timeline.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	timeline.step = 0.001
	timeline.value_changed.connect(_seek)
	replay.add_child(timeline)
	telemetry_plot = WorkbenchControls.TelemetryPlotCanvas.new()
	telemetry_plot.custom_minimum_size = Vector2(0, 66)
	layout.add_child(telemetry_plot)
	scope_label = Label.new()
	scope_label.text = "Schematic component positions · reference Python dynamics · physical validation pending"
	layout.add_child(scope_label)
	status_label = Label.new()
	status_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	layout.add_child(status_label)
	file_dialog = FileDialog.new()
	file_dialog.access = FileDialog.ACCESS_FILESYSTEM
	file_dialog.filters = PackedStringArray(["*.json ; Engineering project"])
	add_child(file_dialog)
	body_dialog = AcceptDialog.new()
	body_dialog.title = "Constrained test body"
	body_dialog.ok_button_text = "Rebuild exact geometry"
	var body_form: VBoxContainer = VBoxContainer.new()
	body_dialog.add_child(body_form)
	var explanation: Label = Label.new()
	explanation.text = "Dimensions drive a solved rectangular sketch and extrusion.\nDensity is an assumption; physical validation remains pending."
	body_form.add_child(explanation)
	body_fields["width_m"] = _numeric_field(body_form, "Width (m)", 0.001, 5, 0.001, 0.2)
	body_fields["height_m"] = _numeric_field(body_form, "Height (m)", 0.001, 5, 0.001, 0.1)
	body_fields["depth_m"] = _numeric_field(body_form, "Depth (m)", 0.001, 5, 0.001, 0.02)
	density_enabled = CheckButton.new()
	density_enabled.text = "Assume a homogeneous material density"
	density_enabled.button_pressed = true
	body_form.add_child(density_enabled)
	body_fields["material_density_kg_m3"] = _numeric_field(body_form, "Density (kg/m³)", 0.001, 100000, 0.001, 500)
	body_dialog.confirmed.connect(_rebuild_body)
	add_child(body_dialog)
	limits_dialog = AcceptDialog.new()
	limits_dialog.title = "Local CAD worker limits"
	limits_dialog.ok_button_text = "Apply for next session"
	var limits_form: VBoxContainer = VBoxContainer.new()
	limits_dialog.add_child(limits_form)
	var limits_help: Label = Label.new()
	limits_help.text = "Limits are checked every 0.1 s; brief peaks can exceed them.\nMemory includes the worker process tree. No hard OS quota.\nGeometry and numerical precision are never reduced to fit."
	limits_form.add_child(limits_help)
	limits_fields["memory"] = _numeric_field(limits_form, "Memory allowance (MiB)", 16, 65536, 16, 1024)
	limits_fields["workspace"] = _numeric_field(limits_form, "Workspace allowance (MiB)", 1, 65536, 1, 256)
	limits_fields["seconds"] = _numeric_field(limits_form, "Maximum job time (s)", 0.01, 900, 0.01, 60)
	limits_status = Label.new()
	limits_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	limits_form.add_child(limits_status)
	limits_dialog.confirmed.connect(_apply_limits)
	add_child(limits_dialog)
	new_project_dialog = AcceptDialog.new()
	new_project_dialog.title = "Create new project"
	new_project_dialog.ok_button_text = "Create project"
	var new_form: VBoxContainer = VBoxContainer.new()
	new_project_dialog.add_child(new_form)
	var name_row: HBoxContainer = HBoxContainer.new()
	new_form.add_child(name_row)
	var name_lbl: Label = Label.new()
	name_lbl.text = "Project name"
	name_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	name_row.add_child(name_lbl)
	new_project_name = LineEdit.new()
	new_project_name.text = "Custom Multirotor Concept"
	new_project_name.custom_minimum_size.x = 240
	name_row.add_child(new_project_name)
	var fam_row: HBoxContainer = HBoxContainer.new()
	new_form.add_child(fam_row)
	var fam_lbl: Label = Label.new()
	fam_lbl.text = "Aircraft family"
	fam_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	fam_row.add_child(fam_lbl)
	new_project_family = OptionButton.new()
	for fam in ["multirotor", "fixed_wing", "helicopter", "vtol"]:
		new_project_family.add_item(fam)
	fam_row.add_child(new_project_family)
	var tpl_row: HBoxContainer = HBoxContainer.new()
	new_form.add_child(tpl_row)
	var tpl_lbl: Label = Label.new()
	tpl_lbl.text = "Starter template"
	tpl_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	tpl_row.add_child(tpl_lbl)
	new_project_template = OptionButton.new()
	new_project_template.add_item("assembly_empty")
	new_project_template.add_item("legacy_reference")
	tpl_row.add_child(new_project_template)
	new_project_dialog.confirmed.connect(_create_new_project)
	add_child(new_project_dialog)
	versions_dialog = AcceptDialog.new()
	versions_dialog.title = "Project versions and recovery"
	versions_dialog.ok_button_text = "Reopen selected version"
	var ver_box: VBoxContainer = VBoxContainer.new()
	versions_dialog.add_child(ver_box)
	versions_status = Label.new()
	versions_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	ver_box.add_child(versions_status)
	versions_tree = Tree.new()
	versions_tree.columns = 3
	versions_tree.set_column_title(0, "Version")
	versions_tree.set_column_title(1, "Saved UTC")
	versions_tree.set_column_title(2, "SHA-256")
	versions_tree.set_column_titles_visible(true)
	versions_tree.hide_root = true
	versions_tree.custom_minimum_size = Vector2(560, 220)
	ver_box.add_child(versions_tree)
	versions_dialog.add_button("Recover last valid", false, "recover_last_valid")
	versions_dialog.confirmed.connect(_reopen_selected_version)
	versions_dialog.custom_action.connect(func(action_name: StringName):
		if action_name == &"recover_last_valid":
			versions_dialog.hide()
			_recover_last_valid())
	add_child(versions_dialog)
	blade_dialog = AcceptDialog.new()
	blade_dialog.title = "Supported parametric blade CAD (Open CASCADE)"
	blade_dialog.ok_button_text = "Rebuild exact blade"
	var blade_form: VBoxContainer = VBoxContainer.new()
	blade_dialog.add_child(blade_form)
	var blade_note: Label = Label.new()
	blade_note.text = "Supported parametric two-station blade loft (not full freeform CAD).\nTip radius must exceed root radius."
	blade_form.add_child(blade_note)
	blade_fields["root_radius_m"] = _numeric_field(blade_form, "Root radius (m)", 0.005, 1.0, 0.005, 0.025)
	blade_fields["root_chord_m"] = _numeric_field(blade_form, "Root chord (m)", 0.005, 0.5, 0.002, 0.032)
	blade_fields["root_twist_deg"] = _numeric_field(blade_form, "Root twist (deg)", -45.0, 45.0, 0.5, 22.0)
	blade_fields["tip_radius_m"] = _numeric_field(blade_form, "Tip radius (m)", 0.02, 2.0, 0.005, 0.19)
	blade_fields["tip_chord_m"] = _numeric_field(blade_form, "Tip chord (m)", 0.005, 0.5, 0.002, 0.016)
	blade_fields["tip_twist_deg"] = _numeric_field(blade_form, "Tip twist (deg)", -45.0, 45.0, 0.5, 8.0)
	blade_fields["thickness_to_chord"] = _numeric_field(blade_form, "Thickness / chord", 0.04, 0.30, 0.01, 0.12)
	blade_density_enabled = CheckButton.new()
	blade_density_enabled.text = "Assume homogeneous blade density"
	blade_density_enabled.button_pressed = true
	blade_form.add_child(blade_density_enabled)
	blade_fields["material_density_kg_m3"] = _numeric_field(blade_form, "Density (kg/m³)", 100.0, 10000.0, 10.0, 1550.0)
	blade_dialog.confirmed.connect(_rebuild_blade)
	add_child(blade_dialog)
	transform_dialog = AcceptDialog.new()
	transform_dialog.title = "Assembly node transform (SI right-handed Z-up)"
	transform_dialog.ok_button_text = "Apply transform"
	var tf_form: VBoxContainer = VBoxContainer.new()
	transform_dialog.add_child(tf_form)
	transform_fields["x"] = _numeric_field(tf_form, "Position X (m)", -10.0, 10.0, 0.01, 0.0)
	transform_fields["y"] = _numeric_field(tf_form, "Position Y (m)", -10.0, 10.0, 0.01, 0.0)
	transform_fields["z"] = _numeric_field(tf_form, "Position Z (m)", -10.0, 10.0, 0.01, 0.0)
	transform_fields["roll_deg"] = _numeric_field(tf_form, "Roll (deg)", -180.0, 180.0, 1.0, 0.0)
	transform_fields["pitch_deg"] = _numeric_field(tf_form, "Pitch (deg)", -180.0, 180.0, 1.0, 0.0)
	transform_fields["yaw_deg"] = _numeric_field(tf_form, "Yaw (deg)", -180.0, 180.0, 1.0, 0.0)
	transform_dialog.confirmed.connect(_apply_node_transform)
	add_child(transform_dialog)
	layout_dialog = AcceptDialog.new()
	layout_dialog.title = "Multirotor Layout, Materials, BOM & Mass"
	layout_dialog.ok_button_text = "Compute BOM & mass"
	var lay_form: VBoxContainer = VBoxContainer.new()
	layout_dialog.add_child(lay_form)
	layout_fields["n_rotors"] = _numeric_field(lay_form, "Rotor count (3..12)", 3, 12, 1, 4)
	layout_fields["arm_radius_m"] = _numeric_field(lay_form, "Arm radius (m)", 0.1, 3.0, 0.01, 0.28)
	layout_fields["wiring_length_m"] = _numeric_field(lay_form, "Bus wiring length (m)", 0.05, 10.0, 0.05, 0.6)
	var lm_row: HBoxContainer = HBoxContainer.new()
	lay_form.add_child(lm_row)
	var lm_lbl: Label = Label.new()
	lm_lbl.text = "Frame material"
	lm_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	lm_row.add_child(lm_lbl)
	layout_material_select = OptionButton.new()
	for mid in ["alu_6061_t6", "cfrp_quasi_iso", "pa12_nylon", "pla_fdg"]:
		layout_material_select.add_item(mid)
	lm_row.add_child(layout_material_select)
	var mot_row: HBoxContainer = HBoxContainer.new()
	lay_form.add_child(mot_row)
	var mot_lbl: Label = Label.new()
	mot_lbl.text = "Motor"
	mot_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	mot_row.add_child(mot_lbl)
	layout_motor_select = OptionButton.new()
	layout_motor_select.add_item("tmotor_mn3508_kv380")
	layout_motor_select.add_item("tmotor_p80iii_kv100")
	mot_row.add_child(layout_motor_select)
	layout_dialog.confirmed.connect(_apply_layout_bom)
	add_child(layout_dialog)
	ground_dialog = AcceptDialog.new()
	ground_dialog.title = "Engineering test ground (SI Z-up)"
	ground_dialog.ok_button_text = "Author test ground"
	var g_form: VBoxContainer = VBoxContainer.new()
	ground_dialog.add_child(g_form)
	ground_fields["wind_x"] = _numeric_field(g_form, "Wind X (m/s)", -40.0, 40.0, 0.5, 0.0)
	ground_fields["wind_y"] = _numeric_field(g_form, "Wind Y (m/s)", -40.0, 40.0, 0.5, 0.0)
	ground_fields["temperature_k"] = _numeric_field(g_form, "Temperature (K)", 200.0, 340.0, 0.5, 288.15)
	ground_fields["pressure_pa"] = _numeric_field(g_form, "Pressure (Pa)", 30000.0, 120000.0, 100.0, 101325.0)
	ground_fields["humidity"] = _numeric_field(g_form, "Humidity (0..1)", 0.0, 1.0, 0.05, 0.0)
	ground_fields["obstacle_x"] = _numeric_field(g_form, "Obstacle X (m)", -20.0, 20.0, 0.5, 4.0)
	ground_rain_check = CheckButton.new()
	ground_rain_check.text = "Request rain (Slice 0D unsupported check)"
	ground_rain_check.button_pressed = false
	g_form.add_child(ground_rain_check)
	ground_dialog.confirmed.connect(_apply_test_ground)
	add_child(ground_dialog)
	mission_dialog = AcceptDialog.new()
	mission_dialog.title = "Mission phases, clock & seed"
	mission_dialog.ok_button_text = "Author & run mission"
	var m_form: VBoxContainer = VBoxContainer.new()
	mission_dialog.add_child(m_form)
	mission_fields["hover_alt_m"] = _numeric_field(m_form, "Target hover altitude (m)", 0.5, 100.0, 0.5, 5.0)
	mission_fields["hover_s"] = _numeric_field(m_form, "Hover duration (s)", 0.5, 120.0, 0.5, 3.0)
	mission_fields["dt_s"] = _numeric_field(m_form, "Controller dt (s)", 0.002, 0.05, 0.002, 0.01)
	mission_fields["seed"] = _numeric_field(m_form, "Experiment seed", 0, 1000000, 1, 42)
	mission_dialog.confirmed.connect(_run_authored_mission)
	add_child(mission_dialog)
	twin_dialog = AcceptDialog.new()
	twin_dialog.title = "Dual Digital-Twin % & Telemetry Comparison"
	twin_report_label = Label.new()
	twin_report_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	twin_report_label.custom_minimum_size = Vector2(540, 220)
	twin_dialog.add_child(twin_report_label)
	add_child(twin_dialog)
	fidelity_dialog = AcceptDialog.new()
	fidelity_dialog.title = "Numerical Fidelity & Execution Budgets"
	fidelity_report_label = Label.new()
	fidelity_report_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	fidelity_report_label.custom_minimum_size = Vector2(540, 220)
	fidelity_dialog.add_child(fidelity_report_label)
	add_child(fidelity_dialog)
	protocol_dialog = AcceptDialog.new()
	protocol_dialog.title = "Frozen Validation Protocols (M20 / P0A-026)"
	protocol_report_label = Label.new()
	protocol_report_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	protocol_report_label.custom_minimum_size = Vector2(560, 220)
	protocol_dialog.add_child(protocol_report_label)
	add_child(protocol_dialog)
	learning_dialog = AcceptDialog.new()
	learning_dialog.title = "Guided Learning & Saved Experiments"
	learning_dialog.ok_button_text = "Run & save experiment"
	var l_form: VBoxContainer = VBoxContainer.new()
	learning_dialog.add_child(l_form)
	var eq_lbl: Label = Label.new()
	eq_lbl.text = "Governing physics: 6-DoF rigid body + quadratic air drag + ideal gas air density."
	l_form.add_child(eq_lbl)
	hypothesis_input = LineEdit.new()
	hypothesis_input.text = "Higher target altitude increases climb demand under wind."
	hypothesis_input.custom_minimum_size.x = 360
	l_form.add_child(hypothesis_input)
	learning_fields["target_altitude_m"] = _numeric_field(l_form, "Target altitude (m)", 0.5, 25.0, 0.5, 3.5)
	learning_fields["wind_x"] = _numeric_field(l_form, "Wind X (m/s)", -20.0, 20.0, 0.5, 2.0)
	learning_dialog.confirmed.connect(_run_guided_experiment)
	add_child(learning_dialog)
	sweep_dialog = AcceptDialog.new()
	sweep_dialog.title = "Bounded Parameter Sweep (constraints & caveats preserved)"
	sweep_dialog.ok_button_text = "Run bounded sweep"
	var sw_form: VBoxContainer = VBoxContainer.new()
	sweep_dialog.add_child(sw_form)
	sweep_fields["max_mass_kg"] = _numeric_field(sw_form, "Max mass constraint (kg)", 1.0, 20.0, 0.2, 4.2)
	sweep_fields["seed"] = _numeric_field(sw_form, "Sweep seed", 0, 100000, 1, 42)
	sweep_dialog.confirmed.connect(_run_bounded_sweep)
	add_child(sweep_dialog)
	_update_camera()


func _numeric_field(parent: Node, title: String, minimum: float, maximum: float, increment: float, initial: float) -> SpinBox:
	var row: HBoxContainer = HBoxContainer.new()
	parent.add_child(row)
	var label: Label = Label.new()
	label.text = title
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(label)
	var field: SpinBox = SpinBox.new()
	field.min_value = minimum
	field.max_value = maximum
	field.step = increment
	field.value = initial
	field.custom_minimum_size.x = 120
	row.add_child(field)
	return field


func _open_limits() -> void:
	if job_pid > 0:
		status_label.text = "Finish or cancel the active job before changing limits."
		return
	var admission_path: String = str(cad_worker.get("session_path")).path_join("resource-admission.json")
	limits_status.text = "No admission decision yet. The next CAD action checks available memory and disk space."
	if FileAccess.file_exists(admission_path):
		var admitted: Variant = JSON.parse_string(FileAccess.get_file_as_string(admission_path))
		if admitted is Dictionary:
			limits_status.text = "Last session: %s\nRequested: %s\nEffective: %s\nReasons: %s" % [admitted.get("status"), str(admitted.get("requested")), str(admitted.get("effective")), str(admitted.get("reasons"))]
	limits_dialog.popup_centered(Vector2i(720, 440))


func _open_help_dialog() -> void:
	help_dialog.popup_centered(Vector2i(620, 340))


func _apply_limits() -> void:
	if job_pid > 0:
		return
	if cad_worker.set_limits(int(limits_fields["memory"].value), int(limits_fields["workspace"].value), float(limits_fields["seconds"].value)):
		status_label.text = "Worker limits saved for the next CAD session."
	else:
		status_label.text = "The old worker could not be stopped; limits were not changed."


func _body_recipe() -> Dictionary:
	if project.is_empty():
		return {}
	for asset in project.get("assets", []):
		if asset["id"] == "body_recipe":
			var metadata: Variant = JSON.parse_string(FileAccess.get_file_as_string(project_asset_root.path_join(asset["path"])))
			if metadata is Dictionary and metadata.get("recipe_type") == "box_1":
				return metadata["recipe"]
	return {}


func _open_body_editor() -> void:
	if job_pid > 0:
		return
	var recipe: Dictionary = _body_recipe()
	if not recipe.is_empty():
		for key in body_fields:
			if recipe.get(key) != null:
				body_fields[key].value = float(recipe[key])
		density_enabled.button_pressed = recipe.get("material_density_kg_m3") != null
	body_dialog.popup_centered(Vector2i(540, 350))


func _rebuild_body() -> void:
	if job_pid > 0:
		return
	var recipe: Dictionary = {"recipe_type": "box_1", "name": "Constrained test body"}
	for key in body_fields:
		recipe[key] = body_fields[key].value
	if not density_enabled.button_pressed:
		recipe["material_density_kg_m3"] = null
	var path: String = _write_payload(recipe)
	_start_job("build-body", path)


func _blade_recipe() -> Dictionary:
	if project.is_empty():
		return {}
	for asset in project.get("assets", []):
		if asset["id"] == "blade_recipe":
			var metadata: Variant = JSON.parse_string(FileAccess.get_file_as_string(project_asset_root.path_join(asset["path"])))
			if metadata is Dictionary and metadata.get("recipe_type") == "blade_1":
				return metadata["recipe"]
	return {}


func _open_blade_editor() -> void:
	if job_pid > 0:
		return
	var recipe: Dictionary = _blade_recipe()
	var stations: Array = recipe.get("stations", [])
	if stations.size() >= 2:
		var root_s: Dictionary = stations[0]
		var tip_s: Dictionary = stations[-1]
		blade_fields["root_radius_m"].value = float(root_s.get("radius_m", 0.025))
		blade_fields["root_chord_m"].value = float(root_s.get("chord_m", 0.032))
		blade_fields["root_twist_deg"].value = float(root_s.get("twist_deg", 22.0))
		blade_fields["tip_radius_m"].value = float(tip_s.get("radius_m", 0.19))
		blade_fields["tip_chord_m"].value = float(tip_s.get("chord_m", 0.016))
		blade_fields["tip_twist_deg"].value = float(tip_s.get("twist_deg", 8.0))
		blade_fields["thickness_to_chord"].value = float(root_s.get("thickness_to_chord", 0.12))
		blade_density_enabled.button_pressed = recipe.get("material_density_kg_m3") != null
		if recipe.get("material_density_kg_m3") != null:
			blade_fields["material_density_kg_m3"].value = float(recipe["material_density_kg_m3"])
	blade_dialog.popup_centered(Vector2i(560, 440))


func _rebuild_blade() -> void:
	if job_pid > 0:
		return
	var r0: float = blade_fields["root_radius_m"].value
	var r1: float = blade_fields["tip_radius_m"].value
	if r1 <= r0:
		status_label.text = "Constraint refused: blade tip radius must exceed root radius."
		return
	var tc: float = blade_fields["thickness_to_chord"].value
	var recipe: Dictionary = {
		"name": "Parametric blade",
		"stations": [
			{"radius_m": r0, "chord_m": blade_fields["root_chord_m"].value, "twist_deg": blade_fields["root_twist_deg"].value, "thickness_to_chord": tc},
			{"radius_m": r1, "chord_m": blade_fields["tip_chord_m"].value, "twist_deg": blade_fields["tip_twist_deg"].value, "thickness_to_chord": tc},
		],
		"profile_samples": 48,
		"mesh_deflection_m": 0.00025,
		"material_density_kg_m3": blade_fields["material_density_kg_m3"].value if blade_density_enabled.button_pressed else null,
	}
	var path: String = _write_payload(recipe)
	_start_job("build-blade", path)


func _open_transform_editor() -> void:
	if job_pid > 0 or project.is_empty():
		return
	if project.get("vehicle", {}).get("format") != "assembly_1":
		status_label.text = "Select an assembly project to edit node transforms."
		return
	var nodes: Array = project["vehicle"].get("nodes", [])
	if nodes.is_empty():
		return
	var node: Dictionary = nodes[0]
	var selected: TreeItem = components.get_selected()
	if selected != null and selected.get_metadata(0) is Dictionary and selected.get_metadata(0).has("node"):
		node = selected.get_metadata(0)["node"]
	var pos: Array = node.get("position_m", [0.0, 0.0, 0.0])
	transform_fields["x"].value = float(pos[0])
	transform_fields["y"].value = float(pos[1])
	transform_fields["z"].value = float(pos[2])
	transform_fields["roll_deg"].value = 0.0
	transform_fields["pitch_deg"].value = 0.0
	transform_fields["yaw_deg"].value = 0.0
	transform_dialog.popup_centered(Vector2i(460, 340))


func _euler_deg_to_wxyz(roll_deg: float, pitch_deg: float, yaw_deg: float) -> Array:
	var hr: float = deg_to_rad(roll_deg) * 0.5
	var hp: float = deg_to_rad(pitch_deg) * 0.5
	var hy: float = deg_to_rad(yaw_deg) * 0.5
	var cr: float = cos(hr)
	var sr: float = sin(hr)
	var cp: float = cos(hp)
	var sp: float = sin(hp)
	var cy: float = cos(hy)
	var sy: float = sin(hy)
	var w: float = cr * cp * cy + sr * sp * sy
	var x: float = sr * cp * cy - cr * sp * sy
	var y: float = cr * sp * cy + sr * cp * sy
	var z: float = cr * cp * sy - sr * sp * cy
	var n: float = sqrt(w * w + x * x + y * y + z * z)
	return [w / n, x / n, y / n, z / n]


func _apply_node_transform() -> void:
	if job_pid > 0 or project.is_empty() or project.get("vehicle", {}).get("format") != "assembly_1":
		return
	var nodes: Array = project["vehicle"].get("nodes", [])
	if nodes.is_empty():
		return
	var target_id: String = str(nodes[0]["id"])
	var selected: TreeItem = components.get_selected()
	if selected != null and selected.get_metadata(0) is Dictionary and selected.get_metadata(0).has("node"):
		target_id = str(selected.get_metadata(0)["node"]["id"])
	var edited: Dictionary = project.duplicate(true)
	for node in edited["vehicle"]["nodes"]:
		if str(node["id"]) == target_id:
			node["position_m"] = [transform_fields["x"].value, transform_fields["y"].value, transform_fields["z"].value]
			node["orientation_wxyz"] = _euler_deg_to_wxyz(
				transform_fields["roll_deg"].value,
				transform_fields["pitch_deg"].value,
				transform_fields["yaw_deg"].value)
	var path: String = _write_payload(edited)
	_start_job("edit-transform", path)


func _push_undo_state() -> void:
	if project.is_empty():
		return
	undo_stack.append({
		"project": project.duplicate(true),
		"asset_root": project_asset_root,
		"document_json": project_document_json,
	})
	if undo_stack.size() > 32:
		undo_stack.pop_front()
	redo_stack.clear()


func _undo_edit() -> void:
	if job_pid > 0 or undo_stack.is_empty():
		status_label.text = "Nothing to undo."
		return
	var current_state: Dictionary = {
		"project": project.duplicate(true),
		"asset_root": project_asset_root,
		"document_json": project_document_json,
	}
	var prior: Dictionary = undo_stack.pop_back()
	if _adopt_project(prior["project"], str(prior["asset_root"])):
		redo_stack.append(current_state)
		project_document_json = str(prior["document_json"])
		project_document_view = project.duplicate(true)
		status_label.text = "Undo applied (%d remaining). Exact solids and LOD restored." % undo_stack.size()


func _redo_edit() -> void:
	if job_pid > 0 or redo_stack.is_empty():
		status_label.text = "Nothing to redo."
		return
	var current_state: Dictionary = {
		"project": project.duplicate(true),
		"asset_root": project_asset_root,
		"document_json": project_document_json,
	}
	var nxt: Dictionary = redo_stack.pop_back()
	if _adopt_project(nxt["project"], str(nxt["asset_root"])):
		undo_stack.append(current_state)
		project_document_json = str(nxt["document_json"])
		project_document_view = project.duplicate(true)
		status_label.text = "Redo applied (%d remaining). Exact solids and LOD restored." % redo_stack.size()


func _open_layout_editor() -> void:
	if job_pid > 0:
		return
	layout_dialog.popup_centered(Vector2i(500, 320))


func _apply_layout_bom() -> void:
	if job_pid > 0:
		return
	var n_rot: int = int(layout_fields["n_rotors"].value)
	var radius: float = float(layout_fields["arm_radius_m"].value)
	var rotors_arr: Array = []
	for i in range(n_rot):
		var ang: float = TAU * float(i) / float(n_rot)
		rotors_arr.append({"position_m": [radius * cos(ang), radius * sin(ang), 0.0], "spin_direction": 1 if (i % 2 == 0) else -1})
	var mat_id: String = layout_material_select.get_item_text(layout_material_select.selected)
	var mot_id: String = layout_motor_select.get_item_text(layout_motor_select.selected)
	var prop_id: String = "tmotor_g30x105_cf" if mot_id == "tmotor_p80iii_kv100" else "tmotor_p15x5_cf"
	var esc_id: String = "esc_80a_12s" if mot_id == "tmotor_p80iii_kv100" else "generic_esc_20a"
	var bat_id: String = "generic_12s_22000mah" if mot_id == "tmotor_p80iii_kv100" else "generic_6s_lipo_16000mah"
	var spec: Dictionary = {
		"rotors": rotors_arr,
		"motor_id": mot_id,
		"propeller_id": prop_id,
		"esc_id": esc_id,
		"battery_id": bat_id,
		"wiring_id": "silicone_awg12_bus",
		"wiring_length_m": float(layout_fields["wiring_length_m"].value),
		"sensor_ids": ["icm42688p_imu"],
		"frame_parts": [{"name": "central_frame", "material_id": mat_id, "shape": "box", "dimensions_m": [0.22, 0.22, 0.02], "position_m": [0.0, 0.0, 0.0]}],
	}
	_start_job("layout-bom", _write_payload(spec))


func _run_clearance_check() -> void:
	if job_pid > 0 or project.is_empty():
		return
	var doc_text: String = _frozen_project_json()
	if doc_text.is_empty():
		return
	var rotors_arr: Array = []
	var vehicle: Dictionary = project.get("vehicle", {})
	if vehicle.get("format") == "legacy_multirotor_0.1":
		for r in vehicle["snapshot"].get("rotors", []):
			rotors_arr.append({"position_m": r["position_m"], "radius_m": 0.19})
	else:
		rotors_arr = [{"position_m": [0.25, 0.25, 0.0], "radius_m": 0.15}, {"position_m": [-0.25, 0.25, 0.0], "radius_m": 0.15}]
	var payload_str: String = '{"project":%s,"rotors":%s,"minimum_clearance_m":0.02}' % [doc_text, JSON.stringify(rotors_arr, "", true, true)]
	_start_job("clearance-check", _write_json_text(payload_str))


func _open_test_ground_dialog() -> void:
	if job_pid > 0 or project.is_empty():
		return
	ground_dialog.popup_centered(Vector2i(500, 360))


func _apply_test_ground() -> void:
	if job_pid > 0 or project.is_empty():
		return
	var doc_text: String = _frozen_project_json()
	if doc_text.is_empty():
		return
	var ground_spec: Dictionary = {
		"wind_world_m_s": [float(ground_fields["wind_x"].value), float(ground_fields["wind_y"].value), 0.0],
		"temperature_k": float(ground_fields["temperature_k"].value),
		"pressure_pa": float(ground_fields["pressure_pa"].value),
		"relative_humidity": float(ground_fields["humidity"].value),
		"rain_mm_h": 5.0 if ground_rain_check.button_pressed else 0.0,
		"obstacles": [{"id": "pillar_1", "center_m": [float(ground_fields["obstacle_x"].value), 0.0, 0.5], "size_m": [0.5, 0.5, 1.0]}],
	}
	var payload_str: String = '{"project":%s,"test_ground":%s}' % [doc_text, JSON.stringify(ground_spec, "", true, true)]
	_start_job("author-ground", _write_json_text(payload_str))


func _open_mission_dialog() -> void:
	if job_pid > 0 or project.is_empty():
		return
	mission_dialog.popup_centered(Vector2i(480, 280))


func _run_authored_mission() -> void:
	if job_pid > 0 or project.is_empty():
		return
	var doc_text: String = _frozen_project_json()
	if doc_text.is_empty():
		return
	var alt: float = float(mission_fields["hover_alt_m"].value)
	var hov_s: float = float(mission_fields["hover_s"].value)
	var dt_s: float = float(mission_fields["dt_s"].value)
	var seed_val: int = int(mission_fields["seed"].value)
	var mission_spec: Dictionary = {
		"controller_dt_s": dt_s,
		"seed": seed_val,
		"phases": [
			{"phase": "takeoff", "duration_s": 1.0, "target_altitude_m": alt},
			{"phase": "hover", "duration_s": hov_s, "target_altitude_m": alt},
			{"phase": "landing", "duration_s": 1.0, "target_altitude_m": 0.0},
		],
	}
	var payload_str: String = '{"project":%s,"mission":%s}' % [doc_text, JSON.stringify(mission_spec, "", true, true)]
	_start_job("author-mission", _write_json_text(payload_str))


func _toggle_play_pause() -> void:
	playing = not playing
	playback_state = "RUNNING" if playing else "PAUSED"
	status_label.text = "Playback %s at %.3f s" % [playback_state, replay_time]


func _step_replay() -> void:
	playing = false
	playback_state = "PAUSED"
	var telemetry: Variant = result.get("result", {}).get("telemetry")
	var dt_step: float = 0.004
	if result.get("execution_fidelity") is Dictionary:
		dt_step = float(result["execution_fidelity"].get("effective_dt_s", 0.004))
	elif telemetry is Dictionary and telemetry.get("t", []).size() >= 2:
		dt_step = maxf(0.001, float(telemetry["t"][1]) - float(telemetry["t"][0]))
	var target_t: float = minf(replay_time + dt_step, timeline.max_value)
	timeline.set_value_no_signal(target_t)
	_seek(target_t)
	status_label.text = "Stepped +%0.4f s -> t=%.4f s (%s)" % [dt_step, replay_time, playback_state]


func _run_authoritative_sim() -> void:
	if job_pid > 0 or project.is_empty():
		return
	var doc_text: String = _frozen_project_json()
	if doc_text.is_empty():
		return
	playback_state = "RUNNING"
	_start_job("simulate", _write_json_text('{"project":%s}' % doc_text))


func _open_twin_dialog() -> void:
	if result.is_empty():
		twin_report_label.text = "No simulation run recorded yet.\nRun an authoritative simulation first to inspect Dual Digital-Twin percentages."
	else:
		var twin: Dictionary = result.get("dual_digital_twin", {})
		var pass_prob: Variant = twin.get("design_pass_fail_probability_pct")
		var phys_match: Variant = twin.get("physical_evidence_match_pct")
		twin_report_label.text = (
			"Design Pass/Fail Probability: %s (%s)\n" +
			"Physical Evidence Match: %s (%s)\n" +
			"Project SHA-256: %s\n" +
			"Model Env SHA-256: %s\n" +
			"Unverified parameters: %s\n" +
			"Missing evidence note: %s"
		) % [
			("%.2f%%" % float(pass_prob)) if pass_prob != null else "INCONCLUSIVE",
			str(twin.get("design_verdict", "UNVERIFIED_ESTIMATE")),
			("%.2f%%" % float(phys_match)) if phys_match != null else "UNVALIDATED",
			str(twin.get("physical_validation_status", "UNVALIDATED")),
			str(result.get("project_sha256", "")).left(16),
			str(result.get("model_environment", {}).get("sha256", "")).left(16),
			str(twin.get("unverified_parameters", [])),
			str(twin.get("missing_physical_evidence_reason", "None")),
		]
	twin_dialog.popup_centered(Vector2i(580, 280))


func _open_fidelity_dialog() -> void:
	var fid: Variant = result.get("execution_fidelity") if not result.is_empty() else null
	if not (fid is Dictionary) or fid.is_empty():
		fidelity_report_label.text = "No recorded execution fidelity block in current result.\nUse 'Run authoritative' to record timestep, integrator, error estimate, and runtime budgets."
	else:
		fidelity_report_label.text = (
			"Backend: %s (%s)\n" +
			"Timestep requested vs effective: %s s vs %s s (%d steps / %d budget)\n" +
			"Solver rate: %s Hz\n" +
			"Numerical error estimate (RK4): %s\n" +
			"Quaternion max norm drift: %s\n" +
			"Wall elapsed vs budget: %s s / %s s (within_limit=%s)"
		) % [
			str(fid.get("backend_id")),
			str(fid.get("integrator")),
			str(fid.get("requested_dt_s")),
			str(fid.get("effective_dt_s")),
			int(fid.get("step_count", 0)),
			int(fid.get("step_budget", 0)),
			str(fid.get("solver_rate_hz")),
			str(fid.get("numerical_error_estimate")),
			str(fid.get("quaternion_max_norm_drift")),
			str(fid.get("wall_elapsed_s")),
			str(fid.get("wall_budget_s")),
			str(fid.get("budget_within_limit")),
		]
	fidelity_dialog.popup_centered(Vector2i(580, 260))


func _open_protocol_catalog() -> void:
	if job_pid > 0:
		return
	var catalog_path: String = repository_root().path_join("data/research/frozen_protocols.json")
	_start_job("register-protocol", _write_payload({"catalog_path": catalog_path}))


func _open_learning_dialog() -> void:
	if job_pid > 0 or project.is_empty():
		return
	learning_dialog.popup_centered(Vector2i(520, 240))


func _run_guided_experiment() -> void:
	if job_pid > 0 or project.is_empty():
		return
	var doc_text: String = _frozen_project_json()
	if doc_text.is_empty():
		return
	var hyp: String = hypothesis_input.text.strip_edges()
	var payload_str: String = '{"project":%s,"hypothesis":%s,"target_altitude_m":%f,"wind_world_m_s":[%f,0.0,0.0]}' % [
		doc_text, JSON.stringify(hyp), float(learning_fields["target_altitude_m"].value), float(learning_fields["wind_x"].value)]
	_start_job("guided-experiment", _write_json_text(payload_str))


func _open_sweep_dialog() -> void:
	if job_pid > 0:
		return
	sweep_dialog.popup_centered(Vector2i(460, 200))


func _run_bounded_sweep() -> void:
	if job_pid > 0:
		return
	var doc_text: String = _frozen_project_json() if not project.is_empty() else "{}"
	var payload_str: String = '{"project":%s,"constraints":{"max_mass_kg":%f},"seed":%d}' % [
		doc_text, float(sweep_fields["max_mass_kg"].value), int(sweep_fields["seed"].value)]
	_start_job("bounded-sweep", _write_json_text(payload_str))


func _run_fixed_wing_vlm() -> void:
	if job_pid > 0:
		return
	_start_job("fixed-wing-sim", _write_payload({"wingspan_m": 1.8, "root_chord_m": 0.26, "tip_chord_m": 0.16, "mass_kg": 2.2}))


func _run_vtol_transition() -> void:
	if job_pid > 0:
		return
	_start_job("vtol-transition", _write_payload({"mass_kg": 3.0, "wing_area_m2": 0.45, "max_rotor_thrust_n": 45.0}))


func _run_helicopter_autorotation() -> void:
	if job_pid > 0:
		return
	_start_job("autorotation-sim", _write_payload({"flare_altitude_m": 8.0, "min_safe_rpm": 950.0}))


func _run_adverse_weather() -> void:
	if job_pid > 0:
		return
	_start_job("adverse-weather", _write_payload({"rain_mm_h": 15.0, "oat_c": -4.0, "lwc_g_m3": 0.5, "exposure_s": 60.0}))


func _run_swarm_sim() -> void:
	if job_pid > 0:
		return
	_start_job("swarm-sim", _write_payload({"initial_positions_m": [[0, 0, 2], [4, 0, 2], [0, 4, 2]], "target_positions_m": [[1, 0, 3], [5, 0, 3], [1, 4, 3]]}))


func _run_sitl_mission() -> void:
	if job_pid > 0:
		return
	_start_job("sitl-mission", _write_payload({"firmware_kind": "px4"}))


func _run_native_cpp_rk4() -> void:
	if engineering == null or not engineering.has_method("simulate_rk4"):
		status_label.text = "Native C++20 simulate_rk4 unavailable; rebuild GDExtension."
		return
	var wind: Array = [0.0, 0.0, 0.0]
	var tg: Variant = project.get("experiment", {}).get("parameters", {}).get("test_ground")
	if tg is Dictionary and tg.get("wind_world_m_s") is Array:
		wind = tg["wind_world_m_s"]
	var cfg: Dictionary = {
		"mass_kg": 2.0,
		"n_rotors": 4,
		"max_total_thrust_n": 72.0,
		"cd_a_m2": 0.05,
		"air_density_kg_m3": 1.225,
		"wind_world_m_s": wind,
		"initial_altitude_m": 2.0,
		"target_altitude_m": 2.5,
		"dt_s": 0.004,
		"duration_s": 0.4,
	}
	var res: Dictionary = engineering.call("simulate_rk4", cfg)
	if not res.get("ok", false):
		status_label.text = "Native C++ kernel refused: %s" % str(res.get("error", "unknown"))
		return
	result = {"experiment_kind": "native_cpp_rk4_1", "result": {"status": "failed" if res.get("aborted", false) else "completed", "telemetry": res.get("telemetry", {})}}
	var t_arr: Array = result["result"]["telemetry"].get("t", [])
	if t_arr.size() > 0:
		timeline.max_value = float(t_arr[-1])
		_seek(0.0)
	playback_state = "FAILED" if res.get("aborted", false) else "COMPLETED"
	status_label.text = "C++20 Native RK4 %s (%d steps, max_alt=%.3f m) · zero-Python mobile-ready." % [
		playback_state, int(res.get("step_count", 0)), float(res.get("max_altitude_m", 0.0))]


func _run_cad_torque() -> void:
	if project.is_empty() or job_pid > 0:
		return
	var document: String = _frozen_project_json()
	if document.is_empty():
		return
	var experiment: Dictionary = {"torque_body_nm": [0.0, 0.0, torque_z.value],
		"duration_s": torque_duration.value, "step_s": torque_step.value}
	_start_job("cad-torque", _write_json_text('{"project":' + document + ',"experiment":' + JSON.stringify(experiment, "", true, true) + '}'))


func _viewport_input(event: InputEvent) -> void:
	if qualification_orbit_left and qualification_started_usec > 0 and qualification_events.size() < 10000:
		if event is InputEventMouseMotion:
			qualification_events.append({"kind": "motion", "usec": Time.get_ticks_usec(), "relative": [event.relative.x, event.relative.y], "buttons": event.button_mask})
		elif event is InputEventMouseButton:
			qualification_events.append({"kind": "button", "usec": Time.get_ticks_usec(), "button": event.button_index, "pressed": event.pressed})
	if event is InputEventMouseMotion and (event.button_mask & MOUSE_BUTTON_MASK_RIGHT or (qualification_orbit_left and event.button_mask & MOUSE_BUTTON_MASK_LEFT)):
		yaw -= event.relative.x * 0.008
		elevation = clampf(elevation + event.relative.y * 0.008, 0.05, 1.4)
		_update_camera()
	elif event is InputEventScreenDrag:
		yaw -= event.relative.x * 0.01
		elevation = clampf(elevation + event.relative.y * 0.01, 0.05, 1.4)
		_update_camera()
	elif event is InputEventMagnifyGesture and event.factor > 0.0:
		distance_m = clampf(distance_m / event.factor, 0.3, 40.0)
		_update_camera()
	if event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_LEFT:
			var item: TreeItem = components.get_root().get_first_child() if components.get_root() else null
			var closest: TreeItem = null
			var best_distance: float = 18.0
			while item != null:
				var metadata: Variant = item.get_metadata(0)
				if metadata is Dictionary:
					var marker: MeshInstance3D = metadata["marker"]
					var screen_point: Vector2 = camera.unproject_position(marker.global_position)
					var offset: float = screen_point.distance_to(event.position)
					if offset < best_distance:
						best_distance = offset
						closest = item
				item = item.get_next()
			if closest != null:
				closest.select(0)
				_select_component()
		if event.button_index == MOUSE_BUTTON_WHEEL_UP:
			distance_m = maxf(0.3, distance_m * 0.9)
		if event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			distance_m *= 1.1
		_update_camera()


func _input(event: InputEvent) -> void:
	if qualification_orbit_left and event is InputEventKey and event.pressed and event.keycode == KEY_SPACE and qualification_started_usec == 0:
		qualification_started_usec = Time.get_ticks_usec()
		qualification_events.clear()


func _update_camera() -> void:
	var target: Vector3 = aircraft.to_global(view_center)
	camera.position = target + Vector3(sin(yaw) * cos(elevation), sin(elevation),
		cos(yaw) * cos(elevation)) * distance_m
	camera.look_at(target)


func _scene_position(position: Array) -> Vector3:
	return Vector3(float(position[0]), float(position[2]), -float(position[1]))


func _refresh_project() -> bool:
	result = {}
	playing = false
	replay_time = 0
	aircraft.position = Vector3.ZERO
	aircraft.quaternion = Quaternion.IDENTITY
	view_center = Vector3.ZERO
	for child in aircraft.get_children():
		aircraft.remove_child(child)
		child.queue_free()
	_refresh_ground_props()
	components.clear()
	var root: TreeItem = components.create_item()
	project_label.text = "%s · %s · document %s" % [
		project["name"], project["aircraft_family"], project["document_version"]]
	var vehicle: Dictionary = project["vehicle"]
	if vehicle["format"] != "legacy_multirotor_0.1":
		var node_objects: Dictionary = {}
		for node in vehicle.get("nodes", []):
			var assembly_node: Node3D = Node3D.new()
			assembly_node.position = _scene_position(node["position_m"])
			var q: Array = node["orientation_wxyz"]
			assembly_node.quaternion = Quaternion(float(q[1]), float(q[3]), -float(q[2]), float(q[0]))
			node_objects[node["id"]] = assembly_node
		for node in vehicle.get("nodes", []):
			var assembly_node: Node3D = node_objects[node["id"]]
			var parent: Node3D = aircraft if node["parent_id"] == null else node_objects[node["parent_id"]]
			parent.add_child(assembly_node)
			var item: TreeItem = components.create_item(root)
			item.set_text(0, str(node["name"]))
			if node["geometry_asset_id"] != null:
				var asset: Dictionary = _asset(node["geometry_asset_id"])
				var marker: MeshInstance3D = _display_mesh(asset)
				if marker == null:
					return false
				assembly_node.add_child(marker)
				item.set_metadata(0, {"marker": marker, "node": node})
		metrics_label.text = "Assembly geometry loaded. Simulation backend is unassigned."
		scope_label.text = "Supported parametric body & blade CAD (Open CASCADE) · not full freeform sketcher · physical validation pending"
		_fit_camera()
		return true
	var parts: Array = vehicle["snapshot"]["parts"]
	for part in parts:
		var item: TreeItem = components.create_item(root)
		item.set_text(0, "%s · %.3f kg" % [part["name"], part["mass_kg"]])
		var marker: MeshInstance3D = MeshInstance3D.new()
		var sphere: SphereMesh = SphereMesh.new()
		sphere.radius = 0.025
		sphere.height = 0.05
		marker.mesh = sphere
		var material: StandardMaterial3D = StandardMaterial3D.new()
		material.albedo_color = Color(0.2, 0.75, 0.9)
		marker.material_override = material
		marker.position = _scene_position(part["position_m"])
		aircraft.add_child(marker)
		item.set_metadata(0, {"marker": marker, "part": part})
	var hub_inst := MeshInstance3D.new()
	var hub_mesh := BoxMesh.new()
	hub_mesh.size = Vector3(0.20, 0.038, 0.20)
	hub_inst.mesh = hub_mesh
	hub_inst.material_override = _make_cad_material(false)
	aircraft.add_child(hub_inst)
	var motor_mat := StandardMaterial3D.new()
	motor_mat.albedo_color = Color(0.75, 0.78, 0.84)
	motor_mat.metallic = 0.85
	motor_mat.roughness = 0.24
	var blade_mat := StandardMaterial3D.new()
	blade_mat.albedo_color = Color(0.16, 0.18, 0.22)
	blade_mat.metallic = 0.20
	blade_mat.roughness = 0.35
	var duct_mat := StandardMaterial3D.new()
	duct_mat.albedo_color = Color(0.28, 0.45, 0.65, 0.30)
	duct_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	last_rotor_scene_positions.clear()
	for r_spec in vehicle["snapshot"].get("rotors", []):
		if not (r_spec is Dictionary):
			continue
		var r_pos: Vector3 = _scene_position(r_spec.get("position_m", [0.0, 0.0, 0.0]))
		last_rotor_scene_positions.append(r_pos)
		var r_len: float = Vector2(r_pos.x, r_pos.z).length()
		if r_len > 0.02:
			var arm := MeshInstance3D.new()
			var arm_m := BoxMesh.new()
			arm_m.size = Vector3(r_len, 0.018, 0.024)
			arm.mesh = arm_m
			arm.position = r_pos * 0.5
			arm.rotation.y = -atan2(r_pos.z, r_pos.x)
			arm.material_override = _make_cad_material(false)
			aircraft.add_child(arm)
		var bell := MeshInstance3D.new()
		var bm := CylinderMesh.new()
		bm.top_radius = 0.024
		bm.bottom_radius = 0.024
		bm.height = 0.032
		bell.mesh = bm
		bell.position = r_pos + Vector3(0.0, 0.016, 0.0)
		bell.material_override = motor_mat
		aircraft.add_child(bell)
		var blade := MeshInstance3D.new()
		blade.mesh = WorkbenchMeshes.build_twisted_blade_mesh(0.18, 0.032, 0.014, 2, int(r_spec.get("spin_direction", 1)))
		blade.position = r_pos + Vector3(0.0, 0.036, 0.0)
		blade.material_override = blade_mat
		aircraft.add_child(blade)
		var ring_mesh := TorusMesh.new()
		ring_mesh.inner_radius = 0.185
		ring_mesh.outer_radius = 0.195
		var duct := MeshInstance3D.new()
		duct.mesh = ring_mesh
		duct.position = r_pos + Vector3(0.0, 0.036, 0.0)
		duct.material_override = duct_mat
		aircraft.add_child(duct)
	var properties: Dictionary = engineering.mass_properties(parts)
	if properties["ok"]:
		metrics_label.text = "Native C++ mass %.3f kg\nCoG %s m" % [
			properties["mass_kg"], str(properties["center_of_mass_m"])]
		_rebuild_viewport_overlays(_scene_position(properties["center_of_mass_m"]))
	else:
		metrics_label.text = properties["error"]
		return false
	scope_label.text = "Schematic component positions · reference Python dynamics · physical validation pending"
	_fit_camera()
	return true


func _fit_camera() -> void:
	var meshes: Array[Node] = aircraft.find_children("*", "MeshInstance3D", true, false)
	if meshes.is_empty():
		_update_camera()
		return
	var first_mesh: MeshInstance3D = meshes[0] as MeshInstance3D
	var bounds: AABB = first_mesh.global_transform * first_mesh.get_aabb()
	for candidate in meshes:
		var mesh: MeshInstance3D = candidate as MeshInstance3D
		bounds = bounds.merge(mesh.global_transform * mesh.get_aabb())
	view_center = aircraft.to_local(bounds.get_center())
	distance_m = maxf(0.3, bounds.size.length() * 1.7)
	_update_camera()


func _asset(identity: String) -> Dictionary:
	for asset in project["assets"]:
		if asset["id"] == identity:
			return asset
	return {}


func _refresh_ground_props() -> void:
	if ground_props == null:
		return
	for child in ground_props.get_children():
		ground_props.remove_child(child)
		child.queue_free()
	var tg: Variant = project.get("experiment", {}).get("parameters", {}).get("test_ground")
	if not (tg is Dictionary):
		return
	# Display-only PBR cues for landing pad and authored obstacles; aerodynamic and contact physics remain separate.
	var ls: Dictionary = tg.get("landing_surface", {})
	var pad: MeshInstance3D = MeshInstance3D.new()
	var pad_mesh: CylinderMesh = CylinderMesh.new()
	pad_mesh.top_radius = 0.6
	pad_mesh.bottom_radius = 0.65
	pad_mesh.height = 0.02
	pad.mesh = pad_mesh
	var pad_mat: StandardMaterial3D = StandardMaterial3D.new()
	pad_mat.albedo_color = Color(0.18, 0.22, 0.26)
	pad_mat.roughness = 0.78
	pad_mat.metallic = 0.1
	pad.material_override = pad_mat
	var pad_pos: Array = ls.get("origin_m", [0.0, 0.0, 0.0])
	pad.position = _scene_position([float(pad_pos[0]), float(pad_pos[1]), float(pad_pos[2]) - 0.01])
	ground_props.add_child(pad)
	for obs in tg.get("obstacles", []):
		if not (obs is Dictionary):
			continue
		var obs_inst: MeshInstance3D = MeshInstance3D.new()
		var box_mesh: BoxMesh = BoxMesh.new()
		var sz: Array = obs.get("size_m", [0.5, 0.5, 1.0])
		box_mesh.size = Vector3(float(sz[0]), float(sz[2]), float(sz[1]))
		obs_inst.mesh = box_mesh
		var obs_mat: StandardMaterial3D = StandardMaterial3D.new()
		obs_mat.albedo_color = Color(0.68, 0.36, 0.16)
		obs_mat.roughness = 0.55
		obs_mat.metallic = 0.25
		obs_inst.material_override = obs_mat
		var ctr: Array = obs.get("center_m", [2.0, 0.0, 0.5])
		obs_inst.position = _scene_position([float(ctr[0]), float(ctr[1]), float(ctr[2])])
		ground_props.add_child(obs_inst)


func _display_mesh(asset: Dictionary) -> MeshInstance3D:
	if asset.get("role") != "display_mesh":
		status_label.text = "This geometry needs a display-mesh adapter."
		return null
	var path: String = project_asset_root.path_join(asset["path"])
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if file == null or file.get_length() > 16 * 1024 * 1024:
		status_label.text = "Display mesh is missing or exceeds the 16 MiB desktop display limit."
		return null
	var bytes: PackedByteArray = file.get_buffer(file.get_length())
	file.close()
	var hash: HashingContext = HashingContext.new()
	hash.start(HashingContext.HASH_SHA256)
	hash.update(bytes)
	if hash.finish().hex_encode() != asset["sha256"]:
		status_label.text = "Display mesh failed its SHA-256 check."
		return null
	var mesh_data: Variant = JSON.parse_string(bytes.get_string_from_utf8())
	if not mesh_data is Dictionary or mesh_data.get("units") != "m" or mesh_data.get("frame") != "local_right_handed_z_up":
		status_label.text = "Display mesh has unsupported units or coordinates."
		return null
	var positions: Array = mesh_data.get("vertices_m", [])
	var triangles: Array = mesh_data.get("triangles", [])
	if positions.is_empty() or triangles.is_empty() or triangles.size() > 100000:
		status_label.text = "Display mesh is empty or exceeds the 100k desktop display triangle limit."
		return null
	var vertices: PackedVector3Array = PackedVector3Array()
	for position in positions:
		if not position is Array or position.size() != 3:
			status_label.text = "Invalid display vertex."
			return null
		for coordinate in position:
			if not (coordinate is float or coordinate is int) or not is_finite(float(coordinate)):
				status_label.text = "Display coordinates must be finite numbers."
				return null
		vertices.append(_scene_position(position))
	var surface: SurfaceTool = SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	for triangle in triangles:
		if not triangle is Array or triangle.size() != 3:
			status_label.text = "Invalid display triangle."
			return null
		for offset in [0, 2, 1]:
			var index: Variant = triangle[offset]
			if not (index is float or index is int) or float(index) != floorf(float(index)) or index < 0 or index >= vertices.size():
				status_label.text = "Display triangle references an invalid vertex."
				return null
			surface.add_vertex(vertices[int(index)])
	surface.generate_normals()
	surface.index()
	# Procedural JSON meshes do not pass through Godot's scene-import LOD pipeline.
	var importer: ImporterMesh = ImporterMesh.new()
	importer.add_surface(Mesh.PRIMITIVE_TRIANGLES, surface.commit_to_arrays())
	importer.generate_lods(60.0, 60.0, [])
	var marker: MeshInstance3D = MeshInstance3D.new()
	marker.mesh = importer.get_mesh()
	marker.set_meta("display_lod_count", importer.get_surface_lod_count(0))
	var material: StandardMaterial3D = _make_cad_material(false)
	marker.material_override = material
	return marker


func _make_cad_material(selected_state: bool) -> StandardMaterial3D:
	var material: StandardMaterial3D = StandardMaterial3D.new()
	if selected_state:
		material.albedo_color = Color(1.0, 0.7, 0.25)
		material.metallic = 0.25
		material.roughness = 0.35
		material.rim_enabled = true
		material.rim = 0.6
		material.rim_tint = 0.5
		return material
	match cad_material_preset:
		"alu_6061_t6":
			material.albedo_color = Color(0.74, 0.78, 0.82)
			material.metallic = 0.85
			material.roughness = 0.28
		"cfrp_quasi_iso":
			material.albedo_color = Color(0.14, 0.16, 0.19)
			material.metallic = 0.15
			material.roughness = 0.38
			material.clearcoat_enabled = true
			material.clearcoat = 0.45
		"pa12_nylon":
			material.albedo_color = Color(0.28, 0.30, 0.33)
			material.metallic = 0.0
			material.roughness = 0.68
		_:
			material.albedo_color = Color(0.2, 0.75, 0.9)
			material.metallic = 0.35
			material.roughness = 0.42
	material.rim_enabled = true
	material.rim = 0.35
	material.rim_tint = 0.5
	return material


func _on_cad_material_selected(index: int) -> void:
	var presets: Array[String] = ["anodized_blue", "alu_6061_t6", "cfrp_quasi_iso", "pa12_nylon"]
	cad_material_preset = presets[clampi(index, 0, presets.size() - 1)]
	_apply_cad_material_preset()
	status_label.text = "Display material preset: %s (display-only; exact CAD/physics unchanged)." % cad_material_preset


func _apply_cad_material_preset() -> void:
	if components == null or components.get_root() == null:
		return
	var selected: TreeItem = components.get_selected()
	var item: TreeItem = components.get_root().get_first_child()
	while item != null:
		var metadata: Variant = item.get_metadata(0)
		if metadata is Dictionary and metadata.has("marker"):
			var marker: MeshInstance3D = metadata["marker"]
			marker.material_override = _make_cad_material(item == selected)
		item = item.get_next()


func _adopt_project(next_project: Dictionary, asset_root: String) -> bool:
	return _adopt_project_with_undo(next_project, asset_root, false)


func _adopt_project_with_undo(next_project: Dictionary, asset_root: String, record_undo: bool) -> bool:
	var previous_project: Dictionary = project
	var previous_root: String = project_asset_root
	var previous_doc: String = project_document_json
	project = next_project
	project_asset_root = asset_root
	if _refresh_project():
		if record_undo and not previous_project.is_empty():
			undo_stack.append({
				"project": previous_project.duplicate(true),
				"asset_root": previous_root,
				"document_json": previous_doc,
			})
			if undo_stack.size() > 32:
				undo_stack.pop_front()
			redo_stack.clear()
		return true
	var reason: String = status_label.text
	project = previous_project
	project_asset_root = previous_root
	if not project.is_empty():
		_refresh_project()
	status_label.text = reason
	return false


func _select_component() -> void:
	var selected: TreeItem = components.get_selected()
	if selected == null or not selected.get_metadata(0) is Dictionary:
		return
	var item: TreeItem = components.get_root().get_first_child()
	while item != null:
		var metadata: Variant = item.get_metadata(0)
		if metadata is Dictionary:
			var marker: MeshInstance3D = metadata["marker"]
			marker.material_override = _make_cad_material(item == selected)
		item = item.get_next()
	var metadata: Dictionary = selected.get_metadata(0)
	if metadata.has("part"):
		var part: Dictionary = metadata["part"]
		status_label.text = "%s · mass %.3f kg · position %s m" % [part["name"], part["mass_kg"], str(part["position_m"])]
	else:
		status_label.text = "%s · CAD geometry · material and physical models require qualification" % metadata["node"]["name"]


func _apply_visual_profile() -> void:
	if world_env == null or world_env.environment == null:
		return
	var env: Environment = world_env.environment
	var has_rd: bool = RenderingServer.get_rendering_device() != null
	var effective: String = visual_profile
	if effective == "auto":
		if has_rd:
			effective = "forward_plus"
		elif OS.has_feature("mobile") or OS.has_feature("android") or OS.has_feature("ios"):
			effective = "mobile_low"
		else:
			effective = "compatibility"
	var use_forward: bool = has_rd and (effective in ["forward_plus", "forward_high"])
	if use_forward:
		var sky_mat: ProceduralSkyMaterial = ProceduralSkyMaterial.new()
		if lighting_mode == "outdoor":
			sky_mat.sky_top_color = Color(0.18, 0.42, 0.78)
			sky_mat.sky_horizon_color = Color(0.68, 0.78, 0.90)
			sky_mat.ground_bottom_color = Color(0.10, 0.14, 0.12)
			sky_mat.ground_horizon_color = Color(0.35, 0.40, 0.38)
		else:
			sky_mat.sky_top_color = Color(0.14, 0.24, 0.38)
			sky_mat.sky_horizon_color = Color(0.42, 0.52, 0.64)
			sky_mat.ground_bottom_color = Color(0.06, 0.08, 0.1)
			sky_mat.ground_horizon_color = Color(0.22, 0.26, 0.3)
		var sky: Sky = Sky.new()
		sky.sky_material = sky_mat
		env.background_mode = Environment.BG_SKY
		env.sky = sky
		env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
		env.tonemap_mode = Environment.TONE_MAPPER_ACES
		env.tonemap_exposure = 1.05
		env.glow_enabled = true
		env.glow_intensity = 0.25
		env.ssao_enabled = (effective == "forward_plus")
		if viewport != null:
			viewport.scaling_3d_scale = 1.0
			viewport.msaa_3d = Viewport.MSAA_4X if effective == "forward_plus" else Viewport.MSAA_2X
		if key_light != null:
			key_light.shadow_enabled = true
		if fill_light != null:
			fill_light.visible = true
		if visual_profile_button != null:
			visual_profile_button.text = "Visual: Forward+ Ultra" if effective == "forward_plus" else "Visual: Forward+ High"
	else:
		var is_mobile_low: bool = (effective == "mobile_low")
		env.background_mode = Environment.BG_COLOR
		env.background_color = Color(0.04, 0.065, 0.09)
		env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
		env.ambient_light_color = Color(0.7, 0.8, 1.0)
		env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
		env.glow_enabled = false
		env.ssao_enabled = false
		if viewport != null:
			viewport.scaling_3d_scale = 0.75 if is_mobile_low else 1.0
			viewport.msaa_3d = Viewport.MSAA_DISABLED if is_mobile_low else Viewport.MSAA_2X
		if key_light != null:
			key_light.shadow_enabled = false
		if fill_light != null:
			fill_light.visible = not is_mobile_low
		if visual_profile_button != null:
			visual_profile_button.text = "Visual: Mobile / Low" if is_mobile_low else "Visual: Integrated / Med"


func _toggle_lighting_mode() -> void:
	lighting_mode = "outdoor" if lighting_mode == "studio" else "studio"
	if lighting_button != null:
		lighting_button.text = "Light: Outdoor" if lighting_mode == "outdoor" else "Light: Studio"
	_apply_visual_profile()
	status_label.text = "HDRI-style lighting mode: %s (display-only; engineering unchanged)." % lighting_mode


func _cycle_visual_profile() -> void:
	var order: Array[String] = ["auto", "mobile_low", "compatibility", "forward_high", "forward_plus"]
	var idx: int = order.find(visual_profile)
	visual_profile = order[(idx + 1) % order.size()]
	_apply_visual_profile()
	status_label.text = "Visual quality preset: %s (display-only; physics/CAD unchanged)." % visual_profile


func _open_new_project_dialog() -> void:
	if job_pid > 0:
		return
	new_project_dialog.popup_centered(Vector2i(520, 240))


func _create_new_project() -> void:
	if job_pid > 0:
		return
	var fam: String = new_project_family.get_item_text(new_project_family.selected)
	var tpl: String = new_project_template.get_item_text(new_project_template.selected)
	var payload: Dictionary = {
		"name": new_project_name.text,
		"aircraft_family": fam,
		"template": tpl,
	}
	var spec_path: String = _write_payload(payload)
	var out_dir: String = ProjectSettings.globalize_path("user://projects/project-%s" % Time.get_ticks_usec())
	DirAccess.make_dir_recursive_absolute(out_dir)
	var out_project: String = out_dir.path_join("project.json")
	current_project_path = out_project
	_start_job("create", spec_path, out_project)


func _import_design() -> void:
	if job_pid > 0:
		return
	file_dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	_connect_dialog(func(path: String):
		current_project_path = ""
		_start_job("import-legacy", path))
	file_dialog.popup_centered_ratio(0.75)


func _load_reference() -> void:
	current_project_path = ""
	_start_job("import-legacy", repository_root().path_join("data/designs/quad_mn3508_6s.json"))


func _open_project() -> void:
	if job_pid > 0:
		return
	file_dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	_connect_dialog(func(path: String):
		current_project_path = path
		_start_job("validate", path))
	file_dialog.popup_centered_ratio(0.75)


func _open_blade_recipe() -> void:
	if job_pid > 0:
		return
	file_dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	_connect_dialog(func(path: String): _start_job("build-blade", path))
	file_dialog.popup_centered_ratio(0.75)


func _save_project() -> void:
	if project.is_empty() or job_pid > 0:
		return
	file_dialog.file_mode = FileDialog.FILE_MODE_SAVE_FILE
	file_dialog.current_file = "project.json"
	_connect_dialog(func(path: String):
		var snapshot: String = _write_job_input()
		current_project_path = path
		_start_job("package", snapshot, path))
	file_dialog.popup_centered_ratio(0.75)


func _save_version() -> void:
	if project.is_empty() or job_pid > 0:
		return
	var target: String = current_project_path
	if target.is_empty() and not project_asset_root.is_empty():
		target = project_asset_root.path_join("project.json")
	if target.is_empty():
		_save_project()
		return
	var snapshot: String = _write_job_input()
	if not snapshot.is_empty():
		current_project_path = target
		_start_job("save-version", snapshot, target)


func _open_versions_dialog() -> void:
	if job_pid > 0:
		return
	var probe_path: String = current_project_path
	if probe_path.is_empty() and not project_asset_root.is_empty():
		probe_path = project_asset_root.path_join("project.json")
	if probe_path.is_empty():
		status_label.text = "Save or open a project first to inspect saved versions or recovery snapshots."
		return
	_start_job("list-versions", probe_path)


func _reopen_selected_version() -> void:
	var selected: TreeItem = versions_tree.get_selected()
	if selected == null:
		return
	var rel_path: String = str(selected.get_metadata(0))
	if rel_path.is_empty():
		return
	var base_dir: String = current_project_path.get_base_dir() if not current_project_path.is_empty() else project_asset_root
	var version_path: String = base_dir.path_join(rel_path)
	_start_job("validate", version_path)


func _recover_last_valid() -> void:
	if job_pid > 0:
		return
	var probe_path: String = current_project_path
	if probe_path.is_empty():
		probe_path = last_valid_project_path
	if probe_path.is_empty() and not project_asset_root.is_empty():
		probe_path = project_asset_root.path_join("project.json")
	if probe_path.is_empty():
		status_label.text = "No saved project directory available for recovery."
		return
	_start_job("recover", probe_path)


func _connect_dialog(action: Callable) -> void:
	for connection in file_dialog.file_selected.get_connections():
		file_dialog.file_selected.disconnect(connection["callable"])
	file_dialog.file_selected.connect(action)


func _write_job_input() -> String:
	var document: String = _frozen_project_json()
	return _write_json_text(document) if not document.is_empty() else ""


func _frozen_project_json() -> String:
	if project_document_json.is_empty() or project != project_document_view:
		status_label.text = "Project needs a verified document. Reopen it or rebuild through the editor."
		return ""
	return project_document_json


func _remember_project_document(path: String) -> void:
	var document: String = FileAccess.get_file_as_string(path)
	if JSON.parse_string(document) == project:
		project_document_json = document
		project_document_view = project.duplicate(true)
	else:
		project_document_json = ""
		project_document_view = {}


func _write_payload(payload: Dictionary) -> String:
	return _write_json_text(JSON.stringify(payload, "", true, true))


func _write_json_text(document: String) -> String:
	var path: String = ProjectSettings.globalize_path("user://input-%s-%s.json" % [OS.get_process_id(), Time.get_ticks_usec()])
	var file: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		status_label.text = "Cannot write the experiment input"
		return ""
	file.store_string(document)
	file.close()
	return path


func _run_experiment() -> void:
	if project.is_empty() or job_pid > 0:
		return
	_start_job("run", _write_job_input())


func _start_job(action: String, input_path: String, output_path: String = "") -> void:
	if job_pid > 0 or input_path.is_empty():
		return
	job_action = action
	job_started_ms = Time.get_ticks_msec()
	job_uses_reusable = action in ["build-blade", "build-body", "cad-torque"]
	if job_uses_reusable:
		var submitted: Dictionary = cad_worker.submit(action, input_path, project_asset_root)
		if submitted.has("failure"):
			status_label.text = submitted["failure"]
			return
		job_pid = submitted["pid"]
		job_output = submitted["output"]
		job_error = submitted["error"]
		job_completion = submitted["completion"]
		job_started = submitted["started"]
		status_label.text = "Running %s in the isolated CAD worker…" % action
		return
	var stem: String = "user://job-%s-%s" % [OS.get_process_id(), Time.get_ticks_usec()]
	job_output = output_path if not output_path.is_empty() else ProjectSettings.globalize_path(stem + ".json")
	job_error = ProjectSettings.globalize_path(stem + "-error.json")
	job_completion = ProjectSettings.globalize_path(stem + "-complete.json")
	job_started = ProjectSettings.globalize_path(stem + "-started.json")
	var cli_action: String = "validate" if action == "edit-transform" else action
	var arguments: PackedStringArray
	if action == "clearance-check":
		job_asset_root = project_asset_root
		arguments = [
			repository_root().path_join("scripts/lab_cad_analysis.py"), input_path, job_output,
			"--clearance", "--asset-root", job_asset_root, "--error-output", job_error, "--completion-output", job_completion]
	else:
		arguments = [
			repository_root().path_join("scripts/lab_project.py"), cli_action, input_path, job_output,
			"--error-output", job_error, "--completion-output", job_completion]
		job_asset_root = project_asset_root if (action in ["package", "save-version", "edit-transform", "author-ground", "author-mission", "run-mission", "simulate", "guided-experiment", "bounded-sweep"]) else input_path.get_base_dir()
		if action in ["validate", "package", "save-version", "edit-transform"]:
			arguments.append_array(["--asset-root", job_asset_root])
		if action == "recover" and not current_project_path.is_empty():
			arguments.append_array(["--restore-to", current_project_path])
	arguments.append_array(["--started-output", job_started])
	job_pid = OS.create_process(python_command(), arguments, false)
	status_label.text = "Running %s…" % action if job_pid > 0 else "Cannot start the configured Python worker"


func _cancel_job() -> void:
	if job_pid > 0:
		if job_uses_reusable:
			if not cad_worker.stop():
				status_label.text = "CAD worker cleanup failed. The job is still tracked."
				return
			job_pid = -1
			status_label.text = "Job cancelled. The current project is available."
			return
		if OS.is_process_running(job_pid):
			if OS.get_name() == "Windows":
				# The Windows venv launcher starts a child interpreter.
				var output: Array = []
				var stopped: int = OS.execute("taskkill", ["/PID", str(job_pid), "/T", "/F"], output, true, false)
				if stopped != 0 and OS.is_process_running(job_pid):
					status_label.text = "Worker termination failed. The job is still tracked."
					return
			else:
				OS.kill(job_pid)
		job_pid = -1
		playback_state = "CANCELLED"
		status_label.text = "Job cancelled. The current project is available."


func _process(delta: float) -> void:
	var finished: bool = false
	if job_pid > 0:
		finished = (FileAccess.file_exists(job_error) or FileAccess.file_exists(job_completion) or cad_worker.has_failed()) if job_uses_reusable else not OS.is_process_running(job_pid)
	if finished:
		job_pid = -1
		if FileAccess.file_exists(job_error):
			var error: Variant = JSON.parse_string(FileAccess.get_file_as_string(job_error))
			var cat: String = str(error.get("category", "error")) if error is Dictionary else "error"
			var msg: String = str(error.get("error", "Invalid result")) if error is Dictionary else "Invalid result"
			status_label.text = "Worker refused [%s]: %s" % [cat, msg]
		elif _completed_output():
			var output: Variant = JSON.parse_string(FileAccess.get_file_as_string(job_output))
			if not output is Dictionary:
				status_label.text = "Worker returned invalid JSON"
			elif job_action == "list-versions":
				versions_tree.clear()
				var ver_root: TreeItem = versions_tree.create_item()
				var vers: Array = output.get("versions", [])
				for v in vers:
					var row: TreeItem = versions_tree.create_item(ver_root)
					row.set_text(0, str(v.get("id", "")))
					row.set_text(1, str(v.get("saved_utc", "")))
					row.set_text(2, str(v.get("project_sha256", "")).left(12))
					row.set_metadata(0, str(v.get("path", "")))
				var rec: Variant = output.get("recovery")
				versions_status.text = "%d saved version(s). Recovery snapshot: %s" % [
					vers.size(),
					str(rec.get("saved_utc", "available")) if rec is Dictionary else "none"]
				versions_dialog.popup_centered(Vector2i(620, 360))
			elif job_action == "recover":
				var rec_proj: Dictionary = output.get("project", {})
				var rec_root: String = current_project_path.get_base_dir() if not current_project_path.is_empty() else project_asset_root
				if not rec_proj.is_empty() and _adopt_project(rec_proj, rec_root):
					if not current_project_path.is_empty() and FileAccess.file_exists(current_project_path):
						_remember_project_document(current_project_path)
					else:
						project_document_json = JSON.stringify(rec_proj, "", true, true)
						project_document_view = rec_proj.duplicate(true)
					status_label.text = "Recovered last valid project (%s)." % str(output.get("project_sha256", "")).left(12)
			elif job_action == "layout-bom":
				var mp: Dictionary = output.get("mass_properties", {})
				_build_procedural_aircraft_family("multirotor_bom", output.get("rotors", []))
				metrics_label.text = "BOM (%d rotors) · Mass %.3f kg\nCoG %s m\nUnverified: %s" % [
					int(output.get("n_rotors", 0)), float(mp.get("mass_kg", 0.0)), str(mp.get("cog_m", [])), str(output.get("unverified_bom_items", []))]
				status_label.text = "Layout BOM and mass properties computed (%d BOM items; physical validation pending)." % output.get("bom", []).size()
			elif job_action == "clearance-check":
				status_label.text = "Clearance %s (min gap: %s m) · %s" % [
					str(output.get("clearance_status")), str(output.get("minimum_observed_clearance_m")), str(output.get("physical_validation_status"))]
			elif job_action == "run-mission":
				result = output
				status_label.text = "Mission completed (seed %s, sha %s) · physical validation pending." % [
					str(output.get("seed")), str(output.get("mission_sha256", "")).left(12)]
			elif job_action == "register-protocol":
				var prots: Array = output.get("protocols", [])
				var lines: Array = []
				for pr in prots:
					lines.append("%s · sha=%s · status=%s" % [str(pr.get("protocol_id")), str(pr.get("frozen_protocol_sha256", "")).left(12), str(pr.get("audit_status"))])
				protocol_report_label.text = "\n".join(lines) if not lines.is_empty() else "No protocols registered."
				protocol_dialog.popup_centered(Vector2i(620, 260))
				status_label.text = "Loaded %d frozen validation protocol(s)." % prots.size()
			elif job_action == "guided-experiment":
				var comp_s: Dictionary = output.get("comparison_summary", {})
				status_label.text = "Guided experiment completed (delta max alt: %.3f m) · %d equations shown · physical validation pending." % [
					float(comp_s.get("delta_max_altitude_m", 0.0)), output.get("equations_and_assumptions", []).size()]
			elif job_action == "bounded-sweep":
				status_label.text = "Bounded sweep %d total (%d feasible, %d failed retained, sha %s) · NOT physical validation." % [
					int(output.get("total_candidates", 0)), int(output.get("feasible_count", 0)), int(output.get("infeasible_count", 0)), str(output.get("candidates_sha256", "")).left(12)]
			elif job_action == "fixed-wing-sim":
				var m: Dictionary = output.get("mission", {})
				_build_procedural_aircraft_family("fixed_wing")
				var fwt: Dictionary = m.get("telemetry", {})
				if not fwt.get("t_s", []).is_empty():
					var fw_x: Array = []
					var fw_y: Array = []
					for idx in range(fwt["t_s"].size()):
						fw_x.append(float(idx) * 0.35)
						fw_y.append(0.0)
					result = {"result": {"status": m.get("status", "completed"), "telemetry": {
						"t": fwt["t_s"], "x": fw_x, "y": fw_y, "z": fwt["altitude_m"], "q_wxyz": []}}}
					timeline.max_value = float(fwt["t_s"][-1])
					_seek(0.0)
					_update_telemetry_plot("Fixed-Wing Altitude (m)")
				status_label.text = "Fixed-Wing VLM mission %s (verdict=%s, range=%.1f m) · physical validation pending." % [
					str(m.get("status")), str(m.get("verdict")), float(m.get("range_m", 0.0))]
			elif job_action == "export-drawing":
				var outs: Dictionary = output.get("outputs", {})
				status_label.text = "2D Orthographic Drawings exported (SVG + DXF) · MAC=%.3f m" % float(output.get("mean_aerodynamic_chord_m", 0.0))
				if blueprint_canvas != null:
					blueprint_canvas.part_title = "%s | DXF+SVG Exported" % str(output.get("part_name", "Wing"))
					blueprint_canvas.queue_redraw()
			elif job_action == "vtol-transition":
				_build_procedural_aircraft_family("vtol")
				var vs: Array = output.get("samples", [])
				if not vs.is_empty():
					var vt: Array = []
					var vx: Array = []
					var vy: Array = []
					var vz: Array = []
					var vq: Array = []
					for s_idx in range(vs.size()):
						vt.append(float(vs[s_idx]["t_s"]))
						vx.append(float(s_idx) * 0.45)
						vy.append(0.0)
						vz.append(12.0 + 0.04 * float(s_idx))
						vq.append([1.0, 0.0, 0.0, 0.0])
					result = {"result": {"status": output.get("status", "completed"), "samples": vs, "telemetry": {
						"t": vt, "x": vx, "y": vy, "z": vz, "q_wxyz": vq}}}
					timeline.max_value = float(vt[-1])
					_seek(0.0)
				status_label.text = "VTOL transition %s (peak temp=%.1f C, verdict=%s) · physical validation pending." % [
					str(output.get("status")), float(output.get("peak_motor_temp_c", 0.0)), str(output.get("verdict"))]
			elif job_action == "autorotation-sim":
				_build_procedural_aircraft_family("helicopter")
				var ht: Dictionary = output.get("telemetry", {})
				if not ht.get("t", []).is_empty():
					result = {"result": {"status": output.get("status", "completed"), "telemetry": ht}}
					timeline.max_value = float(ht["t"][-1])
					_seek(0.0)
				status_label.text = "Helicopter autorotation %s (sink=%.2f m/s, min RPM=%.0f, verdict=%s) · physical validation pending." % [
					str(output.get("status")), float(output.get("touchdown_sink_m_s", 0.0)), float(output.get("min_observed_rpm", 0.0)), str(output.get("verdict"))]
			elif job_action == "sitl-mission":
				status_label.text = "SITL %s (%d waypoints, mean EKF err=%.3f m, clearance=%.2f m, verdict=%s) · SYNTHETIC." % [
					str(output.get("firmware_kind")), int(output.get("waypoint_count", 0)), float(output.get("mean_ekf_position_error_m", 0.0)), float(output.get("min_lidar_clearance_m", 0.0)), str(output.get("verdict"))]
			elif job_action == "adverse-weather":
				var r: Dictionary = output.get("rain", {})
				var i_res: Dictionary = output.get("icing", {})
				status_label.text = "Weather: wet CL_max=%.2f (%s), ice=%.4f kg (%s)." % [
					float(r.get("wet_cl_max", 0.0)), str(r.get("status")), float(i_res.get("accreted_mass_kg", 0.0)), str(i_res.get("verdict", "OK"))]
			elif job_action == "swarm-sim":
				var traj_t: Array = output.get("trajectory_t_s", [])
				var traj_pos: Array = output.get("trajectory_positions_m", [])
				_build_procedural_aircraft_family("swarm", traj_pos[0] if not traj_pos.is_empty() else [])
				if not traj_t.is_empty() and traj_pos.size() == traj_t.size():
					var sx: Array = []
					var sy: Array = []
					var sz: Array = []
					for _k in range(traj_t.size()):
						sx.append(0.0)
						sy.append(0.0)
						sz.append(0.0)
					result = {"result": {"status": output.get("status", "completed"), "swarm_positions": traj_pos, "telemetry": {
						"t": traj_t, "x": sx, "y": sy, "z": sz, "q_wxyz": []}}}
					timeline.max_value = float(traj_t[-1])
					_seek(0.0)
				status_label.text = "Swarm (%d drones): %s (min sep=%.2f m) · physical validation pending." % [
					int(output.get("agent_count", 0)), str(output.get("status")), float(output.get("min_observed_separation_m", 0.0))]
			elif job_action == "run" or job_action == "cad-torque" or job_action == "simulate":
				result = output
				replay_time = 0.0
				playing = false
				var run_status: String = str(result.get("result", {}).get("status", "failed"))
				playback_state = "FAILED" if run_status == "failed" else "COMPLETED"
				timeline.set_value_no_signal(0.0)
				if job_action == "cad-torque":
					_show_cad_properties(output["mass_properties"])
				var telemetry: Variant = result.get("result", {}).get("telemetry")
				if telemetry is Dictionary and telemetry.get("t", []).size() > 0:
					timeline.max_value = float(telemetry["t"][-1])
					_seek(0)
					_update_telemetry_plot("6-DoF Trajectory (Altitude m · Bus Voltage V)")
					status_label.text = "Experiment %s (%s) · %.2f seconds · physical validation pending" % [
					run_status, playback_state,
					(Time.get_ticks_msec() - job_started_ms) / 1000.0]
				else:
					playback_state = "FAILED"
					status_label.text = "Inconclusive: " + str(result.get("result", {}).get("reason", "No trajectory returned"))
			else:
				var next_project: Dictionary
				var next_root: String
				if job_action == "build-blade" or job_action == "build-body":
					next_project = output["project"]
					next_root = str(output["project_path"]).get_base_dir()
				else:
					next_project = output
					next_root = job_output.get_base_dir() if (job_action == "package" or job_action == "save-version" or job_action == "create") else job_asset_root
				if (job_action == "package" or job_action == "save-version") and next_project == project:
					# Saving verified copies does not change the experiment's inputs.
					project_asset_root = next_root
					last_valid_project_path = job_output
					_remember_project_document(job_output)
					status_label.text = "Project version saved. Geometry asset checks passed." if job_action == "save-version" else "Project saved. Geometry asset checks passed."
				elif _adopt_project_with_undo(next_project, next_root, job_action in ["build-blade", "build-body", "edit-transform"]):
					var doc_path: String = str(output["project_path"]) if job_action.begins_with("build-") else job_output
					_remember_project_document(doc_path)
					if job_action in ["create", "validate", "package", "save-version"]:
						last_valid_project_path = doc_path
						if current_project_path.is_empty():
							current_project_path = doc_path
					status_label.text = "Geometry rebuilt. Physical validation pending." if job_action.begins_with("build-") else "Project opened. Document and asset checks passed."
					if output.has("geometry"):
						_show_cad_properties(output["geometry"]["mass_properties"])
		else:
			status_label.text = cad_worker.failure_reason() if job_uses_reusable else "Worker ended without a result. Check LAB_PYTHON and backend dependencies."
	if job_pid < 0 and cad_worker != null and cad_worker.get("pid") > 0 and Time.get_ticks_msec() - last_worker_check_ms > 1000:
		last_worker_check_ms = Time.get_ticks_msec()
		if cad_worker.has_failed():
			cad_worker.stop()
	if playing and not result.is_empty():
		replay_time = minf(replay_time + delta, timeline.max_value)
		timeline.set_value_no_signal(replay_time)
		_seek(replay_time)
		if replay_time >= timeline.max_value:
			playing = false
	hud_timer += delta
	if hud_timer >= 0.25 and viewport_hud_label != null:
		hud_timer = 0.0
		var fps_val: float = Engine.get_frames_per_second()
		var ms_val: float = 1000.0 / maxf(1.0, fps_val)
		var tier_txt: String = visual_profile_button.text if visual_profile_button != null else visual_profile
		viewport_hud_label.text = "FPS: %.1f (%.1f ms) | %s | UNVALIDATED\n%s" % [
			fps_val, ms_val, tier_txt, metrics_label.text.replace("\n", " · ")]
	if not capture_path.is_empty() and not project.is_empty():
		capture_frames += 1
		if capture_frames == 22 and not capture_view.is_empty():
			if capture_view == "flow":
				_run_native_cpp_rk4()
				_update_telemetry_plot("6-DoF Trajectory (Altitude m)")
				ribbon_tabs.current_tab = 3
				show_flow_overlay = true
				_toggle_stress_map()
			elif capture_view == "blueprint":
				ribbon_tabs.current_tab = 2
			elif capture_view == "rotor_flow":
				_run_native_cpp_rk4()
				_update_telemetry_plot("Quadcopter Rotor Downwash + 6-DoF Telemetry")
				ribbon_tabs.current_tab = 3
				_toggle_flow_overlay()
		if capture_frames == 30:
			await RenderingServer.frame_post_draw
			get_viewport().get_texture().get_image().save_png(capture_path)
			get_tree().quit()


func _update_telemetry_plot(title_str: String = "Flight Telemetry (Altitude m · Bus Voltage V)") -> void:
	if telemetry_plot == null:
		return
	var tel: Variant = result.get("result", {}).get("telemetry")
	if tel is Dictionary:
		telemetry_plot.label_title = title_str
		telemetry_plot.series_t = tel.get("t", [])
		telemetry_plot.series_z = tel.get("z", [])
		telemetry_plot.series_v = tel.get("v_bus_v", [])
		telemetry_plot.queue_redraw()


func _completed_output() -> bool:
	if job_uses_reusable:
		return cad_worker.completed_output(job_completion)
	if not FileAccess.file_exists(job_output) or not FileAccess.file_exists(job_completion):
		return false
	var receipt: Variant = JSON.parse_string(FileAccess.get_file_as_string(job_completion))
	return receipt is Dictionary and receipt.get("output_sha256") == FileAccess.get_sha256(job_output)


func _show_cad_properties(properties: Dictionary) -> void:
	if properties.get("mass_kg") == null:
		metrics_label.text = "Uniform density missing.\nMass and inertia are unknown."
	else:
		var tensor: Array = properties["inertia_about_cog_kg_m2"]
		var center: Array = properties["center_of_mass_m"]
		metrics_label.text = "Uniform-density estimate\nMass %.6f kg\nCoG [%.4f, %.4f, %.4f] m\nCentral inertia diagonal\n[%.7f, %.7f, %.7f] kg·m²" % [
			properties["mass_kg"], center[0], center[1], center[2], tensor[0][0], tensor[1][1], tensor[2][2]]
	scope_label.text = "Rigid-body mathematics · assumed uniform density · physical validation pending"


func _seek(time_s: float) -> void:
	replay_time = time_s
	var telemetry: Variant = result.get("result", {}).get("telemetry")
	if not telemetry is Dictionary or telemetry.get("t", []).is_empty():
		return
	var times: Array = telemetry["t"]
	var index: int = 0
	while index + 1 < times.size() and float(times[index + 1]) <= time_s:
		index += 1
	var next: int = mini(index + 1, times.size() - 1)
	var fraction: float = 0.0
	if next != index:
		fraction = (time_s - float(times[index])) / (float(times[next]) - float(times[index]))
	var first: Vector3 = Vector3(float(telemetry["x"][index]), float(telemetry["z"][index]),
		-float(telemetry["y"][index]))
	var second: Vector3 = Vector3(float(telemetry["x"][next]), float(telemetry["z"][next]),
		-float(telemetry["y"][next]))
	aircraft.position = first.lerp(second, fraction)
	var attitudes: Array = telemetry.get("q_wxyz", [])
	if attitudes.size() == times.size():
		var q0: Array = attitudes[index]
		var q1: Array = attitudes[next]
		var rotation0: Quaternion = Quaternion(float(q0[1]), float(q0[3]), -float(q0[2]), float(q0[0])).normalized()
		var rotation1: Quaternion = Quaternion(float(q1[1]), float(q1[3]), -float(q1[2]), float(q1[0])).normalized()
		aircraft.quaternion = rotation0.slerp(rotation1, fraction)
	if result.get("experiment_kind") == "cad_torque_1":
		# The rigid-body state is at its CoG; the CAD mesh retains its original datum.
		aircraft.position -= aircraft.quaternion * _scene_position(result["mass_properties"]["center_of_mass_m"])
	var v_samples: Array = result.get("result", {}).get("samples", [])
	if v_samples.size() == times.size():
		var tilt_deg: float = float(v_samples[index].get("tilt_deg", 90.0))
		for nac_name in ["nacelle_left", "nacelle_right"]:
			var nac: Node = aircraft.find_child(nac_name, true, false)
			if nac is Node3D:
				(nac as Node3D).rotation_degrees = Vector3(0.0, 0.0, -(90.0 - tilt_deg))
	var swarm_frames: Array = result.get("result", {}).get("swarm_positions", [])
	if swarm_frames.size() == times.size():
		var f0: Array = swarm_frames[index]
		var f1: Array = swarm_frames[next]
		for a_idx in range(f0.size()):
			var ag_node: Node = aircraft.find_child("swarm_agent_%d" % a_idx, true, false)
			if ag_node is Node3D:
				var p0: Vector3 = _scene_position(f0[a_idx])
				var p1: Vector3 = _scene_position(f1[a_idx])
				(ag_node as Node3D).position = p0.lerp(p1, fraction)
	_update_camera()


func _build_procedural_aircraft_family(family: String, extra_items: Array = []) -> void:
	for child in aircraft.get_children():
		aircraft.remove_child(child)
		child.queue_free()
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.24, 0.62, 0.92)
	mat.metallic = 0.25
	mat.roughness = 0.35
	var accent := StandardMaterial3D.new()
	accent.albedo_color = Color(0.95, 0.55, 0.15)
	var wing_mat := StandardMaterial3D.new()
	wing_mat.albedo_color = Color(0.84, 0.88, 0.92)
	wing_mat.metallic = 0.15
	wing_mat.roughness = 0.32
	if show_stress_map:
		wing_mat.vertex_color_use_as_albedo = true
	var blade_mat := StandardMaterial3D.new()
	blade_mat.albedo_color = Color(0.14, 0.16, 0.20)
	blade_mat.metallic = 0.30
	blade_mat.roughness = 0.35
	last_rotor_scene_positions.clear()
	if family == "multirotor_bom":
		var hub := MeshInstance3D.new()
		var hub_m := BoxMesh.new()
		hub_m.size = Vector3(0.22, 0.04, 0.22)
		hub.mesh = hub_m
		hub.material_override = mat
		aircraft.add_child(hub)
		for r_entry in extra_items:
			if r_entry is Dictionary:
				var rp: Vector3 = _scene_position(r_entry.get("position_m", [0.0, 0.0, 0.0]))
				last_rotor_scene_positions.append(rp)
				var blade := MeshInstance3D.new()
				blade.mesh = WorkbenchMeshes.build_twisted_blade_mesh(0.18, 0.032, 0.014, 2, int(r_entry.get("spin_direction", 1)))
				blade.position = rp + Vector3(0.0, 0.02, 0.0)
				blade.material_override = blade_mat
				aircraft.add_child(blade)
	elif family == "fixed_wing":
		var fuse := MeshInstance3D.new()
		fuse.mesh = WorkbenchMeshes.build_streamlined_fuselage_mesh(1.05, 0.075)
		fuse.material_override = wing_mat
		aircraft.add_child(fuse)
		var wing := MeshInstance3D.new()
		wing.mesh = WorkbenchMeshes.build_lofted_wing_mesh(1.80, 0.26, 0.14, 5.0, 3.0, show_stress_map)
		wing.material_override = wing_mat
		aircraft.add_child(wing)
		var push_prop := MeshInstance3D.new()
		push_prop.mesh = WorkbenchMeshes.build_twisted_blade_mesh(0.14, 0.028, 0.012, 2, 1)
		push_prop.rotation_degrees = Vector3(0.0, 0.0, 90.0)
		push_prop.position = Vector3(-0.62, 0.0, 0.0)
		push_prop.material_override = blade_mat
		aircraft.add_child(push_prop)
	elif family == "vtol":
		var v_fuse := MeshInstance3D.new()
		v_fuse.mesh = WorkbenchMeshes.build_streamlined_fuselage_mesh(1.10, 0.085)
		v_fuse.material_override = wing_mat
		aircraft.add_child(v_fuse)
		var v_wing := MeshInstance3D.new()
		v_wing.mesh = WorkbenchMeshes.build_lofted_wing_mesh(1.75, 0.26, 0.16, 3.0, 2.0, show_stress_map)
		v_wing.material_override = wing_mat
		aircraft.add_child(v_wing)
		for side in [-1.0, 1.0]:
			var nac := MeshInstance3D.new()
			nac.name = "nacelle_left" if side < 0 else "nacelle_right"
			var nac_m := CylinderMesh.new()
			nac_m.top_radius = 0.042
			nac_m.bottom_radius = 0.042
			nac_m.height = 0.22
			nac.mesh = nac_m
			nac.position = Vector3(0.12, 0.06, side * 0.78)
			nac.material_override = accent
			var nac_prop := MeshInstance3D.new()
			nac_prop.mesh = WorkbenchMeshes.build_twisted_blade_mesh(0.20, 0.032, 0.014, 3, int(side))
			nac_prop.position = Vector3(0.0, 0.12, 0.0)
			nac_prop.material_override = blade_mat
			nac.add_child(nac_prop)
			aircraft.add_child(nac)
			last_rotor_scene_positions.append(nac.position)
	elif family == "helicopter":
		var h_fuse := MeshInstance3D.new()
		h_fuse.mesh = WorkbenchMeshes.build_streamlined_fuselage_mesh(1.35, 0.10)
		h_fuse.material_override = mat
		aircraft.add_child(h_fuse)
		var main_rotor := MeshInstance3D.new()
		main_rotor.mesh = WorkbenchMeshes.build_twisted_blade_mesh(0.72, 0.055, 0.035, 2, 1)
		main_rotor.position = Vector3(0.0, 0.16, 0.0)
		main_rotor.material_override = blade_mat
		aircraft.add_child(main_rotor)
		last_rotor_scene_positions.append(main_rotor.position)
	elif family == "swarm":
		var offsets: Array = extra_items if not extra_items.is_empty() else [[-0.6, -0.6, 0.0], [-0.6, 0.6, 0.0], [0.6, -0.6, 0.0], [0.6, 0.6, 0.0]]
		for s_i in range(offsets.size()):
			var agent := MeshInstance3D.new()
			agent.name = "swarm_agent_%d" % s_i
			var ag_m := SphereMesh.new()
			ag_m.radius = 0.11
			ag_m.height = 0.11
			agent.mesh = ag_m
			agent.position = _scene_position(offsets[s_i])
			agent.material_override = accent
			aircraft.add_child(agent)
	_rebuild_viewport_overlays(Vector3.ZERO, family in ["fixed_wing", "vtol"])
	_fit_camera()


func _on_ribbon_tab_changed(tab_idx: int) -> void:
	for i in range(ribbon_panels.size()):
		ribbon_panels[i].visible = (i == tab_idx)
	_toggle_blueprint_view(tab_idx == 2)


func _toggle_blueprint_view(show_sheet: bool) -> void:
	if blueprint_canvas != null and viewport_container != null:
		blueprint_canvas.visible = show_sheet
		viewport_container.visible = not show_sheet
		if show_sheet:
			blueprint_canvas.queue_redraw()


func _toggle_blueprint_balloons() -> void:
	if blueprint_canvas != null:
		blueprint_canvas.show_balloons = not blueprint_canvas.show_balloons
		blueprint_canvas.queue_redraw()


func _export_active_drawing() -> void:
	if job_pid > 0:
		return
	var out_dir: String = ProjectSettings.globalize_path("user://drawings")
	DirAccess.make_dir_recursive_absolute(out_dir)
	var svg_p: String = out_dir.path_join("wing_blueprint.svg")
	var dxf_p: String = out_dir.path_join("wing_blueprint.dxf")
	_start_job("export-drawing", _write_payload({"name": "AerodynamicsLab-Wing", "wingspan_m": 1.80, "svg_path": svg_p, "dxf_path": dxf_p}))


func _toggle_inertia_rings() -> void:
	show_inertia_rings = not show_inertia_rings
	_rebuild_viewport_overlays(Vector3.ZERO, false)


func _toggle_flow_overlay() -> void:
	show_flow_overlay = not show_flow_overlay
	_rebuild_viewport_overlays(Vector3.ZERO, false)


func _toggle_stress_map() -> void:
	show_stress_map = not show_stress_map
	if colorbar_legend != null:
		colorbar_legend.visible = show_flow_overlay or show_stress_map
		colorbar_legend.title_text = "Wing Bending Stress (MPa)" if show_stress_map else "Airflow Velocity (m/s)"
		colorbar_legend.min_label = "0.0"
		colorbar_legend.max_label = "185" if show_stress_map else "24.0"
		colorbar_legend.queue_redraw()
	_build_procedural_aircraft_family("fixed_wing")


func _snap_view(new_yaw: float, new_elev: float) -> void:
	yaw = new_yaw
	elevation = new_elev
	_update_camera()


func _rebuild_viewport_overlays(cog_pos: Vector3, is_fixed_wing: bool = false) -> void:
	if overlay_group != null and is_instance_valid(overlay_group):
		overlay_group.queue_free()
	overlay_group = Node3D.new()
	aircraft.add_child(overlay_group)
	if show_inertia_rings:
		overlay_group.add_child(WorkbenchMeshes.build_inertia_rings_overlay(cog_pos))
	if show_flow_overlay:
		overlay_group.add_child(WorkbenchMeshes.build_flow_streamlines(last_rotor_scene_positions, is_fixed_wing))
	if colorbar_legend != null:
		colorbar_legend.visible = show_flow_overlay or show_stress_map
		if colorbar_legend.visible:
			colorbar_legend.queue_redraw()


func _exit_tree() -> void:
	if job_pid > 0 and OS.is_process_running(job_pid):
		_cancel_job()
	if cad_worker != null:
		cad_worker.stop()
