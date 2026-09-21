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

    # ---- Taylor-Gertler 表插值（两套船型参数并列，见 _note）
    tg = json.load(open(os.path.join(PKG, "cases", "taylor_gertler_cr_table.json"),
                        encoding="utf-8"))
    fn = v / (9.81 * L) ** 0.5
    # 史实口径：Cp = Cb / Cm（Cb 案例 0.533；Cm 取战舰常见 0.94）—— 模型型线 Cp 受 Cm=0.71 污染
    cp_hist = 0.533 / 0.94
    bt_hist = 27.1 / 8.5
    vol_hist = (26770 / 1.025) / 212.8 ** 3
    tg_hist = R.residual_from_table(tg, cp_hist, bt_hist, vol_hist, fn)
    tg_model = R.residual_from_table(tg, fc["values"]["cp"],
                                     fc["values"]["beam_wl_m"] / fc["values"]["draught_at_wl_m"],
                                     fc["values"]["volume_m3"] / L ** 3, fn)

    def _qpc_for(cr):
        rr = 0.5 * R.RHO_SEA * S * cr * v * v
        return (fr["values"]["rf_n"] + rr) * v / 1000.0 / (shp * R.HP_TO_KW)

    values = {
        "rn": fr["values"]["rn"], "cf_schoenherr": fr["values"]["cf"],
        "cf_total": fr["values"]["cf_total"], "rf_kN": fr["values"]["rf_kN"],
        "cf_ittc1957": R.ittc1957_cf(fr["values"]["rn"]),
        "pe_kw_at_trial": imp["values"]["pe_kw"],
        "r_total_kN": imp["values"]["r_total_n"] / 1000.0,
        "rr_kN": imp["values"]["rr_n"] / 1000.0,
        "cr_implied": imp["values"]["cr_implied"],
        "cr_table_historical": tg_hist["values"]["cr"],
        "cr_table_model": tg_model["values"]["cr"],
    }
    if tg_hist["values"]["cr"]:
        values["qpc_implied_by_table_historical"] = _qpc_for(tg_hist["values"]["cr"])
    if tg_model["values"]["cr"]:
        values["qpc_implied_by_table_model"] = _qpc_for(tg_model["values"]["cr"])

    case = {
        "schema": "plimsoll-resistance-1",
        "ship": "HMS Queen Mary (1913)",
        "_note": ("阻力 v0.1：摩擦（Schoenherr + 0.4e-3 粗糙度）+ **Taylor-Gertler 表插值**"
                  "（Molland A3.8–A3.11；表内 CR×1000 → scale 1e-3）。"
                  "★ 船型参数**必须用史实口径**（Cp = Cb/Cm ≈ 0.567，B/T = 27.1/8.5 = 3.19）："
                  "模型型线的 Cp=0.766 受 Cm=0.71 异常污染，用它插值会得到 Cr≈5e-3、"
                  "反推 QPC≈0.28（荒谬）；史实口径给出 Cr≈1.4e-3、QPC≈0.51（合理），"
                  "并与试航反解 Cr=0.00167 相差约 16% —— **两个独立来源互相印证**。"
                  "ν 取海水 15°C；QPC=0.55 为反解假定值（无来源）。"),
        "inputs": {"speed_kn": v_kn, "shp_trial": shp,
                   "wetted_surface_m2": S, "lwl_m": L,
                   "nu_m2_s": R.NU_SEA_15C, "rho_kg_m3": R.RHO_SEA,
                   "qpc_assumed": 0.55,
                   "form_params_historical": {"cp": cp_hist, "bt": bt_hist,
                                              "volumetric": vol_hist, "fn": fn,
                                              "note": "Cp = Cb(0.533)/Cm(0.94)；B/T、∇/L³ 用正常吃水"},
                   "form_params_model": {"cp": fc["values"]["cp"],
                                         "bt": fc["values"]["beam_wl_m"] / fc["values"]["draught_at_wl_m"],
                                         "volumetric": fc["values"]["volume_m3"] / L ** 3,
                                         "note": "模型型线（Cm=0.71 异常）—— 仅作对照"},
                   "sources": {"S": "cases/queen_mary_1913_formcoeff.json（型线逐站积分）",
                               "L": "同上（水线长）",
                               "trial": "cases/queen_mary_1913_engines.json（Navypedia）",
                               "cr_table": "cases/taylor_gertler_cr_table.json（Molland A3.8-A3.11）"}},
        "values": values,
        "trace": fr["trace"] + imp["trace"] + tg_hist["trace"] + tg_model["trace"],
        "warnings": (fr["warnings"] + imp["warnings"] +
                     ["表插值（史实口径）：" + w for w in tg_hist["warnings"]] +
                     ["表插值（模型口径）：" + w for w in tg_model["warnings"]]),
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(case, f, ensure_ascii=False, indent=2)
    print("written:", OUT)


if __name__ == "__main__":
    main()
