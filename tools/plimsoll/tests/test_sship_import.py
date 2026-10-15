"""Bounded SpringSharp 3.0 parsing and canonical draft projection.

Every fixture here is synthetic: it is built from the recovered 280-position
registry, not from any real ship file. Nothing in this module reads or writes
the filesystem on behalf of the importer.
"""
import base64
import copy
import json
import math

import pytest

from plimsoll import concept_design, loading, project_io, sship_import


def test_independent_imperial_plate_thickness_anchor():
    project = sship_import.preview(sship())["project"]
    fixed = project["systems"]["armour"]["fixed"]
    assert fixed["belt_main"]["facts"]["thickness_m"]["value"] == pytest.approx(0.1524)
    assert fixed["rotating_armour"]["bank1"]["facts"]["thickness_m"]["value"] == pytest.approx(0.3048)


def test_zero_calibre_in_unused_banks_is_preserved_without_invalid_facts():
    records = imperial_fields()
    for bank in range(1, 5):
        records[4 + bank] = "0"
        records[32 + 6 * bank] = "0"
    project = sship_import.preview(build(records))["project"]
    for bank in range(2, 6):
        assert project["systems"]["weapons"][f"bank{bank}"]["facts"].get("calibre_m", {}).get("value") is None
        assert project["migration"]["raw_fields"][32 + 6 * (bank - 1)] == "0"


def test_fractional_mount_count_is_archived_without_truncating_a_model():
    project = sship_import.preview(build(imperial_fields({62: "2.5", 31: "5", 211: "0", 216: "0"})))["project"]
    assert not project["concept_design"]["batteries"]
    assert project["systems"]["weapons"]["bank1"]["facts"].get("mount_count", {}).get("value") is None
    assert project["migration"]["raw_fields"][62] == "2.5"


def test_import_has_a_generated_working_condition_for_estimates_only():
    from plimsoll import analysis
    project = sship_import.preview(sship())["project"]
    assert len(project["loading_conditions"]) == 1
    condition = project["loading_conditions"][0]
    assert "generated" in condition["source"].lower()
    assert condition["overrides"] == {}
    state = loading.resolve_loading(project, condition["id"])
    assert not state["complete_mass"] and not state["complete_cg"]
    result = analysis.compute_project(project, condition["id"], {"stages": ["systems", "geometry", "hydrostatics"]})
    assert result["stages"]["hydrostatics"]["status"] != "completed"
    proposals = result["stages"]["systems"]["data"]["update_proposals"]
    # Shaft power is absent and the speed-to-power screen needs user-supplied
    # balance inputs. Guns/mounts/ammunition/fuel remain independently usable.
    assert {row["item_id"] for row in proposals} == {
        "weapons.bank1.g1.guns", "weapons.bank1.g1.mounts",
        "weapons.bank1.g1.ammunition", "propulsion.fuel"}
    assert any(d["code"] == "concept_design.machinery_unavailable"
               for d in result["stages"]["systems"]["data"]["diagnostics"])
    assert all(row["current_mass_t"] is None and row["requires_review"] for row in proposals)
    applied = analysis.apply_mass_proposals(project, condition["id"], proposals,
                                           current_request=result["request"])["project"]
    assert applied["migration"] == project["migration"]
    assert not loading.resolve_loading(applied, condition["id"])["complete_mass"]


def test_mapped_fields_never_point_to_missing_archival_objects():
    result = sship_import.preview(sship())
    for field in result["fields"]:
        if field["disposition"] == "mapped":
            assert not any(path.startswith(("$.migration.mapping.banks.", "$.migration.mapping.armour."))
                           for path in field["destinations"]), field


@pytest.mark.parametrize("index,key", [(13, "lwl_m"), (14, "beam_m"), (15, "draught_normal_m")])
def test_zero_source_dimension_stays_zero_in_the_nonnegative_hull_contract(index, key):
    project = sship_import.preview(build(imperial_fields({index: "0"})))["project"]
    assert project["hull"][key] == 0
    assert project["migration"]["raw_fields"][index] == "0"


def test_fractional_round_count_is_not_truncated_into_an_estimate():
    result = sship_import.preview(build(imperial_fields({61: "2.5"})))
    assert not result["project"]["concept_design"]["batteries"]
    assert result["project"]["systems"]["weapons"]["bank1"]["facts"].get("rounds_per_gun", {}).get("value") is None
    assert result["project"]["migration"]["raw_fields"][61] == "2.5"


def test_fractional_barrel_length_keeps_its_declared_precision():
    result = sship_import.preview(build(imperial_fields({140: "45.5"})))
    assert result["project"]["concept_design"]["batteries"][0]["barrel_calibres"] == 45.5


def test_unused_mount_group_may_have_an_unknown_per_mount_selector():
    result = sship_import.preview(build(imperial_fields({241: ""})))
    assert result["project"]["concept_design"]["batteries"][0]["mount_count"] == 4


def test_extreme_finite_dimension_is_a_structured_refusal():
    with pytest.raises(sship_import.SshipImportError) as error:
        sship_import.preview(build(imperial_fields({13: "1e308"})))
    assert error.value.diagnostics


def test_freeboard_mapping_points_to_the_actual_derived_record():
    result = sship_import.preview(sship())
    assert result["fields"][28]["destinations"] == ["$.migration.derived.representative_freeboard_m"]


def test_incomplete_freeboard_heights_are_only_archived():
    result = sship_import.preview(build(imperial_fields({23: ""})))
    assert result["fields"][28]["disposition"] == "preserved"
    assert result["project"]["migration"]["derived"]["representative_freeboard_m"]["value"] is None


