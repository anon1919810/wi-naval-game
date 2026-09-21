# -*- coding: utf-8 -*-
"""把解析出的 Taylor-Gertler 表写入仓库案例（plimsoll-cr-table-1）。

数据来源：Molland, Turnock & Hudson, *Ship Resistance and Propulsion*,
Appendix A3, Tables A3.8–A3.11（书页 495–498；数据原始出处 Gertler, DTMB Report 806, 1954）。
表内单位 **CR × 1000**，故 JSON 里存 `scale: 1e-3`，核心插值后即为无量纲 Cr。

轴（按书中）：Cp、B/T、L/∇^⅓、Fr；网格索引顺序 [Cp][B/T][∇/L³][Fr]（与
`resistance.residual_from_table` 一致）。∇/L³ 轴由 L/∇^⅓ 换算 = (1/L/∇^⅓)³，**升序**排列。

解析器：tools/parse_taylor_gertler.py（按坐标解析，含旋转 90° 处理与逐行核对）。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
PARSED = r'C:\Users\杨睿\WorkBuddy\2026-09-17-17-33-38\_tg_parsed.json'
OUT = os.path.join(PKG, 'cases', 'taylor_gertler_cr_table.json')

GROUPS = [5.5, 6.0, 7.0, 8.0, 9.0, 10.0]
BTS = [2.25, 3.00, 3.75]
CPS = ['0.50', '0.60', '0.70', '0.80']


def main():
    tg = json.load(open(PARSED, encoding='utf-8'))
    vol_axis = sorted((1.0 / g) ** 3 for g in GROUPS)
    vol_to_lv = {round((1.0 / g) ** 3, 12): g for g in GROUPS}
    fn_axis = sorted(r['fr'] for r in tg['tables']['0.50']['rows'])

    grid = []
    raw = {}
    for cp in CPS:
        rows = {round(r['fr'], 2): r['cells'] for r in tg['tables'][cp]['rows']}
        raw[cp] = {('%.2f' % f): rows[round(f, 2)] for f in fn_axis}
        bt_block = []
        for j_bt, bt in enumerate(BTS):
            vol_block = []
            for v in vol_axis:
                lv = vol_to_lv[round(v, 12)]
                j_col = GROUPS.index(lv) * 3 + j_bt
                vol_block.append([rows[round(f, 2)][j_col] for f in fn_axis])
            bt_block.append(vol_block)
        grid.append(bt_block)

    case = {
        'schema': 'plimsoll-cr-table-1',
        'ship': '(通用：Taylor-Gertler 系列)',
        '_note': ('剩余阻力系数表。**表内为 CR×1000**，故 scale=1e-3。'
                  '缺格为 null（原书用「—」）：插值时会按可用角点重新归一化并警告。'
                  '用法：配 Schoenherr 摩擦线 + ΔCf=0.0004（原书明确要求），'
                  'LCB 该系列固定在中部。'),
        'source': ('Molland, Turnock & Hudson, Ship Resistance and Propulsion, '
                   'Appendix A3, Tables A3.8-A3.11 (pp. 495-498); '
                   'data after Gertler, M. "A reanalysis of the original test data for '
                   'the Taylor Standard Series", DTMB Report 806 (1954), SNAME reprint 1998'),
        'range': {'cp': [0.50, 0.80], 'bt': [2.25, 3.75], 'l_over_vol13': [5.5, 10.0],
                  'fr': [0.16, 0.58]},
        'scale': 1e-3,
        'axes': {'cp': [float(c) for c in CPS], 'bt': BTS,
                 'volumetric': [round(v, 9) for v in vol_axis], 'fn': fn_axis},
        'cr': grid,
        'raw_rows': raw,
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(case, f, ensure_ascii=False, indent=1)
    n_missing = sum(1 for cp in grid for bt in cp for v in bt for x in v if x is None)
    n_total = len(grid) * len(grid[0]) * len(grid[0][0]) * len(grid[0][0][0])
    print('written %s  (%d/%d 缺格)' % (OUT, n_missing, n_total))


if __name__ == '__main__':
    main()
