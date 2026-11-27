extends RefCounted
class_name WorkbenchMeshes


static func naca4_profile(code: String = "2412", n_pts: int = 18) -> Array[Vector2]:
	var m: float = float(code.substr(0, 1).to_int()) / 100.0
	var p: float = float(code.substr(1, 1).to_int()) / 10.0
	var t: float = float(code.substr(2, 2).to_int()) / 100.0
	var upper: Array[Vector2] = []
	var lower: Array[Vector2] = []
	for i in range(n_pts):
		var beta: float = PI * float(i) / float(n_pts - 1)
		var x: float = 0.5 * (1.0 - cos(beta))
		var yt: float = 5.0 * t * (0.2969 * sqrt(maxf(0.0, x)) - 0.1260 * x - 0.3516 * x * x + 0.2843 * pow(x, 3) - 0.1036 * pow(x, 4))
		var yc: float = 0.0
		var dyc: float = 0.0
		if m > 0.0 and p > 0.0 and p < 1.0:
			if x < p:
				yc = (m / (p * p)) * (2.0 * p * x - x * x)
				dyc = (2.0 * m / (p * p)) * (p - x)
			else:
				yc = (m / pow(1.0 - p, 2.0)) * ((1.0 - 2.0 * p) + 2.0 * p * x - x * x)
				dyc = (2.0 * m / pow(1.0 - p, 2.0)) * (p - x)
		var theta: float = atan(dyc)
		upper.append(Vector2(x - yt * sin(theta), yc + yt * cos(theta)))
		lower.append(Vector2(x + yt * sin(theta), yc - yt * cos(theta)))
	var closed: Array[Vector2] = []
	for idx in range(upper.size() - 1, -1, -1):
		closed.append(upper[idx])
	for idx in range(1, lower.size()):
		closed.append(lower[idx])
	return closed


static func build_cad_grid_and_axes(extent_m: float = 6.0, step_m: float = 0.5, dark_mode: bool = true) -> Node3D:
	var group := Node3D.new()
	group.name = "cad_reference_grid"
	var im := ImmediateMesh.new()
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.vertex_color_use_as_albedo = true
	im.surface_begin(Mesh.PRIMITIVE_LINES, mat)
	var minor_col := Color(0.20, 0.26, 0.33, 0.55) if dark_mode else Color(0.72, 0.76, 0.80, 0.7)
	var major_col := Color(0.32, 0.42, 0.54, 0.85) if dark_mode else Color(0.52, 0.58, 0.64, 0.9)
	var n_lines: int = int(round(extent_m / step_m))
	for i in range(-n_lines, n_lines + 1):
		var c: float = float(i) * step_m
		var col: Color = major_col if (i % 2 == 0) else minor_col
		if i != 0:
			im.surface_set_color(col)
			im.surface_add_vertex(Vector3(-extent_m, 0.0, c))
			im.surface_add_vertex(Vector3(extent_m, 0.0, c))
			im.surface_add_vertex(Vector3(c, 0.0, -extent_m))
			im.surface_add_vertex(Vector3(c, 0.0, extent_m))
	# Origin axes (AeroForge Z-up mapped to Godot X=Fwd, Y=Up, Z=-Left)
	im.surface_set_color(Color(0.92, 0.28, 0.28))
	im.surface_add_vertex(Vector3(-extent_m, 0.002, 0.0))
	im.surface_add_vertex(Vector3(extent_m, 0.002, 0.0))
	im.surface_set_color(Color(0.28, 0.85, 0.38))
	im.surface_add_vertex(Vector3(0.0, 0.002, -extent_m))
	im.surface_add_vertex(Vector3(0.0, 0.002, extent_m))
	im.surface_set_color(Color(0.30, 0.60, 0.98))
	im.surface_add_vertex(Vector3(0.0, 0.0, 0.0))
	im.surface_add_vertex(Vector3(0.0, 1.2, 0.0))
	im.surface_end()
	var grid_inst := MeshInstance3D.new()
	grid_inst.mesh = im
	grid_inst.position.y = -0.115
	group.add_child(grid_inst)
	return group


