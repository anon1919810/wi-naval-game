# -*- coding: utf-8 -*-
"""船体/干舷纯状态单元：原版 SpringSharp 3b3 船体页 + 干舷页的对照（实现自测）。

本文件只覆盖 ``tools/plimsoll/sps_hull.py`` 的公开接口 ``evaluate`` / ``apply_edit``。

对照方式：本文件里的期望值全部由下面的 longhand 算式（或用例内手算）得出，
没有调用被测模块。另取原生参考设计（``Plimsoll-SPS-parity-2026-10-17`` 的
``native-graph-third.json``）里少量判别量作为常量锚点，仅用于数值量级核对。

这是实现自测，不等于与原程序集的等价证明。所有数字都是经验/几何读数，
不涉及任何真实舰船。
"""
import copy
import math
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

import sps_hull as SH  # noqa: E402

FT = 0.3048  # MainForm.Con.feet2metres / FEET2METRES
TON = 35.0   # MainForm.TON (seawater cubic feet per long ton)


def to_ft(value_m):
    """Save page -> original internal unit for a length (metres -> feet)."""
    return value_m / FT


# --------------------------------------------------------------- shared inputs

LENGTH_PARAMS = (
    "length_waterline", "beam_moulded", "beam_at_bulges", "draught_normal",
    "freeboard_forecastle_fore", "freeboard_forecastle_aft",
    "freeboard_flat_deck_fore", "freeboard_flat_deck_aft",
    "freeboard_afterdeck_fore", "freeboard_afterdeck_aft",
    "freeboard_quarterdeck_fore", "freeboard_quarterdeck_aft",
    "freeboard_ram_length", "freeboard_length_stern",
)


def base(**over):
    """Metric hull page, values as saved on the original page (scale 1 = metres)."""
    params = {
        "ship_name": "Synthetic acceptance, not a historical ship",
        "country": "Country, punctuation. 保留",
        "ship_type": "Synthetic acceptance",
        "hull_scale": 1,
        "hull_year": 1910,
        "engine_year": 1905,
        "length_waterline": 180.0,
        "beam_moulded": 25.0,
        "beam_at_bulges": 26.0,
        "draught_normal": 8.0,
        "block_coefficient_normal": 0.55,
        "stern": 0,
        "bow": 0,
        "shafts": 2.0,
        "freeboard_forecastle_fore": 8.0,
        "freeboard_forecastle_aft": 6.0,
        "freeboard_flat_deck_fore": 6.0,
        "freeboard_flat_deck_aft": 5.0,
        "freeboard_afterdeck_fore": 5.0,
        "freeboard_afterdeck_aft": 4.0,
        "freeboard_quarterdeck_fore": 4.0,
        "freeboard_quarterdeck_aft": 4.0,
        "freeboard_forecastle_length": 20.5,
        "freeboard_flat_deck_length": 30.0,
        "freeboard_quarterdeck_length": 15.5,
        "freeboard_length_bow": 0.0,
        "freeboard_ram_length": 0.0,
        "freeboard_length_stern": 0.0,
        # other saved pages: this unit must carry them through untouched
        "gun1_scale": 0,
        "gun1_barrels": 12.0,
        "gun1_mount_type": 3,
        "armour_scale": 0,
        "armour_deck_thickness": 2.0,
        "torpedo1_scale": 0,
        "speed_max_kn": 27.0,
        "misc_weight_void": 50.0,
        "trim": "0",
        "reserved_padding_279": "keep me",
    }
    params.update(over)
    return params


def to_imperial(params):
    """Re-express one saved hull page in feet (scale 0) without changing the ship."""
    out = dict(params)
    for name in LENGTH_PARAMS:
        if out.get(name) is not None:
            out[name] = to_ft(out[name])
    out["hull_scale"] = 0
    return out


def edit(**over):
    state = {
        "length_driver": "waterline",
        "displacement_driver": "block",
        "depth_locked": False,
        "bulkhead_beam_mode": "follow_hull",
    }
    state.update(over)
    return state


