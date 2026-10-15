"""Recovery from transient Windows replacement denial during publication.

Scope: the publication half of :mod:`plimsoll.verification_report` plus the
``verify`` CLI callback that bounds its waiting. A real ``verify --suite quick``
run on this host failed twice at ``os.replace(tmp, core-verification.csv)`` with
``WinError 5`` and produced no evidence at all. These tests pin the recovery
contract:

* only ``os.replace`` failures whose ``winerror`` is 5/32/33 are retried, with a
  finite attempt count and a finite backoff inside one publication budget;
* every attempt re-runs the full destination preflight, the exact lock-token
  check and the expected-target signature check, so a target that changed, a
  stolen lock, a vanished source temporary or a foreign file stops publication
  instead of overwriting evidence after sleeping;
* retry waiting is clipped to the caller's monotonic deadline, and a report that
  cannot be published never becomes a passing authoritative JSON.

Everything except the injected ``os.replace`` denial is real: real temporary
files, real fsync, real signatures, real atomic replacement, real reader probe.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import pytest  # noqa: E402

from plimsoll import app, verification as v  # noqa: E402
from plimsoll import verification_report as vr  # noqa: E402
from plimsoll.verification_cases import build_cases  # noqa: E402


SHA_A = "a" * 64
SHA_B = "b" * 64
RUN_A = "11111111-2222-4333-8444-555555555555"
RUN_B = "99999999-8888-4777-8666-555555555555"

# The identified transient Windows denial codes, written out independently of
# the product constants so a widened product set cannot silently pass here.
TRANSIENT_CODES = (5, 32, 33)
# 0.01+0.02+0.04+0.08+0.16 = 0.31 s: a run that waited out the full backoff is
# clearly slower than this, a clipped or non-retried run is clearly faster. The
# attempt counts below are the decisive evidence; this only separates the two
# regimes on a host whose filesystem is slower than this one.
NO_FULL_BACKOFF_S = 0.30
FOREVER = 10_000


# --------------------------------------------------------------------------
# fixtures and builders
# --------------------------------------------------------------------------

def a_check(name="volume_error", passed=True, required=True, measured=-1.25e-06,
            expected=0.0, tolerance=1e-09, unit="m3", reason=None):
    return {"name": name, "passed": passed, "required": required,
            "measured": measured, "expected": expected, "tolerance": tolerance,
            "unit": unit, "reason": reason}


def a_row(case_id="scale-tank-1", state="passed", assertion_passed=True,
          reason=None, checks=None):
    return {"id": case_id, "state": state, "assertion_passed": assertion_passed,
            "reason": reason,
            "checks": [a_check()] if checks is None else checks}


def a_report(cases=None, *, run_id=RUN_A, generation=0, state="complete",
             suite="quick", consistent=True):
    rows = [a_row()] if cases is None else list(cases)
    return {"schema": vr.SCHEMA, "run_id": run_id, "generation": generation,
            "state": state, "suite": suite,
            "requested_case_ids": [row["id"] for row in rows],
            "cases": rows,
            "source_identity": {
                "files": [{"module": "plimsoll.hull",
                           "path": "C:/pkg/plimsoll/hull.py", "sha256": SHA_A},
                          {"module": "plimsoll.verification_report",
                           "path": "C:/pkg/plimsoll/verification_report.py",
                           "sha256": SHA_B}],
                "method_versions": {"stationed_hull": "hull-1"},
                "consistent": consistent},
            "input_manifest_sha256": SHA_A}


@pytest.fixture()
def out_dir(tmp_path):
    directory = tmp_path / "evidence"
    directory.mkdir()
    return directory


def csv_identity(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    identity = {}
    for item in lines[1].lstrip("#").split(";"):
        key, separator, value = item.partition("=")
        if separator:
            identity[key.strip()] = value.strip()
    return identity


def md_identity(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
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


def assert_no_owned_temporary(directory: Path) -> None:
    leaked = sorted(p.name for p in directory.iterdir()
                    if p.name.startswith(vr.TEMP_PREFIX))
    assert leaked == []


def assert_no_lock(directory: Path) -> None:
    assert not (directory / vr.LOCK_NAME).exists()


def snapshot_bytes(directory: Path) -> dict:
    return {name: (directory / name).read_bytes()
            for name in (vr.JSON_NAME, vr.CSV_NAME, vr.MD_NAME)
            if (directory / name).exists()}


def published_json(directory: Path) -> dict:
    return json.loads((directory / vr.JSON_NAME).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# fault injection: the only mocked call is os.replace
# --------------------------------------------------------------------------

def windows_denial(code, path, message="simulated Windows replacement denial"):
    """The OSError shape a real ``os.replace`` denial produces on Windows.

    ``winerror`` is the only field the product classifies on: a POSIX host never
    sets it, and ``OSError(errno, ...)`` without an explicit Windows code does
    not either, which is exactly why errno alone must not drive a retry.
    """
    error = PermissionError(code, f"[WinError {code}] {message}", str(path))
    error.winerror = code
    return error


def _plain_errno_five(path):
    return OSError(5, "injected replace failure", str(path))


def _posix_eacces(path):
    error = PermissionError(13, "Permission denied", str(path))
    assert getattr(error, "winerror", None) is None
    return error


def _no_space(path):
    return OSError(28, "No space left on device", str(path))


def _other_windows_code(path):
    return windows_denial(1117, path,
                          "the device does not recognize the command")


NON_TRANSIENT = {
    "errno-5-without-winerror": _plain_errno_five,
    "posix-eacces-without-winerror": _posix_eacces,
    "enospc": _no_space,
    "unrelated-winerror-1117": _other_windows_code,
}


class ReplaceSpy:
    """The real ``os.replace``, with counted denials or a permanent fault.

    ``transient`` maps a destination name to ``(attempts, winerror)``: the first
    ``attempts`` attempts of that destination fail with a transient Windows
    denial, later attempts really replace. ``failure`` maps a destination name
    to ``factory(spy, attempt, source, target)`` raising on every attempt. ``hook`` runs before every attempt,
    which is how a concurrent writer or a lock thief is staged *after* the
    preflight and *between* attempts.
    """

    def __init__(self, monkeypatch, *, transient=None, failure=None, hook=None):
        self.transient = {name: tuple(spec) for name, spec
                          in (transient or {}).items()}
        self.failure = dict(failure or {})
        self.hook = hook
        self.calls: list[tuple[Path, Path]] = []
        self.denied: list[str] = []
        self.denied_at: list[float] = []
        self.attempted_at: list[float] = []
        self.succeeded: list[str] = []
        self._monkeypatch = monkeypatch

    def attempts(self, name: str) -> int:
        return sum(1 for _, dst in self.calls if dst.name == name)

    def sources(self, name: str) -> list[Path]:
        return [src for src, dst in self.calls if dst.name == name]

    def __enter__(self):
        real = os.replace

        def spy(src, dst, *args, **kwargs):
            source, target = Path(src), Path(dst)
            self.calls.append((source, target))
            self.attempted_at.append(time.monotonic())
            attempt = self.attempts(target.name)
            if self.hook is not None:
                self.hook(self, attempt, source, target)
            factory = self.failure.get(target.name)
            if factory is not None:
                self.denied.append(target.name)
                self.denied_at.append(time.monotonic())
                raise factory(self, attempt, source, target)
            count, code = self.transient.get(target.name, (0, None))
            if attempt <= count:
                self.denied.append(target.name)
                self.denied_at.append(time.monotonic())
                raise windows_denial(code, target)
            real(src, dst, *args, **kwargs)
            self.succeeded.append(target.name)
            return None

        self._monkeypatch.setattr(vr.os, "replace", spy)
        return self

    def __exit__(self, *exc):
        return False


class FakeClock:
    """A deterministic monotonic clock and sleeper for exact deadline rules.

    ``oversleep`` adds a fixed amount of unrequested wall time to every sleep,
    which is what a loaded scheduler really does and what a deadline contract
    must survive.
    """

    def __init__(self, start=1000.0, oversleep=0.0):
        self.now = float(start)
        self.sleeps: list[float] = []
        self.oversleep = oversleep

    def monotonic(self):
        return self.now

    def sleep(self, delay):
        self.sleeps.append(delay)
        self.now += delay + self.oversleep

    def install(self, monkeypatch):
        monkeypatch.setattr(vr.time, "monotonic", self.monotonic)
        monkeypatch.setattr(vr.time, "sleep", self.sleep)
        return self


# --------------------------------------------------------------------------
# 1. a transient denial is recovered, for every target and code
# --------------------------------------------------------------------------

@pytest.mark.parametrize("name", [vr.CSV_NAME, vr.MD_NAME, vr.JSON_NAME])
@pytest.mark.parametrize("code", TRANSIENT_CODES)
def test_transient_denial_recovers_and_the_consumer_reads_the_retry(
        out_dir, monkeypatch, name, code):
    report = a_report(generation=4)
    with ReplaceSpy(monkeypatch, transient={name: (2, code)}) as spy:
        paths = vr.write_report(report, out_dir)
    assert spy.denied == [name, name], "two real denials must be observed"
    # the published snapshot is this report, and the consumer reads it as a pass
    assert published_json(out_dir) == report
    assert csv_identity(paths["csv"])["run_id"] == RUN_A
    assert md_identity(paths["md"])["generation"] == "4"
    published = vr.read_published(out_dir)
    assert published["passing"] is True
    assert published["identity_match"] is True
    assert published["exit_code"] == 0
    # the retry reused exactly one owned temporary for the denied target
    assert spy.attempts(name) == 3
    assert len(set(spy.sources(name))) == 1
    assert spy.sources(name)[0].parent == out_dir
    assert spy.sources(name)[0].name.startswith(vr.TEMP_PREFIX)
    assert spy.succeeded == [vr.CSV_NAME, vr.MD_NAME, vr.JSON_NAME]
    assert_no_owned_temporary(out_dir)
    assert_no_lock(out_dir)


@pytest.mark.parametrize("name", [vr.CSV_NAME, vr.MD_NAME, vr.JSON_NAME])
def test_a_denied_target_is_re_attempted_in_place(out_dir, monkeypatch, name):
    """Whatever the denied target is, CSV is still replaced before JSON."""
    observed: list[dict] = []

    def hook(spy, attempt, source, target):
        if target.name == vr.JSON_NAME and attempt == 1:
            observed.append({
                "csv": csv_identity(out_dir / vr.CSV_NAME),
                "markdown": md_identity(out_dir / vr.MD_NAME),
                "json": (published_json(out_dir)
                         if (out_dir / vr.JSON_NAME).exists() else None)})

    with ReplaceSpy(monkeypatch, transient={name: (1, 5)}, hook=hook) as spy:
        vr.write_report(a_report(generation=1, state="partial"), out_dir)
    assert spy.succeeded == [vr.CSV_NAME, vr.MD_NAME, vr.JSON_NAME]
    # at the JSON replacement the derived pair already carries this generation
    assert observed[0]["csv"]["generation"] == "1"
    assert observed[0]["markdown"]["generation"] == "1"
    assert observed[0]["json"] is None
    published = vr.read_published(out_dir)
    assert published["identity_match"] is True
    assert published["report"]["state"] == "partial"
    assert published["passing"] is False


def test_csv_and_json_denials_still_publish_in_one_consistent_generation(
        out_dir, monkeypatch):
    with ReplaceSpy(monkeypatch, transient={vr.CSV_NAME: (1, 5),
                                           vr.JSON_NAME: (2, 32)}) as spy:
        paths = vr.write_report(a_report(generation=2, state="complete"), out_dir)
    assert spy.succeeded == [vr.CSV_NAME, vr.MD_NAME, vr.JSON_NAME]
    published = vr.read_published(out_dir)
    assert published["passing"] is True
    assert published["report"]["generation"] == 2
    assert published_json(out_dir) == json.loads(
        paths["json"].read_text(encoding="utf-8"))
    assert_no_owned_temporary(out_dir)


# --------------------------------------------------------------------------
# 2. permanent denial terminates inside a bounded budget
# --------------------------------------------------------------------------

def test_permanent_denial_keeps_previous_authority_and_never_passes(
        out_dir, monkeypatch):
    vr.write_report(a_report(generation=1, state="partial"), out_dir)
    previous = snapshot_bytes(out_dir)
    with ReplaceSpy(monkeypatch, transient={vr.JSON_NAME: (FOREVER, 5)}):
        began = time.monotonic()
        with pytest.raises(vr.PublishError):
            vr.write_report(a_report(generation=2, state="complete"), out_dir)
        elapsed = time.monotonic() - began
    assert elapsed >= 0.30, "the finite backoff is waited out"
    assert elapsed < 5.0, "and the retry budget is bounded"
    assert (out_dir / vr.JSON_NAME).read_bytes() == previous[vr.JSON_NAME]
    assert (out_dir / vr.CSV_NAME).read_bytes() != previous[vr.CSV_NAME]
    published = vr.read_published(out_dir)
    assert published["report"]["generation"] == 1
    assert published["identity_match"] is False
    assert published["passing"] is False
    assert_no_owned_temporary(out_dir)
    assert_no_lock(out_dir)


def test_permanent_denial_of_the_first_target_publishes_nothing(out_dir,
                                                                monkeypatch):
    with ReplaceSpy(monkeypatch, transient={vr.CSV_NAME: (FOREVER, 5)}) as spy:
        with pytest.raises(vr.PublishError):
            vr.write_report(a_report(), out_dir)
    assert spy.succeeded == []
    assert sorted(p.name for p in out_dir.iterdir()) == []
    assert_no_owned_temporary(out_dir)
    assert_no_lock(out_dir)


def test_retry_attempts_are_finite_and_independent_of_the_waiting_budget(
        out_dir, monkeypatch):
    with ReplaceSpy(monkeypatch, transient={vr.CSV_NAME: (FOREVER, 5)}) as spy:
        began = time.monotonic()
        with pytest.raises(vr.PublishError):
            vr.write_report(a_report(), out_dir)
        elapsed = time.monotonic() - began
    # the cap is six attempts; a slow filesystem may cut it earlier through the
    # budget, but never later
    assert 1 < len(spy.denied) <= vr.REPLACE_RETRY_ATTEMPTS
    assert vr.REPLACE_RETRY_ATTEMPTS == len(vr.REPLACE_RETRY_BACKOFF_S) + 1
    assert sum(vr.REPLACE_RETRY_BACKOFF_S) <= vr.PUBLISH_RETRY_BUDGET_S
    assert set(vr.TRANSIENT_REPLACE_WINERRORS) == set(TRANSIENT_CODES)
    assert elapsed < 5.0
    assert_no_owned_temporary(out_dir)


# --------------------------------------------------------------------------
# 3. non-transient failures are never retried
# --------------------------------------------------------------------------

@pytest.mark.parametrize("label", sorted(NON_TRANSIENT))
def test_non_transient_replace_failure_is_not_retried(out_dir, monkeypatch,
                                                      label):
    vr.write_report(a_report(generation=1, state="partial"), out_dir)
    previous = snapshot_bytes(out_dir)
    clock = FakeClock().install(monkeypatch)
    with ReplaceSpy(monkeypatch,
                    failure={vr.CSV_NAME: NON_TRANSIENT[label]}) as spy:
        with pytest.raises(vr.PublishError):
            vr.write_report(a_report(generation=2, state="complete"), out_dir)
    assert spy.denied == [vr.CSV_NAME], "exactly one attempt"
    assert clock.sleeps == [], "no backoff may be waited"
    for name, payload in previous.items():
        assert (out_dir / name).read_bytes() == payload
    assert_no_owned_temporary(out_dir)
    assert_no_lock(out_dir)


def test_a_failure_before_the_replacement_is_never_retried(out_dir, monkeypatch):
    vr.write_report(a_report(generation=1, state="partial"), out_dir)
    previous = snapshot_bytes(out_dir)

    def denied_fsync(descriptor):
        raise windows_denial(5, "<fsync>")

    with ReplaceSpy(monkeypatch) as spy:
        monkeypatch.setattr(vr.os, "fsync", denied_fsync)
        with pytest.raises(vr.PublishError):
            vr.write_report(a_report(generation=2, state="complete"), out_dir)
    assert spy.calls == [], "no replacement may be attempted at all"
    for name, payload in previous.items():
        assert (out_dir / name).read_bytes() == payload
    assert_no_owned_temporary(out_dir)


# --------------------------------------------------------------------------
# 4. target, lock and source temporary are re-checked before every attempt
# --------------------------------------------------------------------------

def test_changed_target_is_not_overwritten_after_a_denial(out_dir, monkeypatch,
                                                          tmp_path):
    vr.write_report(a_report(generation=1, state="partial"), out_dir)
    previous = snapshot_bytes(out_dir)
    planted_dir = tmp_path / "planted"
    vr.write_report(a_report(generation=7, run_id=RUN_B, state="complete"),
                    planted_dir)
    planted = (planted_dir / vr.CSV_NAME).read_bytes()
    assert planted != previous[vr.CSV_NAME]

    def cooperative_writer(spy, attempt, source, target):
        if target.name == vr.CSV_NAME and attempt == 1:
            # another owner published a valid, owned CSV after our preflight
            target.write_bytes(planted)

    with ReplaceSpy(monkeypatch, transient={vr.CSV_NAME: (1, 5)},
                    hook=cooperative_writer) as spy:
        with pytest.raises(vr.PublishError):
            vr.write_report(a_report(generation=2, state="complete"), out_dir)
    assert spy.denied == [vr.CSV_NAME]
    assert spy.succeeded == [], "no replacement may follow the refusal"
    assert (out_dir / vr.CSV_NAME).read_bytes() == planted
    assert (out_dir / vr.MD_NAME).read_bytes() == previous[vr.MD_NAME]
    assert (out_dir / vr.JSON_NAME).read_bytes() == previous[vr.JSON_NAME]
    assert_no_owned_temporary(out_dir)
    assert_no_lock(out_dir)


def test_foreign_target_appearing_after_a_denial_is_not_overwritten(
        out_dir, monkeypatch):
    vr.write_report(a_report(generation=1, state="partial"), out_dir)
    previous = snapshot_bytes(out_dir)

    def foreign_writer(spy, attempt, source, target):
        if target.name == vr.CSV_NAME and attempt == 1:
            target.write_bytes(b"project_id,value\nA,1\n")

    with ReplaceSpy(monkeypatch, transient={vr.CSV_NAME: (1, 5)},
                    hook=foreign_writer) as spy:
        with pytest.raises(vr.PublishError):
            vr.write_report(a_report(generation=2, state="complete"), out_dir)
    assert spy.succeeded == []
    assert (out_dir / vr.CSV_NAME).read_bytes() == b"project_id,value\nA,1\n"
    assert (out_dir / vr.JSON_NAME).read_bytes() == previous[vr.JSON_NAME]
    assert_no_owned_temporary(out_dir)


def test_stolen_lock_after_a_denial_stops_publication(out_dir, monkeypatch):
    foreign = json.dumps({"schema": vr.LOCK_SCHEMA, "pid": 424242,
                          "token": "not-our-token"}).encode("utf-8")

    def thief(spy, attempt, source, target):
        if target.name == vr.CSV_NAME and attempt == 1:
            (out_dir / vr.LOCK_NAME).write_bytes(foreign)

    with ReplaceSpy(monkeypatch, transient={vr.CSV_NAME: (1, 5)},
                    hook=thief) as spy:
        with pytest.raises(vr.PublishError) as error:
            vr.write_report(a_report(), out_dir)
    assert spy.succeeded == [], "no replacement may follow the refusal"
    assert "lock ownership was lost" in str(error.value)
    assert (out_dir / vr.LOCK_NAME).read_bytes() == foreign, \
        "a foreign lock is never deleted or adopted"
    assert not (out_dir / vr.CSV_NAME).exists()
    assert_no_owned_temporary(out_dir)


def test_vanished_source_temporary_after_a_denial_stops_publication(
        out_dir, monkeypatch):
    vr.write_report(a_report(generation=1, state="partial"), out_dir)
    previous = snapshot_bytes(out_dir)

    def remover(spy, attempt, source, target):
        if target.name == vr.CSV_NAME and attempt == 1:
            source.unlink()

    with ReplaceSpy(monkeypatch, transient={vr.CSV_NAME: (1, 5)},
                    hook=remover) as spy:
        with pytest.raises(vr.PublishError):
            vr.write_report(a_report(generation=2, state="complete"), out_dir)
    assert spy.denied == [vr.CSV_NAME]
    assert spy.succeeded == []
    for name, payload in previous.items():
        assert (out_dir / name).read_bytes() == payload
    assert_no_owned_temporary(out_dir)
    assert_no_lock(out_dir)


def test_a_foreign_file_at_the_owned_temporary_path_is_not_replaced(
        out_dir, monkeypatch):
    vr.write_report(a_report(generation=1, state="partial"), out_dir)
    previous = snapshot_bytes(out_dir)
    squatter = b"another process' bytes\n"

    def squatter_hook(spy, attempt, source, target):
        if target.name == vr.CSV_NAME and attempt == 1:
            source.unlink()
            source.write_bytes(squatter)

    with ReplaceSpy(monkeypatch, transient={vr.CSV_NAME: (1, 5)},
                    hook=squatter_hook) as spy:
        with pytest.raises(vr.PublishError):
            vr.write_report(a_report(generation=2, state="complete"), out_dir)
    assert spy.succeeded == []
    assert (out_dir / vr.CSV_NAME).read_bytes() == previous[vr.CSV_NAME]
    assert (out_dir / vr.JSON_NAME).read_bytes() == previous[vr.JSON_NAME]
    # the detected substitution is retained, not cleaned away
    assert spy.sources(vr.CSV_NAME)[0].read_bytes() == squatter


def test_cleanup_keeps_a_foreign_file_substituted_at_the_owned_temporary_path(
        out_dir, monkeypatch):
    """A different inode at the owned temporary path is never deleted.

    The substitution happens while the replacement is in flight and the failure
    is permanent, so no later revalidation reports it: cleanup itself must prove
    ownership before it removes anything.
    """
    foreign = b"foreign bytes must survive"

    def substitute(spy, attempt, source, target):
        replacement = out_dir / "external-owned-file"
        replacement.write_bytes(foreign)
        source.unlink()
        replacement.rename(source)
        raise OSError(28, "No space left on device", str(target))

    with ReplaceSpy(monkeypatch, failure={vr.CSV_NAME: substitute}) as spy:
        with pytest.raises(vr.PublishError) as error:
            vr.write_report(a_report(), out_dir)
    assert spy.succeeded == []
    substituted = spy.sources(vr.CSV_NAME)[0]
    assert substituted.read_bytes() == foreign
    assert not (out_dir / vr.JSON_NAME).exists()
    notes = getattr(error.value.__cause__, "__notes__", [])
    assert any("retained" in note for note in notes), notes


def test_cleanup_keeps_foreign_content_written_into_the_owned_temporary(
        out_dir, monkeypatch):
    """The same inode, different bytes: also somebody else's file now."""
    vr.write_report(a_report(generation=1, state="partial"), out_dir)
    previous = snapshot_bytes(out_dir)
    rewritten = b"foreign bytes at our temporary path\n"

    def rewrite(spy, attempt, source, target):
        if target.name == vr.CSV_NAME and attempt == 1:
            source.write_bytes(rewritten)

    with ReplaceSpy(monkeypatch, transient={vr.CSV_NAME: (1, 5)},
                    hook=rewrite) as spy:
        with pytest.raises(vr.PublishError):
            vr.write_report(a_report(generation=2, state="complete"), out_dir)
    assert spy.succeeded == []
    assert spy.sources(vr.CSV_NAME)[0].read_bytes() == rewritten
    assert (out_dir / vr.CSV_NAME).read_bytes() == previous[vr.CSV_NAME]


