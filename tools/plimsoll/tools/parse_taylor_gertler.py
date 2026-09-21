# -*- coding: utf-8 -*-
"""解析 Molland《Ship Resistance and Propulsion》附录 A3 的 Taylor-Gertler 表。

为什么这么麻烦：这本书把横排的大表**旋转 90°**排在竖版页面上 —— 在 PDF 存储坐标里
「表行（Fr）沿 x、表列（18 列）沿 y」。所以必须按坐标归属，不能靠文本流顺序
（表里有大量缺格「—」，文本流 token 数会与单元格数不符 → 错列是静默错误）。

依赖：pymupdf、原书 PDF（自行准备，见 --src）。
用法：python parse_taylor_gertler.py --src <book.pdf> --out <parsed.json>
校验：脚本内含「Fr=0.16 行 == 书中 0.45 0.54 0.65 …」的自检。
"""
import json
import sys


import pymupdf  # noqa: E402

SRC = r'C:\Users\杨睿\Desktop\732584747-Ship-Resistance-and-Propulsion-Ref1.pdf'
OUT = r'C:\Users\杨睿\WorkBuddy\2026-09-17-17-33-38\_tg_parsed.json'
PAGES = {67: 0.50, 68: 0.60, 69: 0.70, 70: 0.80}
GROUPS = [5.5, 6.0, 7.0, 8.0, 9.0, 10.0]
BTS = [2.25, 3.00, 3.75]


def is_dash(t):
    t = t.strip()
    return t != '' and all(c in '-\u2212\u2013\u2014' for c in t)


def num(t):
    try:
        return float(t.strip().replace('\u2212', '-'))
    except ValueError:
        return None


def parse_page(words):
    head = next((w for w in words if w[4].startswith('L/')), None)
    frw = next((w for w in words if w[4] == 'Fr'), None)
    if head is None or frw is None:
        return None, '找不到 L/∇1/3 或 Fr 锚点'
    x_head, y_fr = head[0], frw[1]

    # 列组头（5.5…10.0）：x≈x_head，y<620
    grp = sorted([(w[1], num(w[4])) for w in words
                  if abs(w[0] - x_head) < 8 and num(w[4]) in GROUPS and w[1] < 620],
                 key=lambda t: -t[0])
    if [g[1] for g in grp] != GROUPS:
        return None, '分组头异常 %s' % [g[1] for g in grp]

    # B/T 列标签：x 在 (x_head, x_head+35)，y<620
    btl = sorted([(w[1], num(w[4])) for w in words
                  if x_head < w[0] < x_head + 35 and num(w[4]) in BTS and w[1] < 620],
                 key=lambda t: -t[0])
    if len(btl) != 18:
        return None, 'B/T 标签 %d 个（应 18）' % len(btl)
    col_y = [t[0] for t in btl]

    # 行标签（Fr 值）：y≈y_fr，x > x_fr
    rows = sorted([((w[0]+w[2])/2.0, num(w[4])) for w in words
                   if abs(w[1] - (y_fr - 6.4)) < 3 and w[0] > frw[0] + 12
                   and num(w[4]) is not None and 0.10 < num(w[4]) < 0.70],
                  key=lambda t: t[0])
    if not rows:
        return None, '找不到 Fr 行标签'

    out = []
    for x_row, fr in rows:
        cells = [None] * 18
        for w in words:
            xc = (w[0] + w[2]) / 2.0
            if abs(xc - x_row) > 4.0 or w[1] > y_fr - 25:
                continue
            txt = w[4]
            v = None if is_dash(txt) else num(txt)
            if v is None and not is_dash(txt):
                continue
            j = min(range(18), key=lambda k: abs(col_y[k] - w[1]))
            if abs(col_y[j] - w[1]) > 12 or cells[j] is not None:
                continue
            cells[j] = v
        out.append({'fr': fr, 'cells': cells})
    return {'rows': out, 'col_y': col_y}, None


def main():
    doc = pymupdf.open(SRC)
    res_all = {'schema': 'taylor-gertler-cr-1', 'units': 'CR x 1000',
               'axes': {'l_over_vol13': GROUPS, 'bt': BTS},
               'source': ('Mollard, Turnock & Hudson, Ship Resistance and Propulsion, '
                          'Appendix A3 Tables A3.8-A3.11 (pp. 495-498); '
                          'data after Gertler, DTMB Report 806 (1954)'),
               'tables': {}}
    for page_no, cp in PAGES.items():
        res, err = parse_page(doc[page_no - 1].get_text('words'))
        if err:
            print('page %d (Cp=%.2f) 失败: %s' % (page_no, cp, err))
            continue
        res_all['tables']['%.2f' % cp] = {'cp': cp, 'rows': res['rows']}
        full = sum(1 for r in res['rows'] if all(c is not None for c in r['cells']))
        miss = sum(1 for r in res['rows'] for c in r['cells'] if c is None)
        print('Cp=%.2f: %d 行（完整 %d 行，缺格 %d）' % (cp, len(res['rows']), full, miss))

    probe = res_all['tables'].get('0.50', {}).get('rows', [{}])[0]
    expect = [0.45, 0.54, 0.65, 0.38, 0.46, 0.55, 0.30, 0.33, 0.44,
              0.24, 0.28, 0.37, 0.22, 0.26, 0.34, 0.20, 0.25, 0.33]
    print('Fr=%.2f 行: %s' % (probe.get('fr', -1), probe.get('cells')))
    print('与肉眼确认一致:', probe.get('cells') == expect)

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(res_all, f, ensure_ascii=False, indent=1)
    print('written', OUT)


if __name__ == '__main__':
    main()
