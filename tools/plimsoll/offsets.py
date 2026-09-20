"""Plimsoll · 型值表导入（offsets）

把「站位型值表」变成 Plimsoll 的站位剖面，喂给 L1 几何法。

为什么要有这一层
----------------
`hull_offsets.json` 是本项目**约定的真实型线接入点**（见 `queen_mary_v4.py:63-64`）。
在此之前船体由内建估算表放样；一旦拿到型线图，只要放一个 `hull_offsets.json`
就能替换，不需要改任何代码。本模块既读那个文件，也能直接从生成脚本里取内建表。

坐标映射（重要）
----------------
生成脚本用 Blender 坐标：**+X 右舷 / +Y 舰艏 / +Z 上**，水线 z=0，1 单位 = 1 m。
Plimsoll 用：**x 沿船长（+ 艏）/ y 右舷 / z 上**。因此

    x_plimsoll = y_blender      y_plimsoll = x_blender      z_plimsoll = z_blender

**没有旋转、没有镜像**。注意这与 FBX 不同 —— 导出 FBX 时会绕 Z 转 180°
（`EXPORT_YAW_DEG=180`），所以**要读 .blend / 生成脚本，不要读 FBX**。
"""

from __future__ import annotations

import ast
import json
import math
import os

from geometry import StationedHull

DECK_Z_DEFAULT = 5.10      # 主甲板高（生成脚本 DECK_Z）


# ---------------------------------------------------------------- 读表


def parse_offsets_from_python(path, varname="OFFSETS"):
    """从生成脚本里取型值表（用 ast 静态解析，不 import —— 那个脚本要 bpy）。"""
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=path)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == varname:
                    rows = ast.literal_eval(node.value)
                    return _validate(rows, path + ":" + varname)
    raise ValueError("在 %s 里找不到 %s 赋值" % (path, varname))


def load_offsets_json(path):
    """读 hull_offsets.json（真实型线接入点）。"""
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    rows = payload["stations"] if isinstance(payload, dict) else payload
    source = payload.get("sources", "") if isinstance(payload, dict) else ""
    return _validate(rows, path), source


def find_offsets(default_dir, filename="hull_offsets.json"):
    """按约定找型线文件；找不到返回 None（此时调用方应回落到生成脚本的内建表）。"""
    p = os.path.join(default_dir, filename)
    return p if os.path.isfile(p) else None


def _validate(rows, origin):
    table = [tuple(float(v) for v in row) for row in rows]
    if len(table) < 5:
        raise ValueError("%s 至少需要 5 个站位，收到 %d" % (origin, len(table)))
    if any(len(r) != 5 for r in table):
        raise ValueError("%s 每站必须是 5 个数 (y, deck_hb, wl_hb, keel_z, flat_hb)" % origin)
    return sorted(table, key=lambda r: r[0])


# ---------------------------------------------------------------- 插值（忠实复现生成脚本）


def station_params(table, y):
    """四点单调三次 Hermite 插值 + 钳位。

    忠实复现 `queen_mary_v4.py` 的 `station_params`：斜率用加权调和平均
    （Fritsch–Carlson 那一类），端点用单侧差分，异号斜率置 0，
    最后 `max(min(a,b), min(max(a,b), value))` **钳位以杜绝过冲**。

    ⚠️ 这个钳位会留下"合成指纹"：平行中体在 y∈[−30,+30] 被钉在恰好 13.60 m，
    龙骨在 y∈[−50,+50] 被钉在恰好 −9.90 m。校验提取结果时要用它分辨
    「模型本来如此」还是「提取错了」。
    """
    rows = table
    if not (rows[0][0] <= y <= rows[-1][0]):
        raise ValueError("y=%.3f 超出型值表范围 [%.3f, %.3f]" % (y, rows[0][0], rows[-1][0]))
    i = next(k for k in range(len(rows) - 1) if rows[k][0] <= y <= rows[k + 1][0])
    h = rows[i + 1][0] - rows[i][0]
    t = (y - rows[i][0]) / h
    out = []
    for col in range(1, 5):
        def slope(j):
            if j == 0:
                return (rows[1][col] - rows[0][col]) / (rows[1][0] - rows[0][0])
            if j == len(rows) - 1:
                return (rows[-1][col] - rows[-2][col]) / (rows[-1][0] - rows[-2][0])
            h0 = rows[j][0] - rows[j - 1][0]
            h1 = rows[j + 1][0] - rows[j][0]
            a = (rows[j][col] - rows[j - 1][col]) / h0
            b = (rows[j + 1][col] - rows[j][col]) / h1
            if a * b <= 0:
                return 0.0
            w1 = 2 * h1 + h0
            w2 = h1 + 2 * h0
            return (w1 + w2) / (w1 / a + w2 / b)
        a, b = rows[i][col], rows[i + 1][col]
        v = ((2 * t ** 3 - 3 * t * t + 1) * a + (t ** 3 - 2 * t * t + t) * h * slope(i)
             + (-2 * t ** 3 + 3 * t * t) * b + (t ** 3 - t * t) * h * slope(i + 1))
        out.append(max(min(a, b), min(max(a, b), v)))
    return tuple(out)