def test_an_owned_temporary_is_still_cleaned_up_after_a_replacement_failure(
        out_dir, monkeypatch):
    """Retention is narrow: a genuinely owned temporary is still removed."""
    with ReplaceSpy(monkeypatch,
                    transient={vr.CSV_NAME: (FOREVER, 5)}) as spy:
        with pytest.raises(vr.PublishError):
            vr.write_report(a_report(), out_dir)
    assert spy.succeeded == []
    assert not spy.sources(vr.CSV_NAME)[0].exists()
    assert_no_owned_temporary(out_dir)
    assert_no_lock(out_dir)


@pytest.mark.parametrize("same_inode", [False, True])
def test_a_file_substituted_while_the_source_is_signed_is_never_published(
        out_dir, monkeypatch, same_inode):
    """The signature binds content, not identity: the source must match both
    the created file and the bytes this run rendered, even when the
    substitution happens while the signature is being read."""
    foreign = b"foreign initial source must never be published"
    real_signature = vr._file_signature
    substituted: list[Path] = []

    def signature(path):
        path = Path(path)
        if path.name.startswith(vr.TEMP_PREFIX) and not substituted:
            if same_inode:
                path.write_bytes(foreign)
            else:
                replacement = out_dir / "foreign-before-signature"
                replacement.write_bytes(foreign)
                path.unlink()
                replacement.rename(path)
            substituted.append(path)
        return real_signature(path)

    with ReplaceSpy(monkeypatch) as spy:
        monkeypatch.setattr(vr, "_file_signature", signature)
        with pytest.raises(vr.PublishError):
            vr.write_report(a_report(), out_dir)
    assert substituted, "the substitution must have been staged"
    assert substituted[0].read_bytes() == foreign
    assert spy.succeeded == [], "no replacement may publish the foreign bytes"
    assert not (out_dir / vr.CSV_NAME).exists()
    assert not (out_dir / vr.JSON_NAME).exists()