static func build_twisted_blade_mesh(radius_m: float = 0.19, root_chord_m: float = 0.032, tip_chord_m: float = 0.015, n_blades: int = 2, spin_dir: int = 1) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var prof: Array[Vector2] = naca4_profile("2412", 12)
	var n_p: int = prof.size()
	var n_span: int = 7
	var r0: float = 0.020
	for b_idx in range(n_blades):
		var az0: float = TAU * float(b_idx) / float(n_blades)
		var rings: Array = []
		for s in range(n_span):
			var frac: float = float(s) / float(n_span - 1)
			var r: float = lerpf(r0, radius_m, frac)
			var chord: float = lerpf(root_chord_m, tip_chord_m, frac) * (1.0 - 0.18 * frac * frac)
			var twist: float = deg_to_rad(lerpf(24.0, 7.0, frac)) * float(spin_dir)
			var ct: float = cos(twist)
			var stw: float = sin(twist)
			var ca: float = cos(az0)
			var sa: float = sin(az0)
			var ring: Array[Vector3] = []
			for pt in prof:
				var px: float = (pt.x - 0.25) * chord
				var py: float = pt.y * chord
				# Local chord along tangent + vertical thickness, then rotate by azimuth around Y up
				var rx: float = px * ct - py * stw
				var ry: float = px * stw + py * ct
				var wx: float = r * ca - rx * sa
				var wz: float = r * sa + rx * ca
				ring.append(Vector3(wx, ry, wz))
			rings.append(ring)
		for s in range(n_span - 1):
			var a: Array[Vector3] = rings[s]
			var b: Array[Vector3] = rings[s + 1]
			for k in range(n_p):
				var kn: int = (k + 1) % n_p
				st.add_vertex(a[k])
				st.add_vertex(b[k])
				st.add_vertex(b[kn])
				st.add_vertex(a[k])
				st.add_vertex(b[kn])
				st.add_vertex(a[kn])
	st.generate_normals()
	return st.commit()


static func build_lofted_wing_mesh(wingspan_m: float = 1.80, root_chord_m: float = 0.26, tip_chord_m: float = 0.14, sweep_deg: float = 5.0, dihedral_deg: float = 3.0, stress_colormap: bool = false) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var prof: Array[Vector2] = naca4_profile("2412", 14)
	var n_p: int = prof.size()
	var n_half: int = 8
	var half_b: float = 0.5 * wingspan_m
	for side in [-1.0, 1.0]:
		var rings: Array = []
		var cols: Array[Color] = []
		for s in range(n_half):
			var eta: float = float(s) / float(n_half - 1)
			var z_span: float = side * eta * half_b
			var x_le: float = -eta * half_b * tan(deg_to_rad(sweep_deg))
			var y_dih: float = eta * half_b * tan(deg_to_rad(dihedral_deg))
			# Winglet upward flare on final station
			if s == n_half - 1:
				y_dih += 0.08
				x_le -= 0.04
			var chord: float = lerpf(root_chord_m, tip_chord_m, eta)
			# Structural root bending stress ~ (1 - eta)^2 (Onshape FEA style: root red -> tip blue)
			var stress_t: float = clampf(pow(1.0 - eta, 1.5), 0.0, 1.0)
			cols.append(_jet_color(stress_t))
			var ring: Array[Vector3] = []
			for pt in prof:
				var vx: float = x_le - pt.x * chord + 0.12
				var vy: float = y_dih + pt.y * chord
				ring.append(Vector3(vx, vy, z_span))
			rings.append(ring)
		for s in range(n_half - 1):
			var a: Array[Vector3] = rings[s]
			var b: Array[Vector3] = rings[s + 1]
			var ca: Color = cols[s]
			var cb: Color = cols[s + 1]
			for k in range(n_p):
				var kn: int = (k + 1) % n_p
				if stress_colormap:
					st.set_color(ca)
				st.add_vertex(a[k])
				if stress_colormap:
					st.set_color(cb)
				st.add_vertex(b[k])
				if stress_colormap:
					st.set_color(cb)
				st.add_vertex(b[kn])
				if stress_colormap:
					st.set_color(ca)
				st.add_vertex(a[k])
				if stress_colormap:
					st.set_color(cb)
				st.add_vertex(b[kn])
				if stress_colormap:
					st.set_color(ca)
				st.add_vertex(a[kn])
	st.generate_normals()
	return st.commit()


static func build_streamlined_fuselage_mesh(length_m: float = 0.95, radius_m: float = 0.08) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var n_x: int = 12
	var n_rad: int = 14
	var rings: Array = []
	for ix in range(n_x):
		var u: float = float(ix) / float(n_x - 1)
		var x: float = (0.4 - u) * length_m
		# Smooth tear-drop / blended UAV fuselage profile
		var env: float = sin(PI * pow(u, 0.72)) * (1.0 - 0.35 * u)
		var r_cur: float = maxf(0.004, radius_m * env)
		var ring: Array[Vector3] = []
		for ir in range(n_rad):
			var th: float = TAU * float(ir) / float(n_rad)
			ring.append(Vector3(x, r_cur * sin(th) * 0.85, r_cur * cos(th)))
		rings.append(ring)
	for ix in range(n_x - 1):
		var a: Array[Vector3] = rings[ix]
		var b: Array[Vector3] = rings[ix + 1]
		for ir in range(n_rad):
			var irn: int = (ir + 1) % n_rad
			st.add_vertex(a[ir])
			st.add_vertex(b[ir])
			st.add_vertex(b[irn])
			st.add_vertex(a[ir])
			st.add_vertex(b[irn])
			st.add_vertex(a[irn])
	st.generate_normals()
	return st.commit()


