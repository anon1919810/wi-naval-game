"""Thin command-line adapter for the reviewed Plimsoll calculation core."""

from __future__ import annotations

import argparse
import copy
from importlib import resources
import itertools
import json
import math
from pathlib import Path
import sys

from . import analysis, exports, geometry_import, project_store

# The bundled usage guide is a fixed package resource, addressed by one
# constant so the read is discoverable and is never assembled from the working
# directory, the project, a calculation or the network.
README_RESOURCE = "CLI_README.md"


class _StrictJSONError(ValueError):
    pass


class _CLIError(ValueError):
    def __init__(self, code, message, *, input_path=None, diagnostics=None,
                 exit_code=2, calculation_status=None, persisted_outputs=None):
        self.code = code
        self.input_path = None if input_path is None else str(input_path)
        self.exit_code = exit_code
        self.calculation_status = calculation_status
        self.persisted_outputs = list(persisted_outputs or [])
        self.diagnostics = diagnostics or [_diagnostic(code, message, self.input_path)]
        super().__init__(message)


def _diagnostic(code, message, path=None):
    return {
        "code": code,
        "severity": "error",
        "path": path or "$",
        "message": str(message),
        "blocking": True,
    }


def _object(pairs):
    value = {}
    for key, member in pairs:
        if key in value:
            raise _StrictJSONError(f"duplicate object key {key!r}")
        value[key] = member
    return value


def _number(token):
    value = float(token)
    if not math.isfinite(value):
        raise _StrictJSONError(f"nonfinite JSON number {token!r}")
    return value


def _constant(token):
    raise _StrictJSONError(f"nonfinite JSON constant {token!r}")


def _read_json(path, *, object_required=True):
    source = Path(path)
    try:
        data = source.read_bytes()
    except OSError as error:
        raise _CLIError(
            "cli.input_read", f"cannot read input: {error}", input_path=source,
        ) from error
    try:
        text = data.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_object,
            parse_float=_number,
            parse_constant=_constant,
        )
        text.encode("utf-8", errors="strict")
    except (UnicodeError, json.JSONDecodeError, _StrictJSONError, ValueError) as error:
        raise _CLIError(
            "cli.json_invalid", f"invalid strict UTF-8 JSON: {error}",
            input_path=source,
        ) from error
    if object_required and not isinstance(value, dict):
        raise _CLIError(
            "cli.json_object_required", "JSON root must be an object",
            input_path=source,
        )
    return value


def _resolved(path):
    return Path(path).resolve()


def _guard_destinations(inputs, outputs):
    input_paths = {_resolved(path) for path in inputs if path is not None}
    output_paths = [_resolved(path) for path in outputs if path not in (None, "-")]
    if len(set(output_paths)) != len(output_paths):
        raise _CLIError("cli.output_alias", "output destinations must be distinct")
    if input_paths.intersection(output_paths):
        raise _CLIError(
            "cli.output_alias", "result destination aliases an explicitly read input",
        )


def _analyze(args):
    input_paths = [args.project, args.options]
    _guard_destinations(input_paths, [args.output, args.csv])
    _read_json(args.project)
    try:
        project = project_store.load(args.project)
    except Exception as error:
        raise _CLIError(
            "cli.project_invalid", f"project is invalid: {error}",
            input_path=args.project, diagnostics=getattr(error, "diagnostics", None),
        ) from error
    options = _read_json(args.options) if args.options else None
    try:
        result = analysis.compute_project(project, args.condition, options)
    except Exception as error:
        raise _CLIError(
            "cli.calculation_input", f"calculation input is invalid: {error}",
            input_path=args.options or args.project,
            diagnostics=getattr(error, "diagnostics", None),
        ) from error

    try:
        json_text = exports.serialize_report(result, format='json')
        if args.csv:
            exports.serialize_report(result, format='csv')
    except (ValueError, TypeError, OverflowError) as error:
        raise _CLIError('cli.output_serialization_failed', f'cannot serialize analysis result: {error}',
            calculation_status=result.get('status'), persisted_outputs=[]) from error
    persisted = []
    outputs = [] if args.output == '-' else [(args.output, 'json')]
    if args.csv:
        outputs.append((args.csv, 'csv'))
    for destination, format_name in outputs:
        try:
            exports.write_report(result, destination, format=format_name)
        except (OSError, ValueError, TypeError, OverflowError) as error:
            raise _CLIError('cli.output_write_failed', f'cannot write {format_name} result: {error}',
                input_path=str(destination), calculation_status=result.get('status'),
                persisted_outputs=persisted) from error
        persisted.append(str(Path(destination).resolve()))
    # Stdout is emitted only after every requested file has been written. It is
    # never counted as a persisted filesystem output.
    if args.output == '-':
        sys.stdout.write(json_text)
    return 0 if result.get("status") == "completed" else 1


