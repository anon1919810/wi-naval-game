# -*- coding: utf-8 -*-
"""Contract checks for the proportional whole-battery mount allocation policy.

Written against the declared contract, not against a draft. The module under
test is a pure function: it reads no project, no ledger and no file, and it must
leave the caller's arguments untouched. These checks pin the pieces a reader
would otherwise have to trust:

* the documented sample divides ``841.3244781676505`` in the proportion of the
  two ``432.6811602005058`` weights and conserves the source total;
* uneven weights give the floating residual to the last positive row;
* a zero-weight row keeps a zero share, and a known zero source gives explicit
  zero allocations;
* an unknown source, an unknown weight, an empty row list, a positive source
  with a zero weight sum and any numeric overflow are **unavailable** with no
  partial records -- never an equal-share fallback;
* duplicate or missing identifiers and every wrong numeric type are refused
  structurally through :class:`AllocationError.diagnostics`;
* the result is finite JSON and keeps the source method and the product policy
  separate.
"""

import copy
from fractions import Fraction
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
from plimsoll import battery_mass_allocation as allocation  # noqa: E402

SAMPLE_SOURCE = 841.3244781676505
SAMPLE_WEIGHT = 432.6811602005058
SAMPLE_SHARE = 420.6622390838252


def rows(*triples):
    return [{"battery_id": battery_id, "target_id": target_id, "weight_t": weight_t}
            for battery_id, target_id, weight_t in triples]


# ------------------------------------------------------------- the sample

def test_the_documented_sample_divides_in_proportion_and_conserves_the_total():
    result = allocation.allocate(
        "main_layout", SAMPLE_SOURCE,
        rows(("main", "weapons.mounts", SAMPLE_WEIGHT),
             ("main_g2", "weapons.mounts2", SAMPLE_WEIGHT)),
        source="declared synthetic layout")
    assert result["status"] == "available"
    assert result["id"] == "main_layout"
    assert result["method_version"] == allocation.METHOD_VERSION
    first, second = result["records"]
    assert first["id"] == "main" and first["target_id"] == "weapons.mounts"
    assert first["weight_t"] == pytest.approx(SAMPLE_WEIGHT)
    assert first["allocated_mass_t"] == pytest.approx(SAMPLE_SHARE, rel=1e-12)
    assert second["allocated_mass_t"] == pytest.approx(SAMPLE_SHARE, rel=1e-12)
    assert first["share"] == pytest.approx(0.5)
    whole = first["allocated_mass_t"] + second["allocated_mass_t"]
    assert whole == pytest.approx(SAMPLE_SOURCE, rel=0, abs=1e-9)
    assert result["values"]["source_mounts_t"] == pytest.approx(SAMPLE_SOURCE)
    assert result["values"]["legacy_mounts_t"] == pytest.approx(2 * SAMPLE_WEIGHT)
    assert result["values"]["allocated_total_t"] == pytest.approx(SAMPLE_SOURCE)


# ------------------------------------------------------- residual / zero

def test_uneven_weights_conserve_the_total_with_the_residual_on_the_last_row():
    result = allocation.allocate("l", 1.0, rows(("a", "ta", 1.0), ("b", "tb", 2.0)))
    first, second = result["records"]
    assert first["allocated_mass_t"] == pytest.approx(1.0 / 3.0)
    assert second["allocated_mass_t"] == pytest.approx(2.0 / 3.0)
    assert first["allocated_mass_t"] < second["allocated_mass_t"]
    assert first["share"] == pytest.approx(1.0 / 3.0)
    assert second["share"] == pytest.approx(2.0 / 3.0)
    assert first["allocated_mass_t"] + second["allocated_mass_t"] == pytest.approx(
        1.0, rel=0, abs=1e-12)


def test_a_zero_weight_row_keeps_a_zero_share_and_the_positive_row_takes_all():
    result = allocation.allocate("l", 10.0, rows(("a", "ta", 0.0), ("b", "tb", 4.0)))
    first, second = result["records"]
    assert first["share"] == 0.0
    assert first["allocated_mass_t"] == 0.0
    assert second["share"] == 1.0
    assert second["allocated_mass_t"] == pytest.approx(10.0)


def test_a_known_zero_source_gives_explicit_zero_allocations():
    for first_weight, second_weight in ((0.0, 0.0), (3.0, 0.0), (3.0, 5.0)):
        result = allocation.allocate(
            "l", 0.0, rows(("a", "ta", first_weight), ("b", "tb", second_weight)))
        assert result["status"] == "available"
        assert result["values"]["allocated_total_t"] == 0.0
        assert [row["allocated_mass_t"] for row in result["records"]] == [0.0, 0.0]


# ----------------------------------------------------------- unavailable

def test_an_unknown_source_is_unavailable_with_no_records():
    result = allocation.allocate("l", None, rows(("a", "ta", 1.0), ("b", "tb", 2.0)))
    assert result["status"] == "unavailable"
    assert result["records"] == []
    assert result["values"]["allocated_total_t"] is None
    # The known row subtotal stays readable; it is never called an allocation.
    assert result["values"]["legacy_mounts_t"] == pytest.approx(3.0)


def test_an_unknown_row_weight_is_unavailable_with_no_records():
    result = allocation.allocate("l", 5.0, rows(("a", "ta", None), ("b", "tb", 2.0)))
    assert result["status"] == "unavailable"
    assert result["records"] == []
    assert result["values"]["legacy_mounts_t"] is None


def test_empty_rows_are_unavailable():
    result = allocation.allocate("l", 1.0, [])
    assert result["status"] == "unavailable"
    assert result["records"] == []


