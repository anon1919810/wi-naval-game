# -*- coding: utf-8 -*-
"""生成 Freeboard 页案例（plimsoll-freeboard-1）—— Queen Mary 1913。

**数据全部由模型推得，外部文献没有型深/干舷**（Navypedia/维基均不列）→ 全标 estimate。

来源链：
  甲板面高  object_manifest.json 的 Forecastle / Quarterdeck 对象包围盒 z 上界
  分段长度  同一批对象的 y 跨度 ÷ 船体 y 总跨度（模型全长 213.4 ≈ LOA；Lwl 212.8 差 0.3%）
  水线位置  Hull 对象 z_min = −9.90（龙骨）；设计水线 z=0 ⇔ 满载吃水 9.9；
            正常吃水 8.5 → 水线 z = −1.40
  因此     干舷 = 甲板面 z − 水线 z

⚠️ 模型不区分「甲板板面」与「舷墙/上层结构」：Forecastle 对象 z[5.05, 7.50]，
   取上表面 7.50 为甲板面（下表面 5.05 与 Hull 甲板 5.10 基本连续）。
   舷弧（sheer）在模型里是平的 → 每段艏艉干舷相同，这是模型局限，已在案例中写明。

跑法：python tools/plimsoll/tools/gen_freeboard_case.py > tools/plimsoll/cases/queen_mary_1913_freeboard.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(PKG))
sys.path.insert(0, PKG)

import offsets as OF  # noqa: E402

# 要看的甲板对象：(对象名, SPS kind)
DECK_OBJECTS = (("Forecastle", "forecastle"), ("Quarterdeck", "quarterdeck"))


def main():
    manifest = json.load(open(os.path.join(REPO, 'queen_mary_v3', 'object_manifest.json'),
                              encoding='utf-8'))
    ship = json.load(open(os.path.join(PKG, 'cases', 'queen_mary_1913.json'), encoding='utf-8'))
    hull = ship['hull']
    lwl = float(hull['lwl_m'])
    beam = float(hull['beam_m'])
    t_normal = float(hull['draught_normal_m'])
    t_deep = float(hull['draught_deep_m'])

    obj = {o['name']: o for o in manifest['objects']}
    hb = obj['Hull']['bounds_world_m']
    keel_z = hb['min'][2]
    span_y = hb['max'][1] - hb['min'][1]
    wl_normal_z = keel_z + t_normal       # 正常吃水对应的水线 z
    wl_deep_z = keel_z + t_deep           # 应为 0

    segments = []
    for name, kind in DECK_OBJECTS:
        b = obj[name]['bounds_world_m']
        deck_z = b['max'][2]
        pct = 100.0 * (b['max'][1] - b['min'][1]) / span_y
        segments.append({
            'id': name.lower(),
            'kind': kind,
            'length_pct_lwl': round(pct, 2),
            'fb_fore_m': round(deck_z - wl_normal_z, 3),
            'fb_aft_m': round(deck_z - wl_normal_z, 3),
            'source': ('depth: 模型 %s 对象包围盒 z[%.2f, %.2f]，取上表面 %.2f 为甲板面'
                       '（下表面 %.2f 与 Hull 甲板 %.2f 连续，模型未区分板厚/舷墙）；'
                       'waterline: Hull z_min=%.2f（龙骨）+ 正常吃水 %.1f → z=%.2f；'
                       'length: 同对象 y 跨度 ÷ 船体 y 总跨度 %.1f'
                       % (name, b['min'][2], b['max'][2], deck_z, b['min'][2], hb['max'][2],
                          keel_z, t_normal, wl_normal_z, span_y)),
            'estimate': True,
        })

    case = {
        'schema': 'plimsoll-freeboard-1',
        'ship': 'HMS Queen Mary (1913)',
        'lwl_m': lwl,
        'beam_m': beam,
        '_note': ('Freeboard 页 v0：**型深/干舷无外部文献源**（Navypedia/维基均不列），'
                  '全部由模型包围盒推得 → 全 estimate。型深 = Hull z[%.2f, %.2f] = %.2f m；'
                  '正常吃水 %.1f → 水线 z=%.2f，满载 %.1f → z=%.2f。'
                  '模型舷弧为平（段内艏艉同值），真实舷弧未考证；'
                  '甲板分段只有 Forecastle/Quarterdeck 两段（模型就这两段），'
                  'Fore/Aft 细分段与 sheer、甲板型、船首/船艉型、Ram length、'
                  'Stern overhang 均为缺口。' % (keel_z, hb['max'][2], hb['max'][2] - keel_z,
                                                t_normal, wl_normal_z, t_deep, wl_deep_z)),
        'segments': segments,
    }
    json.dump(case, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
