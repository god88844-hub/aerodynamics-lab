"""Supervise a reusable local CAD engine, or stop its birth-identified session."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/api"), str(ROOT / "packages"), str(ROOT / "packages/shared-schemas")]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--owner-pid", type=int)
    parser.add_argument("--engine", action="store_true")
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--startup-timeout", type=float, default=30)
    parser.add_argument("--job-timeout", type=float, default=60)
    parser.add_argument("--idle-timeout", type=float, default=300)
    parser.add_argument("--resources-file", type=Path)
    args = parser.parse_args()
    from desktop_worker.supervision import IDENTIFIER, stop_session, supervise
    if not IDENTIFIER.fullmatch(args.session_id):
        parser.error("session ID must be 32 lowercase hexadecimal characters")
    if not args.session.is_absolute():
        parser.error("session directory must be absolute")
    for limit in (args.startup_timeout, args.job_timeout, args.idle_timeout):
        if not 0.01 <= limit <= 900:
            parser.error("worker deadlines must be finite values between 0.01 and 900 seconds")
    if args.engine and args.stop:
        parser.error("engine and stop modes are mutually exclusive")
    try:
        if args.stop:
            stop_session(args.session, args.session_id)
            return 0
        if args.engine:
            from desktop_worker.engine import serve
            return serve(args.session, args.session_id)
        if args.owner_pid is None:
            parser.error("supervision requires the desktop owner PID")
        import json
        resources = None
        if args.resources_file:
            with args.resources_file.open("rb") as source:
                raw = source.read(64 * 1024 + 1)
            if len(raw) > 64 * 1024:
                raise ValueError("Resource request exceeds its size limit")
            resources = json.loads(raw)
        return supervise(args.session, args.session_id, args.owner_pid,
                         startup_timeout=args.startup_timeout, job_timeout=args.job_timeout,
                         idle_timeout=args.idle_timeout, resources=resources)
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
