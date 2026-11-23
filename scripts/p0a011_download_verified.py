"""Download *only* the eight frozen UAV-FD publisher MAT originals, outside Git.

Explicit opt-in. Each file is verified against the committed P0A-010 size and
SHA-256 before use. A corrupt, partial, or HTML/rate-limit response is rejected.
This helper never discovers or substitutes new datasets or modifies baselines.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import benchmark_uav_fd_rotor_order as rotor  # noqa: E402
import benchmark_uav_fd_esc_power as esc  # noqa: E402

FROZEN = {**rotor.FILES, **esc.NEW_FILES}
RECORD = "7648996"


def _verify(path: Path, size: int, digest: str) -> bool:
    if not path.exists() or not path.is_file() or path.stat().st_size != size:
        return False
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest() == digest


def _publisher_urls(filename: str) -> list[str]:
    encoded = urllib.parse.quote(filename, safe="")
    return [
        f"https://zenodo.org/api/records/{RECORD}/files/{encoded}/content",
        f"https://zenodo.org/records/{RECORD}/files/{encoded}?download=1",
    ]


def _get(url: str, path: Path, size: int, digest: str) -> None:
    if urllib.parse.urlparse(url).hostname != "zenodo.org":
        raise ValueError("Only the original Zenodo publisher host is accepted")
    tmp = path.with_suffix(path.suffix + ".partial")
    sha = hashlib.sha256()
    amount = 0
    req = urllib.request.Request(url, headers={
        "User-Agent": "AeroForge-P0A011-reproduction/1.0",
        "Accept": "application/octet-stream",
    })
    try:
        with urllib.request.urlopen(req, timeout=90) as response, tmp.open("wb") as stream:
            # Redirects are allowed only to the Zenodo publisher host.
            host = urllib.parse.urlparse(response.geturl()).hostname
            if host != "zenodo.org":
                raise ValueError(f"Unexpected file redirect host {host!r}")
            while True:
                block = response.read(2 * 1024 * 1024)
                if not block:
                    break
                stream.write(block)
                sha.update(block)
                amount += len(block)
                if amount > size:
                    raise ValueError("publisher response exceeds frozen file size")
        if amount != size or sha.hexdigest() != digest:
            raise ValueError(f"publisher mismatch: expected {size}/{digest}, got {amount}/{sha.hexdigest()}")
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--directory", required=True, type=Path)
    args = p.parse_args()
    destination = args.directory.expanduser().resolve()
    if destination == ROOT or ROOT in destination.parents:
        p.error("Raw publisher archives MUST stay outside Git")
    destination.mkdir(parents=True, exist_ok=True)
    for filename, (size, digest) in sorted(FROZEN.items()):
        path = destination / filename
        if _verify(path, size, digest):
            print(f"VERIFIED cached {filename} {size} {digest}", flush=True)
            continue
        if path.exists():
            raise ValueError(f"Refusing mismatched existing original {path}; inspect/delete manually")
        last_error = None
        for url in _publisher_urls(filename):
            for trial in range(4):
                try:
                    print(f"fetching publisher original {filename} via Zenodo; attempt {trial+1}", flush=True)
                    _get(url, path, size, digest)
                    last_error = None
                    break
                except (OSError, ValueError, urllib.error.URLError) as exc:
                    last_error = exc
                    print(f"retryable publisher download failure: {type(exc).__name__}: {exc}", flush=True)
                    time.sleep(min(2 ** trial, 8))
            if last_error is None:
                break
        if last_error is not None:
            raise RuntimeError(f"Unable to acquire pinned publisher bytes for {filename}") from last_error
        assert _verify(path, size, digest), f"file {filename} failed final size/SHA-256 verification"
        print(f"VERIFIED downloaded {filename} {size} {digest}", flush=True)
    print("ALL EIGHT PUBLISHER RECORDINGS HASH-VERIFIED OUTSIDE GIT", flush=True)


if __name__ == "__main__":
    main()