# --------------------------------------------------------------------------
# 5. the caller deadline bounds the waiting
# --------------------------------------------------------------------------

def test_retry_wait_never_reaches_past_the_caller_deadline(out_dir, monkeypatch):
    """Real clock, real waiting: the host is slow, the clip still holds."""
    vr.write_report(a_report(generation=1, state="partial"), out_dir)
    previous = snapshot_bytes(out_dir)
    deadline = time.monotonic() + 0.30
    with ReplaceSpy(monkeypatch,
                    transient={vr.CSV_NAME: (FOREVER, 5)}) as spy:
        with pytest.raises(vr.PublishError):
            vr.write_report(a_report(generation=2, state="complete"), out_dir,
                            retry_deadline=deadline)
    waited = spy.denied_at[-1] - spy.denied_at[0]
    assert waited <= sum(vr.REPLACE_RETRY_BACKOFF_S)
    assert len(spy.denied) <= len(vr.REPLACE_RETRY_BACKOFF_S) + 1
    for name, payload in previous.items():
        assert (out_dir / name).read_bytes() == payload
    assert_no_owned_temporary(out_dir)
    assert_no_lock(out_dir)


def test_an_expired_deadline_disables_every_retry(out_dir, monkeypatch):
    clock = FakeClock().install(monkeypatch)
    with ReplaceSpy(monkeypatch,
                    transient={vr.CSV_NAME: (FOREVER, 5)}) as spy:
        with pytest.raises(vr.PublishError):
            vr.write_report(a_report(), out_dir, retry_deadline=999.0)
    assert spy.attempts(vr.CSV_NAME) == 1
    assert clock.sleeps == []
    assert_no_owned_temporary(out_dir)


