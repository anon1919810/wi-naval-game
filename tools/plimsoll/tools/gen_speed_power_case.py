# -*- coding: utf-8 -*-
"""生成 QM 速度–阻力–功率曲线案例 + 可视化 HTML。

船型参数用**史实口径**（Cp = Cb/Cm = 0.533/0.94，B/T = 27.1/8.5，∇/L³ 按正常吃水）——
理由见 cases/queen_mary_1913_resistance.json 的 _note（模型型线 Cp 受 Cm 异常污染）。

跑法：python tools/plimsoll/tools/gen_speed_power_case.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

import resistance as R  # noqa: E402

JSON_OUT = os.path.join(PKG, "cases", "queen_mary_1913_speed_power.json")
HTML_OUT = os.path.join(PKG, "cases", "out", "queen_mary_speed_power.html")
TEMPLATE = os.path.join(PKG, "cases", "templates", "speed_power.html")
SPEEDS = [8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 27, 28, 29]
QPC_BAND = (0.50, 0.55, 0.60)
W, H, PAD = 760, 420, 56
V_LO, V_HI = 8.0, 29.0


def build_svg(rows, curves, rt_max, shp_max):
    def xs(v):
        return PAD + (v - V_LO) / (V_HI - V_LO) * (W - 2 * PAD)

    def ys_rt(v):
        return H - PAD - v / rt_max * (H - 2 * PAD)

    def ys_shp(p):
        return H - PAD - p / shp_max * (H - 2 * PAD)

    grid = []
    for gv in range(8, 31, 4):
        grid.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="#e6e8ec"/>'
                    % (xs(gv), PAD, xs(gv), H - PAD))
        grid.append('<text x="%.1f" y="%d" font-size="11" fill="#5b6472" '
                    'text-anchor="middle">%d kn</text>' % (xs(gv), H - PAD + 16, gv))
    for i in range(0, 6):
        val = rt_max * i / 5.0
        y = ys_rt(val)
        grid.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#eef0f3"/>'
                    % (PAD, y, W - PAD, y))
        grid.append('<text x="%d" y="%.1f" font-size="11" fill="#5b6472" '
                    'text-anchor="end">%.0f</text>' % (PAD - 6, y + 4, val))

    rt_path = " ".join("%s%.1f,%.1f" % ("M" if i == 0 else "L", xs(r["speed_kn"]),
                                        ys_rt(r["rt_kN"])) for i, r in enumerate(rows))
    shp_paths = {}
    for q in QPC_BAND:
        shp_paths[q] = " ".join("%s%.1f,%.1f" % ("M" if i == 0 else "L", xs(r["speed_kn"]),
                                                ys_shp(r["shp_required"]))
                                for i, r in enumerate(curves[q]["rows"]))
    tx, ty = xs(28.1), ys_shp(83000)
    return {
        "GRID": "\n  ".join(grid), "RT": rt_path,
        "SHP50": shp_paths[0.50], "SHP55": shp_paths[0.55], "SHP60": shp_paths[0.60],
        "TX": "%.1f" % tx, "TY": "%.1f" % ty,
        "TXL": "%.1f" % (tx + 8), "TYL": "%.1f" % (ty - 8),
        "MID": "%d" % int(W / 2 + 90), "XAX": "%.1f" % (W / 2 + 90),
        "YAX": "%.1f" % (H - PAD + 34), "W": str(W), "H": str(H),
    }


def build_rows(rows, curves):
    out = []
    for i, r in enumerate(rows):
        out.append("<tr><td>%.0f</td><td>%.3f</td><td>%.0f</td><td>%.2f</td>"
                   "<td>%.0f</td><td>%.0f</td><td>%.0f</td><td>%.0f</td><td>%.0f</td></tr>"
                   % (r["speed_kn"], r["fr_used"], r["rf_kN"], (r["cr"] or 0) * 1000,
                      r["rt_kN"], r["pe_kw"],
                      curves[0.50]["rows"][i]["shp_required"],
                      curves[0.55]["rows"][i]["shp_required"],
                      curves[0.60]["rows"][i]["shp_required"]))
    return "\n".join(out)


def main():
    tg = json.load(open(os.path.join(PKG, "cases", "taylor_gertler_cr_table.json"),
                        encoding="utf-8"))
    hp = {"lwl_m": 212.8, "s_m2": 6407.9,
          "cp": 0.533 / 0.94, "bt": 27.1 / 8.5,
          "volumetric": (26770 / 1.025) / 212.8 ** 3}

    curves = {q: R.speed_power_curve(hp, SPEEDS, tg, qpc=q) for q in QPC_BAND}
    base = curves[0.55]
    rows = base["rows"]

    case = {
        "schema": "plimsoll-speed-power-1",
        "ship": "HMS Queen Mary (1913)",
        "_note": ("速度–阻力–功率曲线（Taylor-Gertler 口径）。船型参数用**史实口径**"
                  "（Cp=0.533/0.94=0.567, B/T=3.19, ∇/L³=2.71e-3）——模型型线的 Cp 不可用"
                  "（用它反推 QPC>1，物理不可能）。摩擦 Schoenherr + ΔCf=0.4e-3；"
                  "剩余查 A3.8–A3.11 表。★ 黑盒对照：28 kn 按 QPC=0.55 预测所需 SHP ≈75,300，"
                  "试航 83,000 shp @28.1 kn，偏低 ~10% —— 与文献所述"
                  "「Taylor-Gertler 一般低估 5–10%」一致。Fr<0.16 的低速点端点截断（不外推）。"),
        "hull_params_historical": hp,
        "hull_params_basis": "Cp = Cb(0.533)/Cm(0.94)；B/T、∇/L³ 按正常吃水 8.5 m",
        "sources": {
            "cr_table": "cases/taylor_gertler_cr_table.json（Molland A3.8-A3.11 / Gertler DTMB-806）",
            "wetted_surface": "cases/queen_mary_1913_formcoeff.json",
            "friction": "Schoenherr 0.4631/(lgRn)^2.6 + ΔCf=0.4e-3（原书要求）",
            "trial": "Navypedia: 83,000 shp → 28.1 kn",
        },
        "curves": {("qpc=%.2f" % q): {"rows": c["rows"], "warnings": c["warnings"]}
                   for q, c in curves.items()},
        "trace": base["trace"],
    }
    os.makedirs(os.path.dirname(HTML_OUT), exist_ok=True)
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(case, f, ensure_ascii=False, indent=1)

    rt_max = max(r["rt_kN"] for r in rows) * 1.08
    shp_max = max(r["shp_required"] for r in curves[0.50]["rows"]) * 1.05
    tpl = open(TEMPLATE, encoding="utf-8").read()
    svg = build_svg(rows, curves, rt_max, shp_max)
    svg["ROWS"] = build_rows(rows, curves)
    for k, v in svg.items():
        tpl = tpl.replace("{{%s}}" % k, v)
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(tpl)
    print("written:", JSON_OUT)
    print("written:", HTML_OUT)


if __name__ == "__main__":
    main()