def test_a_positive_source_with_a_zero_weight_sum_is_unavailable():
    result = allocation.allocate("l", 5.0, rows(("a", "ta", 0.0), ("b", "tb", 0.0)))
    assert result["status"] == "unavailable"
    assert result["records"] == []
    assert result["values"]["allocated_total_t"] is None


# ------------------------------------------------- structural rejections

def test_duplicate_and_missing_identifiers_are_refused_structurally():
    with pytest.raises(allocation.AllocationError) as excinfo:
        allocation.allocate("l", 1.0, rows(("a", "ta", 1.0), ("a", "tb", 1.0)))
    assert excinfo.value.diagnostics[0]["severity"] == "error"
    assert excinfo.value.diagnostics[0]["blocking"] is True
    assert excinfo.value.diagnostics[0]["path"] == "$.rows[1].battery_id"
    with pytest.raises(allocation.AllocationError):
        allocation.allocate("l", 1.0, rows(("a", "t", 1.0), ("b", "t", 1.0)))
    with pytest.raises(allocation.AllocationError):
        allocation.allocate("l", 1.0, [{"battery_id": "a", "target_id": "", "weight_t": 1.0}])
    with pytest.raises(allocation.AllocationError):
        allocation.allocate("l", 1.0, [{"battery_id": "a", "weight_t": 1.0}])
    with pytest.raises(allocation.AllocationError):
        allocation.allocate("", 1.0, [])
    with pytest.raises(allocation.AllocationError):
        allocation.allocate("l", 1.0, rows(("a", "ta", 1.0), ("b", "tb", 1.0), ("c", "tc", 1.0)))


@pytest.mark.parametrize("value", [
    True, False, "1", Fraction(1, 2), -1.0, -0.0 - 1, float("inf"), float("-inf"),
    float("nan"), 10 ** 400,
])
def test_invalid_weights_are_refused_structurally(value):
    with pytest.raises(allocation.AllocationError) as excinfo:
        allocation.allocate("l", 1.0,
                            [{"battery_id": "a", "target_id": "ta", "weight_t": value}])
    diagnostic = excinfo.value.diagnostics[0]
    assert diagnostic["severity"] == "error"
    assert diagnostic["blocking"] is True
    assert diagnostic["path"] == "$.rows[0].weight_t"


@pytest.mark.parametrize("value", [
    True, "x", Fraction(1, 3), -1.0, float("inf"), float("nan"),
])
def test_invalid_source_totals_are_refused_structurally(value):
    with pytest.raises(allocation.AllocationError):
        allocation.allocate("l", value, rows(("a", "ta", 1.0)))


@pytest.mark.parametrize("value", [
    True, False, 0, 1.0, float("inf"), {"invalid": float("inf")}, [], ["x"], object(),
])
def test_a_nonstring_declared_source_is_refused_structurally(value):
    with pytest.raises(allocation.AllocationError) as excinfo:
        allocation.allocate("l", 1.0, rows(("a", "ta", 1.0)), source=value)
    diagnostic = excinfo.value.diagnostics[0]
    assert diagnostic["severity"] == "error"
    assert diagnostic["blocking"] is True
    assert diagnostic["path"] == "$.source"


def test_a_null_declared_source_is_allowed():
    result = allocation.allocate("l", 1.0, rows(("a", "ta", 1.0)), source=None)
    assert result["provenance"]["declared_source"] is None


# -------------------------------------------------------- overflow / purity

def test_a_huge_finite_overflow_is_unavailable_and_never_partial():
    result = allocation.allocate("l", 1e308, rows(("a", "ta", 1e308), ("b", "tb", 1e308)))
    assert result["status"] == "unavailable"
    assert result["records"] == []
    assert result["values"]["allocated_total_t"] is None


def test_large_but_finite_source_and_weights_allocate_by_the_ratio():
    # The avoidable product ``total x weight`` would be ``1e400``; the finite
    # shares are ``5e199`` each, so the ratio must be taken first.
    result = allocation.allocate("l", 1e200, rows(("a", "ta", 1e200), ("b", "tb", 1e200)))
    assert result["status"] == "available"
    first, second = result["records"]
    assert first["allocated_mass_t"] == pytest.approx(5e199, rel=1e-12)
    assert second["allocated_mass_t"] == pytest.approx(5e199, rel=1e-12)
    assert result["values"]["legacy_mounts_t"] == pytest.approx(2e200)
    assert first["allocated_mass_t"] + second["allocated_mass_t"] == pytest.approx(
        1e200, rel=1e-12)


def test_the_call_does_not_mutate_its_arguments():
    declared = rows(("a", "ta", 1.0), ("b", "tb", 2.0))
    before = copy.deepcopy(declared)
    source = 9.0
    allocation.allocate("l", source, declared, source="declared")
    assert declared == before
    assert source == 9.0


def test_the_result_is_finite_json_and_keeps_source_and_policy_separate():
    result = allocation.allocate(
        "l", SAMPLE_SOURCE,
        rows(("a", "ta", SAMPLE_WEIGHT), ("b", "tb", SAMPLE_WEIGHT)), source="declared")
    json.dumps(result, allow_nan=False)
    assert result["provenance"] == {
        "source_method_version": allocation.SOURCE_METHOD_VERSION,
        "allocation_policy": allocation.POLICY,
        "declared_source": "declared",
    }
    assert allocation.METHOD_VERSION == "plimsoll-battery-mount-allocation-v1"
    assert allocation.POLICY == "proportional-row-mounts-v1"
    assert allocation.SOURCE_METHOD_VERSION == "sps-3b3-battery-totals-v1"
