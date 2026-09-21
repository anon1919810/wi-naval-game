# -*- coding: utf-8 -*-
"""生成 QM 阻力案例（plimsoll-resistance-1）—— 7.3 的**已算部分**。

输入：
  船型系数  cases/queen_mary_1913_formcoeff.json（由型线真算）
  试航数据  cases/queen_mary_1913_engines.json（83,000 shp → 28.1 kn）

输出：
  Schoenherr 摩擦阻力（含 Taylor 法粗糙度附加）+ **由试航真值反解的隐含 Cr**。
  ⚠️ 剩余阻力图谱（Gertler 1954）缺 → cr_from_table 为 None，见 warnings。

跑法：python tools/plimsoll/tools/gen_resistance_case.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

import resistance as R  # noqa: E402

OUT = os.path.join(PKG, "cases", "queen_mary_1913_resistance.json")


def main():
    fc = json.load(open(os.path.join(PKG, "cases", "queen_mary_1913_formcoeff.json"),
                        encoding="utf-8"))
    eng = json.load(open(os.path.join(PKG, "cases", "queen_mary_1913_engines.json"),
                         encoding="utf-8"))
    v_kn = 28.1                       # 试航（Navypedia：83,000 shp → 28.1 kn）
    shp = float(eng["power_trial_shp"])
    S = float(fc["values"]["wetted_surface_m2"])
    L = float(fc["values"]["lwl_m"])
    v = v_kn * R.KNOT_MPS

    fr = R.friction_resistance(v, L, S, nu=R.NU_SEA_15C, delta_cf=R.DELTA_CF_TAYLOR)
    imp = R.implied_residual_from_trial(shp, v_kn, fr["values"]["rf_n"], S, qpc=0.55)
    cr_missing = R.residual_from_table(None, fc["values"]["cp"],
                                       fc["values"]["beam_wl_m"] / fc["values"]["draught_at_wl_m"],
                                       fc["values"]["volume_m3"] / L ** 3,
                                       v / (9.81 * L) ** 0.5)

    case = {
        "schema": "plimsoll-resistance-1",
        "ship": "HMS Queen Mary (1913)",
        "_note": ("阻力 v0：只含**已算部分**。摩擦用 Schoenherr（Taylor 法口径）+ 0.4e-3 粗糙度；"
                  "剩余阻力图谱（Gertler 1954 DTMB-806）**缺** → cr_from_table 为 None；"
                  "cr_implied 是由试航真值**反解**的（QPC=0.55 为假定，无来源）。"
                  "ν 取海水 15°C 1.19e-6。"),
        "inputs": {"speed_kn": v_kn, "shp_trial": shp,
                   "wetted_surface_m2": S, "lwl_m": L,
                   "nu_m2_s": R.NU_SEA_15C, "rho_kg_m3": R.RHO_SEA,
                   "qpc_assumed": 0.55,
                   "sources": {"S": "cases/queen_mary_1913_formcoeff.json（型线逐站积分）",
                               "L": "同上（水线长）",
                               "trial": "cases/queen_mary_1913_engines.json（Navypedia）"}},
        "values": {
            "rn": fr["values"]["rn"], "cf_schoenherr": fr["values"]["cf"],
            "cf_total": fr["values"]["cf_total"], "rf_kN": fr["values"]["rf_kN"],
            "cf_ittc1957": R.ittc1957_cf(fr["values"]["rn"]),
            "pe_kw_at_trial": imp["values"]["pe_kw"],
            "r_total_kN": imp["values"]["r_total_n"] / 1000.0,
            "rr_kN": imp["values"]["rr_n"] / 1000.0,
            "cr_implied": imp["values"]["cr_implied"],
            "cr_from_table": cr_missing["values"]["cr"],
        },
        "trace": fr["trace"] + imp["trace"],
        "warnings": fr["warnings"] + imp["warnings"] + cr_missing["warnings"],
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(case, f, ensure_ascii=False, indent=2)
    print("written:", OUT)


if __name__ == "__main__":
    main()
