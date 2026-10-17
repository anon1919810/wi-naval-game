# -*- coding: utf-8 -*-
"""性能单元：原版 SpringSharp 3b3 性能页四个经验读数的纯数值对照。

只覆盖 tools/plimsoll/sps_performance.py 的公开接口 evaluate()：
- 手算锚值 recoil / flotation / shell / torpedo；
- 分支保持：stability>0、stability<=0、负 composite、room 两分支、主炮 0 与未知之别；
- 依赖隔离：单一缺项不抹掉独立读数；
- 结构化拒绝：错误根 / 类型 / bool 冒充数值 / 非有限 / 未知键；输入不被修改。

这是实现自测，不等于与原程序集的等价证明。
"""
import copy
import json
import math
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

import sps_performance as SP  # noqa: E402


def _recoil_inputs(**over):
    data = {
        "broadside_lb": 1000.0,
        "displacement_lt": 8000.0,
        "freeboard_distributed_ft": 10.0,
        "gun_super_factor": 1.5,
        "beam_bulges_ft": 60.0,
        "stability_adjusted": 2.0,
        "steadiness_adjusted": 50.0,
    }
    data.update(over)
    return data


def _flotation_inputs(**over):
    data = _recoil_inputs(
        composite_strength=1.0,
        use_capped_freeboard=True,
        freeboard_cap_ft=20.0,
        freeboard_distributed_ft=10.0,
        waterplane_sqft=700.0,
        displacement_lt=7000.0,
        stability_adjusted=1.0,
        room_float=1.0,
        date_float=1.0,
    )
    data.update(over)
    return data


def _torpedo_inputs(**over):
    data = _flotation_inputs(
        beam_bulges_ft=75.0,
        first_gun_calibre_in=8.0,
        hull_length_ft=400.0,
        draught_ft=20.0,
        bulkhead_thickness_in=6.0,
        bulkhead_length_ft=100.0,
        bulkhead_height_ft=20.0,
        space_hull_fraction=0.0,
        first_torpedo_weapon_weight_lt=0.0,
        first_torpedo_count=0,
        first_torpedo_diameter_in=20.0,
    )
    data.update(over)
    return data


def _codes(result):
    return [d["code"] for d in result["diagnostics"]]


# --- recoil：手算 + 分支 ---------------------------------------------------

def test_recoil_hand_computed_value():
    # base = (1000/8000)*10*1.5/60 = 0.03125
    # inner = (8000^(1/3)/60*3)^2 = 1.0 ; base*1.0*7 = 0.21875
    # stability=2>0 且 steadiness=50 -> denom = 2*((50-50)/150+1) = 2 -> 0.109375
    out = SP.evaluate(_recoil_inputs())
    assert out["values"]["recoil_index"] == pytest.approx(0.109375, rel=1e-12)


def test_recoil_zero_and_negative_stability_skip_division():
    # 已知 0 / 负都不满足 >0，源式不做除法；此时 steadiness 无贡献，可以缺省。
    data = _recoil_inputs(stability_adjusted=0.0)
    del data["steadiness_adjusted"]
    assert SP.evaluate(data)["values"]["recoil_index"] == pytest.approx(0.21875, rel=1e-12)

    neg = _recoil_inputs(stability_adjusted=-3.0)
    del neg["steadiness_adjusted"]
    assert SP.evaluate(neg)["values"]["recoil_index"] == pytest.approx(0.21875, rel=1e-12)


def test_recoil_unknown_stability_is_undetermined():
    data = _recoil_inputs()
    del data["stability_adjusted"]
    out = SP.evaluate(data)
    assert out["values"]["recoil_index"] is None
    assert "undetermined_branch" in _codes(out)


# --- flotation：room 两分支 / 负 composite ---------------------------------

def test_flotation_room_branches_square_vs_linear():
    # 基础 = (10*700/35 + 7000)/2 = 3600（stability=1 走四次方=1，composite=1 不缩放）
    square = _flotation_inputs(use_capped_freeboard=False, room_float=2.0)
    assert SP.evaluate(square)["values"]["flotation_lb"] == pytest.approx(900.0, rel=1e-12)

    linear = _flotation_inputs(use_capped_freeboard=False, room_float=0.5)
    assert SP.evaluate(linear)["values"]["flotation_lb"] == pytest.approx(7200.0, rel=1e-12)


def test_flotation_capped_freeboard_branch_and_date():
    # 基础 = (20*700/35 + 7000)/2 = 3700，date=1
    out = SP.evaluate(_flotation_inputs())
    assert out["values"]["flotation_lb"] == pytest.approx(3700.0, rel=1e-12)