def _schema_error(message, path):
    raise _CLIError(
        "cli.schema_invalid", message,
        diagnostics=[_diagnostic("cli.schema_invalid", message, path)],
    )


def _exact_keys(value, allowed, path):
    extras = set(value) - set(allowed)
    if extras:
        _schema_error(f"unexpected keys: {sorted(extras)!r}", path)


def _required_text(value, path):
    if not isinstance(value, str) or not value.strip():
        _schema_error("must be a nonempty string", path)
    return value


def _batch_cases(document):
    _exact_keys(document, {"schema", "cases"}, "$")
    if document.get("schema") != "plimsoll-batch-1":
        _schema_error("schema must be 'plimsoll-batch-1'", "$.schema")
    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        _schema_error("cases must be a nonempty array", "$.cases")
    seen = set()
    for index, case in enumerate(cases):
        path = f"$.cases[{index}]"
        if not isinstance(case, dict):
            _schema_error("case must be an object", path)
        _exact_keys(case, {"id", "project", "condition_id", "options"}, path)
        identifier = _required_text(case.get("id"), path + ".id")
        if identifier in seen:
            _schema_error("case IDs must be unique", path + ".id")
        seen.add(identifier)
        _required_text(case.get("project"), path + ".project")
        _required_text(case.get("condition_id"), path + ".condition_id")
        if "options" in case and not isinstance(case["options"], dict):
            _schema_error("options must be an object", path + ".options")
    return cases


def _load_project(path):
    _read_json(path)
    try:
        return project_store.load(path)
    except Exception as error:
        raise _CLIError(
            "cli.project_invalid", f"project is invalid: {error}", input_path=path,
            diagnostics=getattr(error, "diagnostics", None),
        ) from error


def _failure_diagnostics(error, path):
    diagnostics = getattr(error, "diagnostics", None)
    if isinstance(diagnostics, list) and diagnostics:
        return copy.deepcopy(diagnostics)
    code = error.code if isinstance(error, _CLIError) else "cli.case_failed"
    return [_diagnostic(code, str(error), path)]


def _identity(result, key):
    return result.get(key) if isinstance(result, dict) else None


def _batch(args):
    manifest_path = Path(args.manifest).resolve()
    manifest = _read_json(manifest_path)
    cases = _batch_cases(manifest)
    declarations = []
    for case in cases:
        project_path = Path(case["project"])
        if not project_path.is_absolute():
            project_path = manifest_path.parent / project_path
        declarations.append((case, project_path.resolve()))

    out = Path(args.out).resolve()
    result_paths = [out / f"{index:04d}.result.json" for index in range(1, len(cases) + 1)]
    summary_path = out / "batch-summary.json"
    input_paths = [manifest_path, *(path for _, path in declarations)]
    _guard_destinations(input_paths, [*result_paths, summary_path, args.csv])
    try:
        out.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise _CLIError(
            "cli.output_directory", f"cannot create output directory: {error}",
            input_path=out,
        ) from error

    rows = []
    persisted = []
    for ordinal, ((case, project_path), result_path) in enumerate(
            zip(declarations, result_paths), 1):
        declaration = {
            "project": case["project"],
            "condition_id": case["condition_id"],
            "options": copy.deepcopy(case.get("options")),
        }
        result = None
        diagnostics = []
        saved_name = None
        persistence = {"status": "not_attempted", "path": None, "diagnostics": []}
        try:
            project = _load_project(project_path)
            result = analysis.compute_project(
                project, case["condition_id"], case.get("options"),
            )
            diagnostics = copy.deepcopy(result.get("diagnostics", []))
            exports.serialize_report(result, format="json")
            try:
                exports.write_report(result, result_path, format="json")
            except Exception as error:
                failure = _diagnostic(
                    "cli.output_write_failed", f"cannot write result: {error}",
                    str(result_path),
                )
                diagnostics.append(failure)
                persistence = {
                    "status": "failed", "path": None, "diagnostics": [failure],
                }
            else:
                saved_name = result_path.name
                persisted.append(saved_name)
                persistence = {
                    "status": "saved", "path": saved_name, "diagnostics": [],
                }
        except Exception as error:
            diagnostics = _failure_diagnostics(error, f"$.cases[{ordinal - 1}]")
        rows.append({
            "id": case["id"],
            "ordinal": ordinal,
            "declaration": declaration,
            "result_path": saved_name,
            "status": _identity(result, "status") or "failed",
            "project_id": _identity(result, "project_id"),
            "condition_id": _identity(result, "condition_id") or case["condition_id"],
            "project_fingerprint": _identity(result, "project_fingerprint"),
            "input_fingerprint": _identity(result, "input_fingerprint"),
            "request_fingerprint": _identity(result, "request_fingerprint"),
            "diagnostics": diagnostics,
            "persistence": persistence,
        })

    completed = all(
        row["status"] == "completed" and row["persistence"]["status"] == "saved"
        for row in rows
    )
    summary = {
        "schema": "plimsoll-batch-result-1",
        "status": "completed" if completed else "partial",
        "manifest": {"path": str(args.manifest), "schema": manifest["schema"]},
        "case_count": len(rows),
        "cases": rows,
    }
    try:
        exports.serialize_document(summary, format="json")
        if args.csv:
            exports.serialize_document(summary, format="csv")
        exports.write_document(summary, summary_path, format="json")
        persisted.append(summary_path.name)
        if args.csv:
            exports.write_document(summary, args.csv, format="csv")
            persisted.append(str(args.csv))
    except Exception as error:
        raise _CLIError(
            "cli.output_write_failed", f"cannot write batch summary: {error}",
            input_path=summary_path, exit_code=1,
            calculation_status=summary["status"], persisted_outputs=persisted,
        ) from error
    return 0 if completed else 1


