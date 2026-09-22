#!/usr/bin/env python3
"""Plimsoll CLI

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

if __package__:
    from . import hydrostatics as H
else:
    import hydrostatics as H

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


def _load_offsets_hull(a, case_dir, hull):
    """取型值表船体。

    **通用性契约（2026-09-22）**：Plimsoll 是通用求解器，CLI 不知道任何具体船。
    型线来源优先级：`--offsets <file>` → 案例 `hull.offsets_path`（相对案例文件目录）。
    都没有就明确报错并告诉用户怎么给 —— **不扫描仓库路径、不回落到任何生成脚本**。
    甲板高：offsets 文件自带 `deck_z_m` → 案例 `hull.depth_m`，再没有就报错。
    """
    if __package__:
        from . import offsets as OF
    else:
        import offsets as OF

    path = a.offsets or hull.get("offsets_path")
    if not path:
        raise SystemExit(
            "ERROR: 本船未声明型线。两种给法任选：\n"
            "  1. 案例 hull 段加 \"offsets_path\": \"<hull_offsets.json>\"（相对案例文件目录）\n"
            "     JSON 每站 5 个数 (y, deck_hb, wl_hb, keel_z, flat_hb)，可带 deck_z_m 与 source\n"
            "  2. 命令行 --offsets <file> 直接指定")
    if not os.path.isabs(path) and not os.path.isfile(path):
        cand = os.path.join(case_dir, path)
        path = cand if os.path.isfile(cand) else path
    if not os.path.isfile(path):
        raise SystemExit("ERROR: 型线文件不存在：%s" % path)

    table, note, deck_z_file = OF.load_offsets_payload(path)
    if a.deck_z is not None:
        deck_z = a.deck_z
    elif deck_z_file is not None:
        deck_z = deck_z_file
    elif hull.get("depth_m") is not None:
        deck_z = hull["depth_m"]
    else:
        raise SystemExit("ERROR: 甲板高没有来源：offsets 文件给 deck_z_m，"
                         "或案例 hull 给 depth_m，或命令行 --deck-z。")
    return OF.build_hull(table, deck_z=deck_z), "型线：%s（%s）" % (path, note or "无说明"), deck_z


def main() -> int:
    ap = argparse.ArgumentParser(description="Plimsoll · 参数化静水力（L0）")
    ap.add_argument("ship", nargs="?", help="ship.json 路径")
    ap.add_argument("-o", "--out", help="写出 result.json")
    ap.add_argument("--selftest", action="store_true", help="只跑核心自检")
    ap.add_argument("--gz", action="store_true",
                    help="额外输出大角稳性 GZ 曲线（L1 几何法）")
    ap.add_argument("--hull", choices=["offsets", "reference"], default="offsets",
                    help="GZ 用哪种船体：offsets=型值表船体（默认，真实几何）；"
                         "reference=合成参照船体（与 L0 同源，仅供交叉验证）")
    ap.add_argument("--offsets", help="型线 JSON 路径；省略则用案例 hull.offsets_path")
    ap.add_argument("--deck-z", type=float, default=None,
                    help="主甲板 z（型值表坐标，水线 z=0）；优先级高于文件与案例")
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
    print("Plimsoll · %s" % name)
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

    gz_block = None
    if a.gz:
        if __package__:
            from . import geometric as GM
            from . import geometry as GE
            from . import offsets as OF
        else:
            import geometric as GM
            import geometry as GE
            import offsets as OF
        import math as _m
        kg = hull.get("kg_m")
        if kg is None:
            print()
            print("跳过 GZ：需要 kg_m。")
        else:
            angles = [0, 5, 10, 15, 20, 30, 40, 50, 60]

            if a.hull == "reference":
                # 参照船体的龙骨在 z=0，甲板高度必须自吃水推出来。
                # 不要用 hull["depth_m"] —— 那是**型值表船体**的甲板高（水线在 z=0），
                # 两种船体的坐标基准不同，混用会让甲板低于水线，GZ 直接算成负的。
                L, B = hull["lwl_m"], hull["beam_m"]
                T = hull.get("draught_normal_m") or hull.get("draught_m")
                Cb, Cwp = hull["block_coeff"], hull.get("waterplane_coeff", 0.80)
                deck_z = T * 1.6
                h = GE.make_reference_hull(L, B, T, Cb, Cwp, deck=deck_z)
                vol = Cb * L * B * T
                prov = "合成参照船体（与 L0 同源，仅供交叉验证）"
                wl_z = T                      # 参照船体：龙骨在 0，设计水线在 T
            else:
                # 甲板高不允许静默默认值 —— 没来源就明确报错（通用性契约）。
                case_dir = os.path.dirname(os.path.abspath(a.ship))
                h, prov, deck_z = _load_offsets_hull(a, case_dir, hull)
                vol = GM.hydrostatics_upright(h, 0.0)["volume_m3"]
                wl_z = 0.0                    # 型值表船体：设计水线就在 z=0

            gz_warnings = ["GZ 采用所选船体的设计载荷与输入 KG，几何和 KG 来源须分别核验。"]
            if a.hull != "reference":
                gz_warnings.append("型线 GZ 使用设计水线 z=0 的排水体积；独立于 L0 正常载荷，不能混作同一工况。")
            top_z = max(z for _, poly in h.stations for _, z in poly)
            rows = GM.gz_curve(h, kg, vol, angles)
            deepest = max(r["waterline_d_m"] for r in rows)
            if deepest > top_z - 0.01:
                gz_warnings.append("平衡水线 %.3f m 接近或超过船体顶端 %.3f m，GZ 不可信。" % (deepest, top_z))
                print()
                print("  ⚠ 平衡水线 %.3f m 已超过船体顶端 %.3f m —— 该船体定义不足以承载此排水量，"
                      "GZ 不可信。检查甲板高度（reference 用 T×1.6；offsets 用 DECK_Z）"
                      % (deepest, top_z))
            print()
            print("GZ 曲线（L1 几何法，等体积倾斜）")
            print("  船体来源：%s" % prov)
            print("  排水体积 %.1f m³   KG %.2f m   甲板 z=%.2f m" % (vol, kg, deck_z))

            half = max(max(abs(y) for y, _ in poly) for _, poly in h.stations)
            freeboard = deck_z - wl_z
            if half > 0 and freeboard > 0:
                limit = _m.degrees(_m.atan(freeboard / half))
                gz_warnings.append("甲板浸没角约 %.1f°；超过此角度的封闭船体 GZ 未验证，不应作真实稳性结论。" % limit)
                print("  ⚠ 甲板浸没角约 %.1f°（干舷 %.2f m ÷ 半宽 %.2f m）——"
                      "超过它浸没剖面被主甲板截断，GZ 偏小，该角以上数值不应引用"
                      % (limit, freeboard, half))
            print("  %-8s %-12s %s" % ("横倾", "复原力臂 m", "平衡水线 m"))
            for r in rows:
                bar = "█" * int(max(0.0, r["gm_arm_m"]) * 8)
                print("  %-8s %-12.4f %-12.3f %s"
                      % ("%d°" % r["angle_deg"], r["gm_arm_m"], r["waterline_d_m"], bar))
            peak = max(rows, key=lambda r: r["gm_arm_m"])
            print("  最大复原力臂 %.4f m @ %d°" % (peak["gm_arm_m"], peak["angle_deg"]))
            gz_block = {"hull_source": prov, "deck_z_m": deck_z, "rows": rows,
                        "loading_condition": "reference_normal" if a.hull == "reference" else "offsets_design_waterline",
                        "volume_m3": vol, "waterline_z_m": wl_z,
                        "kg_m": kg, "estimate": True, "warnings": gz_warnings}

    if a.out:
        result = {
            "schema": "plimsoll-result-1",
            "ship": name,
            "engine": "plimsoll L0 (parametric hydrostatics)",
            "historically_certified": False,
            "loading_condition": hull.get("loading_condition", "normal"),
            "mass_unit": "metric_tonne",
            "values": out["values"],
            "shape_model": out["shape_model"],
            "kg_sensitivity": H.sensitivity_kg(hull, ks),
            "gz_curve": gz_block,
            "trace": out["trace"],
            "warnings": out["warnings"] + (gz_block["warnings"] if gz_block else []),
        }
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
        print()
        print("已写出 %s" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
