"""Private one-request worker for the parent-owned offline verifier."""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import tempfile


def atomic_write(path, value):
    path = Path(path)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as out:
            name = out.name
            json.dump(value, out, ensure_ascii=False, sort_keys=True, allow_nan=False)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
        name = None
    finally:
        if name is not None:
            Path(name).unlink(missing_ok=True)


def perform(request):
    from .verification import _digest, _source_identity, execute_case
    if request.get("schema") != "plimsoll-verification-worker-1" or _digest(request["case"]) != request["case_sha256"]:
        raise ValueError("invalid worker request identity")
    source_sha = _digest(_source_identity())
    if source_sha != request["source_sha256"]:
        raise ValueError("worker sources differ from parent")
    row = execute_case(request["case"])
    return {"schema": request["schema"], "run_id": request["run_id"], "case_sha256": request["case_sha256"],
            "source_sha256": source_sha, "row": row}


def main(argv=None):
    from .verification import _read_strict
    request_path, result_path = map(Path, sys.argv[1:] if argv is None else argv)
    request = _read_strict(request_path)
    atomic_write(result_path.with_suffix(".progress.json"), {"state": "started", "pid": os.getpid(),
                                                           "case_id": request["case"]["id"], "run_id": request["run_id"]})
    atomic_write(result_path, perform(request))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
