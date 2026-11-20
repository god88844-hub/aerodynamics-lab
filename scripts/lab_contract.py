"""Validate foundation documents without treating schema validity as execution/evidence."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "packages/shared-schemas"), str(ROOT / "packages")]
from aeroforge_schemas.foundation import (AeroLoads, AeroSurface, EvidenceRecord, Frames,
    JobRecord, ModelIdentity, ResourceLimits, Solver, require_backend)
from aeroforge_schemas.project import EngineeringProject
from aeroforge_schemas.cad import BladeRecipe, BoxRecipe, CadTorqueRequest
from desktop_worker.protocol import WorkerRequest
from desktop_worker.io import write_result

CONTRACTS = {"frames": Frames, "project": EngineeringProject, "model": ModelIdentity,
             "solver": Solver, "resources": ResourceLimits, "geometry_aero": AeroSurface,
             "aero_loads": AeroLoads, "job": JobRecord, "evidence": EvidenceRecord,
             "blade": BladeRecipe, "box": BoxRecipe, "cad_torque": CadTorqueRequest,
             "worker_request": WorkerRequest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", choices=CONTRACTS)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--require-executable", action="store_true")
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("input and output must be separate")
    try:
        if args.input.stat().st_size > 16 * 1024**2:
            raise ValueError("contract document exceeds 16 MiB")
        document = CONTRACTS[args.contract].model_validate_json(args.input.read_bytes())
        if args.require_executable:
            backend = getattr(document, "execution_backend", getattr(document, "backend_id", None))
            if backend is None:
                raise ValueError("this contract has no execution capability")
            require_backend(backend)
        write_result(args.output, {"contract": args.contract, "schema_valid": True,
                                  "physical_validation_status": "unvalidated",
                                  "document": document.model_dump(mode="json")})
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