def test_injected_clock_bounds_every_sleep_to_the_caller_deadline(out_dir,
                                                                   monkeypatch):
    """Exact deadline arithmetic, with no wall-clock tolerance."""
    clock = FakeClock().install(monkeypatch)
    with ReplaceSpy(monkeypatch,
                    transient={vr.CSV_NAME: (FOREVER, 5)}) as spy:
        with pytest.raises(vr.PublishError):
            vr.write_report(a_report(), out_dir, retry_deadline=1000.30)
    assert clock.sleeps == pytest.approx([0.01, 0.02, 0.04, 0.08, 0.15])
    assert sum(clock.sleeps) == pytest.approx(0.30)
    assert len(spy.denied) == 5
    assert spy.succeeded == []
    assert_no_owned_temporary(out_dir)


def test_a_scheduler_oversleep_never_starts_another_replacement(out_dir,
                                                                monkeypatch):
    """A sleep may return long after it was asked for; the retry must still
    stop, and the original denial must be what surfaces."""
    clock = FakeClock(oversleep=1.0).install(monkeypatch)
    with ReplaceSpy(monkeypatch,
                    transient={vr.CSV_NAME: (FOREVER, 5)}) as spy:
        with pytest.raises(vr.PublishError) as error:
            vr.write_report(a_report(), out_dir, retry_deadline=1000.05)
    assert clock.sleeps == [0.01]
    assert clock.now > 1000.05, "the sleeper really overshot the deadline"
    assert len(spy.denied) == 1, "no replacement may start after the deadline"
    assert spy.succeeded == []
    assert isinstance(error.value.__cause__, PermissionError)
    assert error.value.__cause__.winerror == 5
    assert not (out_dir / vr.JSON_NAME).exists()
    assert_no_owned_temporary(out_dir)


