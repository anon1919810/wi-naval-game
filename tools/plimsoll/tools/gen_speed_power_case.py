# -*- coding: utf-8 -*-
"""生成 QM 速度–阻力–功率曲线案例 + 可视化 HTML。

正常载荷估算参数来自共享 case adapter；模型满载另作对照。

跑法：python tools/plimsoll/tools/gen_speed_power_case.py
"""
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

import resistance as R  # noqa: E402
from tools.qm_resistance_inputs import load_inputs, read_case

JSON_OUT = os.path.join(PKG, "cases", "queen_mary_1913_speed_power.json")
HTML_OUT = os.path.join(PKG, "cases", "out", "queen_mary_speed_power.html")
TEMPLATE = os.path.join(PKG, "cases", "templates", "speed_power.html")
SPEEDS = [8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 27, 28, 29]
QPC_BAND = (0.50, 0.55, 0.60)
W, H, PAD = 760, 420, 56
V_LO, V_HI = 8.0, 29.0


def build_svg(rows, curves, rt_max, shp_max, trial=None):
    trial = trial or {"speed_kn": 28.1, "shp": 83000}
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

    def path(points, key, ordinate):
        parts = []
        pen_down = False
        for row in points:
            value = row[key]
            if value is None:
                pen_down = False
                continue
            parts.append("%s%.1f,%.1f" % ("L" if pen_down else "M",
                                        xs(row["speed_kn"]), ordinate(value)))
            pen_down = True
        return " ".join(parts)

    rt_path = path(rows, "rt_kN", ys_rt)
    shp_paths = {q: path(curves[q]["rows"], "shp_required", ys_shp) for q in QPC_BAND}
    tx, ty = xs(trial["speed_kn"]), ys_shp(trial["shp"])
    for i in range(6):
        grid.append('<text x="%d" y="%.1f" font-size="10" fill="#2f6fd0">%.0f</text>' %
                    (W - PAD + 4, ys_shp(shp_max * i / 5) + 4, shp_max * i / 5))
    return {
        "GRID": "\n  ".join(grid), "RT": rt_path,
        "SHP50": shp_paths[0.50], "SHP55": shp_paths[0.55], "SHP60": shp_paths[0.60],
        "TX": "%.1f" % tx, "TY": "%.1f" % ty,
        "TXL": "%.1f" % (tx - 8), "TYL": "%.1f" % (ty - 8),
        "MID": "%d" % int(W / 2 + 90), "XAX": "%.1f" % (W / 2 + 90),
        "YAX": "%.1f" % (H - PAD + 34), "W": str(W), "H": str(H),
    }


def build_rows(rows, curves):
    def fmt(value, spec=".0f"):
        return "—" if value is None else format(value, spec)

    output = []
    for i, r in enumerate(rows):
        cells = [fmt(r["speed_kn"], "g"), fmt(r["fr"], ".3f"), fmt(r["rf_kN"]),
                 fmt(r["cr"] * 1000 if r["cr"] is not None else None, ".2f"),
                 fmt(r["rt_kN"]), fmt(r["pe_kw"])]
        cells += [fmt(curves[q]["rows"][i]["shp_required"]) for q in QPC_BAND]
        diagnostic = "；".join(r.get("warnings", [])) or "估算"
        cells.append(html.escape(diagnostic))
        output.append("<tr>" + "".join("<td>%s</td>" % c for c in cells) + "</tr>")
    return "\n".join(output)


def main():
    tg = read_case("taylor_gertler_cr_table.json")
    hp, assumptions, trial = load_inputs()
    speeds = sorted(set(SPEEDS + [trial["speed_kn"]]))
    curves = {q: R.speed_power_curve(hp, speeds, tg, qpc=q) for q in QPC_BAND}
    base = curves[assumptions["qpc"]]
    rows = base["rows"]
    comparison = next(r for r in rows if r["speed_kn"] == trial["speed_kn"])
    predicted = comparison["shp_required"]
    delta_pct = (predicted / trial["shp"] - 1) * 100 if predicted is not None else None
    note = ("正常载荷估算，湿面积使用同载荷 Mumford 经验式；Cm 和 QPC 为假定值。"
            "试航载荷及史料吨位单位未确认；功率偏差只作诊断，不作为验证通过的依据。")
    case = {
        "schema": "plimsoll-speed-power-2", "ship": "HMS Queen Mary (1913)",
        "estimate": True, "_note": note, "hull_params_normal_estimate": hp,
        "trial_reference": trial,
        "trial_comparison": {"speed_kn": trial["speed_kn"], "shp_predicted": predicted,
                             "deviation_pct": delta_pct, "validated": False},
        "curves": {"qpc=%.2f" % q: c for q, c in curves.items()},
        "trace": base["trace"], "warnings": base["warnings"],
    }
    os.makedirs(os.path.dirname(HTML_OUT), exist_ok=True)
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(case, f, ensure_ascii=False, indent=1)

    rt_max = max((r["rt_kN"] for r in rows if r["rt_kN"] is not None), default=1.) * 1.08
    shp_max = max([trial["shp"]] + [r["shp_required"] for r in curves[.50]["rows"]
                                  if r["shp_required"] is not None]) * 1.15
    with open(TEMPLATE, encoding="utf-8") as f:
        tpl = f.read()
    svg = build_svg(rows, curves, rt_max, shp_max, trial)
    svg["ROWS"] = build_rows(rows, curves)
    svg["BASIS"] = html.escape("T=%.2f m，Lwl=%.2f m，S=%.1f m²（经验式），Cp=%.4f，B/T=%.3f；%s" %
                               (hp["draught_m"], hp["lwl_m"], hp["s_m2"], hp["cp"], hp["bt"], note))
    svg["TRIAL"] = html.escape("试航参考 %.0f shp @ %g kn（载荷未确认）" % (trial["shp"], trial["speed_kn"]))
    svg["COMPARISON"] = (html.escape("同速 %g kn，QPC=%.2f：预测 %.0f shp，相对试航参考偏差 %+.1f%%。%s" %
                                  (trial["speed_kn"], assumptions["qpc"], predicted, delta_pct, note))
                         if predicted is not None else "剩余阻力不可用；总功率与偏差置空。")
    svg["WARNINGS"] = "".join("<li>%s</li>" % html.escape(w) for w in base["warnings"])
    for k, value in svg.items():
        tpl = tpl.replace("{{%s}}" % k, value)
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(tpl)
    print("written:", JSON_OUT)
    print("written:", HTML_OUT)


if __name__ == "__main__":
    main()