_SWEEP_FIELDS = {
    "resistance.speed_kn": (201, "kn"),
    "resistance.qpc": (21, "dimensionless"),
}


def _positive_values(value, path, limit):
    if not isinstance(value, list) or not value:
        _schema_error("values must be a nonempty array", path)
    if len(value) > limit:
        _schema_error(f"values must contain at most {limit} entries", path)
    for index, member in enumerate(value):
        if (isinstance(member, bool) or not isinstance(member, (int, float))
                or not math.isfinite(member) or member <= 0):
            _schema_error("values must be finite positive numbers", f"{path}[{index}]")


def _meaningful_source(value, path):
    if ((isinstance(value, str) and value.strip())
            or (isinstance(value, dict) and value)):
        return
    _schema_error("source must be a nonempty string or object", path)


def _sweep_axes(document):
    _exact_keys(
        document,
        {"schema", "project", "condition_id", "base_options", "axes"},
        "$",
    )
    if document.get("schema") != "plimsoll-sweep-1":
        _schema_error("schema must be 'plimsoll-sweep-1'", "$.schema")
    _required_text(document.get("project"), "$.project")
    _required_text(document.get("condition_id"), "$.condition_id")
    if not isinstance(document.get("base_options"), dict):
        _schema_error("base_options must be an object", "$.base_options")
    axes = document.get("axes")
    if not isinstance(axes, list) or not axes:
        _schema_error("axes must be a nonempty array", "$.axes")
    seen = set()
    grid_size = 1
    for index, axis in enumerate(axes):
        path = f"$.axes[{index}]"
        if not isinstance(axis, dict):
            _schema_error("axis must be an object", path)
        _exact_keys(axis, {"field", "values", "source", "estimate"}, path)
        field = axis.get("field")
        if not isinstance(field, str) or field not in _SWEEP_FIELDS:
            _schema_error("unsupported sweep field", path + ".field")
        if field in seen:
            _schema_error("sweep fields must be unique", path + ".field")
        seen.add(field)
        limit, _ = _SWEEP_FIELDS[field]
        _positive_values(axis.get("values"), path + ".values", limit)
        _meaningful_source(axis.get("source"), path + ".source")
        if not isinstance(axis.get("estimate"), bool):
            _schema_error("estimate must be boolean", path + ".estimate")
        grid_size *= len(axis["values"])
    if grid_size > 1000:
        _schema_error("sweep grid must contain at most 1000 points", "$.axes")
    return axes


def _point_options(base_options, axes, values):
    options = copy.deepcopy(base_options)
    resistance = options.setdefault("resistance", {})
    if not isinstance(resistance, dict):
        _schema_error("base_options.resistance must be an object", "$.base_options.resistance")
    varied = []
    for axis, value in zip(axes, values):
        field = axis["field"]
        _, unit = _SWEEP_FIELDS[field]
        varied.append({
            "field": field,
            "value": value,
            "unit": unit,
            "source": copy.deepcopy(axis["source"]),
            "estimate": axis["estimate"],
        })
        if field == "resistance.speed_kn":
            resistance["speeds_kn"] = [value]
        else:
            resistance["qpc_override"] = {
                "value": value,
                "source": copy.deepcopy(axis["source"]),
                "estimate": axis["estimate"],
            }
    return options, varied