def test_an_oversleeping_scheduler_never_buys_more_than_the_attempt_limit(
        out_dir, monkeypatch):
    """Without a caller deadline the finite attempt limit still binds, and a
    late wake-up cannot buy an extra one."""
    clock = FakeClock(oversleep=0.01).install(monkeypatch)
    with ReplaceSpy(monkeypatch,
                    transient={vr.CSV_NAME: (FOREVER, 5)}) as spy:
        with pytest.raises(vr.PublishError):
            vr.write_report(a_report(), out_dir)
    assert len(spy.denied) == len(vr.REPLACE_RETRY_BACKOFF_S) + 1
    assert clock.sleeps == pytest.approx(list(vr.REPLACE_RETRY_BACKOFF_S))


def test_a_late_wake_up_cannot_buy_attempts_past_the_module_budget(
        out_dir, monkeypatch):
    """A badly oversleeping scheduler is cut by the budget, not by a cap."""
    clock = FakeClock(oversleep=10.0).install(monkeypatch)
    with ReplaceSpy(monkeypatch,
                    transient={vr.CSV_NAME: (FOREVER, 5)}) as spy:
        with pytest.raises(vr.PublishError):
            vr.write_report(a_report(), out_dir)
    assert len(spy.denied) == 1
    assert clock.sleeps == [0.01]