def test_flotation_negative_composite_zero_base_then_room_and_date():
    # 负 composite：基础 0，且不再读 capped/freeboard/waterplane/displacement。
    data = {"composite_strength": -1.0, "room_float": 2.0, "date_float": 3.0}
    out = SP.evaluate(data)
    assert out["values"]["flotation_lb"] == pytest.approx(0.0, abs=0.0)
    # 负 composite 分支不需要 stability；recoil 因缺 stability 而不可用。
    assert out["values"]["recoil_index"] is None


# --- shell：主炮 0 的 6in 基准 与 未知之别 --------------------------------

def test_shell_hits_explicit_zero_calibre_uses_six_inch_reference():
    # flotation=3700, date=1 -> 6^3/2 = 108 -> 3700/108
    out = SP.evaluate(_flotation_inputs(first_gun_calibre_in=0.0))
    assert out["values"]["shell_reference_calibre_in"] == pytest.approx(6.0)
    assert out["values"]["shell_hits"] == pytest.approx(3700.0 / 108.0, rel=1e-12)


def test_shell_hits_positive_calibre_uses_own_reference():
    out = SP.evaluate(_flotation_inputs(first_gun_calibre_in=5.0))
    assert out["values"]["shell_reference_calibre_in"] == pytest.approx(5.0)
    assert out["values"]["shell_hits"] == pytest.approx(3700.0 / 62.5, rel=1e-12)


def test_shell_hits_unknown_calibre_is_not_treated_as_zero():
    data = _flotation_inputs()
    assert "first_gun_calibre_in" not in data
    out = SP.evaluate(data)
    assert out["values"]["shell_hits"] is None
    assert out["values"]["shell_reference_calibre_in"] is None
    # flotation 与主炮无关，仍应独立可得。
    assert out["values"]["flotation_lb"] == pytest.approx(3700.0, rel=1e-12)


# --- torpedo：基准重量 / 缺直径不阻断 / 依赖隔离 --------------------------

def _torpedo_base():
    return SP.evaluate(_torpedo_inputs())["values"]["torpedo_hits"]


def test_torpedo_baseline_and_weight_scaling():
    base = _torpedo_base()
    assert base == pytest.approx(1.586715005092082, rel=1e-12)

    scaled = SP.evaluate(_torpedo_inputs(
        first_torpedo_weapon_weight_lt=6.0, first_torpedo_count=2,
    ))["values"]["torpedo_hits"]
    assert scaled == pytest.approx(base * (1.313 / (6.0 / 2.0)), rel=1e-12)


def test_torpedo_unknown_weight_is_undetermined_not_baseline():
    data = _torpedo_inputs()
    del data["first_torpedo_weapon_weight_lt"]
    out = SP.evaluate(data)
    # 未知弹重 -> 源式 >0 分支无法判定，穿透读数为未知，不臆造 20in 基准。
    assert out["values"]["torpedo_hits"] is None
    assert out["values"]["torpedo_reference_diameter_in"] is None
    assert "undetermined_branch" in _codes(out)
    # 独立读数不受影响。
    assert out["values"]["recoil_index"] is not None
    assert out["values"]["flotation_lb"] is not None
    assert out["values"]["shell_hits"] is not None


def test_torpedo_known_nonpositive_weight_takes_baseline():
    # 只有显式已知的非正弹重才走源式 else 的 20in 基准分支。
    for weight in (0.0, -4.0):
        out = SP.evaluate(_torpedo_inputs(first_torpedo_weapon_weight_lt=weight))
        assert out["values"]["torpedo_hits"] == pytest.approx(_torpedo_base(), rel=1e-12)
        assert out["values"]["torpedo_reference_diameter_in"] == pytest.approx(20.0)


def test_torpedo_positive_weight_without_usable_count_is_unknown():
    # 正弹重必须有可用的正 count；count=0 时不可算，也不回退基准。
    out = SP.evaluate(_torpedo_inputs(
        first_torpedo_weapon_weight_lt=6.0, first_torpedo_count=0,
        first_torpedo_diameter_in=21.0,
    ))
    assert out["values"]["torpedo_hits"] is None
    # 正弹重仍按其声明口径标注，而不是偷偷变成 20in。
    assert out["values"]["torpedo_reference_diameter_in"] == pytest.approx(21.0)
    assert "invalid_value" in _codes(out)

    missing = _torpedo_inputs(first_torpedo_weapon_weight_lt=6.0)
    del missing["first_torpedo_count"]
    out2 = SP.evaluate(missing)
    assert out2["values"]["torpedo_hits"] is None
    assert "missing_dependency" in _codes(out2)