def n2(value):
    """C# ``ToString("n2")`` on a float, read back with fpCheck."""
    from decimal import Decimal, ROUND_HALF_UP
    return float(Decimal(repr(float(value))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# ------------------------------------------------------- longhand expectations

_L = to_ft(180.0)
_B = to_ft(25.0)
_BB = to_ft(26.0)
_T = to_ft(8.0)
_CB = 0.55
_RATIO = _CB / (1.006 - 0.0056 * _CB ** -3.56)
_DISP = _L * _BB * _T * _CB / TON
_CO_SHARP = 0.4 * (_BB / _L * 6.0) ** (1.0 / 3.0) * math.sqrt(_CB / 0.52)
_CO_WP = 0.262 + 0.76 * _RATIO
_WP_AREA = _CO_WP * _L * _B
_WETTED = _L * _T * 1.7 + _DISP * TON / _T
_DRAUGHT_SIDE = ((1.006 - 0.0056 * _CB ** -3.56) * 2.0 - 1.0) * _T


def run(params=None, editing=None, **kw):
    return SH.evaluate(base() if params is None else params,
                       editing=edit() if editing is None else editing, **kw)


# --------------------------------------------------------------------- tests

def test_native_reference_full_state_reproduces_longhand_hull_and_freeboard():
    """One complete controlled original load; every reading checked against longhand."""
    result = run()
    assert result["method_version"] == "sps-3b3-hull-v1"
    assert result["status"] == "available"
    assert result["diagnostics"] == []

    hull = result["hull"]
    assert set(hull) == set(SH.HULL_FIELDS)
    assert hull["length"] == pytest.approx(_L, rel=2e-9)
    assert hull["lengthOA"] == pytest.approx(_L, rel=2e-9)
    assert hull["lengthStem"] == pytest.approx(0.0, abs=1e-12)
    assert hull["beam"] == pytest.approx(_B, rel=2e-9)
    assert hull["beamBulges"] == pytest.approx(_BB, rel=2e-9)
    assert hull["draught"] == pytest.approx(_T, rel=2e-9)
    assert hull["block"] == pytest.approx(_CB, rel=2e-9)
    assert hull["displacement"] == pytest.approx(_DISP, rel=2e-9)
    assert hull["coSharp"] == pytest.approx(_CO_SHARP, rel=2e-9)
    assert hull["coWaterPlane"] == pytest.approx(_CO_WP, rel=2e-9)
    assert hull["lengthBeam"] == pytest.approx(_L / _BB, rel=2e-9)
    assert hull["lengthEffect"] == pytest.approx(_L, rel=2e-9)
    assert hull["speedNatural"] == pytest.approx(math.sqrt(_L), rel=2e-9)
    assert hull["waterplaneArea"] == pytest.approx(_WP_AREA, rel=2e-9)
    assert hull["wettedSurface"] == pytest.approx(_WETTED, rel=2e-9)
    assert hull["draughtSide"] == pytest.approx(_DRAUGHT_SIDE, rel=2e-9)
    assert hull["crewMax"] == int(_DISP ** 0.75 * 0.65)
    assert hull["crewMin"] == int(int(_DISP ** 0.75 * 0.65) * 0.7692)
    assert hull["dateHull"] == 1910 and hull["dateEngine"] == 1905
    assert hull["dateAdjFloat"] == pytest.approx(1.0, rel=1e-12)

    # anchors recorded from the native full state (float32 source)
    assert hull["displacement"] == pytest.approx(20777.13, rel=2e-5)
    assert hull["coSharp"] == pytest.approx(0.392214537, rel=2e-4)
    assert hull["coWaterPlane"] == pytest.approx(0.697890341, rel=2e-6)
    assert hull["waterplaneArea"] == pytest.approx(33804.13, rel=2e-6)
    assert hull["wettedSurface"] == pytest.approx(54056.3555, rel=2e-6)
    assert hull["speedNatural"] == pytest.approx(24.3012581, rel=2e-6)
    assert hull["crewMax"] == 1124 and hull["crewMin"] == 864

    fc_for, fc_aft = to_ft(8.0), to_ft(6.0)
    fd_for, fd_aft = to_ft(6.0), to_ft(5.0)
    ad_for, ad_aft = to_ft(5.0), to_ft(4.0)
    qd_for, qd_aft = to_ft(4.0), to_ft(4.0)
    fc_len, fd_len, qd_len = 0.205, 0.30, 0.155
    ad_len = 1.0 - fc_len - fd_len - qd_len
    free_fc = fc_aft + (fc_for - fc_aft) * 0.4
    free_fd = (fd_for + fd_aft) / 2.0
    free_ad = (ad_for + ad_aft) / 2.0
    free_qd = (qd_for + qd_aft) / 2.0
    freeboard = free_fc * fc_len + free_fd * fd_len + free_ad * ad_len + free_qd * qd_len

    free = result["freeboard"]
    assert set(free) == set(SH.FREEBOARD_FIELDS)
    for name, expected in (("freeFCFor", fc_for), ("freeFCAft", fc_aft),
                           ("freeFDFor", fd_for), ("freeFDAft", fd_aft),
                           ("freeADFor", ad_for), ("freeADAft", ad_aft),
                           ("freeQDFor", qd_for), ("freeQDAft", qd_aft)):
        assert free[name] == pytest.approx(expected, rel=2e-9), name
    assert free["fcLength"] == pytest.approx(fc_len, rel=2e-9)
    assert free["fdLength"] == pytest.approx(fd_len, rel=2e-9)
    assert free["qdLength"] == pytest.approx(qd_len, rel=2e-9)
    assert free["adLength"] == pytest.approx(ad_len, rel=2e-9)
    assert free["freeFC"] == pytest.approx(free_fc, rel=2e-9)
    assert free["freeFD"] == pytest.approx(free_fd, rel=2e-9)
    assert free["freeAD"] == pytest.approx(free_ad, rel=2e-9)
    assert free["freeQD"] == pytest.approx(free_qd, rel=2e-9)
    assert free["freeboard"] == pytest.approx(freeboard, rel=2e-9)
    assert free["freeDistributed"] == pytest.approx(
        (free_fd * fd_len + free_ad * ad_len) / (fd_len + ad_len), rel=2e-9)
    assert free["freeboardCap"] == pytest.approx(freeboard, rel=2e-9)
    assert free["lengthBow"] == 0.0 and free["lengthRam"] == 0.0 and free["lengthStern"] == 0.0

    # native anchors
    assert free["freeboard"] == pytest.approx(17.0406837, rel=2e-6)
    assert free["freeDistributed"] == pytest.approx(16.3016739, rel=2e-6)
    assert free["freeFC"] == pytest.approx(22.3097115, rel=2e-6)
    assert free["adLength"] == pytest.approx(0.34, rel=2e-9)

    # other pages survive verbatim
    for key, value in base().items():
        if key in SH.CONSUMED_PARAMETERS:
            continue
        assert result["parameters"][key] == value, key


def test_bulges_and_moulded_beam_stay_separate():
    """waterplaneArea uses moulded beam, coSharp/lengthBeam/lengthEffect use bulges."""
    wide = run(base(beam_at_bulges=30.0))
    assert wide["hull"]["coSharp"] != pytest.approx(_CO_SHARP, rel=1e-6)
    assert wide["hull"]["lengthBeam"] == pytest.approx(_L / to_ft(30.0), rel=2e-9)
    assert wide["hull"]["waterplaneArea"] == pytest.approx(_WP_AREA, rel=2e-9)

    fat = run(base(beam_moulded=30.0))
    assert fat["hull"]["waterplaneArea"] == pytest.approx(_CO_WP * _L * to_ft(30.0), rel=2e-9)
    assert fat["hull"]["coSharp"] == pytest.approx(_CO_SHARP, rel=2e-9)
    assert fat["hull"]["lengthBeam"] == pytest.approx(_L / _BB, rel=2e-9)


def test_freeboard_profiles_are_three_distinct_shapes_and_segments_follow_source():
    """Captured freeboard is a .6aft+.4fore mix on FC and a plain mean elsewhere."""
    flush = base(**_endpoints(6.0))
    raised = base(**_endpoints(6.0, forecastle_fore=9.0, flat_deck_fore=9.0))
    low_fd = base(**_endpoints(6.0, flat_deck_aft=3.0))
    readings = {name: run(params)["freeboard"]["freeboard"]
                for name, params in (("flush", flush), ("raised", raised), ("low_fd", low_fd))}
    assert len({round(v, 6) for v in readings.values()}) == 3

    free = run(raised)["freeboard"]
    assert free["freeFC"] == pytest.approx(to_ft(6.0) + (to_ft(9.0) - to_ft(6.0)) * 0.4, rel=2e-9)
    assert free["freeFD"] == pytest.approx(
        (to_ft(9.0) + to_ft(6.0)) / 2.0, rel=2e-9)
    assert free["freeAD"] == pytest.approx(to_ft(6.0), rel=2e-9)
    assert free["freeQD"] == pytest.approx(to_ft(6.0), rel=2e-9)

    thin = run(low_fd)["freeboard"]
    assert thin["freeFD"] == pytest.approx((to_ft(6.0) + to_ft(3.0)) / 2.0, rel=2e-9)
    assert thin["freeAD"] == pytest.approx(to_ft(6.0), rel=2e-9)


def _endpoints(value_m, *, forecastle_fore=None, forecastle_aft=None, flat_deck_fore=None,
               flat_deck_aft=None, afterdeck_fore=None, afterdeck_aft=None,
               quarterdeck_fore=None, quarterdeck_aft=None):
    def pick(override):
        return value_m if override is None else override

    return {
        "freeboard_forecastle_fore": pick(forecastle_fore),
        "freeboard_forecastle_aft": pick(forecastle_aft),
        "freeboard_flat_deck_fore": pick(flat_deck_fore),
        "freeboard_flat_deck_aft": pick(flat_deck_aft),
        "freeboard_afterdeck_fore": pick(afterdeck_fore),
        "freeboard_afterdeck_aft": pick(afterdeck_aft),
        "freeboard_quarterdeck_fore": pick(quarterdeck_fore),
        "freeboard_quarterdeck_aft": pick(quarterdeck_aft),
    }


def test_block_and_displacement_drivers_are_reciprocal():
    """Sliding Cb drives displacement; typing displacement drives Cb back."""
    block_driven = run()
    displacement = block_driven["hull"]["displacement"]

    state = edit(displacement_driver="displacement", normal_displacement_lt=displacement)
    result = SH.evaluate(base(), editing=state)
    assert result["hull"]["displacement"] == pytest.approx(displacement, rel=1e-12)
    assert result["hull"]["block"] == pytest.approx(_CB, rel=1e-9)

    # explicit driver switch keeps the actual displacement, then editing Δ moves Cb
    switched = SH.apply_edit(base(), edit(), {"kind": "set_displacement_driver",
                                              "value": "displacement"})
    assert switched["editing"]["normal_displacement_lt"] == pytest.approx(displacement, rel=1e-9)
    doubled = SH.apply_edit(switched["parameters"], switched["editing"],
                            {"kind": "set_parameter", "name": "normal_displacement_lt",
                             "value": displacement * 2.0})
    after = SH.evaluate(doubled["parameters"], editing=doubled["editing"])
    assert after["hull"]["displacement"] == pytest.approx(displacement * 2.0, rel=1e-9)
    assert after["hull"]["block"] == pytest.approx(_CB * 2.0, rel=1e-9)

    # the Cb slider field selects block driving again and recomputes Δ
    back = SH.apply_edit(doubled["parameters"], doubled["editing"],
                         {"kind": "set_parameter", "name": "block_coefficient_normal",
                          "value": 0.55})
    assert back["editing"]["displacement_driver"] == "block"
    assert SH.evaluate(back["parameters"], editing=back["editing"])["hull"]["displacement"] == \
        pytest.approx(_DISP, rel=1e-9)


def test_length_driver_bow_angle_ram_and_stern_extension():
    """lengthStem uses the FC fore freeboard; bow angle is an angle, not a length."""
    stem = to_ft(8.0) * math.tan(20.0 * math.pi / 180.0)

    angled = run(base(freeboard_length_bow=20.0, bow=1))
    assert angled["hull"]["length"] == pytest.approx(_L, rel=2e-9)
    assert angled["hull"]["lengthStem"] == pytest.approx(stem, rel=2e-9)
    assert angled["hull"]["lengthOA"] == pytest.approx(_L + stem, rel=2e-9)
    assert angled["freeboard"]["lengthBow"] == 20.0

    ram = run(base(freeboard_length_bow=20.0, bow=3, freeboard_ram_length=10.0))
    assert ram["hull"]["lengthOA"] == pytest.approx(_L + max(stem, to_ft(10.0)), rel=2e-9)

    short_ram = run(base(freeboard_length_bow=20.0, bow=3, freeboard_ram_length=2.0))
    assert short_ram["hull"]["lengthOA"] == pytest.approx(_L + stem, rel=2e-9)

    stern = run(base(freeboard_length_stern=15.0))
    assert stern["freeboard"]["lengthStern"] == pytest.approx(to_ft(15.0), rel=2e-9)
    assert stern["hull"]["lengthOA"] == pytest.approx(_L + to_ft(15.0), rel=2e-9)

    # overall length drives LWL, and switching driver keeps the actual ship
    loa = _L + stem
    metric_loa = loa * FT
    overall = SH.evaluate(base(freeboard_length_bow=20.0, bow=1),
                          editing=edit(length_driver="overall", overall_length=metric_loa))
    assert overall["hull"]["lengthOA"] == pytest.approx(loa, rel=2e-9)
    assert overall["hull"]["length"] == pytest.approx(_L, rel=2e-9)
    assert overall["parameters"]["length_waterline"] == pytest.approx(180.0, rel=2e-9)

    switched = SH.apply_edit(base(), edit(), {"kind": "set_length_driver", "value": "overall"})
    assert switched["editing"]["length_driver"] == "overall"
    assert switched["editing"]["overall_length"] == pytest.approx(180.0, rel=1e-9)
    assert SH.evaluate(switched["parameters"], editing=switched["editing"])["hull"]["length"] == \
        pytest.approx(_L, rel=2e-9)


def test_depth_lock_recomputes_from_snapshot_and_unlock_keeps_freeboard():
    locked = SH.apply_edit(base(), edit(), {"kind": "set_depth_lock", "value": True})
    depths = locked["editing"]["depths"]
    assert len(depths) == 8
    assert depths["freeFCFor"] == pytest.approx(_T + to_ft(8.0), rel=2e-9)

    deeper = SH.apply_edit(locked["parameters"], locked["editing"],
                           {"kind": "set_parameter", "name": "draught_normal", "value": 10.0})
    result = SH.evaluate(deeper["parameters"], editing=deeper["editing"])
    assert result["hull"]["draught"] == pytest.approx(to_ft(10.0), rel=2e-9)
    for field, depth in depths.items():
        assert result["freeboard"][field] == pytest.approx(depth - to_ft(10.0), rel=2e-9), field
    # the snapshot itself is not rewritten by a draught change
    assert deeper["editing"]["depths"] == depths
    assert deeper["parameters"]["freeboard_forecastle_fore"] == pytest.approx(6.0, rel=2e-9)

    unlocked = SH.apply_edit(deeper["parameters"], deeper["editing"],
                            {"kind": "set_depth_lock", "value": False})
    assert unlocked["editing"]["depth_locked"] is False
    after_unlock = SH.evaluate(unlocked["parameters"], editing=unlocked["editing"])
    assert after_unlock["freeboard"]["freeFCFor"] == pytest.approx(to_ft(6.0), rel=2e-9)


def test_hull_scale_round_trip_converts_lengths_but_not_the_bow_angle():
    params = base(freeboard_length_bow=20.0, bow=1)
    down = SH.apply_edit(params, edit(), {"kind": "set_scale", "page": "hull", "value": 0})
    assert down["parameters"]["hull_scale"] == 0
    assert down["parameters"]["length_waterline"] == pytest.approx(_L, rel=2e-9)
    assert down["parameters"]["draught_normal"] == pytest.approx(_T, rel=2e-9)
    assert down["parameters"]["freeboard_forecastle_fore"] == pytest.approx(to_ft(8.0), rel=2e-9)
    assert down["parameters"]["freeboard_flat_deck_length"] == 30.0  # a percentage
    assert down["parameters"]["freeboard_length_bow"] == 20.0       # an angle
    assert down["parameters"]["block_coefficient_normal"] == 0.55
    assert down["parameters"]["gun1_scale"] == 0
    assert down["parameters"]["armour_deck_thickness"] == 2.0

    back = SH.apply_edit(down["parameters"], down["editing"],
                        {"kind": "set_scale", "page": "hull", "value": 1})
    for name in LENGTH_PARAMS:
        assert back["parameters"][name] == pytest.approx(params[name], rel=1e-9), name
    assert back["parameters"]["freeboard_length_bow"] == 20.0
    first = SH.evaluate(params, editing=edit())
    again = SH.evaluate(back["parameters"], editing=back["editing"])
    assert again["hull"]["lengthOA"] == pytest.approx(first["hull"]["lengthOA"], rel=1e-9)
    assert again["hull"]["beamBulges"] == pytest.approx(first["hull"]["beamBulges"], rel=1e-9)

    # the other saved pages keep both their selector and their values
    other = SH.apply_edit(base(**{"gun2_scale": 1, "torpedo1_size": 21.0}), edit(),
                          {"kind": "set_scale", "page": "hull", "value": 0})
    assert other["parameters"]["gun2_scale"] == 1
    assert other["parameters"]["torpedo1_size"] == 21.0


def test_freeboard_presets_replay_the_two_source_buttons_at_ui_precision():
    length_ft = _L
    est_bow = 1.1 * math.sqrt(length_ft)  # dateAdjFloat == 1 for 1910
    est_other_flush = 0.7 * math.sqrt(length_ft)
    est_other_raised = 0.9 * math.sqrt(length_ft)

    imperial = to_imperial(base())
    flush = SH.apply_edit(imperial, edit(), {"kind": "freeboard_preset", "value": "flush"})
    free = SH.evaluate(flush["parameters"], editing=flush["editing"])["freeboard"]
    assert free["freeFCFor"] == pytest.approx(round(est_bow, 2), rel=2e-9)
    mean = round((est_bow + est_other_flush) / 2.0, 2)
    assert free["freeFCAft"] == pytest.approx(mean, rel=2e-9)
    assert free["freeFDFor"] == pytest.approx(mean, rel=2e-9)
    for field in ("freeFDAft", "freeADFor", "freeADAft", "freeQDFor", "freeQDAft"):
        assert free[field] == pytest.approx(round(est_other_flush, 2), rel=2e-9), field

    raised = SH.apply_edit(imperial, edit(), {"kind": "freeboard_preset", "value": "raised"})
    free = SH.evaluate(raised["parameters"], editing=raised["editing"])["freeboard"]
    assert free["freeFCFor"] == pytest.approx(round(est_bow, 2), rel=2e-9)
    for field in ("freeFCAft", "freeFDFor", "freeFDAft"):
        assert free[field] == pytest.approx(round(est_other_raised, 2), rel=2e-9), field
    half = round(est_other_raised / 2.0, 2)
    for field in ("freeADFor", "freeADAft", "freeQDFor", "freeQDAft"):
        assert free[field] == pytest.approx(half, rel=2e-9), field

    # the source round-trips the unrounded estimate through the page-unit text
    metric = SH.apply_edit(base(), edit(), {"kind": "freeboard_preset", "value": "flush"})
    assert metric["parameters"]["freeboard_forecastle_fore"] == pytest.approx(8.15, rel=2e-9)
    assert metric["parameters"]["freeboard_forecastle_aft"] == pytest.approx(
        round((est_bow + est_other_flush) / 2.0 * FT, 2), rel=2e-9)


def test_zero_and_unknown_do_not_erase_independent_readings():
    zero = run(base(block_coefficient_normal=0.0))
    assert zero["status"] == "partial"
    assert zero["hull"]["displacement"] == 0.0
    assert zero["hull"]["coSharp"] == 0.0
    assert zero["hull"]["speedNatural"] == pytest.approx(math.sqrt(_L), rel=2e-9)
    assert zero["hull"]["waterplaneArea"] is None
    assert zero["hull"]["coWaterPlane"] is None
    assert zero["hull"]["wettedSurface"] == pytest.approx(_L * _T * 1.7, rel=2e-9)
    assert zero["hull"]["crewMax"] == 0 and zero["hull"]["crewMin"] == 0
    assert any(d["field"] == "coWaterPlane" for d in zero["diagnostics"])
    assert zero["freeboard"]["freeboard"] == pytest.approx(
        run()["freeboard"]["freeboard"], rel=2e-9)

    thin = base()
    thin["length_waterline"] = None
    thin["draught_normal"] = "not a number"
    unknown = run(thin)
    assert unknown["status"] == "partial"
    assert unknown["hull"]["length"] is None and unknown["hull"]["lengthOA"] is None
    assert unknown["hull"]["beam"] == pytest.approx(_B, rel=2e-9)
    assert unknown["hull"]["draughtSide"] is None
    assert unknown["hull"]["coSharp"] is None
    assert unknown["freeboard"]["freeboard"] == pytest.approx(
        run()["freeboard"]["freeboard"], rel=2e-9)
    severities = {d["severity"] for d in unknown["diagnostics"]}
    assert "error" in severities and severities <= {"error", "warning"}
    assert any(d["field"] == "draught_normal" and d["severity"] == "error"
               for d in unknown["diagnostics"])
    assert any(d["field"] == "length" for d in unknown["diagnostics"])
    assert "trim" in unknown["parameters"] and unknown["parameters"]["trim"] == "0"
    assert unknown["parameters"]["reserved_padding_279"] == "keep me"


def test_unknown_enum_and_shafts_branches_keep_independent_values():
    stern_two = run(base(stern=2))
    assert stern_two["hull"]["lengthEffect"] == pytest.approx(_BB / _CO_SHARP + _L, rel=2e-6)
    stern_one = run(base(stern=1))
    assert stern_one["hull"]["lengthEffect"] == pytest.approx(_BB * 0.5 / _CO_SHARP + _L, rel=2e-6)

    one_screw = run(base(shafts=1.0))
    assert one_screw["hull"]["coWaterPlane"] == pytest.approx(
        min(0.175 + 0.875 * _RATIO, 1.0), rel=2e-9)
    missing_screws = run(base(shafts=None))
    assert missing_screws["hull"]["coWaterPlane"] is None
    assert missing_screws["hull"]["waterplaneArea"] is None
    assert missing_screws["hull"]["wettedSurface"] == pytest.approx(_WETTED, rel=2e-9)
    assert missing_screws["hull"]["coSharp"] == pytest.approx(_CO_SHARP, rel=2e-9)

    # a thin block coefficient puts the source correction term out of the real domain
    thin_block = run(base(block_coefficient_normal=0.25))
    assert thin_block["hull"]["coWaterPlane"] is None
    assert thin_block["hull"]["coSharp"] == pytest.approx(
        0.4 * (_BB / _L * 6.0) ** (1.0 / 3.0) * math.sqrt(0.25 / 0.52), rel=2e-9)


def test_freeboard_cap_beam_branch_and_submerged_casemate():
    # freeboard below beam/3 with no casemate: unchanged
    assert run()["freeboard"]["freeboardCap"] == pytest.approx(
        run()["freeboard"]["freeboard"], rel=2e-9)

    # submerged casemate branch subtracts 6 ft, negative results are kept
    capped = run(base(**_endpoints(1.0)), submerged_casemate=True)
    assert capped["freeboard"]["freeboard"] < to_ft(25.0) / 3.0
    assert capped["freeboard"]["freeboardCap"] == pytest.approx(
        capped["freeboard"]["freeboard"] - 6.0, rel=2e-9)
    assert capped["freeboard"]["freeboardCap"] < 0.0
    assert any(d["code"] == "negative_freeboard_cap" and d["field"] == "freeboardCap"
               for d in capped["diagnostics"])
    with_casemate = SH.evaluate(base(**_endpoints(1.0)), submerged_casemate=False)
    assert with_casemate["freeboard"]["freeboardCap"] == pytest.approx(
        with_casemate["freeboard"]["freeboard"], rel=2e-9)

    # freeboard above beam/3: squared over the beam third
    tall = run(base(**_endpoints(40.0)))
    assert tall["freeboard"]["freeboard"] > _B / 3.0
    assert tall["freeboard"]["freeboardCap"] == pytest.approx(
        tall["freeboard"]["freeboard"] ** 2 / (_B / 3.0), rel=2e-9)


def test_ordinary_beam_edit_carries_bulges_and_follows_hull_bulkhead_beam():
    """HullControl.beamEnter: ordinary beam resets bulges (and the shared bulkhead beam).

    ArmourControl.bulkheadBeamBoxTextChanged only makes that lock permanent when the
    user actually focused the armour box, so the default is ``follow_hull``.
    """
    assert run()["editing"]["bulkhead_beam_mode"] == "follow_hull"

    start = to_imperial(base())
    stepped = SH.apply_edit(start, edit(), {"kind": "set_parameter",
                                            "name": "beam_moulded", "value": 84.0})
    assert stepped["parameters"]["beam_moulded"] == 84.0
    assert stepped["parameters"]["beam_at_bulges"] == 84.0        # not the old bulges
    assert stepped["parameters"]["armour_bulkhead_beam"] == 84.0
    assert stepped["editing"]["bulkhead_beam_mode"] == "follow_hull"

    # an explicit armour bulkhead beam edit is the source's focused-box case
    fixed = SH.apply_edit(stepped["parameters"], stepped["editing"],
                          {"kind": "set_parameter", "name": "armour_bulkhead_beam",
                           "value": 80.0})
    assert fixed["editing"]["bulkhead_beam_mode"] == "fixed"
    assert fixed["parameters"]["armour_bulkhead_beam"] == 80.0
    again = SH.apply_edit(fixed["parameters"], fixed["editing"],
                          {"kind": "set_parameter", "name": "beam_moulded", "value": 90.0})
    assert again["parameters"]["beam_at_bulges"] == 90.0          # bulges still follows
    assert again["parameters"]["armour_bulkhead_beam"] == 80.0    # the fixed beam holds

    # a bulges edit is its own field and never touches the bulkhead beam
    bulged = SH.apply_edit(again["parameters"], again["editing"],
                           {"kind": "set_parameter", "name": "beam_at_bulges", "value": 95.0})
    assert bulged["parameters"]["armour_bulkhead_beam"] == 80.0
    assert bulged["parameters"]["beam_moulded"] == 90.0
    assert bulged["parameters"]["beam_at_bulges"] == 95.0


def test_beam_edit_reproduces_the_source_armour_unit_quirk_verbatim():
    """beamEnter has ONE branch condition (``arm.scale.SelectedIndex == 1``) that picks
    the text unit for *both* coupled boxes, while each box is then re-read with its own
    page combo. The native reference itself ships hull_scale=1 with armour_scale=0, so
    the mixed-unit read is an original reachable state and is not corrected here.
    """
    beam_m = 30.001

    # both pages metric: n2 metre text, each box re-read in metres
    both_metric = SH.apply_edit(base(armour_scale=1), edit(),
                                {"kind": "set_parameter", "name": "beam_moulded",
                                 "value": beam_m})
    assert both_metric["parameters"]["beam_at_bulges"] == pytest.approx(n2(beam_m), rel=2e-9)
    assert both_metric["parameters"]["armour_bulkhead_beam"] == pytest.approx(
        n2(beam_m), rel=2e-9)
    assert not any(d["code"] == "source_quirk" for d in both_metric["diagnostics"])

    # the native-valid mixed state: the armour page picks a feet text, the bulges box
    # re-reads that number as metres. Both saved boxes hold the same written number, but
    # the two boxes are in different units, so the internal readings diverge: the bulges
    # value is read as metres while the bulkhead beam is read as feet.
    mixed = SH.apply_edit(base(), edit(), {"kind": "set_parameter",
                                           "name": "beam_moulded", "value": beam_m})
    text_ft = beam_m / FT                      # beam .ToString() -- armour page is feet
    assert mixed["parameters"]["beam_at_bulges"] == pytest.approx(text_ft, rel=2e-9)
    assert mixed["parameters"]["armour_bulkhead_beam"] == pytest.approx(text_ft, rel=2e-9)
    quirks = [d for d in mixed["diagnostics"] if d["code"] == "source_quirk"]
    assert len(quirks) == 1 and quirks[0]["severity"] == "warning"
    assert quirks[0]["field"] == "beam_at_bulges"
    assert "hull_scale=1" in quirks[0]["message"]
    assert "armour_scale=0" in quirks[0]["message"]

    # The coupled bulges quirk does not alter the newly entered moulded beam.
    reading = SH.evaluate(mixed["parameters"], editing=mixed["editing"])
    assert reading["hull"]["beamBulges"] == pytest.approx(text_ft / FT, rel=2e-9)
    assert reading["hull"]["beamBulges"] != pytest.approx(text_ft, rel=1e-5)
    assert reading["hull"]["beam"] == pytest.approx(beam_m / FT, rel=2e-9)
    assert reading["hull"]["waterplaneArea"] == pytest.approx(_CO_WP * _L * beam_m / FT, rel=2e-9)

    # both pages in feet: x.ToString(), exact
    feet = SH.apply_edit(to_imperial(base()), edit(),
                         {"kind": "set_parameter", "name": "beam_moulded", "value": 84.123})
    assert feet["parameters"]["beam_at_bulges"] == 84.123
    assert feet["parameters"]["armour_bulkhead_beam"] == 84.123
    assert not any(d["code"] == "source_quirk" for d in feet["diagnostics"])

    # the mirrored mix (hull feet, armour metric): the text is n2 metres, so the bulges
    # box reads a metre number as feet and the reading is off by the square of the ratio
    mirrored = SH.apply_edit(to_imperial(base(armour_scale=1)), edit(),
                             {"kind": "set_parameter", "name": "beam_moulded",
                              "value": 84.123})
    text_m = n2(84.123 * FT)
    assert mirrored["parameters"]["beam_at_bulges"] == pytest.approx(text_m, rel=2e-9)
    assert mirrored["parameters"]["armour_bulkhead_beam"] == pytest.approx(text_m, rel=2e-9)
    assert any(d["code"] == "source_quirk" for d in mirrored["diagnostics"])
    assert SH.evaluate(mirrored["parameters"], editing=mirrored["editing"])["hull"][
        "beamBulges"] == pytest.approx(text_m, rel=2e-9)


def test_unknown_bow_and_stern_stay_unknown_and_minus_one_is_a_saved_state():
    """No default is invented for a null enum: its dependants come back null with a
    field diagnostic. ``-1`` is the source's saved "nothing selected" state and simply
    falls through every equality test (it is not silently turned into 0 either).
    """
    unknown_stern = run(base(stern=None))
    assert unknown_stern["hull"]["lengthEffect"] is None
    assert unknown_stern["hull"]["coWaterPlane"] is None
    assert unknown_stern["hull"]["waterplaneArea"] is None
    assert unknown_stern["hull"]["length"] == pytest.approx(_L, rel=2e-9)      # independent
    assert unknown_stern["hull"]["speedNatural"] is None
    assert any(d["field"] == "lengthEffect" for d in unknown_stern["diagnostics"])
    assert any(d["field"] == "coWaterPlane" for d in unknown_stern["diagnostics"])

    fresh = run(base(stern=-1))         # native-default-full.json ships stern = -1
    assert fresh["status"] == "available"
    assert fresh["hull"]["lengthEffect"] == pytest.approx(_L, rel=2e-9)        # not 2, not 1
    assert fresh["hull"]["coWaterPlane"] == pytest.approx(_CO_WP, rel=2e-9)    # default branch

    # a bow that cannot be read leaves the ram-vs-stem ladder undecidable
    unknown_bow = run(base(bow=None, freeboard_length_bow=20.0, freeboard_ram_length=10.0))
    assert unknown_bow["hull"]["lengthOA"] is None
    assert unknown_bow["hull"]["length"] == pytest.approx(_L, rel=2e-9)
    # with no ram length the source's first branch is decided false, so LOA survives
    decided = run(base(bow=None, freeboard_length_bow=20.0))
    assert decided["hull"]["lengthOA"] == pytest.approx(
        _L + to_ft(8.0) * math.tan(20.0 * math.pi / 180.0), rel=2e-9)

    # an out-of-range index is bad data, not a fourth selection
    bad_index = run(base(stern=9))
    assert bad_index["hull"]["coWaterPlane"] is None
    assert any(d["field"] == "stern" and d["severity"] == "error"
               for d in bad_index["diagnostics"])


def test_depth_locked_endpoint_edit_keeps_the_snapshot_and_is_overwritten():
    """Original event order: the 8 depths are written only by depthLockBtnClick's lock
    case, and the following draughtCalc re-derives each endpoint from the snapshot. So a
    locked FC/QD edit is overwritten by depth - T and the snapshot is left alone.
    """
    locked = SH.apply_edit(base(), edit(), {"kind": "set_depth_lock", "value": True})
    snapshot = copy.deepcopy(locked["editing"]["depths"])
    depth_fc_for = snapshot["freeFCFor"]

    edited = SH.apply_edit(locked["parameters"], locked["editing"],
                           {"kind": "set_parameter",
                            "name": "freeboard_forecastle_fore", "value": 20.0})
    assert edited["editing"]["depths"] == snapshot                  # snapshot untouched
    assert edited["parameters"]["freeboard_forecastle_fore"] == pytest.approx(
        (depth_fc_for - _T) * FT, rel=2e-9)                         # depth - T, in metres
    result = SH.evaluate(edited["parameters"], editing=edited["editing"])
    assert result["freeboard"]["freeFCFor"] == pytest.approx(depth_fc_for - _T, rel=2e-9)
    assert result["freeboard"]["freeFCFor"] != pytest.approx(to_ft(20.0), rel=1e-6)

    # the FD/AD boxes are disabled while locked, so their edits are refused outright
    refused = SH.apply_edit(locked["parameters"], locked["editing"],
                            {"kind": "set_parameter",
                             "name": "freeboard_flat_deck_aft", "value": 1.0})
    assert refused["parameters"]["freeboard_flat_deck_aft"] == \
        locked["parameters"]["freeboard_flat_deck_aft"]
    assert refused["editing"]["depths"] == snapshot
    assert any(d["code"] == "depth_locked_endpoint" and d["severity"] == "warning"
               for d in refused["diagnostics"])

    # the preset writes boxes too, so while locked the snapshot wins over it
    preset = SH.apply_edit(locked["parameters"], locked["editing"],
                           {"kind": "freeboard_preset", "value": "raised"})
    assert preset["editing"]["depths"] == snapshot
    assert any(d["code"] == "depth_locked_preset" for d in preset["diagnostics"])
    assert SH.evaluate(preset["parameters"], editing=preset["editing"])["freeboard"][
        "freeFCFor"] == pytest.approx(depth_fc_for - _T, rel=2e-9)


def test_score_and_scale_edits_leave_unknown_editing_keys_alone():
    state = edit(length_driver="overall", overall_length=180.0, engine_notes="kept")
    result = SH.evaluate(base(), editing=state)
    assert result["editing"]["engine_notes"] == "kept"
    assert result["editing"]["length_driver"] == "overall"
    # nothing invents the un-saved lock or the un-set displacement special
    assert "normal_displacement_lt" not in result["editing"]
    assert "depths" not in result["editing"]

    locked = SH.apply_edit(base(), state, {"kind": "set_depth_lock", "value": True})
    assert locked["editing"]["engine_notes"] == "kept"
    assert locked["editing"]["length_driver"] == "overall"
    scaled = SH.apply_edit(locked["parameters"], locked["editing"],
                           {"kind": "set_scale", "page": "hull", "value": 0})
    assert scaled["editing"]["engine_notes"] == "kept"
    assert scaled["editing"]["overall_length"] == pytest.approx(_L, rel=2e-9)


def test_leaving_unknown_editing_mode_falls_back_to_follow_hull():
    assert SH.evaluate(base(), editing=edit(bulkhead_beam_mode=None))["editing"][
        "bulkhead_beam_mode"] == "follow_hull"
    assert SH.evaluate(base(), editing={"bulkhead_beam_mode": 7})["editing"][
        "bulkhead_beam_mode"] == "follow_hull"
    assert SH.evaluate(base(), editing=edit(bulkhead_beam_mode="fixed"))["editing"][
        "bulkhead_beam_mode"] == "fixed"


def test_inputs_are_never_mutated_and_bad_input_is_structured():
    params = base()
    editing = edit()
    snapshot = copy.deepcopy(params), copy.deepcopy(editing)
    SH.evaluate(params, editing=editing)
    assert (params, editing) == snapshot

    SH.apply_edit(params, editing, {"kind": "set_parameter", "name": "draught_normal",
                                    "value": 9.0})
    SH.apply_edit(params, editing, {"kind": "set_depth_lock", "value": True})
    SH.apply_edit(params, editing, {"kind": "freeboard_preset", "value": "flush"})
    assert (params, editing) == snapshot

    bad = run(base(block_coefficient_normal=True, beam_moulded="wide",
                   beam_at_bulges=float("nan"), draught_normal=float("inf")))
    assert bad["status"] == "partial"
    assert bad["hull"]["block"] is None
    assert bad["hull"]["beam"] is None
    assert bad["hull"]["beamBulges"] is None
    assert bad["hull"]["draught"] is None
    for diag in bad["diagnostics"]:
        assert set(diag) == {"code", "severity", "field", "message"}
        assert diag["severity"] in {"error", "warning"}

    # unknown numeric name, unknown kind, non-command: diagnostics, no exception
    rejected = SH.apply_edit(params, editing, {"kind": "set_parameter",
                                               "name": "gun1_barrels", "value": 12.0})
    assert rejected["parameters"] == params
    assert rejected["diagnostics"][0]["severity"] == "error"
    assert rejected["diagnostics"][0]["field"] == "gun1_barrels"
    unknown = SH.apply_edit(params, editing, {"kind": "set_parameter",
                                              "name": "not_a_field", "value": 1.0})
    assert unknown["parameters"] == params
    assert unknown["diagnostics"][0]["field"] == "not_a_field"
    assert SH.apply_edit(params, editing, {"kind": "no_such_command"})["parameters"] == params
    assert SH.apply_edit(params, editing, None)["parameters"] == params
    assert SH.apply_edit(params, editing, {"kind": "set_scale", "page": "guns",
                                           "value": 0})["parameters"] == params
    assert SH.evaluate(None)["status"] == "unavailable"
    assert SH.evaluate(None)["hull"]["length"] is None
    assert SH.evaluate(None)["diagnostics"][0]["severity"] == "error"


def test_an_absent_editing_state_is_an_empty_state_not_an_error():
    """``editing`` is optional: no upper-layer edits yet, so everything defaults."""
    result = SH.evaluate(base())
    assert result["status"] == "available"
    assert result["diagnostics"] == []
    assert result["editing"] == {"length_driver": "waterline",
                                 "displacement_driver": "block",
                                 "depth_locked": False,
                                 "bulkhead_beam_mode": "follow_hull"}
    assert result["hull"]["lengthOA"] == pytest.approx(_L, rel=2e-9)

    started = SH.apply_edit(base(), None, {"kind": "set_depth_lock", "value": True})
    assert started["editing"]["depth_locked"] is True
    assert len(started["editing"]["depths"]) == 8

    # a non-mapping editing state is still reported, not swallowed
    assert SH.evaluate(base(), editing="waterline")["diagnostics"][0]["field"] == "editing"