def test_a_generous_deadline_does_not_enlarge_the_publication_budget(
        out_dir, monkeypatch):
    with ReplaceSpy(monkeypatch,
                    transient={vr.CSV_NAME: (FOREVER, 5)}) as spy:
        began = time.monotonic()
        with pytest.raises(vr.PublishError):
            vr.write_report(a_report(), out_dir,
                            retry_deadline=time.monotonic() + 600.0)
        elapsed = time.monotonic() - began
    assert elapsed >= 0.30 and elapsed < 5.0
    assert spy.succeeded == []
    assert 1 < len(spy.denied) <= vr.REPLACE_RETRY_ATTEMPTS


def test_recovery_still_works_when_a_deadline_is_supplied(out_dir, monkeypatch):
    report = a_report(generation=5)
    with ReplaceSpy(monkeypatch, transient={vr.JSON_NAME: (3, 33)}):
        vr.write_report(report, out_dir, retry_deadline=time.monotonic() + 30.0)
    published = vr.read_published(out_dir)
    assert published["passing"] is True
    assert published["report"]["generation"] == 5
    assert published_json(out_dir) == report


@pytest.mark.parametrize("bad", [True, float("inf"), float("-inf"),
                                 float("nan"), "later", object()])
def test_invalid_deadline_is_rejected_before_any_write(out_dir, bad):
    with pytest.raises(ValueError):
        vr.write_report(a_report(), out_dir, retry_deadline=bad)
    assert list(out_dir.iterdir()) == []
    assert_no_lock(out_dir)