def _sweep(args):
    sweep_path = Path(args.sweep).resolve()
    document = _read_json(sweep_path)
    axes = _sweep_axes(document)
    project_path = Path(document["project"])
    if not project_path.is_absolute():
        project_path = sweep_path.parent / project_path
    project_path = project_path.resolve()
    points = list(itertools.product(*(axis["values"] for axis in axes)))
    out = Path(args.out).resolve()
    result_paths = [out / f"{index:04d}.result.json" for index in range(1, len(points) + 1)]
    summary_path = out / "sweep-summary.json"
    _guard_destinations(
        [sweep_path, project_path], [*result_paths, summary_path, args.csv],
    )
    project = _load_project(project_path)
    try:
        out.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise _CLIError(
            "cli.output_directory", f"cannot create output directory: {error}",
            input_path=out,
        ) from error

    rows = []
    persisted = []
    for ordinal, (values, result_path) in enumerate(zip(points, result_paths), 1):
        options, varied = _point_options(document["base_options"], axes, values)
        result = None
        diagnostics = []
        saved_name = None
        persistence = {"status": "not_attempted", "path": None, "diagnostics": []}
        try:
            result = analysis.compute_project(
                project, document["condition_id"], options,
            )
            diagnostics = copy.deepcopy(result.get("diagnostics", []))
            exports.serialize_report(result, format="json")
            try:
                exports.write_report(result, result_path, format="json")
            except Exception as error:
                failure = _diagnostic(
                    "cli.output_write_failed", f"cannot write result: {error}",
                    str(result_path),
                )
                diagnostics.append(failure)
                persistence = {
                    "status": "failed", "path": None, "diagnostics": [failure],
                }
            else:
                saved_name = result_path.name
                persisted.append(saved_name)
                persistence = {
                    "status": "saved", "path": saved_name, "diagnostics": [],
                }
        except Exception as error:
            diagnostics = _failure_diagnostics(error, f"$.points[{ordinal - 1}]")
        rows.append({
            "ordinal": ordinal,
            "varied": varied,
            "options": options,
            "result_path": saved_name,
            "status": _identity(result, "status") or "failed",
            "project_id": _identity(result, "project_id"),
            "condition_id": _identity(result, "condition_id") or document["condition_id"],
            "project_fingerprint": _identity(result, "project_fingerprint"),
            "input_fingerprint": _identity(result, "input_fingerprint"),
            "request_fingerprint": _identity(result, "request_fingerprint"),
            "diagnostics": diagnostics,
            "persistence": persistence,
        })

    completed = all(
        row["status"] == "completed" and row["persistence"]["status"] == "saved"
        for row in rows
    )
    summary = {
        "schema": "plimsoll-sweep-result-1",
        "status": "completed" if completed else "partial",
        "declaration": copy.deepcopy(document),
        "point_count": len(rows),
        "points": rows,
    }
    try:
        exports.serialize_document(summary, format="json")
        if args.csv:
            exports.serialize_document(summary, format="csv")
        exports.write_document(summary, summary_path, format="json")
        persisted.append(summary_path.name)
        if args.csv:
            exports.write_document(summary, args.csv, format="csv")
            persisted.append(str(args.csv))
    except Exception as error:
        raise _CLIError(
            "cli.output_write_failed", f"cannot write sweep summary: {error}",
            input_path=summary_path, exit_code=1,
            calculation_status=summary["status"], persisted_outputs=persisted,
        ) from error
    return 0 if completed else 1


def _readme(args):
    """Print the bundled usage guide; read one fixed package resource, write nothing."""
    try:
        raw = (resources.files(__package__).joinpath(README_RESOURCE).read_bytes()
               if __package__ else Path(__file__).with_name(README_RESOURCE).read_bytes())
    except (OSError, ModuleNotFoundError, ValueError) as error:
        raise _CLIError(
            "cli.readme_unavailable", f"cannot read bundled README: {error}",
        ) from error
    try:
        raw.decode("utf-8")
    except UnicodeError as error:
        raise _CLIError(
            "cli.readme_unavailable", f"bundled README is not valid UTF-8: {error}",
        ) from error
    # The verified bytes go out unchanged. Writing through the text layer would
    # rewrite every newline for the platform, so the resource is emitted exactly
    # as it is bundled and a caller can compare it against the file itself.
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:
        sys.stdout.write(raw.decode("utf-8"))
    else:
        buffer.write(raw)
        buffer.flush()
    return 0