# --------------------------------------------------------------- registry ---
# Recovered positions used by the synthetic fixtures (format-evidence.json).
IDX_NAME = 0
IDX_COUNTRY = 1
IDX_TYPE = 2
IDX_HULL_SCALE = 3
IDX_GUN_SCALE = 4
IDX_ARMOUR_SCALE = 10
IDX_HULL_YEAR = 11
IDX_MISC_VITAL = 12
IDX_LWL = 13
IDX_BEAM = 14
IDX_DRAUGHT = 15
IDX_STERN = 16
IDX_CB = 17
IDX_QD_AFT = 18
IDX_QD_LENGTH = 20
IDX_QD_FORE = 21
IDX_AD_AFT = 22
IDX_FD_LENGTH = 23
IDX_AD_FORE = 24
IDX_FD_AFT = 25
IDX_FC_LENGTH = 26
IDX_FD_FORE = 27
IDX_FC_AFT = 28
IDX_FC_FORE = 29
IDX_BARRELS = 31
IDX_CALIBRE = 32
IDX_GUN_TYPE = 33
IDX_SUPER_MOUNT_G1_EARLY = 34
IDX_SUB_MOUNT_G1_EARLY = 35
IDX_SHELL_WEIGHT = 36
IDX_MAGAZINE = 61
IDX_MOUNTS = 62
IDX_MOUNT_TYPE = 63
IDX_LAYOUT_G1 = 64
IDX_BELT_MAIN = 80
IDX_BELT_MAIN_LENGTH = 81
IDX_BELT_MAIN_HEIGHT = 82
IDX_GUN_ARM_FACE = 92
IDX_DECK_ARMOUR = 107
IDX_CONNING_FORE = 108
IDX_SPEED_MAX = 109
IDX_SPEED_CRUISE = 110
IDX_RANGE = 111
IDX_SHAFTS = 112
IDX_PCT_COAL = 113
IDX_FUEL_COAL = 114
IDX_FUEL_OIL = 115
IDX_FUEL_DIESEL = 116
IDX_FUEL_PETROL = 117
IDX_FUEL_BATTERY = 118
IDX_ENGINE_SIMPLE = 119
IDX_ENGINE_COMPOUND = 120
IDX_ENGINE_TURBINE = 121
IDX_DRIVE_DIRECT = 122
IDX_DRIVE_GEARED = 123
IDX_BULGED_BEAM = 127
IDX_ENGINE_YEAR = 128
IDX_GUN_YEAR = 129
IDX_CAL_LENGTH = 140
IDX_MAGAZINE_2 = 145
IDX_LAYOUT_G2 = 149
IDX_SUPER_MOUNT_G2_EARLY = 154
IDX_SUPER_SUPER = 159
IDX_DECK_MOUNT_G2_EARLY = 164
IDX_SUB_MOUNT_G2_EARLY = 169
IDX_SUB_SUB = 174
IDX_BELT_MAIN_INCLINE = 201
IDX_BULGE = 202
IDX_BULGE_LENGTH = 203
IDX_BULGE_HEIGHT = 204
IDX_BULKHEAD_BEAM = 206
IDX_DECK_FC = 207
IDX_DECK_QD = 208
IDX_DECK_COVERAGE = 209
IDX_CONNING_AFT = 210
IDX_SUPER_MOUNT_G1 = 211
IDX_SUB_MOUNT_G1 = 216
IDX_SUPER_MOUNT_G2 = 221
IDX_DECK_MOUNT_G2 = 226
IDX_SUB_MOUNT_G2 = 231
IDX_GUNS_IN_MOUNT_G1 = 236
IDX_GUNS_IN_MOUNT_G2 = 241
IDX_MISC_VOID = 246
IDX_PADDING_FIRST = 247
FIELD_COUNT = 280
LONG_TON_T = 1.0160469088
POUND_KG = 0.45359237
FT_M = 0.3048
IN_MM = 25.4

DOT_HEADER = "SpringSharp Version 3.0"
COMMA_HEADER = "SpringSharp Version 3,0"


def imperial_fields(overrides=None):
    """Return a complete synthetic imperial field list (no real ship data)."""
    values = [""] * FIELD_COUNT
    values[IDX_NAME] = "SYNTHETIC IMPERIAL CRUISER"
    values[IDX_COUNTRY] = "Synthetic Registry"
    values[IDX_TYPE] = "Cruiser"
    values[IDX_HULL_SCALE] = "0"
    values[IDX_GUN_SCALE] = "0"
    values[IDX_ARMOUR_SCALE] = "0"
    values[IDX_HULL_YEAR] = "1905"
    values[IDX_MISC_VITAL] = "100"
    values[IDX_LWL] = "400"
    values[IDX_BEAM] = "50"
    values[IDX_DRAUGHT] = "15"
    values[IDX_STERN] = "0"
    values[IDX_CB] = "0.550"
    # A flat freeboard profile in feet plus the source length percentages.
    values[IDX_QD_AFT] = "6"
    values[IDX_QD_LENGTH] = "10"
    values[IDX_QD_FORE] = "6"
    values[IDX_AD_AFT] = "5"
    values[IDX_FD_LENGTH] = "10"
    values[IDX_AD_FORE] = "5"
    values[IDX_FD_AFT] = "4"
    values[IDX_FC_LENGTH] = "20"
    values[IDX_FD_FORE] = "4"
    values[IDX_FC_AFT] = "4"
    values[IDX_FC_FORE] = "6"
    values[IDX_BARRELS] = "4"
    values[IDX_CALIBRE] = "12"
    values[IDX_GUN_TYPE] = "1"
    values[IDX_SHELL_WEIGHT] = "100"
    values[IDX_MAGAZINE] = "100"
    values[IDX_MOUNTS] = "4"
    values[IDX_MOUNT_TYPE] = "0"
    values[IDX_LAYOUT_G1] = "0"
    values[IDX_BELT_MAIN] = "6"
    values[IDX_BELT_MAIN_LENGTH] = "300"
    values[IDX_BELT_MAIN_HEIGHT] = "20"
    values[IDX_GUN_ARM_FACE] = "12"
    values[IDX_DECK_ARMOUR] = "2"
    values[IDX_CONNING_FORE] = "8"
    values[IDX_SPEED_MAX] = "20"
    values[IDX_SPEED_CRUISE] = "15"
    values[IDX_RANGE] = "4000"
    values[IDX_SHAFTS] = "2"
    values[IDX_PCT_COAL] = "100"
    values[IDX_FUEL_COAL] = "True"
    values[IDX_ENGINE_COMPOUND] = "True"
    values[IDX_DRIVE_GEARED] = "True"
    values[IDX_BULGED_BEAM] = "53"
    values[IDX_ENGINE_YEAR] = "1903"
    values[IDX_GUN_YEAR] = "1905"
    values[IDX_CAL_LENGTH] = "45"
    values[IDX_SUPER_MOUNT_G1] = "2"
    values[IDX_SUB_MOUNT_G1] = "2"
    values[IDX_GUNS_IN_MOUNT_G1] = "0"
    values[IDX_GUNS_IN_MOUNT_G2] = "0"
    for base in (IDX_SUPER_MOUNT_G2, IDX_DECK_MOUNT_G2, IDX_SUB_MOUNT_G2):
        for bank in range(5):
            values[base + bank] = "0"
    values[IDX_MISC_VOID] = "50"
    for index, text in (overrides or {}).items():
        values[int(index)] = text
    return values


def build(fields, *, header=DOT_HEADER, newline="\r\n", tail="", encoding="utf-8"):
    """Encode a synthetic field list into SpringSharp 3.0 file bytes."""
    assert len(fields) == FIELD_COUNT
    text = newline.join([header, *fields]) + (newline + tail if tail else "")
    return text.encode(encoding)


def sship(overrides=None):
    return build(imperial_fields(overrides))


def field(preview, index):
    return preview["fields"][index]


def codes(preview):
    return {item["code"] for item in preview["diagnostics"]}


# ----------------------------------------------------------------- contract --

