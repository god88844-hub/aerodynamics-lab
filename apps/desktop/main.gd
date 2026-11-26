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
var world_env: WorldEnvironment
var key_light: DirectionalLight3D
var fill_light: DirectionalLight3D
var current_project_path: String = ""
var last_valid_project_path: String = ""
var qualification_orbit_left: bool = false
var qualification_started_usec: int = 0
var qualification_events: Array = []


func repository_root() -> String:
	return ProjectSettings.globalize_path("res://").trim_suffix("/").get_base_dir().get_base_dir()


func python_command() -> String:
	var configured: String = OS.get_environment("LAB_PYTHON")
	return configured if not configured.is_empty() else "python"


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
		margin.add_theme_constant_override("margin_" + side, 16)
	add_child(margin)
	var layout: VBoxContainer = VBoxContainer.new()
	layout.add_theme_constant_override("separation", 12)
	margin.add_child(layout)
	var title: Label = Label.new()
	title.text = "Aerodynamics Lab"
	title.add_theme_font_size_override("font_size", 26)
	layout.add_child(title)
	project_label = Label.new()
	project_label.text = "Desktop foundation prototype"
	layout.add_child(project_label)
	var toolbar: HFlowContainer = HFlowContainer.new()
	layout.add_child(toolbar)
	_add_button(toolbar, "New project", _open_new_project_dialog)
	_add_button(toolbar, "Import design", _import_design)
	_add_button(toolbar, "Load reference", _load_reference)
	_add_button(toolbar, "Open project", _open_project)
	_add_button(toolbar, "Save project", _save_project)
	_add_button(toolbar, "Save version", _save_version)
	_add_button(toolbar, "Versions / Recover", _open_versions_dialog)
	_add_button(toolbar, "Run reference experiment", _run_experiment)
	_add_button(toolbar, "Cancel job", _cancel_job)
	_add_button(toolbar, "Build blade example", func():
		_start_job("build-blade", repository_root().path_join("data/cad/blade-example.json")))
	_add_button(toolbar, "Build blade recipe", _open_blade_recipe)
	_add_button(toolbar, "New / edit test body", _open_body_editor)
	_add_button(toolbar, "Run applied-torque experiment", _run_cad_torque)
	_add_button(toolbar, "Worker limits", _open_limits)
	visual_profile_button = Button.new()
	visual_profile_button.text = "Visual: Auto"
	visual_profile_button.pressed.connect(_cycle_visual_profile)
	toolbar.add_child(visual_profile_button)
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
	var viewport_container: SubViewportContainer = SubViewportContainer.new()
	viewport_container.stretch = true
	viewport_container.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	viewport_container.mouse_filter = Control.MOUSE_FILTER_STOP
	viewport_container.gui_input.connect(_viewport_input)
	split.add_child(viewport_container)
	viewport = SubViewport.new()
	viewport.size = Vector2i(900, 500)
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	viewport.own_world_3d = true
	viewport_container.add_child(viewport)
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
	ground_mesh.size = Vector2(8, 8)
	ground.mesh = ground_mesh
	var ground_material: StandardMaterial3D = StandardMaterial3D.new()
	ground_material.albedo_color = Color(0.11, 0.16, 0.2)
	ground_material.roughness = 0.85
	ground_material.metallic = 0.05
	ground.material_override = ground_material
	ground.position.y = -0.12
	world.add_child(ground)
	var replay: HBoxContainer = HBoxContainer.new()
	layout.add_child(replay)
	_add_button(replay, "Play / pause", func(): playing = not playing)
	timeline = HSlider.new()
	timeline.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	timeline.step = 0.001
	timeline.value_changed.connect(_seek)
	replay.add_child(timeline)
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
		scope_label.text = "CAD geometry · physical validation pending"
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
	var properties: Dictionary = engineering.mass_properties(parts)
	if properties["ok"]:
		metrics_label.text = "Native C++ mass %.3f kg\nCoG %s m" % [
			properties["mass_kg"], str(properties["center_of_mass_m"])]
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