@pytest.mark.parametrize("expired", [0, -1])
def test_a_past_numeric_deadline_is_a_valid_expired_deadline(out_dir,
                                                             monkeypatch,
                                                             expired):
    """A monotonic instant that has passed disables retries; it is not an
    error, and the snapshot is still published with one attempt."""
    clock = FakeClock().install(monkeypatch)
    with ReplaceSpy(monkeypatch,
                    transient={vr.CSV_NAME: (FOREVER, 5)}) as spy:
        with pytest.raises(vr.PublishError):
            vr.write_report(a_report(), out_dir, retry_deadline=expired)
    assert spy.attempts(vr.CSV_NAME) == 1
    assert clock.sleeps == []
    assert_no_owned_temporary(out_dir)


@pytest.mark.parametrize("expired", [0, -1])
def test_an_expired_deadline_still_publishes_an_unchanged_snapshot(out_dir,
                                                                   expired):
    """The deadline bounds waiting only; it never withdraws a publishable
    report."""
    report = a_report(generation=3)
    vr.write_report(report, out_dir, retry_deadline=expired)
    assert published_json(out_dir) == report
    assert vr.read_published(out_dir)["passing"] is True


def test_the_deadline_is_keyword_only_and_backwards_compatible(out_dir):
    with pytest.raises(TypeError):
        vr.write_report(a_report(), out_dir, time.monotonic() + 5.0)
    assert list(out_dir.iterdir()) == []
    # the historical two-argument call still publishes
    paths = vr.write_report(a_report(), out_dir)
    assert set(paths) == {"json", "csv", "md"}
    assert vr.read_published(out_dir)["passing"] is True


