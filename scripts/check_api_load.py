"""Measure an isolated AeroForge deployment under competing simulation requests."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
from threading import Barrier
from time import perf_counter
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4


def check_load(base_url: str) -> dict:
    def request(path, method="GET", payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        start = perf_counter()
        query = Request(base_url.rstrip("/") + path, method=method, data=data,
                        headers={"Content-Type": "application/json"})
        try:
            response = urlopen(query, timeout=60)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read()
            return response.status, raw, dict(response.headers), perf_counter() - start

    status, raw, _, _ = request("/api/designs/reference")
    assert status == 200, status
    design = json.loads(raw)["snapshot"]
    design["name"] = f"Load acceptance {uuid4()}"
    status, raw, _, _ = request("/api/designs", "POST", {"snapshot": design})
    assert status == 200, (status, raw)
    design_id = json.loads(raw)["id"]
    try:
        barrier = Barrier(9)
        def simulate():
            barrier.wait(timeout=15)
            return request(f"/api/designs/{design_id}/simulate", "POST", {
                "scenario": "hover-ideal", "params": {"duration_s": 20, "dt_s": 0.001},
            })
        with ThreadPoolExecutor(max_workers=12) as workers:
            simulations = [workers.submit(simulate) for _ in range(8)]
            barrier.wait(timeout=15)
            reads = list(workers.map(
                request, ["/api/health", f"/api/designs/{design_id}"] * 60,
            ))
            outcomes = [future.result() for future in simulations]
        assert all(row[0] == 200 for row in reads), "Read request failed during solver contention"
        assert all(row[0] in (200, 503) for row in outcomes), "Unexpected simulation response"
        completed = [row for row in outcomes if row[0] == 200]
        busy = [row for row in outcomes if row[0] == 503]
        assert completed and busy, "The workload did not exercise both execution and rejection"
        for _, raw, _, _ in completed:
            result = json.loads(raw)
            assert result["status"] == "completed", result
            status, frozen, _, _ = request(f"/api/simulations/{result['simulation_id']}/inputs")
            assert status == 200 and sha256(frozen).hexdigest() == result["input_sha256"]
        assert all(row[2].get("retry-after", row[2].get("Retry-After")) == "1" for row in busy)
        latencies = sorted(row[3] for row in reads)
        p95 = latencies[int(0.95 * (len(latencies) - 1))]
        assert p95 < 2.0 and max(latencies) < 5.0, "Read responsiveness exceeded the acceptance budget"
        status, raw, _, recovery_s = request(f"/api/designs/{design_id}/simulate", "POST", {
            "scenario": "hover-ideal", "params": {"duration_s": 0.02},
        })
        assert status == 200 and json.loads(raw)["status"] == "completed", "Solver slot did not recover"
        return {
            "concurrent_simulation_requests": 8, "read_requests": len(reads),
            "completed_simulations": len(completed), "busy_responses": len(busy),
            "read_median_s": median(latencies), "read_p95_s": p95, "read_max_s": max(latencies),
            "recovery_run_s": recovery_s, "verdict": "PASS",
        }
    finally:
        status, _, _, _ = request(f"/api/designs/{design_id}", "DELETE")
        assert status == 200, "Test design cleanup failed"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5173")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = json.dumps(check_load(args.base_url), indent=2)
    print(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report + "\n", encoding="utf-8")
