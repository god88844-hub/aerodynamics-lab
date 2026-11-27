extends RefCounted
class_name WorkbenchControls


class BlueprintSheetCanvas extends Control:
	var part_title: String = "AeroGlider-Wing | NACA 2412"
	var span_m: float = 1.80
	var root_chord_m: float = 0.26
	var tip_chord_m: float = 0.14
	var mass_text: String = "Mass 3.708 kg"
	var show_balloons: bool = true

	func _draw() -> void:
		var r: Rect2 = Rect2(Vector2(12, 12), size - Vector2(24, 24))
		draw_rect(r, Color(0.97, 0.98, 0.99), true)
		draw_rect(r, Color(0.18, 0.22, 0.28), false, 2.0)
		var inner: Rect2 = Rect2(r.position + Vector2(10, 10), r.size - Vector2(20, 20))
		draw_rect(inner, Color(0.28, 0.34, 0.42), false, 1.0)
		var font: Font = ThemeDB.fallback_font
		# Top planform orthographic projection
		var cx: float = inner.position.x + inner.size.x * 0.45
		var top_y: float = inner.position.y + inner.size.y * 0.34
		var sc: float = minf(inner.size.x * 0.38 / maxf(0.5, span_m), 210.0)
		var hb: float = 0.5 * span_m * sc
		var cr: float = root_chord_m * sc
		var ct: float = tip_chord_m * sc
		var plan := PackedVector2Array([
			Vector2(cx, top_y - cr * 0.5),
			Vector2(cx + hb, top_y - ct * 0.4),
			Vector2(cx + hb, top_y + ct * 0.6),
			Vector2(cx, top_y + cr * 0.5),
			Vector2(cx - hb, top_y + ct * 0.6),
			Vector2(cx - hb, top_y - ct * 0.4),
		])
		draw_colored_polygon(plan, Color(0.88, 0.93, 0.98))
		for i in range(plan.size()):
			draw_line(plan[i], plan[(i + 1) % plan.size()], Color(0.10, 0.15, 0.22), 2.0, true)
		# Dimension line for wingspan
		var dim_y: float = top_y - cr * 0.5 - 24.0
		draw_line(Vector2(cx - hb, dim_y), Vector2(cx + hb, dim_y), Color(0.12, 0.42, 0.78), 1.5, true)
		draw_string(font, Vector2(cx - 48.0, dim_y - 6.0), "SPAN %.3f m" % span_m, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color(0.1, 0.35, 0.7))
		# Front dihedral orthographic view
		var front_y: float = inner.position.y + inner.size.y * 0.68
		draw_line(Vector2(cx - hb, front_y - 12.0), Vector2(cx, front_y), Color(0.10, 0.15, 0.22), 2.2, true)
		draw_line(Vector2(cx, front_y), Vector2(cx + hb, front_y - 12.0), Color(0.10, 0.15, 0.22), 2.2, true)
		draw_string(font, Vector2(inner.position.x + 18.0, front_y - 18.0), "FRONT DIHEDRAL VIEW", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(0.3, 0.36, 0.44))
		# Callout balloons matching Fusion 360 drawings
		if show_balloons:
			var balloons := [
				{"n": "1", "pt": Vector2(cx + hb * 0.5, top_y), "b": Vector2(cx + hb * 0.65, top_y - 46.0)},
				{"n": "2", "pt": Vector2(cx, top_y), "b": Vector2(cx + 38.0, top_y + 44.0)},
			]
			for bl in balloons:
				draw_line(bl["pt"], bl["b"], Color(0.15, 0.15, 0.15), 1.2, true)
				draw_circle(bl["b"], 12.0, Color(1.0, 1.0, 1.0))
				draw_arc(bl["b"], 12.0, 0, TAU, 24, Color(0.1, 0.1, 0.1), 1.5, true)
				draw_string(font, bl["b"] + Vector2(-4.0, 5.0), bl["n"], HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(0.05, 0.05, 0.05))
		# Engineering Title Block bottom-right
		var tb := Rect2(inner.end - Vector2(340, 74), Vector2(340, 74))
		draw_rect(tb, Color(0.93, 0.95, 0.97), true)
		draw_rect(tb, Color(0.15, 0.20, 0.26), false, 1.5)
		draw_string(font, tb.position + Vector2(10, 22), "AERODYNAMICS LAB · ENGINEERING SHEET", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(0.08, 0.12, 0.18))
		draw_string(font, tb.position + Vector2(10, 42), part_title, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(0.12, 0.25, 0.45))
		draw_string(font, tb.position + Vector2(10, 62), "%s | UNITS: SI METERS | UNVALIDATED" % mass_text, HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.35, 0.20, 0.12))


