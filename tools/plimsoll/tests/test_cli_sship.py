"""``import-sship`` command: conversion, preview and destination protection.

Every input is a synthetic SpringSharp 3.0 fixture built in memory from the
recovered 280-position registry.
"""
import json
import os

import pytest

from plimsoll import app, project_io, sship_import

from test_sship_import import FIELD_COUNT, build, imperial_fields


def write_source(tmp_path, fields=None, **kwargs):
    """Write a synthetic .sship fixture and return its path."""
    path = tmp_path / "synthetic-cruiser.sship"
    path.write_bytes(build(fields if fields is not None else imperial_fields(), **kwargs))
    return path


def error_payload(capsys):
    captured = capsys.readouterr()
    return captured, json.loads(captured.err)


def test_help_is_read_only_without_touching_the_filesystem(capsys, tmp_path):
    with pytest.raises(SystemExit) as result:
        app.main(["import-sship", "--help"])
    assert result.value.code == 0
    out = capsys.readouterr().out
    assert "--preview" in out and "--output" in out and "--name" in out
    assert list(tmp_path.iterdir()) == []


def test_preview_emits_the_full_preview_and_writes_nothing(tmp_path, capsys):
    source = write_source(tmp_path)
    before = source.read_bytes()
    assert app.main(["import-sship", str(source), "--preview"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "plimsoll-sship-preview-1"
    assert payload["method_version"] == "springsharp-3.0-migration-1"
    assert len(payload["fields"]) == FIELD_COUNT
    assert payload["source"]["filename"] == source.name
    assert payload["project"]["schema"] == "plimsoll-project-1"
    assert source.read_bytes() == before
    assert sorted(entry.name for entry in tmp_path.iterdir()) == [source.name]


def test_preview_to_a_file_matches_stdout(tmp_path, capsys):
    source = write_source(tmp_path)
    target = tmp_path / "preview.json"
    assert app.main(["import-sship", str(source), "--preview", "--output", str(target)]) == 0
    assert capsys.readouterr().out == ""
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["schema"] == "plimsoll-sship-preview-1"


def test_conversion_writes_a_valid_canonical_project(tmp_path, capsys):
    source = write_source(tmp_path)
    target = tmp_path / "converted.project.json"
    assert app.main(["import-sship", str(source), "--output", str(target)]) == 0
    assert capsys.readouterr().out == ""
    project = project_io.normalize_project(json.loads(target.read_text(encoding="utf-8")))
    assert project["schema"] == "plimsoll-project-1"
    assert project["migration"]["schema"] == "plimsoll-sship-migration-1"
    assert project["migration"]["raw_fields"] == imperial_fields()
    assert project["name"] == "SYNTHETIC IMPERIAL CRUISER"


def test_conversion_to_stdout_is_the_default(tmp_path, capsys):
    source = write_source(tmp_path)
    assert app.main(["import-sship", str(source)]) == 0
    project = json.loads(capsys.readouterr().out)
    assert project["schema"] == "plimsoll-project-1"
    assert sorted(entry.name for entry in tmp_path.iterdir()) == [source.name]


def test_supplied_name_is_used_verbatim(tmp_path, capsys):
    source = write_source(tmp_path, imperial_fields({0: ""}))
    assert app.main(["import-sship", str(source), "--name", "Renamed Cruiser"]) == 0
    project = json.loads(capsys.readouterr().out)
    assert project["name"] == "Renamed Cruiser"
    assert project["migration"]["source"]["filename"] == source.name


def test_blank_name_falls_back_to_the_filename_stem(tmp_path, capsys):
    source = write_source(tmp_path, imperial_fields({0: ""}))
    assert app.main(["import-sship", str(source), "--name", "   "]) == 0
    project = json.loads(capsys.readouterr().out)
    assert project["name"] == "synthetic-cruiser"


@pytest.mark.parametrize("relative", [True, False])
def test_existing_output_is_refused_and_untouched(tmp_path, capsys, relative, monkeypatch):
    source = write_source(tmp_path)
    target = tmp_path / "converted.project.json"
    target.write_text("USER PROJECT\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    argument = os.path.relpath(target, tmp_path) if relative else str(target)
    assert app.main(["import-sship", str(source), "--output", argument]) == 2
    _, payload = error_payload(capsys)
    assert payload["code"] == "cli.output_exists"
    assert target.read_text(encoding="utf-8") == "USER PROJECT\n"


def test_symlink_output_is_refused(tmp_path, capsys):
    source = write_source(tmp_path)
    victim = tmp_path / "victim.json"
    victim.write_text("USER PROJECT\n", encoding="utf-8")
    link = tmp_path / "link.json"
    try:
        link.symlink_to(victim)
    except (OSError, NotImplementedError):  # pragma: no cover - platform without links
        pytest.skip("symlinks are unavailable on this platform")
    assert app.main(["import-sship", str(source), "--output", str(link)]) == 2
    _, payload = error_payload(capsys)
    assert payload["code"] == "cli.output_exists"
    assert victim.read_text(encoding="utf-8") == "USER PROJECT\n"


def test_broken_symlink_output_is_refused(tmp_path, capsys):
    source = write_source(tmp_path)
    link = tmp_path / "dangling.json"
    try:
        link.symlink_to(tmp_path / "absent.json")
    except (OSError, NotImplementedError):  # pragma: no cover - platform without links
        pytest.skip("symlinks are unavailable on this platform")
    assert app.main(["import-sship", str(source), "--output", str(link)]) == 2
    _, payload = error_payload(capsys)
    assert payload["code"] == "cli.output_exists"
    assert not (tmp_path / "absent.json").exists()


@pytest.mark.parametrize("preview", [False, True])
def test_linked_destination_is_refused_even_without_link_support(tmp_path, capsys,
                                                                 monkeypatch, preview):
    # Platforms without link privileges still exercise the same refusal: the
    # destination is reported as an existing link, including a dangling one.
    source = write_source(tmp_path)
    target = tmp_path / "linked.json"
    target.write_text("USER PROJECT\n", encoding="utf-8")
    real_lexists = app.os.path.lexists
    monkeypatch.setattr(app.os.path, "lexists", lambda path: True)
    args = ["import-sship", str(source), "--output", str(target)]
    if preview:
        args.append("--preview")
    assert app.main(args) == 2
    _, payload = error_payload(capsys)
    assert payload["code"] == "cli.output_exists"
    assert target.read_text(encoding="utf-8") == "USER PROJECT\n"
    assert real_lexists(target) is True


def test_exclusive_create_refuses_a_linked_destination_at_write_time(tmp_path,
                                                                     monkeypatch):
    # Even if the pre-flight check passes, the exclusive create is the last guard.
    source = write_source(tmp_path)
    target = tmp_path / "raced.json"
    monkeypatch.setattr(app.os.path, "lexists", lambda path: False)
    assert app.main(["import-sship", str(source), "--output", str(target)]) == 0
    assert target.exists()


@pytest.mark.parametrize("preview", [False, True])
def test_output_aliasing_the_input_is_refused(tmp_path, capsys, preview):
    source = write_source(tmp_path)
    before = source.read_bytes()
    args = ["import-sship", str(source), "--output", str(source)]
    if preview:
        args.append("--preview")
    assert app.main(args) == 2
    _, payload = error_payload(capsys)
    assert payload["code"] == "cli.output_alias"
    assert source.read_bytes() == before


@pytest.mark.parametrize("preview", [False, True])
def test_hardlink_output_aliasing_the_input_is_refused(tmp_path, capsys, preview):
    source = write_source(tmp_path)
    alias = tmp_path / "alias.sship"
    try:
        os.link(source, alias)
    except (OSError, NotImplementedError):  # pragma: no cover - filesystem without links
        pytest.skip("hard links are unavailable on this filesystem")
    before = source.read_bytes()
    args = ["import-sship", str(source), "--output", str(alias)]
    if preview:
        args.append("--preview")
    assert app.main(args) == 2
    _, payload = error_payload(capsys)
    assert payload["code"] in {"cli.output_alias", "cli.output_exists"}
    assert source.read_bytes() == before
    assert alias.read_bytes() == before


def test_invalid_source_creates_no_output(tmp_path, capsys):
    source = tmp_path / "broken.sship"
    source.write_bytes(b"SpringSharp Version 2.0\r\n" + b"1\r\n" * FIELD_COUNT)
    target = tmp_path / "converted.project.json"
    assert app.main(["import-sship", str(source), "--output", str(target)]) == 2
    _, payload = error_payload(capsys)
    assert payload["code"] == "cli.sship_import"
    assert payload["diagnostics"][0]["code"] == "sship.version_unsupported"
    assert not target.exists()


def test_unreadable_source_is_a_structured_error(tmp_path, capsys):
    missing = tmp_path / "absent.sship"
    target = tmp_path / "converted.project.json"
    assert app.main(["import-sship", str(missing), "--output", str(target)]) == 2
    _, payload = error_payload(capsys)
    assert payload["code"] == "cli.input_read"
    assert not target.exists()


def test_oversized_source_is_refused_without_output(tmp_path, capsys):
    source = tmp_path / "huge.sship"
    source.write_bytes(build(imperial_fields()) + b"\r\n" + b"n" * (sship_import.MAX_BYTES + 1))
    target = tmp_path / "converted.project.json"
    assert app.main(["import-sship", str(source), "--output", str(target)]) == 2
    _, payload = error_payload(capsys)
    assert payload["diagnostics"][0]["code"] == "sship.source.too_large"
    assert not target.exists()


def test_core_contract_is_the_single_source_for_the_cli(tmp_path, capsys):
    source = write_source(tmp_path)
    assert app.main(["import-sship", str(source), "--preview"]) == 0
    preview = json.loads(capsys.readouterr().out)
    direct = sship_import.preview(source.read_bytes(), filename=source.name)
    assert preview == json.loads(json.dumps(direct))


def test_output_created_during_parsing_is_never_replaced(tmp_path, capsys, monkeypatch):
    source = write_source(tmp_path)
    target = tmp_path / "converted.project.json"
    foreign = "FOREIGN PROJECT\n"
    original = sship_import.convert

    def racing_convert(*args, **kwargs):
        target.write_text(foreign, encoding="utf-8")
        return original(*args, **kwargs)

    monkeypatch.setattr(sship_import, "convert", racing_convert)
    assert app.main(["import-sship", str(source), "--output", str(target)]) == 2
    _, payload = error_payload(capsys)
    assert payload["code"] == "cli.output_exists"
    assert target.read_text(encoding="utf-8") == foreign


def test_preview_output_created_during_parsing_is_never_replaced(tmp_path, capsys,
                                                                 monkeypatch):
    source = write_source(tmp_path)
    target = tmp_path / "preview.json"
    foreign = "FOREIGN PREVIEW\n"
    original = sship_import.preview

    def racing_preview(*args, **kwargs):
        target.write_text(foreign, encoding="utf-8")
        return original(*args, **kwargs)

    monkeypatch.setattr(sship_import, "preview", racing_preview)
    assert app.main(["import-sship", str(source), "--preview",
                     "--output", str(target)]) == 2
    _, payload = error_payload(capsys)
    assert payload["code"] == "cli.output_exists"
    assert target.read_text(encoding="utf-8") == foreign


def test_written_project_is_canonical_and_reopenable(tmp_path, capsys):
    source = write_source(tmp_path)
    target = tmp_path / "converted.project.json"
    assert app.main(["import-sship", str(source), "--output", str(target)]) == 0
    text = target.read_text(encoding="utf-8")
    assert text.endswith("\n")
    project = project_io.normalize_project(json.loads(text))
    assert project["id"].startswith("sship-")
    assert project["migration"]["source"]["sha256"] == project["sources"][
        "springsharp3"]["sha256"]


def test_existing_commands_are_unchanged():
    parser = app._parser()
    actions = [action for action in parser._actions
               if getattr(action, "choices", None) and "import-sship" in action.choices]
    assert len(actions) == 1
    assert set(actions[0].choices) >= {
        "analyze", "batch", "sweep", "import-geometry", "readme", "verify", "import-sship",
    }