# --------------------------------------------------------------------------
# 6. the verify CLI keeps its own budget and never reports a false pass
# --------------------------------------------------------------------------

def test_cli_retry_budget_is_bounded_with_a_large_total_timeout(tmp_path,
                                                                monkeypatch):
    out = tmp_path / "evidence"
    out.mkdir()
    with ReplaceSpy(monkeypatch,
                    transient={vr.CSV_NAME: (FOREVER, 5)}) as spy:
        began = time.monotonic()
        assert app.main(["verify", "--output-dir", str(out),
                         "--total-timeout-s", "300"]) == 1
        elapsed = time.monotonic() - began
    assert len(spy.denied) == len(vr.REPLACE_RETRY_BACKOFF_S) + 1
    assert spy.succeeded == []
    assert elapsed < 10.0
    assert not (out / vr.JSON_NAME).exists()
    assert_no_owned_temporary(out)
    assert_no_lock(out)


def test_cli_exhausted_total_deadline_does_not_wait_for_retries(tmp_path,
                                                               monkeypatch):
    out = tmp_path / "evidence"
    out.mkdir()
    with ReplaceSpy(monkeypatch,
                    transient={vr.CSV_NAME: (FOREVER, 5)}) as spy:
        began = time.monotonic()
        assert app.main(["verify", "--output-dir", str(out),
                         "--total-timeout-s", "0.001"]) == 1
        elapsed = time.monotonic() - began
    # the caller's budget is already spent when the first snapshot is published,
    # so exactly one attempt is made and no backoff is waited
    assert spy.attempts(vr.CSV_NAME) == 1
    assert elapsed < NO_FULL_BACKOFF_S + 5.0
    assert not (out / vr.JSON_NAME).exists()
    assert_no_owned_temporary(out)
    assert_no_lock(out)


def test_cli_publishes_one_consistent_generation_after_a_transient_denial(
        tmp_path, monkeypatch):
    out = tmp_path / "evidence"
    out.mkdir()
    monkeypatch.setattr(v, "build_cases", lambda suite: build_cases("quick")[1:2])
    with ReplaceSpy(monkeypatch, transient={vr.CSV_NAME: (1, 5)}):
        code = app.main(["verify", "--output-dir", str(out),
                         "--total-timeout-s", "300"])
    assert code in (0, 1)
    published = vr.read_published(out)
    assert published["present"] is True
    assert published["identity_match"] is True, \
        "the derived pair and the authoritative JSON must share one generation"
    assert published["report"]["state"] == "complete"
    assert published["passing"] is (published["exit_code"] == 0)
    assert_no_owned_temporary(out)
    assert_no_lock(out)


def test_cli_final_timeout_evidence_is_published_without_retries(tmp_path,
                                                                monkeypatch):
    """The post-deadline failure snapshot keeps its existing single-attempt
    behaviour: three consistent files, an honest non-pass."""
    out = tmp_path / "evidence"
    with ReplaceSpy(monkeypatch):
        assert app.main(["verify", "--output-dir", str(out),
                         "--total-timeout-s", ".01"]) == 1
    published = vr.read_published(out)
    assert published["identity_match"] is True
    assert published["passing"] is False
    assert published["report"]["state"] == "complete"
    assert any(row["state"] in ("timeout", "not_started")
               for row in published["report"]["cases"])
    assert_no_owned_temporary(out)
    assert_no_lock(out)


def test_no_publication_state_reaches_the_report_or_the_cli_summary(
        tmp_path, monkeypatch, capsys):
    """The deadline stays a local value: the published report and the CLI
    summary keep exactly the fields they had before."""
    out = tmp_path / "evidence"
    out.mkdir()
    monkeypatch.setattr(v, "build_cases", lambda suite: build_cases("quick")[1:2])
    assert app.main(["verify", "--output-dir", str(out),
                     "--total-timeout-s", "300"]) in (0, 1)
    published = vr.read_published(out)
    assert set(published["report"]) == {
        "schema", "run_id", "generation", "state", "suite",
        "requested_case_ids", "cases", "source_identity",
        "input_manifest_sha256", "runtime", "limits", "elapsed_s"}
    text = (out / vr.JSON_NAME).read_text(encoding="utf-8")
    assert "retry_deadline" not in text and "PUBLISH_RETRY" not in text
    assert "retry" not in (out / vr.CSV_NAME).read_text(encoding="utf-8").lower()
    summary = json.loads(capsys.readouterr().out)
    assert summary["schema"] == "plimsoll-cli-verification-summary-1"
    assert set(summary) == {"schema", "run_id", "state", "suite", "exit_code",
                            "cases", "source_consistent", "elapsed_s", "outputs"}
    assert summary["exit_code"] == published["exit_code"]
    assert_no_owned_temporary(out)
    assert_no_lock(out)