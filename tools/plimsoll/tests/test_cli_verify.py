"""CLI preflight, explicit work, failure evidence, and existing entrypoints."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from plimsoll import app, verification as v, verification_report as vr


def test_verify_help_is_read_only(monkeypatch, capsys):
    monkeypatch.setattr(v, "run_verification", lambda *a, **k: pytest.fail("help computed"))
    with pytest.raises(SystemExit) as result:
        app.main(["verify", "--help"])
    assert result.value.code == 0
    assert "--output-dir" in capsys.readouterr().out


@pytest.mark.parametrize("flags", [[], ["--suite", "unknown"], ["--case-timeout-s", "nan"],
                                 ["--total-timeout-s", "0"], ["--case-timeout-s", "-1"]])
def test_usage_does_no_calculation_or_write(tmp_path, monkeypatch, flags):
    monkeypatch.setattr(v, "run_verification", lambda *a, **k: pytest.fail("invalid usage computed"))
    out = tmp_path / "absent"
    args = ["verify"] + flags
    if flags:
        args += ["--output-dir", str(out)]
    assert app.main(args) == 2
    assert not out.exists()


def test_foreign_output_is_preflighted_before_computation(tmp_path, monkeypatch):
    data = b"USER DATA\n"
    path = tmp_path / vr.CSV_NAME
    path.write_bytes(data)
    monkeypatch.setattr(v, "run_verification", lambda *a, **k: pytest.fail("unsafe output computed"))
    assert app.main(["verify", "--output-dir", str(tmp_path)]) == 2
    assert path.read_bytes() == data
    assert not (tmp_path / vr.LOCK_NAME).exists()


def test_real_parent_deadline_returns_three_consistent_failure_formats(tmp_path):
    out = tmp_path / "evidence"
    assert app.main(["verify", "--output-dir", str(out), "--total-timeout-s", ".01"]) == 1
    read = vr.read_published(out)
    assert read["identity_match"] is True
    assert read["passing"] is False
    assert read["report"]["state"] == "complete"
    assert len(read["report"]["cases"]) == len(read["report"]["requested_case_ids"])
    assert any(c["state"] in ("timeout", "not_started") for c in read["report"]["cases"])


def test_initial_partial_is_published_before_runner_first_case(tmp_path, monkeypatch):
    original = v.run_verification
    def run(suite, **kwargs):
        checkpoint = kwargs["checkpoint"]
        def observe(report):
            checkpoint(report)
            if report["generation"] == 0:
                read = vr.read_published(tmp_path)
                assert read["report"]["state"] == "partial"
                assert read["passing"] is False
        kwargs["checkpoint"] = observe
        return original(suite, **kwargs)
    monkeypatch.setattr(v, "run_verification", run)
    assert app.main(["verify", "--output-dir", str(tmp_path), "--total-timeout-s", ".01"]) == 1


def test_source_identity_and_output_defaults_are_recorded(tmp_path, monkeypatch):
    from plimsoll.verification_cases import build_cases
    monkeypatch.setattr(v, "build_cases", lambda suite: build_cases("quick")[1:2])
    assert app.main(["verify", "--output-dir", str(tmp_path)]) == 0
    probe = vr.read_published(tmp_path)
    assert probe["passing"] is True
    report = probe["report"]
    assert report["limits"] == {"case_timeout_s": 180.0, "total_timeout_s": 1800.0}
    assert report["suite"] == "quick"
    assert report["source_identity"]["files"]


def test_output_failure_is_nonzero_and_preserves_authority(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise vr.PublishError("injected output medium failure")
    monkeypatch.setattr(vr, "write_report", fail)
    assert app.main(["verify", "--output-dir", str(tmp_path)]) == 1
    assert not (tmp_path / vr.JSON_NAME).exists()
    assert not (tmp_path / vr.LOCK_NAME).exists()
