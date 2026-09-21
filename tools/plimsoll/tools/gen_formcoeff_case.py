# -*- coding: utf-8 -*-
"""把型线推出的船型系数物化成案例 JSON —— 7.3 阻力模型的地基数据。

**这些系数是算出来的，不是抄来的**：逐站剖面在水线以下积分得 ∇、Am、LCB，
再由定义式得 Cb / Cp / Cm；半进流角按显式约定（离中线 Bwl/10）量取。

跑法：python tools/plimsoll/tools/gen_formcoeff_case.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

import offsets as OF  # noqa: E402
import hull as H      # noqa: E402

OUT = os.path.join(PKG, "cases", "queen_mary_1913_formcoeff.json")


def main():
    tbl, src, dz = OF.load_offsets_payload(
        os.path.join(PKG, "cases", "queen_mary_1913_offsets.json"))
    hull = OF.build_hull(tbl, deck_z=dz)
    fc = H.form_coefficients(hull, z=0.0)
    ie = H.half_angle_of_entrance(hull, z=0.0)

    wet = H.wetted_surface_from_hull(hull)
    trace = [dict(t, estimate=True, input_geometry_estimate=True)
             for t in fc["trace"] + ie["trace"] + wet["trace"]]
    case = {
        "schema": "plimsoll-formcoeff-1",
        "ship": "HMS Queen Mary (1913)",
        "_note": ("由型线（cases/queen_mary_1913_offsets.json，水线 z=0 = 满载吃水 9.9 m）"
                  "逐站积分推出，非文献值。口径：L 取该水线处水线长；B 取水线最大宽；"
                  "T = z − 龙骨 z。半进流角口径为『离中线 Bwl/10 处切线』（口径不唯一）。"
                  "⚠️ Cm 明显低于战舰常见 0.9+，说明型线**形状分布**与史实不符"
                  "（体积/Cb 已验证，形状未验证）—— 7.3 阻力对 Cm/Cp 极敏感，须带着这个限界用。"),
        "offsets_source": src,
        "estimate": True,
        "loading_condition": "model_design_full_load",
        "datum": {"waterline_z_m": 0.0, "keel_z_m": -9.9, "draught_m": 9.9},
        "values": {
            "volume_m3": fc["values"]["volume_m3"],
            "midship_area_m2": fc["values"]["midship_area_m2"],
            "x_of_max_area_m": fc["values"]["x_of_max_area_m"],
            "lcb_x_m": fc["values"]["lcb_x_m"],
            "beam_wl_m": fc["values"]["beam_wl_m"],
            "draught_at_wl_m": fc["values"]["draught_at_wl_m"],
            "lwl_m": fc["values"]["lwl_m"],
            "cb": fc["values"]["cb"],
            "cp": fc["values"]["cp"],
            "cm": fc["values"]["cm"],
            "iE_deg": ie["values"]["iE_deg"],
            "wetted_surface_m2": H.wetted_surface_from_hull(hull)["values"]["wetted_surface_m2"],
        },
        "trace": trace,
        "warnings": fc["warnings"] + ie["warnings"] + wet["warnings"] +
                    ["所有几何结果继承输入模型型线的 estimate；数值积分不等于史实测量。"],
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(case, f, ensure_ascii=False, indent=2)
    print("written:", OUT)


if __name__ == "__main__":
    main()
