extends RefCounted

const PROTOCOL: String = "desktop_worker_1"
const MAX_REQUEST_BYTES: int = 16 * 1024 * 1024

var repository: String
var python: String
var pid: int = -1
var session_id: String = ""
var session_path: String = ""
var context: Dictionary = {}
var resources: Dictionary = {"contract_version": "local_cad_resources_1",
	"memory_bytes": 1073741824, "workspace_bytes": 268435456, "wall_time_s": 60.0}


func _init(root: String, interpreter: String) -> void:
	repository = root
	python = interpreter


func is_running() -> bool:
	return pid > 0 and OS.is_process_running(pid)


func has_failed() -> bool:
	return not is_running() or FileAccess.file_exists(session_path.path_join("retired.json"))


func _nonce() -> String:
	return Crypto.new().generate_random_bytes(16).hex_encode()


func _start() -> bool:
	if not session_path.is_empty() and not stop():
		return false
	session_id = _nonce()
	session_path = ProjectSettings.globalize_path("user://cad-workers/" + session_id)
	if DirAccess.make_dir_recursive_absolute(session_path) != OK:
		return false
	var limits_path: String = session_path.path_join("resource-request.json")
	var limits_file: FileAccess = FileAccess.open(limits_path, FileAccess.WRITE)
	if limits_file == null:
		return false
	limits_file.store_string(JSON.stringify(resources, "", true, true))
	limits_file.close()
	pid = OS.create_process(python, [repository.path_join("scripts/lab_worker.py"),
		"--session", session_path, "--session-id", session_id, "--owner-pid", str(OS.get_process_id()),
		"--resources-file", limits_path, "--job-timeout", str(resources["wall_time_s"])], false)
	return pid > 0


func submit(operation: String, input_path: String, asset_root: String) -> Dictionary:
	var source: FileAccess = FileAccess.open(input_path, FileAccess.READ)
	if source == null or source.get_length() > MAX_REQUEST_BYTES:
		return {"failure": "CAD input is missing or exceeds the 16 MiB request limit."}
	var raw_payload: String = source.get_as_text()
	var payload: Variant = JSON.parse_string(raw_payload)
	source.close()
	if not payload is Dictionary:
		return {"failure": "CAD input must be a JSON object."}
	if has_failed() and not _start():
		return {"failure": "Cannot start or cleanly replace the CAD worker."}
	if FileAccess.file_exists(session_path.path_join("pending.json")):
		return {"failure": "The CAD worker already has a pending request."}
	var job_id: String = _nonce()
	var packet: Dictionary = {"protocol": PROTOCOL, "session_id": session_id, "job_id": job_id,
		"operation": operation, "asset_root": asset_root if operation == "cad-torque" else null,
		"resources": resources}
	# Keep the verified engineering JSON numbers out of a rendering-parser round trip.
	# Trusted routing fields follow the payload; the engine validates the full packet.
	var encoded: PackedByteArray = ('{"payload":' + raw_payload + ',' + JSON.stringify(packet, "", true, true).trim_prefix('{')).to_utf8_buffer()
	if encoded.size() > MAX_REQUEST_BYTES:
		return {"failure": "CAD request exceeds the 16 MiB protocol limit."}
	var temporary: String = session_path.path_join(".pending.tmp")
	var output: FileAccess = FileAccess.open(temporary, FileAccess.WRITE)
	if output == null:
		return {"failure": "Cannot write the CAD worker request."}
	output.store_buffer(encoded)
	output.flush()
	output.close()
	var digest: String = FileAccess.get_sha256(temporary)
	if DirAccess.rename_absolute(temporary, session_path.path_join("pending.json")) != OK:
		return {"failure": "Cannot publish the CAD worker request."}
	var directory: String = session_path.path_join("jobs/" + job_id)
	context = {"pid": pid, "session_id": session_id, "job_id": job_id, "request_sha256": digest,
		"output": directory.path_join("result.json"), "error": directory.path_join("error.json"),
		"completion": directory.path_join("complete.json"), "started": directory.path_join("started.json")}
	return context


func completed_output(completion_path: String) -> bool:
	if context.is_empty() or completion_path != context["completion"] or not FileAccess.file_exists(context["output"]) or not FileAccess.file_exists(completion_path):
		return false
	var receipt: Variant = JSON.parse_string(FileAccess.get_file_as_string(context["completion"]))
	if not receipt is Dictionary or receipt.get("protocol") != PROTOCOL:
		return false
	for key in ["session_id", "job_id", "request_sha256"]:
		if receipt.get(key) != context[key]:
			return false
	var approval_path: String = completion_path.get_base_dir().path_join("approved.json")
	if not FileAccess.file_exists(approval_path) or receipt.get("resource_approval_sha256") != FileAccess.get_sha256(approval_path):
		return false
	var approval: Variant = JSON.parse_string(FileAccess.get_file_as_string(approval_path))
	if not approval is Dictionary:
		return false
	for key in ["protocol", "session_id", "job_id", "request_sha256", "output_sha256"]:
		if approval.get(key) != receipt.get(key):
			return false
	return receipt.get("output_sha256") == FileAccess.get_sha256(context["output"])


func failure_reason() -> String:
	var retired: Variant = JSON.parse_string(FileAccess.get_file_as_string(session_path.path_join("retired.json"))) if FileAccess.file_exists(session_path.path_join("retired.json")) else null
	return str(retired.get("reason", "Worker ended without a result.")) if retired is Dictionary else "Worker ended without a result. Check the configured Python dependencies."


func set_limits(memory_mib: int, workspace_mib: int, seconds: float) -> bool:
	if not stop():
		return false
	resources = {"contract_version": "local_cad_resources_1", "memory_bytes": memory_mib * 1048576,
		"workspace_bytes": workspace_mib * 1048576, "wall_time_s": seconds}
	return true


func stop() -> bool:
	if session_path.is_empty():
		return true
	if not FileAccess.file_exists(session_path.path_join("supervisor.json")) and not is_running():
		pid = -1
		return true
	var output: Array = []
	var code: int = OS.execute(python, [repository.path_join("scripts/lab_worker.py"),
		"--session", session_path, "--session-id", session_id, "--stop"], output, true, false)
	if code != 0:
		return false
	pid = -1
	return true