def _configure_utf8():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def _emit_error(command, error):
    payload = {
        "schema": "plimsoll-cli-error-1",
        "command": command,
        "code": error.code,
        "message": str(error),
        "input_path": error.input_path,
        "diagnostics": error.diagnostics,
    }
    if error.calculation_status is not None:
        payload["calculation_status"] = error.calculation_status
        payload["persisted_outputs"] = error.persisted_outputs
    sys.stderr.write(exports.serialize_document(payload, format="json"))


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise _CLIError('cli.usage', message,
            diagnostics=[_diagnostic('cli.usage', message, '$.argv')])


def _parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(prog="plimsoll")
    commands = parser.add_subparsers(dest="command", required=True)

    analyze = commands.add_parser("analyze", help="calculate one selected loading")
    analyze.add_argument("project")
    analyze.add_argument("--condition", required=True)
    analyze.add_argument("--options")
    analyze.add_argument("--output", default="-")
    analyze.add_argument("--csv")

    batch = commands.add_parser("batch", help="calculate an explicit case manifest")
    batch.add_argument("manifest")
    batch.add_argument("--out", required=True)
    batch.add_argument("--csv")

    sweep = commands.add_parser("sweep", help="calculate a bounded speed/QPC grid")
    sweep.add_argument("sweep")
    sweep.add_argument("--out", required=True)
    sweep.add_argument("--csv")

    geometry = commands.add_parser("import-geometry", help="materialize explicit geometry bytes")
    geometry.add_argument("project")
    geometry.add_argument("geometry")
    geometry.add_argument("--format", required=True,
                          choices=("legacy-offsets-5", "plimsoll-section-polygons-1"))
    geometry.add_argument("--keel-offset-m", required=True)
    geometry.add_argument(
        "--provenance", required=True,
        help="nonempty text or JSON object describing the geometry's provenance",
    )
    geometry.add_argument("--estimate", required=True, choices=("true", "false"))
    geometry.add_argument("--output", required=True)

    commands.add_parser("readme", help="print the bundled command-line guide")
    return parser


def _import_geometry(args):
    """把显式字节物化为自包含几何；不做任何自动查找/迁移。

    读取调用方显式给出的几何字节，连同其声明（格式、龙骨偏移、
    provenance、estimate）一并交给 geometry_import 物化为规范化项目副本，
    再原子落盘。不解析引用、不跨目录迁移、不自动查找任何外部资源。
    """
    _guard_destinations([args.project, args.geometry], [args.output])
    project = _load_project(args.project)
    try:
        content = Path(args.geometry).read_bytes()
    except OSError as error:
        raise _CLIError(
            "cli.input_read", f"cannot read input: {error}", input_path=args.geometry,
        ) from error
    try:
        keel = float(args.keel_offset_m)
    except ValueError as error:
        raise _CLIError(
            "cli.keel_offset_invalid", f"keel offset is not a number: {error}",
            input_path=args.geometry,
        ) from error
    estimate = {"true": True, "false": False}[args.estimate]
    raw = args.provenance
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = raw  # not valid JSON: treat the literal text as the source
    if isinstance(parsed, dict) and parsed:
        source = parsed
    elif isinstance(parsed, str):
        source = parsed  # decoded JSON string literal, without surrounding quotes
    else:
        # null / number / bool / array / empty object -> keep raw literal text
        source = raw
    if isinstance(source, str) and not source.strip():
        raise _CLIError(
            "cli.provenance_invalid",
            "provenance must be a nonempty string or object",
            input_path=args.geometry,
        )
    try:
        imported = geometry_import.import_geometry_content(
            project, content, format=args.format, keel_offset_m=keel,
            source=source, estimate=estimate,
        )
    except geometry_import.GeometryImportError as error:
        raise _CLIError(
            "cli.geometry_import", str(error), input_path=args.geometry,
            diagnostics=error.diagnostics,
        ) from error
    try:
        project_store.save(args.output, imported)
    except Exception as error:
        raise _CLIError(
            "cli.output_write", f"cannot write output: {error}", input_path=args.output,
        ) from error
    return 0


def main(argv=None) -> int:
    """Run the calculation-core command line."""
    _configure_utf8()
    values = list(sys.argv[1:] if argv is None else argv)
    command = values[0] if values and not values[0].startswith("-") else None
    try:
        args = _parser().parse_args(values)
        if args.command == "analyze":
            return _analyze(args)
        if args.command == "batch":
            return _batch(args)
        if args.command == "sweep":
            return _sweep(args)
        if args.command == "import-geometry":
            return _import_geometry(args)
        if args.command == "readme":
            return _readme(args)
        raise NotImplementedError(f"command {args.command!r} is not implemented")
    except _CLIError as error:
        _emit_error(command, error)
        return error.exit_code