def section_profile(deck_hb, wl_hb, keel_z, flat_hb, deck_z=DECK_Z_DEFAULT):
    """单站剖面：(z, 半宽) 序列，自甲板向下到龙骨。

    忠实复现生成脚本：9 点舷弧段（指数 .85）+ 24 点龙骨余弦弧（指数 .92）。
    """
    pts = []
    for i in range(9):
        t = i / 8
        pts.append((deck_z * (1 - t), deck_hb + (wl_hb - deck_hb) * t ** .85))
    for i in range(1, 25):
        f = i / 24
        pts.append((keel_z * f, flat_hb + (wl_hb - flat_hb) * math.cos(math.pi * .5 * f ** .92)))
    return pts


def halfbeam_at(table, y, z, deck_z=DECK_Z_DEFAULT):
    """某站位在高度 z 处的半宽（线性插值）。"""
    prof = section_profile(*station_params(table, y), deck_z=deck_z)
    if z >= prof[0][0]:
        return prof[0][1]
    for (z1, h1), (z2, h2) in zip(prof, prof[1:]):
        if z2 <= z <= z1:
            t = 0.0 if z1 == z2 else (z1 - z) / (z1 - z2)
            return h1 + (h2 - h1) * t
    return prof[-1][1]


def keel_at(table, y):
    return station_params(table, y)[2]


def deck_halfbeam(table, y):
    return station_params(table, y)[0]


# ---------------------------------------------------------------- 造站位船体


def build_hull(table, deck_z=DECK_Z_DEFAULT, n_stations=121, n_section=96,
               spacing="cosine", extra_ys=()):
    """型值表 → Plimsoll `StationedHull`。

    站位：默认 cosine 分布（两端加密），并强制并入型值表本身的 y 值与 `extra_ys`
    —— 表值是曲率转折处，必须被采到，否则插值在转折附近会有偏差。

    每站剖面：在 [keel_at(y), deck_z] 上按 cosine 采 n_section 个高度，
    用 `halfbeam_at` 求半宽；再镜像成闭合多边形（右舷上行 → 甲板 → 左舷下行）。
    同时强制并入 z = 0（水线）这个折点。
    """
    y0, y1 = table[0][0], table[-1][0]
    L = y1 - y0
    ys = []
    for i in range(n_stations):
        t = i / (n_stations - 1.0)
        ys.append(y0 + L * (t if spacing == "uniform" else 0.5 * (1 - math.cos(math.pi * t))))
    for extra in list(extra_ys) + [r[0] for r in table]:
        if y0 <= extra <= y1:
            ys.append(extra)
    ys = sorted({round(v, 9) for v in ys})

    stations = []
    for y in ys:
        keel = keel_at(table, y)
        levels = _levels(keel, deck_z, n_section)
        right = [(halfbeam_at(table, y, z, deck_z), z) for z in levels]
        poly = list(right)
        poly.append((-right[-1][0], right[-1][1]))          # 甲板另一舷
        for (hb, z) in reversed(right[:-1]):
            poly.append((-hb, z))
        stations.append((y, poly))                          # x_plimsoll = y_blender
    return StationedHull(stations, name="offsets:%d stations" % len(stations))


def _levels(keel, deck_z, n):
    """[keel, deck_z] 上的采样高度：cosine 加密 + 强制并入 z=0 水线折点。"""
    out = []
    for i in range(n):
        t = i / (n - 1.0)
        out.append(keel + (deck_z - keel) * 0.5 * (1 - math.cos(math.pi * t)))
    out.append(0.0)
    out.append(keel)
    out.append(deck_z)
    return sorted({round(v, 9) for v in out})
