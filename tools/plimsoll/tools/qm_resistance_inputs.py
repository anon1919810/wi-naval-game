"""Queen Mary case adapter: one normal-loading basis shared by both generators.

Ship-specific source selection belongs here, outside the generic solver.
"""
import json
from pathlib import Path

import hull as H
import resistance as R

CASES = Path(__file__).resolve().parents[1] / "cases"


def read_case(name):
    with (CASES / name).open(encoding="utf-8") as stream:
        return json.load(stream)


def build_normal_basis(hull, assumptions):
    L = float(hull["lwl_m"])
    B = float(hull["beam_m"])
    T = float(hull["draught_normal_m"])
    volume = float(hull["displacement_normal_t"]) / (R.RHO_SEA / 1000.)
    cb = volume / (L * B * T)
    cm = float(assumptions["cm"])
    wet = H.wetted_surface_parametric(dict(hull, block_coeff=cb))
    sources = dict(hull.get("sources", {}))
    sources.update({
        "cb": "normal displacement / (rho * Lwl * B * T); no rounded Cb reuse",
        "cp": "Cb / Cm; Cm is an assumption, not a measured Queen Mary section",
        "cm": assumptions.get("cm_source", "assumed"),
        "s_m2": "Mumford S=L*(1.7*T+Cb*B), all inputs at normal loading",
        "displacement_unit": "metric tonne internally; historical source unit unresolved",
    })
    return {
        "loading_condition": "normal", "estimate": True,
        "lwl_m": L, "beam_m": B, "draught_m": T, "volume_m3": volume,
        "displacement_t": float(hull["displacement_normal_t"]),
        "displacement_unit": "metric_tonne", "displacement_unit_is_estimate": True,
        "s_m2": wet["values"]["wetted_surface_m2"],
        "cb": cb, "cm": cm, "cp": cb / cm, "bt": B / T,
        "volumetric": volume / L ** 3, "sources": sources,
        "trace": wet["trace"],
        "warnings": wet["warnings"] + [
            "正常载荷估算：Cm 为假定值，湿面积由同载荷主尺度经验式计算，未使用满载模型湿面积。",
            "史料吨位的长吨/公吨未确认；此处按公吨计算，试航载荷未确认，不能据功率接近宣称已验证。",
        ],
    }


def load_inputs():
    ship = read_case("queen_mary_1913.json")
    assumptions = ship["resistance_assumptions"]
    hp = build_normal_basis(ship["hull"], assumptions)
    engine = read_case("queen_mary_1913_engines.json")
    trial = {"speed_kn": engine["trial_speed_kn"], "shp": engine["power_trial_shp"],
             "loading_condition": "unknown", "source": engine["power_trial_source"]}
    return hp, assumptions, trial
