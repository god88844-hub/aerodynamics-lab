"""Stage unchanged, lock-hash-approved cached wheels for an offline installation."""
from email.parser import BytesParser
from hashlib import file_digest
import json
from pathlib import Path
import re
import shutil
import sys
from zipfile import ZipFile, BadZipFile

from packaging.tags import sys_tags

lock, cache, output = map(Path, sys.argv[1:])
allowed = set(re.findall(r"sha256:([a-f0-9]{64})", lock.read_text()))
tags = [str(t) for t in sys_tags()]
output.mkdir(exist_ok=False)
records = []
for source in cache.rglob("*.body"):
    with source.open("rb") as stream:
        if stream.read(2) != b"PK":
            continue
        stream.seek(0)
        digest = file_digest(stream, "sha256").hexdigest()
    if digest not in allowed:
        continue
    try:
        with ZipFile(source) as archive:
            wheel_names = [n for n in archive.namelist() if n.endswith(".dist-info/WHEEL")]
            if len(wheel_names) != 1:
                continue
            wheel_name = wheel_names[0]
            if archive.getinfo(wheel_name).file_size > 65536:
                raise ValueError("Oversized wheel metadata")
            wheel = BytesParser().parsebytes(archive.read(wheel_name))
            metadata = BytesParser().parsebytes(archive.read(wheel_name.removesuffix("WHEEL") + "METADATA"))
            tag = next((t for t in tags if t in wheel.get_all("Tag", [])), None)
            if tag is None:
                continue
            name = re.sub(r"[-_.]+", "_", metadata["Name"])
            version = metadata["Version"].replace("-", "_")
            build = (wheel["Build"] + "-") if wheel["Build"] else ""
            filename = f"{name}-{version}-{build}{tag}.whl"
    except BadZipFile:
        continue
    destination = output / filename
    if not destination.exists():
        shutil.copyfile(source, destination)
    elif destination.read_bytes() != source.read_bytes():
        raise ValueError("Ambiguous wheel filename; refusing overwrite")
    records.append({"file": filename, "sha256": digest, "source_cache_body": str(source), "bytes": source.stat().st_size})
(output.parent / "wheelhouse-manifest.json").write_text(json.dumps({
    "scope": "Unchanged wheel bytes approved by the lock; compatible filename tags reconstructed from WHEEL/METADATA. Pip rechecks hashes offline.",
    "requirements_sha256": __import__("hashlib").sha256(lock.read_bytes()).hexdigest(), "wheels": records}, indent=2) + "\n", encoding="utf-8")
print(f"Staged {len(records)} lock-approved compatible wheels")
