"""Strict canonical verification report: schema, destinations, atomic evidence.

This module owns the whole *output* unit of the core verification command and
knows nothing about cases, oracles or kernels. It pins one canonical report so a
separate runner can produce snapshots incrementally:

* ``validate_report(report)`` accepts a structurally complete, strictly JSON-safe
  ``plimsoll-core-verification-1`` object and raises ``ValueError`` otherwise.
* ``output_session(output_dir)`` preflights and exclusively locks one output
  directory *before* any calculation and holds the lock across every
  checkpoint/final publication.
* ``write_report(report, output_dir)`` renders all three formats in memory and
  then publishes derived CSV/Markdown **before** the authoritative JSON.
* ``exit_code_for(report)`` derives 0/1 and never trusts a self-asserted
  top-level flag.
* ``read_published(output_dir)`` is the consumer-side probe: a reader must
  accept a snapshot only when the authoritative JSON is complete, every
  requested case row exists and the derived formats carry the same run_id and
  generation.

Publication order, failures and limitations
-------------------------------------------
The authoritative JSON is replaced last for *every* snapshot. A crash can
leave old JSON paired with newer derived files; readers reject that mixed
generation. If JSON replacement succeeds, both derived files have already
been replaced. If it fails, JSON keeps its previous bytes. This unit does not
promise an all-file rollback and does not promise new files on unwritable
media. Readers must therefore compare run_id/generation across the three files
(``read_published``) and treat a mismatch as "not a pass". A failed
publication raises before the caller can report success; if a *previous run's*
complete report is still present it stays on disk as the last trustworthy
evidence of that older run, so callers must surface the write failure rather
than re-reading the directory.

Transient replacement denial
----------------------------
``os.replace`` can be denied transiently on Windows (WinError 5 access denied,
32 sharing violation, 33 lock violation) even though this process owns the
directory and the lock. Such a failure is retried: the *same* owned temporary
is re-attempted up to ``REPLACE_RETRY_ATTEMPTS`` times with the finite backoff
``REPLACE_RETRY_BACKOFF_S``. The waiting is bounded twice: by a monotonic
budget that starts with each replacement (``PUBLISH_RETRY_BUDGET_S``; the three
destinations of one snapshot may each transiently fail and later succeed, so a
snapshot can spend up to three replacement budgets, further cut by one caller
deadline, and any permanent failure stops the destinations not yet attempted)
and, when the caller supplies one, by ``write_report(...,
retry_deadline=...)``. That deadline is an absolute ``time.monotonic()``
instant, re-read after every backoff and immediately before every retry's
replacement: no retry is *started* once it has been observed, while the first
attempt is never withheld and the attempt already in flight still finishes its
own revalidation and its synchronous ``os.replace``. A scheduler sleep is best
effort and may return late; the guarantee is that re-check, not a hard real
time wake-up. The deadline bounds waiting, never publication itself -- a
report that can be published is never withheld because the budget is spent.

Only those three Windows codes are retried. A missing ``winerror`` (every POSIX
platform, and ``OSError(errno, ...)`` without an explicit Windows code) and any
other code are permanent for this run and propagate immediately, as does every
failure *before* the replacement (temporary creation, write, flush, fsync).
Before every attempt -- including after sleeping -- the writer re-runs the
full destination preflight, the exact lock-token check, the expected target
signature check and the source temporary's own descriptor identity and content
signature. The source is proven to be the created file once, immediately after
it is signed, so a file substituted while signing is never adopted as this
run's source. A changed target, a stolen lock, a vanished or substituted
temporary, a reparse point or a foreign target therefore stops publication and
preserves what is on disk. The target is never unlinked and never written
non-atomically. Cleanup deletes only the file this run created, proven by the
descriptor identity captured at creation; once a substitution or a content
change has been detected, the path is retained for explicit recovery instead
of deleted.

Locking policy: the lock file is created with ``O_CREAT | O_EXCL`` so two
owners can never race into the same directory; a present lock always fails
fast with the recorded owner. No live/stale process liveness guessing is
performed -- a lock left by a dead process must be removed manually after the
owner is confirmed gone. Only the current owner ever deletes its own lock and
its own temporary files.
"""
from __future__ import annotations

import csv
import hashlib
from contextlib import contextmanager
import io
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import threading
import time
from typing import NamedTuple
import uuid

from . import exports


SCHEMA = "plimsoll-core-verification-1"
LOCK_SCHEMA = "plimsoll-core-verification-lock-1"
JSON_NAME = "core-verification.json"
CSV_NAME = "core-verification.csv"
MD_NAME = "core-verification.md"
LOCK_NAME = ".plimsoll-core-verification.lock"
TEMP_PREFIX = ".plimsoll-core-verification-"
CSV_MARKER = "#plimsoll-core-verification-1"
MARKDOWN_MARKER = "<!-- plimsoll-core-verification-1 -->"
PROJECT_SCHEMA = "plimsoll-project-1"