def test_torpedo_missing_diameter_does_not_block_hits():
    data = _torpedo_inputs(first_torpedo_weapon_weight_lt=6.0, first_torpedo_count=2)
    del data["first_torpedo_diameter_in"]
    out = SP.evaluate(data)
    assert out["values"]["torpedo_hits"] is not None
    assert out["values"]["torpedo_reference_diameter_in"] is None


def test_missing_torpedo_dependency_does_not_erase_other_readings():
    data = _torpedo_inputs()
    del data["bulkhead_length_ft"]
    out = SP.evaluate(data)
    assert out["values"]["torpedo_hits"] is None
    assert out["values"]["recoil_index"] is not None
    assert out["values"]["flotation_lb"] is not None
    assert out["values"]["shell_hits"] is not None
    assert out["status"] == "partial"


# --- 结构化拒绝 ------------------------------------------------------------

def test_wrong_root_type_is_structured_not_raised():
    out = SP.evaluate("not a mapping")
    assert out["status"] == "unavailable"
    assert all(v is None for v in out["values"].values())
    assert "invalid_root_type" in _codes(out)


def test_unknown_key_is_rejected():
    data = _recoil_inputs()
    data["displacement_ton"] = 8000.0
    out = SP.evaluate(data)
    assert out["status"] == "unavailable"
    assert "unknown_key" in _codes(out)


def test_bool_and_string_masquerading_as_number_are_rejected():
    out = SP.evaluate(_recoil_inputs(broadside_lb=True))
    assert out["values"]["recoil_index"] is None
    assert "invalid_type" in _codes(out)

    out2 = SP.evaluate(_recoil_inputs(broadside_lb="1000"))
    assert out2["values"]["recoil_index"] is None
    assert "invalid_type" in _codes(out2)


def test_non_finite_values_are_rejected():
    for bad in (float("inf"), float("-inf"), float("nan")):
        out = SP.evaluate(_recoil_inputs(displacement_lt=bad))
        assert out["values"]["recoil_index"] is None
        assert "non_finite" in _codes(out)


def test_huge_numeric_input_is_rejected_without_raw_overflow():
    # float(10**1000) 会抛 OverflowError；必须结构化拒绝而不是原始异常。
    out = SP.evaluate({"broadside_lb": 10 ** 1000})
    assert out["status"] == "unavailable"
    assert "non_finite" in _codes(out)


def test_huge_torpedo_count_is_rejected_structurally():
    out = SP.evaluate(_torpedo_inputs(
        first_torpedo_weapon_weight_lt=6.0, first_torpedo_count=10 ** 1000,
    ))
    assert out["values"]["torpedo_hits"] is None
    assert "out_of_range" in _codes(out)


def test_zero_denominator_is_structured():
    out = SP.evaluate(_recoil_inputs(displacement_lt=0.0))
    assert out["values"]["recoil_index"] is None
    assert "zero_denominator" in _codes(out)


# --- 形状 / 状态 / 输入不变 ------------------------------------------------

def test_output_shape_and_available_status():
    out = SP.evaluate(_torpedo_inputs(
        first_torpedo_weapon_weight_lt=6.0, first_torpedo_count=2,
        first_torpedo_diameter_in=21.0,
    ))
    assert out["method_version"] == SP.METHOD_VERSION == "sps-3b3-performance-v1"
    assert set(out["values"]) == {
        "recoil_index", "flotation_lb", "shell_hits", "torpedo_hits",
        "shell_reference_calibre_in", "torpedo_reference_diameter_in",
    }
    assert out["status"] == "available"
    assert all(v is not None for v in out["values"].values())
    assert out["provenance"]
    # 有限 JSON：不夹紧、不四舍五入，直接可序列化。
    json.dumps(out, allow_nan=False)


def test_everything_unknown_is_unavailable():
    out = SP.evaluate({})
    assert out["status"] == "unavailable"
    assert all(v is None for v in out["values"].values())
    assert out["diagnostics"]


def test_inputs_are_not_mutated():
    data = _torpedo_inputs(first_torpedo_weapon_weight_lt=6.0, first_torpedo_count=2)
    before = copy.deepcopy(data)
    SP.evaluate(data)
    assert data == before


def test_negative_finite_reading_is_kept_with_warning():
    # 合法源状态下的负读数应保留并告警，不被夹紧成 0。
    out = SP.evaluate(_flotation_inputs(
        composite_strength=1.0, room_float=-2.0, use_capped_freeboard=False,
    ))
    assert out["values"]["flotation_lb"] == pytest.approx(-1800.0, rel=1e-12)
    assert "negative_result" in _codes(out)
