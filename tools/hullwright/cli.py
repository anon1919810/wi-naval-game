#!/usr/bin/env python3
"""hullwright CLI

    python cli.py cases/queen_mary_1913.json              # 打印表格
    python cli.py cases/queen_mary_1913.json -o out.json  # 写 JSON
    python cli.py --selftest                              # 核心自检

显示层的取整只发生在这里；核心保持全精度。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import hydrostatics as H  # noqa: E402

# 显示用：键 → (中文名, 小数位, 单位)
DISPLAY = [
    ("displacement_t",          "排水量",         0,  "t"),
    ("displacement_volume_m3",  "排水体积",       0,  "m³"),
    ("awp_m2",                  "水线面面积",     1,  "m²"),
    ("tpc_t_per_cm",            "每厘米吃水吨数", 2,  "t/cm"),
    ("kb_m",                    "浮心高 KB",      3,  "m"),
    ("bm_t_m",                  "横稳心半径 BM",  3,  "m"),
    ("km_m",                    "横稳心高 KM",    3,  "m"),
    ("kg_m",                    "重心高 KG",      3,  "m"),
    ("gm_m",                    "初稳性高 GM",    3,  "m"),
    ("roll_period_s",           "横摇周期",       2,  "s"),
    ("bm_l_m",                  "纵稳心半径 BM_L", 1, "m"),
    ("mct1cm_t_m_per_cm",       "每厘米纵倾力矩", 0,  "t·m/cm"),
]


def main() -> int:
    ap = argparse.ArgumentParser(description="hullwright · 参数化静水力（L0）")
    ap.add_argument("ship", nargs="?", help="ship.json 路径")
    ap.add_argument("-o", "--out", help="写出 result.json")
    ap.add_argument("--selftest", action="store_true", help="只跑核心自检")
    a = ap.parse_args()

    if a.selftest or not a.ship:
        H._selfcheck_box()
        H._selfcheck_monotonic()
        print("核心自检通过：方箱退化 ✓  单调性 ✓")
        return 0

    with open(a.ship, encoding="utf-8") as f:
        ship = json.load(f)

    hull = ship["hull"]
    out = H.compute(hull)

    name = ship.get("name", "(未命名)")
    print("=" * 62)
    print("hullwright · %s" % name)
    print("=" * 62)
    print("水线面形状模型：f(x) = (1−(2x/L)²)^p，p = %.4f（由 Cwp=%.3f 反解）"
          % (out["shape_model"]["p"], out["shape_model"]["waterplane_coeff"]))
    print("-" * 62)
    v = out["values"]
    for key, label, nd, unit in DISPLAY:
        if key not in v:
            continue
        est = next((t["estimate"] for t in out["trace"] if t["key"] == key), False)
        mark = " *" if est else "  "
        print("%-14s %14.*f %-8s%s" % (label, nd, v[key], unit, mark))
    if v.get("displacement_input_t"):
        print("%-14s %14.0f %-8s   （偏差 %+.2f%%）"
              % ("（输入排水量）", v["displacement_input_t"], "t", v["displacement_deviation_pct"]))
    print("-" * 62)
    if any(t["estimate"] for t in out["trace"]):
        print("* = 含 estimate 成分，来源见 trace")

    if out["warnings"]:
        print()
        print("警告：")
        for w in out["warnings"]:
            print("  ! %s" % w)

    # KG 敏感性：GM 完全由 KG 决定，而 KG 属 L2。摊开比假装精确诚实。
    km = v["km_m"]
    lo, hi = max(0.5, km * 0.65), km * 0.95
    ks = [round(lo + (hi - lo) * i / 6.0, 2) for i in range(7)]
    print()
    print("KG 敏感性（KM = %.3f m 为几何量，固定）：" % km)
    print("  %-9s %-9s %-11s %s" % ("KG (m)", "GM (m)", "横摇周期(s)", "初稳性"))
    for r in H.sensitivity_kg(hull, ks):
        print("  %-9.2f %-9.3f %-11s %s"
              % (r["kg_m"], r["gm_m"],
                 ("%.2f" % r["roll_period_s"]) if r["roll_period_s"] else "—",
                 "OK" if r["stable"] else "不足（会翻）"))
    print("  ↑ GM 与 KG 是一一对应的；请用实测或 L2 重量分组把 KG 定下来。")

    if a.out:
        result = {
            "schema": "hullwright-result-1",
            "ship": name,
            "engine": "hullwright L0 (parametric hydrostatics)",
            "historically_certified": False,
            "values": out["values"],
            "shape_model": out["shape_model"],
            "kg_sensitivity": H.sensitivity_kg(hull, ks),
            "trace": out["trace"],
            "warnings": out["warnings"],
        }
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
        print()
        print("已写出 %s" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