REPORT_STATES = ("partial", "complete")
CASE_STATES = ("pending", "passed", "failed", "timeout", "error", "not_started")
SUITES = ("quick", "extended", "all")

# Transient Windows replacement denials, identified by their WinError code only.
# Anything else -- a missing winerror (every POSIX platform), another code, or a
# failure before os.replace -- is permanent for this run and is never retried.
TRANSIENT_REPLACE_WINERRORS = frozenset({
    5,   # ERROR_ACCESS_DENIED
    32,  # ERROR_SHARING_VIOLATION
    33,  # ERROR_LOCK_VIOLATION
})
# Finite backoff; the last entry is waited before the final attempt.
REPLACE_RETRY_BACKOFF_S = (0.01, 0.02, 0.04, 0.08, 0.16)
REPLACE_RETRY_ATTEMPTS = len(REPLACE_RETRY_BACKOFF_S) + 1
# Monotonic waiting budget for one destination replacement. Each of a
# snapshot's three destinations can transiently pay it before succeeding, so a
# snapshot is bounded by three of them; it is what bounds a slow or
# pathological filesystem independently of the attempt count.
PUBLISH_RETRY_BUDGET_S = 0.5

_SHA256 = re.compile(r"\A[0-9a-f]{64}\Z")

CSV_COLUMNS = (
    "schema", "run_id", "generation", "report_state", "suite",
    "case_id", "case_state", "assertion_passed", "case_reason",
    "check_name", "check_passed", "check_required", "unit",
    "measured", "expected", "tolerance", "check_reason",
)

_ESCAPES = (("\\", "&#92;"), ("|", "&#124;"), ("\r\n", "&#10;"),
            ("\n", "&#10;"), ("\r", "&#13;"))

_OWNED_LOCKS: dict[str, str] = {}
_SESSION_THREADS: dict[str, int] = {}
_EXPECTED_TARGETS: dict[str, dict] = {}
_REGISTRY = threading.Lock()


class ReportError(ValueError):
    """Base class for every invalid report or unusable destination."""


class DestinationError(ReportError):
    """The output directory or a fixed report name is not safe to write."""


class DestinationBusyError(DestinationError):
    """Another process (or this one) already owns the output directory."""


class PublishError(ReportError):
    """A publication step failed; previously replaced files stay replaced."""


class _Signature(NamedTuple):
    """Identity and content of one inspected file, bound at the same read."""

    device: int
    inode: int
    size: int
    mtime_ns: int
    digest: str


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------

def _strict_json_text(report: object) -> str:
    try:
        return exports.serialize_document(report, format="json")
    except (TypeError, RecursionError, ValueError) as error:
        raise ReportError(
            f"report is not strictly JSON serialisable: {error}") from error


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ReportError(message)