def test_preview_returns_the_exact_public_contract(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data = sship()
    result = sship_import.preview(data, filename="Synthetic Ship.sship")

    assert result["schema"] == "plimsoll-sship-preview-1"
    assert result["method_version"] == "springsharp-3.0-migration-1"
    assert set(result) == {
        "schema", "method_version", "source", "project", "fields",
        "counts", "diagnostics", "limitations",
    }
    assert set(result["source"]) == {
        "filename", "sha256", "byte_length", "encoding", "header", "version",
        "decimal_separator",
    }
    assert result["source"]["filename"] == "Synthetic Ship.sship"
    assert result["source"]["byte_length"] == len(data)
    assert result["source"]["header"] == DOT_HEADER
    assert result["source"]["version"] == "3.0"
    assert result["source"]["decimal_separator"] == "."
    assert len(result["source"]["sha256"]) == 64
    # The importer takes bytes and touches no path at all.
    assert list(tmp_path.iterdir()) == []


def test_field_records_and_counts_cover_exactly_280():
    result = sship_import.preview(sship())
    assert len(result["fields"]) == FIELD_COUNT
    for index, entry in enumerate(result["fields"]):
        assert entry["index"] == index
        assert entry["line"] == index + 2
        assert entry["name"]
        assert entry["raw"] == imperial_fields()[index]
        assert entry["disposition"] in {"mapped", "preserved", "duplicate", "reserved"}
        assert isinstance(entry["destinations"], list)
        assert entry["reason"]
    counts = result["counts"]
    assert set(counts) == {"mapped", "preserved", "duplicate", "reserved"}
    assert (counts["mapped"] + counts["preserved"] + counts["duplicate"]
            + counts["reserved"]) == FIELD_COUNT
    for disposition in ("mapped", "preserved", "duplicate", "reserved"):
        assert counts[disposition] == sum(
            1 for entry in result["fields"] if entry["disposition"] == disposition)


def test_padding_is_preserved_and_never_becomes_a_parameter():
    fields = imperial_fields({IDX_PADDING_FIRST: "999999"})
    result = sship_import.preview(build(fields))
    for index in range(IDX_PADDING_FIRST, FIELD_COUNT):
        assert field(result, index)["disposition"] == "reserved"
        assert field(result, index)["destinations"] == []
    assert result["counts"]["reserved"] == FIELD_COUNT - IDX_PADDING_FIRST
    assert field(result, IDX_PADDING_FIRST)["raw"] == "999999"
    # A non-numeric padding token is not a malformed parameter either.
    padded = imperial_fields({IDX_PADDING_FIRST: "ignored"})
    assert sship_import.preview(build(padded))["counts"]["reserved"] == FIELD_COUNT - IDX_PADDING_FIRST


def test_notes_tail_is_preserved_exactly_and_raw_bytes_round_trip():
    tail = "Notes: synthetic fixture.\r\nSecond line, with a comma 1,234.\n"
    data = build(imperial_fields(), tail=tail)
    result = sship_import.preview(data, filename="synthetic.sship")
    archive = result["project"]["migration"]
    assert archive["notes"] == tail
    assert archive["original_base64"] == base64.b64encode(data).decode("ascii")
    assert base64.b64decode(archive["original_base64"]) == data
    assert archive["raw_fields"] == imperial_fields()
    assert archive["schema"] == "plimsoll-sship-migration-1"
    assert archive["method_version"] == "springsharp-3.0-migration-1"
    assert archive["source"] == result["source"]


def test_text_fields_are_never_punctuation_swapped():
    fields = imperial_fields({IDX_COUNTRY: "Royaume, 1er (Suisse)"})
    result = sship_import.preview(build(fields, header=COMMA_HEADER))
    assert field(result, IDX_COUNTRY)["raw"] == "Royaume, 1er (Suisse)"
    assert result["project"]["metadata"]["country"]["value"] == "Royaume, 1er (Suisse)"


# ------------------------------------------------------------- header/bytes --

@pytest.mark.parametrize("header,version,separator", [
    (DOT_HEADER, "3.0", "."),
    (COMMA_HEADER, "3,0", ","),
])
def test_both_supported_headers(header, version, separator):
    result = sship_import.preview(build(imperial_fields(), header=header))
    assert result["source"]["header"] == header
    assert result["source"]["version"] == version
    assert result["source"]["decimal_separator"] == separator


@pytest.mark.parametrize("header", [
    "SpringSharp Version 2.0",
    "SpringSharp Version 1.0",
    "SpringStyle Version 1.0",
    "SpringSharp Version 4.0",
    "SpringSharp Version 3.1",
    "",
])
def test_other_versions_are_rejected_with_a_diagnostic(header):
    with pytest.raises(sship_import.SshipImportError) as error:
        sship_import.preview(build(imperial_fields(), header=header))
    assert "sship.version_unsupported" in {item["code"] for item in error.value.diagnostics}
    assert all(item["severity"] == "error" for item in error.value.diagnostics)


@pytest.mark.parametrize("encoding,expected", [
    ("utf-8", "utf-8"),
    ("utf-8-sig", "utf-8-bom"),
    ("utf-16-le-bom", "utf-16-le-bom"),
    ("utf-16-be-bom", "utf-16-be-bom"),
])
def test_supported_encodings_decode_strictly(encoding, expected):
    text = "\r\n".join([DOT_HEADER, *imperial_fields(), "tail"])
    if encoding == "utf-16-le-bom":
        data = b"\xff\xfe" + text.encode("utf-16-le")
    elif encoding == "utf-16-be-bom":
        data = b"\xfe\xff" + text.encode("utf-16-be")
    else:
        data = text.encode(encoding)
    result = sship_import.preview(data)
    assert result["source"]["encoding"] == expected
    assert len(result["fields"]) == FIELD_COUNT


def test_unmarked_utf16_and_invalid_utf8_are_rejected():
    with pytest.raises(sship_import.SshipImportError):
        sship_import.preview((DOT_HEADER + "\r\n").encode("utf-16-le"))
    with pytest.raises(sship_import.SshipImportError) as error:
        sship_import.preview(b"SpringSharp Version 3.0\r\n\xff\xfe\x00bad")
    assert "sship.source.encoding_invalid" in {
        item["code"] for item in error.value.diagnostics}


@pytest.mark.parametrize("newline", ["\r\n", "\r", "\n"])
def test_all_three_record_separators_are_accepted(newline):
    result = sship_import.preview(build(imperial_fields(), newline=newline))
    assert len(result["fields"]) == FIELD_COUNT
    assert result["project"]["hull"]["lwl_m"] == pytest.approx(400 * FT_M)


def test_missing_final_newline_is_accepted_but_truncation_is_not():
    text = "\r\n".join([DOT_HEADER, *imperial_fields()])
    assert len(sship_import.preview(text.encode("utf-8"))["fields"]) == FIELD_COUNT
    short = "\r\n".join([DOT_HEADER, *imperial_fields()[:279]]).encode("utf-8")
    with pytest.raises(sship_import.SshipImportError) as error:
        sship_import.preview(short)
    assert "sship.fields.truncated" in {item["code"] for item in error.value.diagnostics}


def test_oversized_input_and_lines_are_rejected():
    padded = imperial_fields({IDX_NAME: "x" * (sship_import.MAX_LINE_CHARS + 1)})
    with pytest.raises(sship_import.SshipImportError) as error:
        sship_import.preview(build(padded))
    assert "sship.field.too_long" in {item["code"] for item in error.value.diagnostics}

    blob = build(imperial_fields()) + b"\r\n" + b"n" * (sship_import.MAX_BYTES + 1)
    with pytest.raises(sship_import.SshipImportError) as error:
        sship_import.preview(blob)
    assert "sship.source.too_large" in {item["code"] for item in error.value.diagnostics}


# ------------------------------------------------------------------ numbers --

@pytest.mark.parametrize("token,header,expected", [
    ("1234.5", DOT_HEADER, 1234.5),
    ("1.234,5", COMMA_HEADER, 1234.5),
    ("12,5", COMMA_HEADER, 12.5),
    ("1 234.5", DOT_HEADER, 1234.5),
    ("1\u00a0234.5", DOT_HEADER, 1234.5),
    ("1\u202f234,5", COMMA_HEADER, 1234.5),
    ("1,234", DOT_HEADER, 1234.0),
    ("1.5e3", DOT_HEADER, 1500.0),
    ("2,5E2", COMMA_HEADER, 250.0),
    ("0", DOT_HEADER, 0.0),
    ("+7", DOT_HEADER, 7.0),
    (".5", DOT_HEADER, 0.5),
])
def test_grouped_and_scientific_numbers_follow_the_header_convention(token, header, expected):
    result = sship_import.preview(build(imperial_fields({IDX_LWL: token}), header=header))
    assert result["project"]["hull"]["lwl_m"] == pytest.approx(expected * FT_M)


@pytest.mark.parametrize("token,header", [
    ("1.23", COMMA_HEADER),
    ("1.0000", COMMA_HEADER),
    ("12,345,6", COMMA_HEADER),
    ("1,23.5", COMMA_HEADER),
    ("1.2.3", DOT_HEADER),
    ("1.2.3.4", DOT_HEADER),
    ("nan", DOT_HEADER),
    ("inf", DOT_HEADER),
    ("Infinity", DOT_HEADER),
    ("1e400", DOT_HEADER),
    ("--3", DOT_HEADER),
    ("1,2x", DOT_HEADER),
    ("12 34 5", DOT_HEADER),
])
def test_ambiguous_or_malformed_numbers_are_rejected(token, header):
    with pytest.raises(sship_import.SshipImportError) as error:
        sship_import.preview(build(imperial_fields({IDX_LWL: token}), header=header))
    assert "sship.field.number_invalid" in {item["code"] for item in error.value.diagnostics}


def test_numeric_token_length_is_bounded():
    token = "1" * (sship_import.MAX_TOKEN_CHARS + 1)
    with pytest.raises(sship_import.SshipImportError) as error:
        sship_import.preview(build(imperial_fields({IDX_LWL: token})))
    assert "sship.field.number_invalid" in {item["code"] for item in error.value.diagnostics}


def test_blank_is_unknown_and_zero_is_zero():
    blank = sship_import.preview(build(imperial_fields({IDX_MISC_VITAL: ""})))
    misc = {item["id"]: item for group in blank["project"]["weight_groups"]
            for item in group["items"]}
    assert misc["misc.vital"]["mass_t"] is None
    zero = sship_import.preview(build(imperial_fields({IDX_MISC_VITAL: "0"})))
    misc = {item["id"]: item for group in zero["project"]["weight_groups"]
            for item in group["items"]}
    assert misc["misc.vital"]["mass_t"] == 0.0
    assert field(zero, IDX_MISC_VITAL)["raw"] == "0"


def test_negative_dimensions_are_errors():
    with pytest.raises(sship_import.SshipImportError) as error:
        sship_import.preview(build(imperial_fields({IDX_LWL: "-5"})))
    assert "sship.field.negative" in {item["code"] for item in error.value.diagnostics}


def test_out_of_domain_values_stay_archived_instead_of_being_clamped():
    result = sship_import.preview(build(imperial_fields({IDX_CB: "1.4"})))
    assert result["project"]["hull"]["block_coeff"] is None
    assert field(result, IDX_CB)["disposition"] == "preserved"
    assert "sship.value.out_of_domain" in codes(result)
    assert field(result, IDX_CB)["raw"] == "1.4"


# -------------------------------------------------------------------- units --

def test_scale_selectors_are_independent_per_group():
    # Hull stays feet, gun becomes millimetres, armour stays inches.
    result = sship_import.preview(build(imperial_fields({
        IDX_HULL_SCALE: "0", IDX_GUN_SCALE: "1", IDX_ARMOUR_SCALE: "0",
        IDX_CALIBRE: "304.8",
    })))
    hull = result["project"]["hull"]
    assert hull["lwl_m"] == pytest.approx(400 * FT_M)
    assert hull["beam_m"] == pytest.approx(50 * FT_M)
    battery = result["project"]["concept_design"]["batteries"][0]
    assert battery["calibre_mm"] == pytest.approx(304.8)
    belt = result["project"]["systems"]["armour"]["fixed"]["belt_main"]["facts"]
    assert belt["thickness_m"]["value"] == pytest.approx(0.1524)
    assert belt["length_m"]["value"] == pytest.approx(300 * FT_M)
    assert belt["length_m"]["value"] != pytest.approx(300)


def test_scale_selector_command_values_are_rejected():
    for index in (IDX_HULL_SCALE, IDX_GUN_SCALE, IDX_ARMOUR_SCALE):
        for command in ("2", "3"):
            with pytest.raises(sship_import.SshipImportError) as error:
                sship_import.preview(build(imperial_fields({index: command})))
            assert "sship.scale.selector_unsupported" in {
                item["code"] for item in error.value.diagnostics}


def test_shell_weight_is_always_pounds_even_with_metric_calibre():
    result = sship_import.preview(build(imperial_fields({
        IDX_GUN_SCALE: "1", IDX_CALIBRE: "304.8", IDX_SHELL_WEIGHT: "100",
    })))
    battery = result["project"]["concept_design"]["batteries"][0]
    assert battery["shell_mass_kg"] == pytest.approx(100 * POUND_KG)
    other = sship_import.preview(build(imperial_fields({
        IDX_HULL_SCALE: "1", IDX_ARMOUR_SCALE: "1", IDX_SHELL_WEIGHT: "100",
    })))
    assert other["project"]["concept_design"]["batteries"][0]["shell_mass_kg"] \
        == pytest.approx(100 * POUND_KG)


def test_misc_weights_are_always_long_tons_regardless_of_scale():
    fields = imperial_fields({IDX_HULL_SCALE: "1", IDX_ARMOUR_SCALE: "1"})
    for index in (IDX_MISC_VITAL, 198, 199, 200, IDX_MISC_VOID):
        fields[index] = "100"
    result = sship_import.preview(build(fields))
    misc = {item["id"]: item for group in result["project"]["weight_groups"]
            for item in group["items"]}
    for key in ("misc.vital", "misc.hull", "misc.deck", "misc.above", "misc.void"):
        assert misc[key]["mass_t"] == pytest.approx(100 * LONG_TON_T)


# ----------------------------------------------------------------- weapons --

def test_final_duplicate_block_overrides_the_earlier_copy():
    result = sship_import.preview(build(imperial_fields({
        IDX_SUPER_MOUNT_G1_EARLY: "9", IDX_SUB_MOUNT_G1_EARLY: "9",
        IDX_SUPER_MOUNT_G2_EARLY: "9", IDX_DECK_MOUNT_G2_EARLY: "9",
        IDX_SUB_MOUNT_G2_EARLY: "9",
        IDX_SUPER_MOUNT_G1: "1", IDX_SUB_MOUNT_G1: "1",
        IDX_SUPER_MOUNT_G2: "0", IDX_DECK_MOUNT_G2: "0", IDX_SUB_MOUNT_G2: "0",
    })))
    assert result["counts"]["duplicate"] == 25
    for offset in range(5):
        assert field(result, IDX_SUPER_MOUNT_G1_EARLY + 6 * offset)["disposition"] == "duplicate"
        assert field(result, IDX_SUB_MOUNT_G1_EARLY + 6 * offset)["disposition"] == "duplicate"
        assert field(result, IDX_SUPER_MOUNT_G2_EARLY + offset)["disposition"] == "duplicate"
        assert field(result, IDX_DECK_MOUNT_G2_EARLY + offset)["disposition"] == "duplicate"
        assert field(result, IDX_SUB_MOUNT_G2_EARLY + offset)["disposition"] == "duplicate"
    # The final occurrence wins: two above the freeboard deck, two below.
    assert result["project"]["concept_design"]["batteries"][0]["mount_count"] == 4
    assert field(result, IDX_SUPER_MOUNT_G1_EARLY)["raw"] == "9"


def test_ignored_duplicate_never_falls_back_when_the_final_value_is_blank():
    result = sship_import.preview(build(imperial_fields({
        IDX_SUB_MOUNT_G1_EARLY: "3", IDX_SUB_MOUNT_G1: "",
    })))
    assert "sship.battery.count_unknown" in codes(result)
    assert result["project"]["concept_design"].get("batteries", []) == []


def test_ignored_duplicate_with_unreadable_text_is_a_warning_not_a_rejection():
    result = sship_import.preview(build(imperial_fields({
        IDX_SUB_MOUNT_G1_EARLY: "not-a-number",
    })))
    assert "sship.field.ignored_invalid" in codes(result)
    assert all(item["severity"] in {"warning", "info"} for item in result["diagnostics"])


def test_divergent_duplicates_raise_a_visible_warning():
    result = sship_import.preview(build(imperial_fields({
        IDX_SUPER_MOUNT_G1_EARLY: "2", IDX_SUPER_MOUNT_G1: "3",
    })))
    assert "sship.duplicate.value_conflict" in codes(result)


def test_group_two_mounts_split_into_separate_canonical_batteries():
    result = sship_import.preview(build(imperial_fields({
        IDX_MOUNTS: "6", IDX_SUPER_MOUNT_G1: "2", IDX_SUB_MOUNT_G1: "2",
        IDX_SUPER_MOUNT_G2: "1", IDX_DECK_MOUNT_G2: "0", IDX_SUB_MOUNT_G2: "1",
        IDX_GUNS_IN_MOUNT_G1: "0", IDX_GUNS_IN_MOUNT_G2: "8", IDX_BARRELS: "16",
    })))
    batteries = result["project"]["concept_design"]["batteries"]
    assert [item["barrels_per_mount"] for item in batteries] == [1, 6]
    assert [item["mount_count"] for item in batteries] == [4, 2]
    assert [item["shared_cradle"] for item in batteries] == [False, False]
    assert len({item["guns_item_id"] for item in batteries}) == 2


def test_identical_groups_stay_one_canonical_battery():
    result = sship_import.preview(build(imperial_fields({
        IDX_MOUNTS: "6", IDX_SUPER_MOUNT_G1: "2", IDX_SUB_MOUNT_G1: "2",
        IDX_SUPER_MOUNT_G2: "1", IDX_DECK_MOUNT_G2: "0", IDX_SUB_MOUNT_G2: "1",
        IDX_GUNS_IN_MOUNT_G1: "3", IDX_GUNS_IN_MOUNT_G2: "3", IDX_BARRELS: "12",
    })))
    batteries = result["project"]["concept_design"]["batteries"]
    assert len(batteries) == 1
    assert batteries[0]["mount_count"] == 6
    assert batteries[0]["barrels_per_mount"] == 2
    assert batteries[0]["shared_cradle"] is True


def test_shared_cradle_index_is_taken_from_the_original_table():
    result = sship_import.preview(build(imperial_fields({
        IDX_MOUNTS: "2", IDX_SUPER_MOUNT_G1: "2", IDX_SUB_MOUNT_G1: "0",
        IDX_GUNS_IN_MOUNT_G1: "3",  # "Twin mount"
    })))
    battery = result["project"]["concept_design"]["batteries"][0]
    assert battery["barrels_per_mount"] == 2
    assert battery["shared_cradle"] is True


def test_inconsistent_group_counts_keep_the_bank_but_drop_the_model():
    result = sship_import.preview(build(imperial_fields({
        IDX_MOUNTS: "1", IDX_SUPER_MOUNT_G1: "5", IDX_SUB_MOUNT_G1: "5",
    })))
    assert "sship.battery.count_inconsistent" in codes(result)
    assert result["project"]["concept_design"].get("batteries", []) == []
    assert "bank1" in result["project"]["systems"]["weapons"]
    assert field(result, IDX_SUPER_MOUNT_G1)["disposition"] == "preserved"
    assert result["project"]["migration"]["raw_fields"][IDX_SUPER_MOUNT_G1] == "5"


def test_out_of_domain_battery_is_preserved_without_its_model():
    result = sship_import.preview(build(imperial_fields({IDX_CALIBRE: "600"})))
    assert "sship.concept.battery_unsupported" in codes(result)
    assert result["project"]["concept_design"].get("batteries", []) == []
    facts = result["project"]["systems"]["weapons"]["bank1"]["facts"]
    assert facts["calibre_m"]["value"] == pytest.approx(600 * IN_MM / 1000.0)
    assert facts["calibre_m"]["value"] > 1.0


def test_total_barrels_are_not_equated_with_mounts():
    result = sship_import.preview(build(imperial_fields({
        IDX_MOUNTS: "4", IDX_SUPER_MOUNT_G1: "2", IDX_SUB_MOUNT_G1: "2",
        IDX_BARRELS: "16", IDX_GUNS_IN_MOUNT_G1: "2",
    })))
    battery = result["project"]["concept_design"]["batteries"][0]
    assert battery["mount_count"] == 4
    assert battery["barrels_per_mount"] == 4
    assert battery["guns_item_id"] != battery["mounts_item_id"]
    assert battery["ammunition_item_id"] not in {battery["guns_item_id"],
                                                 battery["mounts_item_id"]}


def test_broadside_count_is_never_a_sourced_installed_count_claim():
    result = sship_import.preview(sship())
    battery = result["project"]["concept_design"]["batteries"][0]
    assert battery["broadside_guns"] is None
    assert result["project"]["concept_design"].get("balance") is None
    assert any("broadside" in text.lower() for text in result["limitations"])


def test_weapon_facts_stay_editable_and_rotating_armour_is_kept():
    result = sship_import.preview(sship())
    leaf = result["project"]["systems"]["weapons"]["bank1"]
    assert leaf["facts"]["weapon_type"]["value"] == "breech_loading"
    assert leaf["facts"]["mount_count"]["value"] == 4
    assert leaf["facts"]["rounds_per_gun"]["value"] == 100
    assert leaf["facts"]["projectile_mass_kg"]["value"] == pytest.approx(100 * POUND_KG)
    assert leaf["weight_item_ids"]
    rotating = result["project"]["systems"]["armour"]["fixed"]["rotating_armour"]["bank1"]
    assert rotating["facts"]["thickness_m"]["value"] == pytest.approx(0.3048)
    assert rotating["facts"]["zone"]["value"] == "rotating_armour"


# --------------------------------------------------------------- propulsion --

def test_machinery_and_fuel_are_enabled_for_the_supported_steam_domain():
    result = sship_import.preview(sship())
    config = result["project"]["concept_design"]
    assert config["machinery"]["kind"] == "compound"
    assert config["machinery"]["coal_pct"] == 100.0
    assert config["machinery"]["speed_kn"] == 20.0
    assert config["fuel"]["range_nm"] == 4000.0
    assert config["fuel"]["cruise_speed_kn"] == 15.0
    assert config["screws"] == 2
    facts = result["project"]["systems"]["propulsion"]["machinery"]["facts"]
    assert facts["shafts"]["value"] == 2
    assert facts["max_speed_kn"]["value"] == 20.0
    assert facts["transmission"]["value"] == "Geared"
    assert facts["energy_source"]["value"] == "Coal fired boilers"


def test_diesel_is_never_coerced_into_the_steam_domain():
    result = sship_import.preview(build(imperial_fields({
        IDX_FUEL_COAL: "False", IDX_FUEL_DIESEL: "True", IDX_PCT_COAL: "0",
    })))
    config = result["project"]["concept_design"]
    assert config.get("machinery") is None
    assert config.get("fuel") is None
    assert "sship.concept.propulsion_unsupported" in codes(result)


def test_missing_shaft_power_stays_null():
    result = sship_import.preview(sship())
    facts = result["project"]["systems"]["propulsion"]["machinery"]["facts"]
    assert facts["design_power_kw"]["value"] is None
    assert facts["trial_power_kw"]["value"] is None
    assert result["project"]["concept_design"]["machinery"]["shaft_power_kw"] is None


def test_zero_speed_is_not_treated_as_a_supplied_value():
    result = sship_import.preview(build(imperial_fields({IDX_SPEED_MAX: "0"})))
    facts = result["project"]["systems"]["propulsion"]["machinery"]["facts"]
    assert facts["max_speed_kn"]["value"] is None
    assert "sship.value.zero_not_positive" in codes(result)
    assert result["project"]["concept_design"]["machinery"]["speed_kn"] is None


# ------------------------------------------------------- physical honesty ---

def test_no_geometry_cg_or_full_ledger_is_manufactured():
    project = sship_import.preview(sship())["project"]
    assert project["geometry"] is None
    assert project["compartments"] == []
    assert project["openings"] == []
    assert project["opening_definition"] == "unknown"
    assert len(project["loading_conditions"]) == 1
    assert project["loading_conditions"][0]["reference_displacement_t"] is None
    assert project["loading_conditions"][0]["overrides"] == {}
    for key in ("lwl_m", "beam_m", "draught_normal_m", "block_coeff"):
        assert isinstance(project["hull"][key], float)
    ledger = {item["id"]: item for group in project["weight_groups"] for item in group["items"]}
    assert ledger["misc.unknown"]["mass_t"] is None
    for key, item in ledger.items():
        if key.startswith(("weapons.", "propulsion.")):
            assert item["mass_t"] is None
        assert item["x_m"] is None and item["y_m"] is None and item["kg_m"] is None
    assert all("ballast" not in item["id"] for item in ledger.values())


def test_derived_displacement_uses_the_bulged_beam_formula():
    result = sship_import.preview(sship())
    derived = result["project"]["migration"]["derived"]
    expected_lt = (400 * 53 * 15 * 0.550) / 35.0
    assert derived["normal_displacement_long_tons"]["value"] == pytest.approx(expected_lt)
    assert derived["normal_displacement_t"]["value"] == pytest.approx(expected_lt * LONG_TON_T)
    assert derived["normal_displacement_t"]["source_fields"] == [
        IDX_LWL, IDX_BULGED_BEAM, IDX_DRAUGHT, IDX_CB]
    assert "L_ft" in derived["normal_displacement_t"]["formula"]
    assert result["project"]["concept_design"]["target_displacement_t"] == pytest.approx(
        expected_lt * LONG_TON_T)


def test_missing_bulged_beam_is_never_substituted_by_the_moulded_beam():
    result = sship_import.preview(build(imperial_fields({IDX_BULGED_BEAM: ""})))
    derived = result["project"]["migration"]["derived"]
    assert derived["normal_displacement_long_tons"]["value"] is None
    assert derived["normal_displacement_t"]["value"] is None
    assert "sship.derived.bulged_beam_required" in codes(result)
    assert result["project"].get("concept_design") is None


def test_representative_freeboard_uses_the_original_length_weighting():
    # FC = 0.6*4 + 0.4*6 = 4.8 ft, FD = 4, AD = 5, QD = 6;
    # fc/fd/qd = 20/10/10 % so ad = 60 %.
    # 4.8*0.2 + 4*0.1 + 5*0.6 + 6*0.1 = 4.96 ft.
    result = sship_import.preview(sship())
    derived = result["project"]["migration"]["derived"]
    expected = (4.8 * 0.2 + 4.0 * 0.1 + 5.0 * 0.6 + 6.0 * 0.1) * FT_M
    assert derived["representative_freeboard_m"]["value"] == pytest.approx(expected)
    assert result["project"]["concept_design"]["freeboard_m"] == pytest.approx(expected)
    assert derived["representative_freeboard_m"]["formula"].startswith("FC_m = 0.6")
    assert derived["freeboard_forecastle_m"]["value"] == pytest.approx(4.8 * FT_M)
    assert derived["freeboard_quarterdeck_m"]["value"] == pytest.approx(6.0 * FT_M)
    assert derived["representative_freeboard_m"]["inputs"]["length_fractions"] == pytest.approx(
        {"fc": 0.2, "fd": 0.1, "qd": 0.1, "ad": 0.6})


def test_metric_freeboard_sample_matches_the_recovered_weighting():
    # A metric sample: FCaft 6 FCfore 8, FD 5/6, AD 4/5, QD 4/4 with the
    # declared 20/30/15 % lengths, so ad = 35 %.
    # FC = 6.8, FD = 5.5, AD = 4.5, QD = 4.0;
    # 6.8*0.20 + 5.5*0.30 + 4.5*0.35 + 4.0*0.15 = 5.185 m.
    fields = imperial_fields({
        IDX_HULL_SCALE: "1", IDX_LWL: "120", IDX_BEAM: "15", IDX_DRAUGHT: "5",
        IDX_BULGED_BEAM: "16", IDX_QD_AFT: "4", IDX_QD_LENGTH: "15", IDX_AD_AFT: "4",
        IDX_FD_LENGTH: "30", IDX_AD_FORE: "5", IDX_FD_AFT: "5", IDX_FC_LENGTH: "20",
        IDX_FD_FORE: "6", IDX_FC_AFT: "6", IDX_QD_FORE: "4", IDX_FC_FORE: "8",
    })
    derived = sship_import.preview(build(fields))["project"]["migration"]["derived"]
    assert derived["representative_freeboard_m"]["value"] == pytest.approx(5.185)
    assert derived["freeboard_forecastle_m"]["value"] == pytest.approx(6.8)
    assert derived["freeboard_flat_deck_m"]["value"] == pytest.approx(5.5)
    assert derived["freeboard_afterdeck_m"]["value"] == pytest.approx(4.5)
    assert derived["freeboard_quarterdeck_m"]["value"] == pytest.approx(4.0)


def test_installed_barrels_must_agree_with_both_mount_groups():
    # 4 single mounts carry 4 barrels, not the 9 the source used to declare.
    wrong = sship_import.preview(build(imperial_fields({IDX_BARRELS: "9"})))
    assert "sship.battery.barrels_inconsistent" in codes(wrong)
    assert wrong["project"]["concept_design"].get("batteries", []) == []
    facts = wrong["project"]["systems"]["weapons"]["bank1"]["facts"]
    assert facts["mount_count"]["value"] == 4
    assert field(wrong, IDX_BARRELS)["disposition"] == "mapped"
    assert "bank1" in wrong["project"]["systems"]["weapons"]

    right = sship_import.preview(build(imperial_fields({IDX_BARRELS: "4"})))
    assert "sship.battery.barrels_inconsistent" not in codes(right)
    assert len(right["project"]["concept_design"]["batteries"]) == 1


def test_installed_barrels_are_checked_across_both_groups():
    fields = imperial_fields({
        IDX_MOUNTS: "6", IDX_SUPER_MOUNT_G1: "2", IDX_SUB_MOUNT_G1: "2",
        IDX_SUPER_MOUNT_G2: "1", IDX_DECK_MOUNT_G2: "0", IDX_SUB_MOUNT_G2: "1",
        IDX_GUNS_IN_MOUNT_G1: "0", IDX_GUNS_IN_MOUNT_G2: "8", IDX_BARRELS: "4",
    })
    result = sship_import.preview(build(fields))
    assert "sship.battery.barrels_inconsistent" in codes(result)
    assert result["project"]["concept_design"].get("batteries", []) == []


def test_blank_scale_selector_is_unknown_not_implicitly_imperial():
    fields = imperial_fields({IDX_HULL_SCALE: "", IDX_GUN_SCALE: "",
                              IDX_ARMOUR_SCALE: ""})
    result = sship_import.preview(build(fields))
    assert "sship.scale.selector_unknown" in codes(result)
    hull = result["project"]["hull"]
    assert hull["lwl_m"] is None
    assert hull["beam_m"] is None
    assert hull["draught_normal_m"] is None
    assert field(result, IDX_LWL)["disposition"] == "preserved"
    assert field(result, IDX_LWL)["raw"] == "400"
    facts = result["project"]["systems"]["weapons"]["bank1"]["facts"]
    assert "calibre_m" not in facts
    belt = result["project"]["systems"]["armour"]["fixed"]["belt_main"]["facts"]
    assert "thickness_m" not in belt
    # Dimensionless counts stay readable without any unit.
    assert facts["mount_count"]["value"] == 4
    assert result["project"]["migration"]["derived"]["normal_displacement_t"]["value"] is None


def test_utf16_byte_order_mark_never_leaks_into_the_header():
    text = "\r\n".join([DOT_HEADER, *imperial_fields(), "tail"])
    for bom, codec in ((b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be")):
        result = sship_import.preview(bom + text.encode(codec), filename="s.sship")
        assert result["source"]["header"] == DOT_HEADER
        assert result["source"]["fields" if False else "filename"] == "s.sship"
        assert result["project"]["migration"]["raw_fields"][0] == imperial_fields()[0]
        assert result["project"]["name"] == "SYNTHETIC IMPERIAL CRUISER"
        assert result["project"]["migration"]["notes"] == "tail"


def test_utf8_bom_is_also_consumed():
    text = "\r\n".join([DOT_HEADER, *imperial_fields(), "tail"])
    result = sship_import.preview(b"\xef\xbb\xbf" + text.encode("utf-8"))
    assert result["source"]["encoding"] == "utf-8-bom"
    assert result["source"]["header"] == DOT_HEADER


def test_concept_estimates_are_not_adopted_and_ledger_masses_stay_null():
    result = sship_import.preview(sship())
    assert result["project"]["concept_design"]["estimate"] is True
    ledger = {item["id"]: item for group in result["project"]["weight_groups"]
              for item in group["items"]}
    guns = ledger["weapons.bank1.g1.guns"]
    assert guns["mass_t"] is None
    assert guns["estimate"] is None


# --------------------------------------------------------------- the draft ---

def test_supported_batteries_and_machinery_reuse_the_existing_estimates():
    # The generated working condition permits existing estimates without
    # inventing a historical condition, masses, positions or overrides.
    project = sship_import.preview(sship())["project"]
    assert "generated" in project["loading_conditions"][0]["source"].lower()
    project["loading_conditions"] = [
        {"id": "normal", "label": "Normal", "reference_displacement_t": None,
         "overrides": {}}]
    project = project_io.normalize_project(project)

    state = loading.resolve_loading(project, "normal")
    generated = concept_design.generated_models(project, state)
    assert {item["code"] for item in generated["diagnostics"] if item.get("blocking")} == {
        "concept_design.machinery_unavailable"}
    assert generated["hull_proxy"] is not None
    components = {model["concept_component"]: system
                  for system, models in generated["systems"].items()
                  for model in models if "concept_component" in model}
    assert {"guns", "mounts", "ammunition", "fuel"} <= set(components)
    assert "machinery" not in components
    for model in generated["systems"]["weapons.bank1"]:
        assert model["method"] == "empirical_estimate_v1"
        assert model["estimate"] is True
        assert model["linked_weight_item_id"].startswith("weapons.bank1.g1.")
    # Generated models propose masses; nothing is written into the ledger.
    ledger = {item["id"]: item for group in project["weight_groups"] for item in group["items"]}
    assert ledger["weapons.bank1.g1.guns"]["mass_t"] is None
    assert ledger["propulsion.machinery"]["mass_t"] is None


def test_diesel_bank_never_reaches_a_concept_model():
    project = sship_import.preview(build(imperial_fields({
        IDX_FUEL_COAL: "False", IDX_FUEL_DIESEL: "True", IDX_PCT_COAL: "0",
    })))["project"]
    project["loading_conditions"] = [
        {"id": "normal", "label": "Normal", "reference_displacement_t": None,
         "overrides": {}}]
    project = project_io.normalize_project(project)
    state = loading.resolve_loading(project, "normal")
    generated = concept_design.generated_models(project, state)
    assert generated["systems"].get("propulsion.machinery") is None
    assert generated["systems"].get("propulsion.fuel") is None


def test_generated_project_validates_without_blocking_diagnostics():
    result = sship_import.preview(sship())
    errors = [item for item in project_io.validate_project(result["project"])
              if item["severity"] == "error"]
    assert errors == []


def test_import_normalize_export_reimport_is_stable():
    result = sship_import.preview(sship(), filename="Synthetic Ship.sship")
    once = project_io.normalize_project(result["project"])
    text = json.dumps(once, ensure_ascii=False, sort_keys=True, allow_nan=False)
    twice = project_io.normalize_project(json.loads(text))
    assert twice == once
    assert twice["migration"]["raw_fields"] == imperial_fields()
    assert project_io.input_fingerprint(once) == project_io.input_fingerprint(twice)


def test_project_identity_is_deterministic_and_name_falls_back_to_the_stem():
    fields = imperial_fields({IDX_NAME: ""})
    first = sship_import.preview(build(fields), filename="HMS Example.sship")
    second = sship_import.preview(build(fields), filename="HMS Example.sship")
    assert first["project"]["id"] == second["project"]["id"]
    assert first["project"]["id"].startswith("sship-")
    assert first["project"]["name"] == "HMS Example"
    assert "sship.name.fallback" in codes(first)
    assert sship_import.preview(sship())["project"]["name"] == "SYNTHETIC IMPERIAL CRUISER"


def test_supplied_name_wins_and_is_not_rewritten():
    project = sship_import.convert(sship(), filename="synthetic.sship", name="Renamed Cruiser")
    assert project["name"] == "Renamed Cruiser"
    assert project["migration"]["source"]["filename"] == "synthetic.sship"


def test_conversion_does_not_mutate_its_inputs():
    data = sship()
    before = bytes(data)
    preview = sship_import.preview(data)
    snapshot = copy.deepcopy(preview)
    project = sship_import.convert(data)
    assert data == before
    assert preview == snapshot
    assert project["migration"]["source"]["sha256"] == preview["source"]["sha256"]


def test_out_of_domain_year_stays_archived_with_a_warning():
    result = sship_import.preview(build(imperial_fields({IDX_ENGINE_YEAR: "2200"})))
    assert result["project"]["metadata"]["engine_built_year"]["value"] is None
    assert field(result, IDX_ENGINE_YEAR)["disposition"] == "preserved"
    assert "sship.value.out_of_domain" in codes(result)
    assert field(result, IDX_ENGINE_YEAR)["raw"] == "2200"


def test_unreadable_active_field_is_rejected_with_its_source_line():
    with pytest.raises(sship_import.SshipImportError) as error:
        sship_import.preview(build(imperial_fields({IDX_ENGINE_YEAR: "not-a-year"})))
    item = next(entry for entry in error.value.diagnostics
                if entry["code"] == "sship.field.number_invalid")
    assert item["line"] == IDX_ENGINE_YEAR + 2
    assert item["index"] == IDX_ENGINE_YEAR
    assert item["blocking"] is True


def test_reported_diagnostics_are_structured_and_non_fatal():
    result = sship_import.preview(sship())
    assert result["diagnostics"]
    for item in result["diagnostics"]:
        assert set(item) >= {"code", "severity", "path", "message", "blocking"}
        assert item["severity"] in {"warning", "info"}
        assert item["blocking"] is False
    assert isinstance(result["limitations"], list) and result["limitations"]


def test_preview_rejects_non_bytes_input():
    with pytest.raises(sship_import.SshipImportError) as error:
        sship_import.preview(DOT_HEADER)
    assert "sship.source.not_bytes" in {item["code"] for item in error.value.diagnostics}


def test_preview_is_json_serializable_and_finite():
    result = sship_import.preview(sship())
    text = json.dumps(result, ensure_ascii=False, allow_nan=False)
    assert json.loads(text)["project"] == result["project"]
    for entry in result["project"]["migration"]["derived"].values():
        value = entry["value"]
        assert value is None or (isinstance(value, float) and math.isfinite(value))


def test_armour_extents_follow_the_armour_scale_selector():
    # ArmourControl.cs reads belt/bulkhead/bulge extents with
    # fpCheck(..., Con.feet2metres, scale.SelectedIndex) where `scale` is the
    # armour thickness selector saved at position 10, not the hull scale at 3.
    result = sship_import.preview(build(imperial_fields({
        IDX_ARMOUR_SCALE: "1", IDX_HULL_SCALE: "0", IDX_BELT_MAIN: "152.4",
        IDX_BELT_MAIN_LENGTH: "300", IDX_BELT_MAIN_HEIGHT: "6.096",
    })))
    belt = result["project"]["systems"]["armour"]["fixed"]["belt_main"]["facts"]
    assert belt["thickness_m"]["value"] == pytest.approx(0.1524)
    assert belt["length_m"]["value"] == pytest.approx(300.0)
    assert belt["height_m"]["value"] == pytest.approx(6.096)
    # The hull scale is untouched by the metric armour selector.
    assert result["project"]["hull"]["beam_m"] == pytest.approx(50 * FT_M)
    assert "sship.armour.length_scale" not in codes(result)

    imperial = sship_import.preview(build(imperial_fields({
        IDX_ARMOUR_SCALE: "0", IDX_HULL_SCALE: "1",
    })))
    belt = imperial["project"]["systems"]["armour"]["fixed"]["belt_main"]["facts"]
    assert belt["thickness_m"]["value"] == pytest.approx(0.1524)
    assert belt["length_m"]["value"] == pytest.approx(300 * FT_M)
    assert imperial["project"]["hull"]["beam_m"] == pytest.approx(50.0)
