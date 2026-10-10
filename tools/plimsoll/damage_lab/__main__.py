"""Standalone CLI: frozen aftermath reports for local tools and user-configured AI."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

from . import run_experiment
from .exports import serialize_report


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_object,
                      parse_constant=lambda token: (_ for _ in ()).throw(ValueError("nonfinite JSON: " + token)))


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=path.parent,
                                         prefix=".damage-lab-", delete=False) as stream:
            name = stream.name
            stream.write(content)
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Known-hit gameplay aftermath coupled to the Plimsoll flooding core.")
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--condition", required=True)
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--csv", type=Path)
    args = parser.parse_args(argv)
    try:
        inputs = [args.project.resolve(), args.experiment.resolve()]
        outputs = [p.resolve() for p in (args.output, args.csv) if p is not None]
        for i, path in enumerate(outputs):
            for other in inputs + outputs[:i]:
                if path == other or path.exists() and other.exists() and path.samefile(other):
                    raise ValueError("output paths must be distinct and must not overwrite input files")
        result = run_experiment(read_json(inputs[0]), args.condition, read_json(inputs[1]))
        reports = [serialize_report(result, "json")]
        if args.csv:
            reports.append(serialize_report(result, "csv"))
        for path, content in zip(outputs, reports):
            atomic_write(path, content)
        print(json.dumps({"status": result["status"], "request_fingerprint": result["request_fingerprint"],
                          "output": str(outputs[0])}))
        return 0 if result["status"] == "completed" else 3 if result["status"] == "canceled" else 2
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(json.dumps({"status": "failed", "message": str(error),
                          "diagnostics": getattr(error, "diagnostics", [])}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