def _exact_bool(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise ReportError(f"{label} must be a JSON boolean, got "
                          f"{type(value).__name__}")
    return value


def _text(value: object, label: str, *, allow_empty: bool = True) -> str:
    if not isinstance(value, str):
        raise ReportError(f"{label} must be a string, got "
                          f"{type(value).__name__}")
    if not allow_empty and not value.strip():
        raise ReportError(f"{label} must not be empty")
    return value


def _optional_text(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _text(value, label)


def _required_text(value: object, label: str) -> str:
    return _text(value, label, allow_empty=False)


def _sha256(value: object, label: str) -> str:
    text = _text(value, label)
    if not _SHA256.match(text):
        raise ReportError(f"{label} must be 64 lowercase hex characters: "
                          f"{text!r}")
    return text


def _validate_source_identity(value: object) -> None:
    if not isinstance(value, dict):
        raise ReportError("source_identity must be a JSON object")
    files = value.get("files")
    if not isinstance(files, list) or not files:
        raise ReportError("source_identity.files must be a non-empty array")
    for index, entry in enumerate(files):
        label = f"source_identity.files[{index}]"
        if not isinstance(entry, dict):
            raise ReportError(f"{label} must be a JSON object")
        _required_text(entry.get("module"), f"{label}.module")
        _required_text(entry.get("path"), f"{label}.path")
        _sha256(entry.get("sha256"), f"{label}.sha256")
    versions = value.get("method_versions")
    if not isinstance(versions, dict):
        raise ReportError("source_identity.method_versions must be a JSON object")
    _exact_bool(value.get("consistent"), "source_identity.consistent")


def _validate_check(value: object, label: str) -> None:
    if not isinstance(value, dict):
        raise ReportError(f"{label} must be a JSON object")
    _required_text(value.get("name"), f"{label}.name")
    for key in ("passed", "required", "measured", "expected", "tolerance",
                "unit", "reason"):
        if key not in value:
            raise ReportError(f"{label}.{key} is required")
    if value["passed"] is not None:
        _exact_bool(value["passed"], f"{label}.passed")
    _exact_bool(value["required"], f"{label}.required")
    _text(value["unit"], f"{label}.unit")
    reason = _optional_text(value["reason"], f"{label}.reason")
    if value["passed"] is not True and not (reason and reason.strip()):
        raise ReportError(
            f"{label} did not pass and must carry an explicit reason "
            f"(passed={value['passed']!r})")


def _validate_row(value: object, label: str) -> str:
    if not isinstance(value, dict):
        raise ReportError(f"{label} must be a JSON object")
    case_id = _required_text(value.get("id"), f"{label}.id")
    state = _text(value.get("state"), f"{label}.state")
    if state not in CASE_STATES:
        raise ReportError(f"{label}.state must be one of {CASE_STATES}")
    _exact_bool(value.get("assertion_passed"), f"{label}.assertion_passed")
    if "reason" not in value:
        raise ReportError(f"{label}.reason is required (string or null)")
    reason = _optional_text(value["reason"], f"{label}.reason")
    checks = value.get("checks")
    if not isinstance(checks, list):
        raise ReportError(f"{label}.checks must be an array")
    if state in ("failed", "timeout", "error") and not (reason and reason.strip()):
        raise ReportError(
            f"{label} state {state!r} requires an explicit row reason")
    for index, check in enumerate(checks):
        _validate_check(check, f"{label}.checks[{index}]")
    return case_id


def validate_report(report: dict) -> None:
    """Reject anything that is not a complete, strict verification report."""
    if not isinstance(report, dict):
        raise ReportError(f"report must be a JSON object, got "
                          f"{type(report).__name__}")
    # Strict JSON first: no NaN/Inf, no cycles, string keys, no custom objects.
    _strict_json_text(report)
    if report.get("schema") != SCHEMA:
        raise ReportError(f"report schema must be {SCHEMA!r}, got "
                          f"{report.get('schema')!r}")
    run_id = _required_text(report.get("run_id"), "run_id")
    try:
        uuid.UUID(run_id)
    except (ValueError, AttributeError, TypeError) as error:
        raise ReportError(f"run_id must be a UUID string: {run_id!r}") from error
    generation = report.get("generation")
    if isinstance(generation, bool) or not isinstance(generation, int) \
            or generation < 0:
        raise ReportError("generation must be a non-negative integer that is "
                          "not a boolean")
    state = _text(report.get("state"), "state")
    if state not in REPORT_STATES:
        raise ReportError(f"state must be one of {REPORT_STATES}")
    suite = _text(report.get("suite"), "suite")
    if suite not in SUITES:
        raise ReportError(f"suite must be one of {SUITES}")
    requested = report.get("requested_case_ids")
    if not isinstance(requested, list) or not requested:
        raise ReportError("requested_case_ids must be a non-empty array")
    for index, case_id in enumerate(requested):
        _required_text(case_id, f"requested_case_ids[{index}]")
    if len(set(requested)) != len(requested):
        raise ReportError("requested_case_ids must not contain duplicates")
    cases = report.get("cases")
    if not isinstance(cases, list):
        raise ReportError("cases must be an array")
    seen: list[str] = []
    for index, row in enumerate(cases):
        seen.append(_validate_row(row, f"cases[{index}]"))
    duplicates = sorted({item for item in seen if seen.count(item) > 1})
    if duplicates:
        raise ReportError(f"cases must contain one row per requested id; "
                          f"duplicated: {duplicates}")
    missing = [item for item in requested if item not in set(seen)]
    extra = sorted(set(seen) - set(requested))
    if missing or extra:
        raise ReportError(
            f"cases must cover requested_case_ids exactly; missing={missing} "
            f"unrequested={extra}")
    _validate_source_identity(report.get("source_identity"))
    _sha256(report.get("input_manifest_sha256"), "input_manifest_sha256")


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def _md_cell(value: str) -> str:
    text = str(value)
    for raw, escaped in _ESCAPES:
        text = text.replace(raw, escaped)
    return text


def _json_value(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _plain_cell(value: object) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return value
    return _json_value(value)


def _render_csv(report: dict) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    output.write(CSV_MARKER + "\n")
    output.write(
        f"#run_id={report['run_id']};generation={report['generation']};"
        f"state={report['state']};suite={report['suite']};"
        f"partial={'YES' if report['state'] == 'partial' else 'NO'}\n")
    writer.writerow(CSV_COLUMNS)
    for row in report["cases"]:
        common = [report["schema"], report["run_id"], report["generation"],
                  report["state"], report["suite"], row["id"], row["state"],
                  _plain_cell(row["assertion_passed"]),
                  _plain_cell(row["reason"])]
        for check in row["checks"] or (None,):
            if check is None:
                writer.writerow(common + [""] * (len(CSV_COLUMNS) - len(common)))
                continue
            writer.writerow(common + [
                check["name"], _plain_cell(check["passed"]),
                _plain_cell(check["required"]), check["unit"],
                _json_value(check["measured"]), _json_value(check["expected"]),
                _json_value(check["tolerance"]), _plain_cell(check["reason"]),
            ])
    return output.getvalue()


def _md_table(header: tuple[str, ...], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |",
             "| " + " | ".join("---" for _ in header) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(_md_cell(cell) for cell in row) + " |")
    return lines


def _render_markdown(report: dict) -> str:
    identity = report["source_identity"]
    lines = [MARKDOWN_MARKER, "# Plimsoll core verification report", ""]
    for key, value in (("schema", report["schema"]),
                       ("run_id", report["run_id"]),
                       ("generation", report["generation"]),
                       ("state", report["state"]),
                       ("suite", report["suite"]),
                       ("input_manifest_sha256", report["input_manifest_sha256"])):
        lines.append(f"- {key}: {_md_cell(str(value))}")
    lines.append("")
    if report["state"] == "partial":
        lines.append("**PARTIAL RESULT - not a passing verification.**")
        lines.append("")
    lines.append("Derived exit code: "
                 f"`{exit_code_for(report)}` (complete, consistent source "
                 "identity, one passing row per requested case and every "
                 "required check passed).")
    lines.append("")
    lines.append("Table cells escape `\\` as `&#92;`, `|` as `&#124;`, "
                 "CR as `&#13;` and LF as `&#10;`; replacing those entities "
                 "recovers the exact original value.")
    lines.append("")
    lines.append("## Source identity")
    lines.append("")
    lines.append(f"- consistent: {_md_cell(str(identity['consistent']))}")
    lines.append("")
    lines.extend(_md_table(
        ("module", "path", "sha256"),
        [[entry["module"], entry["path"], entry["sha256"]]
         for entry in identity["files"]]))
    lines.append("")
    lines.append("## Method versions")
    lines.append("")
    lines.extend(_md_table(("name", "version"), [
        [name, _json_value(value)]
        for name, value in sorted(identity["method_versions"].items())]))
    lines.append("")
    lines.append("## Cases")
    lines.append("")
    lines.extend(_md_table(
        ("case_id", "case_state", "assertion_passed", "reason"),
        [[row["id"], row["state"], _plain_cell(row["assertion_passed"]),
          _plain_cell(row["reason"])] for row in report["cases"]]))
    lines.append("")
    lines.append("## Checks")
    lines.append("")
    check_rows: list[list[str]] = []
    for row in report["cases"]:
        if not row["checks"]:
            check_rows.append([row["id"], "(none)", "", "", "", "", "", "", ""])
            continue
        for check in row["checks"]:
            check_rows.append([
                row["id"], check["name"], _plain_cell(check["required"]),
                _plain_cell(check["passed"]), check["unit"],
                _json_value(check["measured"]), _json_value(check["expected"]),
                _json_value(check["tolerance"]), _plain_cell(check["reason"])])
    lines.extend(_md_table(
        ("case_id", "check", "required", "passed", "unit", "measured",
         "expected", "tolerance", "reason"), check_rows))
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# exit code
# --------------------------------------------------------------------------

def exit_code_for(report: dict) -> int:
    """Derive the verification exit code; malformed input never passes."""
    try:
        validate_report(report)
    except (ReportError, TypeError, RecursionError):
        return 1
    if report["state"] != "complete":
        return 1
    if report["source_identity"]["consistent"] is not True:
        return 1
    rows = {row["id"]: row for row in report["cases"]}
    requested = list(report["requested_case_ids"])
    if len(rows) != len(report["cases"]) or set(rows) != set(requested):
        return 1
    for case_id in requested:
        row = rows[case_id]
        if row["state"] != "passed" or row["assertion_passed"] is not True:
            return 1
        checks = row["checks"]
        required = [check for check in checks if check["required"] is True]
        if not checks or not required:
            return 1
        for check in required:
            if check["passed"] is not True:
                return 1
    return 0


# --------------------------------------------------------------------------
# destinations
# --------------------------------------------------------------------------

def _is_reparse(path: Path) -> bool:
    try:
        info = os.lstat(path)
    except (OSError, ValueError):
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & marker)


def _prepare_directory(output_dir: object) -> Path:
    if output_dir is None or isinstance(output_dir, bool):
        raise DestinationError("output_dir is required")
    directory = Path(output_dir)
    if not directory.is_absolute():
        raise DestinationError(
            f"output directory must be an absolute path: {directory}")
    for candidate in _ancestors(directory):
        if os.path.lexists(candidate) and _is_reparse(candidate):
            raise DestinationError(
                f"output path crosses a link/junction/reparse point: "
                f"{candidate}")
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise DestinationError(
            f"cannot create output directory {directory}: {error}") from error
    for candidate in _ancestors(directory):
        if os.path.lexists(candidate) and _is_reparse(candidate):
            raise DestinationError(
                f"output path crosses a link/junction/reparse point: "
                f"{candidate}")
    return directory


def _ancestors(path: Path) -> list[Path]:
    chain = []
    current = path
    while True:
        chain.append(current)
        parent = current.parent
        if parent == current:
            return chain
        current = parent


def _recognize(name: str, text: str) -> tuple[bool, str]:
    if name == JSON_NAME:
        try:
            document = json.loads(text)
        except ValueError as error:
            return False, f"existing {name} is not valid JSON ({error})"
        if not isinstance(document, dict):
            return False, f"existing {name} is not a JSON object"
        schema = document.get("schema")
        if schema == PROJECT_SCHEMA:
            return False, (f"existing {name} is an input project file "
                           f"({PROJECT_SCHEMA}); refusing to overwrite it")
        if schema != SCHEMA:
            return False, (f"existing {name} has schema {schema!r}, not "
                           f"{SCHEMA!r}")
        try:
            validate_report(document)
        except ReportError as error:
            return False, f"existing {name} is not a strict owned report ({error})"
        return True, ""
    lines = text.splitlines()
    marker = CSV_MARKER if name == CSV_NAME else MARKDOWN_MARKER
    if not lines:
        return False, f"existing {name} is empty"
    if lines[0].rstrip("\r") != marker:
        return False, (f"existing {name} does not start with the "
                       f"{SCHEMA} marker line")
    identity = _csv_identity(text) if name == CSV_NAME else _markdown_identity(text)
    try:
        uuid.UUID(identity["run_id"])
        generation = int(identity["generation"])
        if generation < 0 or identity["state"] not in REPORT_STATES or identity.get("suite") not in SUITES:
            raise ValueError("invalid identity")
        if name == CSV_NAME:
            reader = csv.reader(io.StringIO("\n".join(lines[2:])))
            if tuple(next(reader)) != CSV_COLUMNS:
                raise ValueError("missing canonical column header")
            for row in reader:
                if len(row) != len(CSV_COLUMNS) or row[0] != SCHEMA:
                    raise ValueError("malformed canonical CSV row")
        elif identity.get("schema") != SCHEMA or not _SHA256.fullmatch(identity.get("input_manifest_sha256", "")) or "# Plimsoll core verification report" not in lines:
            raise ValueError("missing canonical Markdown identity")
    except (KeyError, ValueError, StopIteration) as error:
        return False, f"existing {name} has incomplete ownership evidence ({error})"
    return True, ""


def preflight_destinations(output_dir: Path) -> Path:
    """Reject unsafe output names before the first write of a run."""
    directory = _prepare_directory(output_dir)
    problems: list[str] = []
    for name in (JSON_NAME, CSV_NAME, MD_NAME):
        path = directory / name
        if not os.path.lexists(path):
            continue
        if _is_reparse(path):
            problems.append(f"{name} is a link/junction/reparse point")
            continue
        if not path.is_file():
            problems.append(f"{name} is not a regular file")
            continue
        try:
            raw = path.read_bytes()
        except OSError as error:
            problems.append(f"{name} cannot be read ({error})")
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            problems.append(f"{name} is not valid UTF-8 ({error})")
            continue
        owned, why = _recognize(name, text)
        if not owned:
            problems.append(why)
    if problems:
        raise DestinationError(
            "refusing to write core verification evidence into "
            f"{directory}: " + "; ".join(problems))
    return directory


# --------------------------------------------------------------------------
# exclusive output session
# --------------------------------------------------------------------------

def _lock_key(directory: Path) -> str:
    return os.path.normcase(os.path.abspath(str(directory)))


def _read_lock_owner(path: Path) -> dict:
    try:
        raw = path.read_bytes()
    except OSError:
        return {}
    try:
        document = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {}
    return document if isinstance(document, dict) else {}


def _acquire_lock(directory: Path) -> str:
    key = _lock_key(directory)
    with _REGISTRY:
        if key in _OWNED_LOCKS:
            raise DestinationBusyError(
                f"output directory is already locked by this process: "
                f"{directory}")
    token = uuid.uuid4().hex
    payload = json.dumps({
        "schema": LOCK_SCHEMA,
        "token": token,
        "pid": os.getpid(),
        "host": os.environ.get("COMPUTERNAME") or "",
        "acquired_utc": time_utc(),
    }, sort_keys=True).encode("utf-8")
    path = directory / LOCK_NAME
    try:
        # O_EXCL creation: no check-then-create race with a competing owner.
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        owner = _read_lock_owner(path)
        detail = f"pid {owner.get('pid')!r}" if owner else "unreadable owner"
        raise DestinationBusyError(
            f"{path} already exists ({detail}); another run owns this output "
            f"directory. This tool never guesses whether an existing lock is "
            f"stale: confirm the owner is gone, then delete {LOCK_NAME} "
            f"manually.") from error
    created = None
    try:
        created = os.fstat(descriptor)
        stream = os.fdopen(descriptor, "wb")
        descriptor = None  # stream now owns the descriptor, including failure
        with stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException as error:
        if descriptor is not None:
            os.close(descriptor)
        try:
            current = os.lstat(path)
            owner = _read_lock_owner(path)
            if created is not None and (current.st_dev, current.st_ino) == (created.st_dev, created.st_ino) and (not owner or owner.get("token") == token):
                path.unlink()
            elif created is None:
                error.add_note(f"lock identity unavailable; retained {path} for explicit recovery")
        except OSError as cleanup_error:
            error.add_note(f"created lock cleanup failed: {cleanup_error}")
        if isinstance(error, OSError):
            raise PublishError(f"cannot persist output lock in {directory}: {error}") from error
        raise
    with _REGISTRY:
        _OWNED_LOCKS[key] = token
    return token


def _discard_lock(path: Path, token: str) -> None:
    owner = _read_lock_owner(path)
    if not owner or owner.get("schema") != LOCK_SCHEMA or owner.get("token") != token or _is_reparse(path):
        raise DestinationError(
            f"{path} is owned by another token; refusing to delete it")
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _release_lock(directory: Path, token: str) -> None:
    try:
        _discard_lock(directory / LOCK_NAME, token)
    finally:
        with _REGISTRY:
            _OWNED_LOCKS.pop(_lock_key(directory), None)
            _SESSION_THREADS.pop(_lock_key(directory), None)


def _require_lock(directory, token):
    path = directory / LOCK_NAME
    owner = _read_lock_owner(path) if not _is_reparse(path) else {}
    if owner.get("schema") != LOCK_SCHEMA or owner.get("token") != token:
        raise DestinationError("output lock ownership was lost; refusing publication")


def _file_signature(path):
    if not os.path.lexists(path):
        return None
    if _is_reparse(path) or not path.is_file():
        raise DestinationError(f"output target is not an ordinary owned file: {path}")
    first = os.lstat(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    last = os.lstat(path)
    signature = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
    if signature(first) != signature(last):
        raise DestinationError(f"output target changed while inspected: {path}")
    return _Signature(*signature(last), digest)


def time_utc() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds")


@contextmanager
def output_session(output_dir):
    """Lock one output directory for a whole run and preflight its names.

    Yields the prepared absolute directory. The exclusive lock is held from
    before the first calculation until after the last publication, so
    ``write_report`` calls inside the body reuse it instead of re-locking.
    """
    directory = _prepare_directory(output_dir)
    token = _acquire_lock(directory)
    _SESSION_THREADS[_lock_key(directory)] = threading.get_ident()
    try:
        preflight_destinations(directory)
        yield directory
    except BaseException as error:
        try:
            _release_lock(directory, token)
        except Exception as release_error:  # keep the primary cause
            error.add_note(f"output lock release failed: {release_error}")
        raise
    else:
        _release_lock(directory, token)


# --------------------------------------------------------------------------
# atomic publication
# --------------------------------------------------------------------------

def _is_transient_replace_failure(error: BaseException) -> bool:
    """True only for the identified Windows replacement denials.

    The WinError code is the whole classification: ``errno`` is not consulted
    because the same value means different things per platform, and a POSIX
    failure never carries ``winerror`` at all.
    """
    return getattr(error, "winerror", None) in TRANSIENT_REPLACE_WINERRORS


def _retry_deadline(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or not math.isfinite(value):
        raise ReportError(
            "retry_deadline must be None or a finite time.monotonic() "
            f"instant, got {value!r}")
    return float(value)


def _exhausted_note(attempts: int, denials: list, reason: str) -> str:
    return (f"transient Windows replacement denial {denials} was not retried "
            f"after {attempts} attempt(s): {reason}; the failed target keeps "
            f"its previous bytes and readers must reject any mixed generation")


def _temporary_identity(descriptor: int) -> tuple:
    """Identity of the created file, taken from its own descriptor."""
    info = os.fstat(descriptor)
    return (info.st_dev, info.st_ino)


def _is_our_file(path: Path, identity: tuple | None) -> bool:
    """True when the path still holds the file this run created."""
    if identity is None:
        return True  # no descriptor proof was ever taken; content still binds
    try:
        info = os.lstat(path)
    except (OSError, ValueError):
        return False
    return (info.st_dev, info.st_ino) == identity


def _still_ours(path: Path, identity: tuple | None) -> bool:
    """True when it is safe to unlink that path during cleanup.

    ``False`` for an unknown identity and for any path whose inode is not the
    created one: cleanup must retain such a file instead of deleting somebody
    else's.
    """
    if identity is None:
        return False
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return True  # already gone: nothing of ours is left to delete
    except (OSError, ValueError):
        return False  # cannot prove ownership: retain
    return (info.st_dev, info.st_ino) == identity


def _publish_text(directory: Path, name: str, text: str, *, token: str,
                  retry_deadline: float | None) -> None:
    """Replace one owned destination atomically, retrying transient denial.

    The temporary is created, signed and identified once. Every attempt -- the
    first and each retry, after the backoff -- re-proves ownership of the
    destination names, of the lock, of the expected target bytes and of the
    source temporary before calling ``os.replace``, and every retry re-reads
    the clock so that a late wake-up cannot buy an extra replacement. The
    target is never unlinked, never truncated and never rewritten non-atomically.
    """
    destination = directory / name
    encoded = text.encode("utf-8")
    temporary: Path | None = None
    identity: tuple | None = None
    retain = False
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=directory, prefix=TEMP_PREFIX, suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            identity = _temporary_identity(stream.fileno())
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        source_signature = _file_signature(temporary)
        # Bind the source to this run's rendered bytes and to the file the
        # descriptor created. A signature read after a substitution cannot
        # certify somebody else's content, so the content is compared with what
        # was written, not merely with whatever the path holds now.
        rendered_digest = hashlib.sha256(encoded).hexdigest()
        if not _is_our_file(temporary, identity) \
                or source_signature.digest != rendered_digest:
            retain = True
            raise DestinationError(
                f"owned source temporary vanished or changed: {temporary}")
        expected = _EXPECTED_TARGETS[_lock_key(directory)][name]
        # The budget starts with this replacement, not with the run, so waiting
        # is bounded even when the caller supplies no deadline at all.
        deadline = time.monotonic() + PUBLISH_RETRY_BUDGET_S
        if retry_deadline is not None:
            deadline = min(deadline, retry_deadline)
        denials: list = []
        denial: OSError | None = None
        attempt = 0
        while True:
            # Bind preflight to actual target bytes and recheck immediately
            # before every replacement. This guards cooperative/concurrent
            # writes, not an OS adversary racing inside the final replace
            # system call. A sleep must never create a blind overwrite.
            preflight_destinations(directory)
            _require_lock(directory, token)
            if _file_signature(destination) != expected:
                raise DestinationError(
                    f"output target changed after preflight: {destination}")
            if not _is_our_file(temporary, identity) \
                    or _file_signature(temporary) != source_signature:
                # Someone else now owns that path: it is retained, never deleted.
                retain = True
                raise DestinationError(
                    f"owned source temporary vanished or changed: {temporary}")
            if attempt and deadline <= time.monotonic():
                # A sleep is best effort and may return long after it was asked
                # for. The first attempt is never withheld, because final failure
                # evidence must still be published; every retry re-reads the
                # clock here, after the sleep and this ownership preflight, and
                # stops with the original denial rather than replacing anyway.
                denial.add_note(_exhausted_note(
                    len(denials), denials,
                    "the publication retry deadline passed while waiting"))
                raise denial
            try:
                os.replace(temporary, destination)
            except OSError as error:
                if not _is_transient_replace_failure(error):
                    raise
                denials.append(error.winerror)
                denial = error
                if attempt >= len(REPLACE_RETRY_BACKOFF_S):
                    error.add_note(_exhausted_note(
                        attempt + 1, denials,
                        f"the {REPLACE_RETRY_ATTEMPTS}-attempt limit"))
                    raise
                remaining = deadline - time.monotonic()
                if remaining <= 0.0:
                    error.add_note(_exhausted_note(
                        attempt + 1, denials,
                        "the publication retry deadline is exhausted"))
                    raise
                delay = min(REPLACE_RETRY_BACKOFF_S[attempt], remaining)
                attempt += 1
                time.sleep(delay)
                continue
            temporary = None
            return
    except BaseException as error:
        if temporary is not None:
            if retain or not _still_ours(temporary, identity):
                error.add_note(
                    f"{temporary} is no longer provably this run's file; "
                    f"retained for explicit recovery instead of deleted")
            else:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError as cleanup_error:
                    error.add_note(f"owned temporary cleanup failed at "
                                   f"{temporary}: {cleanup_error}")
        raise


def write_report(report: dict, output_dir: Path, *,
                 retry_deadline=None) -> dict:
    """Publish one snapshot as CSV, Markdown and the authoritative JSON.

    All three documents are rendered and validated in memory before the first
    mutation, then the derived formats are replaced before the authoritative
    JSON. Returns the three exact output paths.

    ``retry_deadline`` is an optional keyword-only absolute ``time.monotonic()``
    instant, so every existing call is unchanged. It bounds *waiting*, not the
    synchronous ``os.replace`` call: the clock is re-read after every backoff
    and immediately before every retry's replacement, so no retry starts once
    the deadline has been observed (a scheduler sleep may still overshoot in
    wall time -- the guarantee is the re-check, not a hard real time wake-up).
    The first attempt is never withheld, because final failure evidence must
    still be published. Omitted means this module's own finite per-replacement
    budget; an instant already in the past disables retries entirely, which is
    exactly the behaviour the final failure-evidence publication after a total
    timeout needs. ``verify`` passes its remaining-run instant so that transient
    denial recovery cannot push a command past ``--total-timeout-s``.
    """
    validate_report(report)
    caller_deadline = _retry_deadline(retry_deadline)
    directory = _prepare_directory(output_dir)
    token = _OWNED_LOCKS.get(_lock_key(directory))
    owns_lock = token is not None and _SESSION_THREADS.get(_lock_key(directory)) == threading.get_ident()
    if not owns_lock:
        token = _acquire_lock(directory)
    try:
        _require_lock(directory, token)
        preflight_destinations(directory)
        _EXPECTED_TARGETS[_lock_key(directory)] = {name: _file_signature(directory / name) for name in (CSV_NAME, MD_NAME, JSON_NAME)}
        texts = {
            JSON_NAME: _strict_json_text(report),
            CSV_NAME: _render_csv(report),
            MD_NAME: _render_markdown(report),
        }
        published: list[str] = []
        try:
            for name in (CSV_NAME, MD_NAME, JSON_NAME):
                _publish_text(directory, name, texts[name], token=token,
                              retry_deadline=caller_deadline)
                published.append(name)
        except BaseException as error:
            pending = [name for name in (CSV_NAME, MD_NAME, JSON_NAME)
                       if name not in published]
            raise PublishError(
                f"core verification publication failed in {directory}: "
                f"replaced={published} pending={pending}; the failed target "
                f"and every not-yet-published file keep their previous "
                f"bytes, but files already replaced stay replaced and "
                f"readers must reject the mixed generation. Cause: "
                f"{error}") from error
    finally:
        _EXPECTED_TARGETS.pop(_lock_key(directory), None)
        if not owns_lock:
            primary = sys.exception()
            try:
                _release_lock(directory, token)
            except Exception as cleanup_error:
                if primary is None:
                    raise
                primary.add_note(f"output lock cleanup also failed: {cleanup_error}")
    return {"json": directory / JSON_NAME, "csv": directory / CSV_NAME,
            "md": directory / MD_NAME}


# --------------------------------------------------------------------------
# consumer-side probe
# --------------------------------------------------------------------------

def _strict_load(path: Path) -> object:
    def constant(name):
        raise ValueError(f"non-finite JSON token {name}")

    def number(text):
        value = float(text)
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError(f"non-finite JSON number {text}")
        return value

    return json.loads(path.read_text(encoding="utf-8"), parse_constant=constant,
                      parse_float=number)


def _csv_identity(text: str) -> dict:
    lines = text.splitlines()
    if len(lines) < 2 or lines[0].rstrip("\r") != CSV_MARKER:
        return {}
    identity = {}
    for item in lines[1].lstrip("#").split(";"):
        key, separator, value = item.partition("=")
        if separator:
            identity[key.strip()] = value.strip()
    return identity


def _markdown_identity(text: str) -> dict:
    lines = text.splitlines()
    if not lines or lines[0].rstrip("\r") != MARKDOWN_MARKER:
        return {}
    identity = {}
    for line in lines[1:]:
        if not line.strip():
            if identity:
                break
            continue
        if not line.startswith("- "):
            continue
        key, separator, value = line[2:].partition(":")
        if separator:
            identity[key.strip()] = value.strip()
    return identity


def _normalised(identity: dict) -> dict:
    generation = identity.get("generation")
    try:
        generation = int(generation)
    except (TypeError, ValueError):
        generation = None
    return {"run_id": identity.get("run_id"), "generation": generation,
            "state": identity.get("state")}


def read_published(output_dir: Path) -> dict:
    """Read one published snapshot the way a consumer must judge it.

    ``passing`` is true only when all three files exist, the authoritative
    JSON validates, the derived formats carry the same run_id, generation and
    state, and the derived exit code is 0.
    """
    directory = Path(output_dir)
    probe = {"present": False, "report": None, "exit_code": 1,
             "identity": {}, "identity_match": False, "passing": False,
             "problem": None}
    json_path = directory / JSON_NAME
    csv_path = directory / CSV_NAME
    md_path = directory / MD_NAME
    if not all(path.is_file() for path in (json_path, csv_path, md_path)):
        probe["problem"] = "one or more of the three report files is missing"
        return probe
    probe["present"] = True
    try:
        document = _strict_load(json_path)
    except (OSError, ValueError, UnicodeDecodeError) as error:
        probe["problem"] = f"authoritative JSON unreadable: {error}"
        return probe
    if not isinstance(document, dict):
        probe["problem"] = "authoritative JSON is not an object"
        return probe
    probe["report"] = document
    probe["exit_code"] = exit_code_for(document)
    try:
        csv_text = csv_path.read_text(encoding="utf-8")
        md_text = md_path.read_text(encoding="utf-8")
        for name, source in ((CSV_NAME, csv_text), (MD_NAME, md_text)):
            owned, reason = _recognize(name, source)
            if not owned:
                probe["problem"] = reason
                return probe
        csv_identity = _normalised(_csv_identity(csv_text))
        md_identity = _normalised(_markdown_identity(md_text))
    except (OSError, UnicodeDecodeError) as error:
        probe["problem"] = f"derived format unreadable: {error}"
        return probe
    probe["identity"] = {"csv": csv_identity, "markdown": md_identity}
    authoritative = {"run_id": document.get("run_id"),
                     "generation": document.get("generation"),
                     "state": document.get("state")}
    probe["identity_match"] = (csv_identity == authoritative
                               and md_identity == authoritative)
    if not probe["identity_match"]:
        probe["problem"] = (
            "derived formats do not carry the authoritative run_id, "
            "generation and state")
    probe["passing"] = bool(probe["identity_match"]
                            and probe["exit_code"] == 0)
    return probe