static func build_inertia_rings_overlay(cog_scene: Vector3) -> Node3D:
	var root := Node3D.new()
	root.name = "isaac_inertia_rings"
	root.position = cog_scene
	var im := ImmediateMesh.new()
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.vertex_color_use_as_albedo = true
	im.surface_begin(Mesh.PRIMITIVE_LINES, mat)
	var specs := [
		{"col": Color(0.95, 0.25, 0.25), "axis": 0, "r": 0.24},
		{"col": Color(0.25, 0.90, 0.42), "axis": 1, "r": 0.28},
		{"col": Color(0.25, 0.62, 0.98), "axis": 2, "r": 0.22},
	]
	for spec in specs:
		im.surface_set_color(spec["col"])
		var r: float = float(spec["r"])
		var ax: int = int(spec["axis"])
		for i in range(48):
			var a0: float = TAU * float(i) / 48.0
			var a1: float = TAU * float(i + 1) / 48.0
			im.surface_add_vertex(_ring_pt(ax, r, a0))
			im.surface_add_vertex(_ring_pt(ax, r, a1))
	im.surface_end()
	var mi := MeshInstance3D.new()
	mi.mesh = im
	root.add_child(mi)
	var cog_dot := MeshInstance3D.new()
	var sp := SphereMesh.new()
	sp.radius = 0.022
	sp.height = 0.044
	cog_dot.mesh = sp
	var cm := StandardMaterial3D.new()
	cm.albedo_color = Color(1.0, 0.82, 0.15)
	cm.emission_enabled = true
	cm.emission = Color(1.0, 0.72, 0.05)
	cog_dot.material_override = cm
	root.add_child(cog_dot)
	return root


static func _ring_pt(axis: int, r: float, ang: float) -> Vector3:
	if axis == 0:
		return Vector3(0.0, r * cos(ang), r * sin(ang))
	if axis == 1:
		return Vector3(r * cos(ang), 0.0, r * sin(ang))
	return Vector3(r * cos(ang), r * sin(ang), 0.0)


static func build_flow_streamlines(rotor_positions: Array, fixed_wing: bool = false) -> Node3D:
	var root := Node3D.new()
	root.name = "aero_flow_streamlines"
	var im := ImmediateMesh.new()
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.vertex_color_use_as_albedo = true
	im.surface_begin(Mesh.PRIMITIVE_LINES, mat)
	if fixed_wing or rotor_positions.is_empty():
		for i in range(-6, 7):
			var z: float = float(i) * 0.13
			var swirl: float = 0.10 * sin(absf(z) * 2.5)
			for s in range(18):
				var t0: float = float(s) / 18.0
				var t1: float = float(s + 1) / 18.0
				var x0: float = 0.6 - t0 * 2.1
				var x1: float = 0.6 - t1 * 2.1
				var y0: float = 0.08 - 0.18 * pow(maxf(0.0, t0 - 0.25), 1.2) + swirl * sin(t0 * 5.0)
				var y1: float = 0.08 - 0.18 * pow(maxf(0.0, t1 - 0.25), 1.2) + swirl * sin(t1 * 5.0)
				var col: Color = _jet_color(clampf(0.25 + 0.65 * sin(t0 * PI) * (1.0 - 0.35 * absf(z)), 0.0, 1.0))
				im.surface_set_color(col)
				im.surface_add_vertex(Vector3(x0, y0, z))
				im.surface_add_vertex(Vector3(x1, y1, z))
	else:
		for r_pos in rotor_positions:
			for k in range(6):
				var ang0: float = TAU * float(k) / 6.0
				for s in range(16):
					var t0: float = float(s) / 16.0
					var t1: float = float(s + 1) / 16.0
					# Contracted slipstream radius r(y) = R / sqrt(2) + helical swirl
					var rad0: float = lerpf(0.16, 0.10, t0)
					var rad1: float = lerpf(0.16, 0.10, t1)
					var a0: float = ang0 + t0 * 3.8
					var a1: float = ang0 + t1 * 3.8
					var p0: Vector3 = r_pos + Vector3(rad0 * cos(a0), 0.16 - t0 * 0.62, rad0 * sin(a0))
					var p1: Vector3 = r_pos + Vector3(rad1 * cos(a1), 0.16 - t1 * 0.62, rad1 * sin(a1))
					var col: Color = _jet_color(clampf(0.2 + 0.8 * sin(t0 * PI * 0.85), 0.0, 1.0))
					im.surface_set_color(col)
					im.surface_add_vertex(p0)
					im.surface_add_vertex(p1)
	im.surface_end()
	var mi := MeshInstance3D.new()
	mi.mesh = im
	root.add_child(mi)
	return root


static func _jet_color(t: float) -> Color:
	var v: float = clampf(t, 0.0, 1.0)
	var r: float = clampf(1.5 - absf(4.0 * v - 3.0), 0.0, 1.0)
	var g: float = clampf(1.5 - absf(4.0 * v - 2.0), 0.0, 1.0)
	var b: float = clampf(1.5 - absf(4.0 * v - 1.0), 0.0, 1.0)
	return Color(r, g, b, 0.92)