func _display_mesh(asset: Dictionary) -> MeshInstance3D:
	if asset.get("role") != "display_mesh":
		status_label.text = "This geometry needs a display-mesh adapter."
		return null
	var path: String = project_asset_root.path_join(asset["path"])
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if file == null or file.get_length() > 16 * 1024 * 1024:
		status_label.text = "Display mesh is missing or exceeds the prototype's 16 MiB limit."
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
		status_label.text = "Display mesh is empty or exceeds the prototype triangle limit."
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
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_color = Color(0.2, 0.75, 0.9)
	material.metallic = 0.35
	material.roughness = 0.42
	marker.material_override = material
	return marker


func _adopt_project(next_project: Dictionary, asset_root: String) -> bool:
	var previous_project: Dictionary = project
	var previous_root: String = project_asset_root
	project = next_project
	project_asset_root = asset_root
	if _refresh_project():
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
			marker.material_override.albedo_color = Color(1.0, 0.7, 0.25) if item == selected else Color(0.2, 0.75, 0.9)
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
	var use_pbr: bool = (visual_profile == "forward_plus") or (visual_profile == "auto" and has_rd)
	if use_pbr and has_rd:
		var sky_mat: ProceduralSkyMaterial = ProceduralSkyMaterial.new()
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
		env.ssao_enabled = true
		if key_light != null:
			key_light.shadow_enabled = true
		if fill_light != null:
			fill_light.visible = true
		if visual_profile_button != null:
			visual_profile_button.text = "Visual: Forward+ PBR"
	else:
		env.background_mode = Environment.BG_COLOR
		env.background_color = Color(0.04, 0.065, 0.09)
		env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
		env.ambient_light_color = Color(0.7, 0.8, 1.0)
		env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
		env.glow_enabled = false
		env.ssao_enabled = false
		if key_light != null:
			key_light.shadow_enabled = false
		if fill_light != null:
			fill_light.visible = true
		if visual_profile_button != null:
			visual_profile_button.text = "Visual: Compatibility"


func _cycle_visual_profile() -> void:
	if visual_profile == "auto":
		visual_profile = "compatibility"
	elif visual_profile == "compatibility":
		visual_profile = "forward_plus"
	else:
		visual_profile = "auto"
	_apply_visual_profile()
	status_label.text = "Visual profile set to %s (display-only; physics/CAD unchanged)." % visual_profile


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
	var arguments: PackedStringArray = [
		repository_root().path_join("scripts/lab_project.py"), action, input_path, job_output,
		"--error-output", job_error, "--completion-output", job_completion]
	job_asset_root = project_asset_root if (action == "package" or action == "save-version") else input_path.get_base_dir()
	if action == "validate" or action == "package" or action == "save-version":
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
			elif job_action == "run" or job_action == "cad-torque":
				result = output
				replay_time = 0.0
				playing = false
				timeline.set_value_no_signal(0.0)
				if job_action == "cad-torque":
					_show_cad_properties(output["mass_properties"])
				var telemetry: Variant = result.get("result", {}).get("telemetry")
				if telemetry is Dictionary and telemetry.get("t", []).size() > 0:
					timeline.max_value = float(telemetry["t"][-1])
					_seek(0)
					status_label.text = "Experiment %s · %.2f seconds · physical validation pending" % [
					result.get("result", {}).get("status", "failed"),
					(Time.get_ticks_msec() - job_started_ms) / 1000.0]
				else:
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
				elif _adopt_project(next_project, next_root):
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
	if not capture_path.is_empty() and not project.is_empty():
		capture_frames += 1
		if capture_frames == 30:
			await RenderingServer.frame_post_draw
			get_viewport().get_texture().get_image().save_png(capture_path)
			get_tree().quit()


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
		var rotation0: Quaternion = Quaternion(float(q0[1]), float(q0[3]), -float(q0[2]), float(q0[0]))
		var rotation1: Quaternion = Quaternion(float(q1[1]), float(q1[3]), -float(q1[2]), float(q1[0]))
		aircraft.quaternion = rotation0.slerp(rotation1, fraction)
	if result.get("experiment_kind") == "cad_torque_1":
		# The rigid-body state is at its CoG; the CAD mesh retains its original datum.
		aircraft.position -= aircraft.quaternion * _scene_position(result["mass_properties"]["center_of_mass_m"])
	_update_camera()


func _exit_tree() -> void:
	if job_pid > 0 and OS.is_process_running(job_pid):
		_cancel_job()
	if cad_worker != null:
		cad_worker.stop()