class TelemetryPlotCanvas extends Control:
	var series_t: Array = []
	var series_z: Array = []
	var series_v: Array = []
	var label_title: String = "Flight Telemetry (Altitude m · Bus Voltage V)"

	func _draw() -> void:
		draw_rect(Rect2(Vector2.ZERO, size), Color(0.06, 0.08, 0.11, 0.92), true)
		draw_rect(Rect2(Vector2.ZERO, size), Color(0.18, 0.24, 0.32), false, 1.0)
		var font: Font = ThemeDB.fallback_font
		draw_string(font, Vector2(10, 16), label_title, HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.75, 0.85, 0.95))
		if series_t.size() < 2 or series_z.size() != series_t.size():
			draw_string(font, Vector2(10, size.y * 0.62), "Run Fixed-Wing, VTOL, Heli Autorotation, C++ RK4, or Authoritative Sim for live curves.", HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.50, 0.58, 0.68))
			return
		var pad := Vector2(12, 24)
		var w: float = maxf(20.0, size.x - 24.0)
		var h: float = maxf(20.0, size.y - 32.0)
		var z_min: float = float(series_z[0])
		var z_max: float = z_min
		for zv in series_z:
			z_min = minf(z_min, float(zv))
			z_max = maxf(z_max, float(zv))
		var span_z: float = maxf(0.1, z_max - z_min)
		var pts := PackedVector2Array()
		for i in range(series_t.size()):
			var fx: float = float(i) / float(series_t.size() - 1)
			var fy: float = 1.0 - (float(series_z[i]) - z_min) / span_z
			pts.append(Vector2(pad.x + fx * w, pad.y + fy * h))
		draw_polyline(pts, Color(0.30, 0.78, 0.98), 2.0, true)
		if series_v.size() == series_t.size():
			var vpts := PackedVector2Array()
			for i in range(series_t.size()):
				var fx: float = float(i) / float(series_t.size() - 1)
				var fy: float = 1.0 - clampf((float(series_v[i]) - 18.0) / 8.0, 0.0, 1.0)
				vpts.append(Vector2(pad.x + fx * w, pad.y + fy * h))
			draw_polyline(vpts, Color(0.95, 0.65, 0.25), 1.6, true)
		draw_string(font, Vector2(size.x - 165.0, 16), "Alt [%.2f..%.2f m]" % [z_min, z_max], HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.30, 0.78, 0.98))


class ColorbarLegend extends Control:
	var title_text: String = "Airflow Velocity (m/s)"
	var min_label: String = "0.0"
	var max_label: String = "24.0"

	func _draw() -> void:
		draw_rect(Rect2(Vector2.ZERO, size), Color(0.06, 0.08, 0.11, 0.85), true)
		draw_rect(Rect2(Vector2.ZERO, size), Color(0.24, 0.30, 0.40), false, 1.0)
		var font: Font = ThemeDB.fallback_font
		draw_string(font, Vector2(8, 16), title_text, HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.88, 0.92, 0.98))
		var bar_rect := Rect2(10, 24, size.x - 20.0, 12.0)
		var n_seg: int = 24
		var sw: float = bar_rect.size.x / float(n_seg)
		for i in range(n_seg):
			var t: float = float(i) / float(n_seg - 1)
			draw_rect(Rect2(bar_rect.position.x + float(i) * sw, bar_rect.position.y, sw + 1.0, bar_rect.size.y), WorkbenchMeshes._jet_color(t), true)
		draw_string(font, Vector2(10, 50), min_label, HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(0.55, 0.78, 0.98))
		draw_string(font, Vector2(size.x - 42.0, 50), max_label, HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(0.98, 0.45, 0.35))
