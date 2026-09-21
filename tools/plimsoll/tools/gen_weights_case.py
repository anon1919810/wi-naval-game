# -*- coding: utf-8 -*-
"""从游戏模型数据生成 L2 重量分组案例（plimsoll-weights-1）。

来源链（每项都带 source，几何推得的一律 estimate）：
  厚度  queen_mary_v3/armour_zones.json   （wiki，per-zone source）
  范围  queen_mary_v3/object_manifest.json（包围盒按 role 选面 + 曲率系数，estimate）
  钢密度 7850 kg/m3（教科书常量，写入 params 并带出处）

跑法：python tools/plimsoll/tools/gen_weights_case.py > tools/plimsoll/cases/queen_mary_1913_weights.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(PKG))

STEEL_KG_M3 = 7850.0          # 钢密度；出处：造船学教科书常量（低碳钢 7850）
CURVE_FACTOR = 1.10           # 外板展开面积 / 投影面积；estimate
KEEL_Z = -9.9                 # 模型坐标：龙骨 z；KG 换算为自龙骨

# role → (选哪个包围盒面, 面数倍率, 曲率系数)
RULE = {
    'armour_belt':     ('side', 2, CURVE_FACTOR),
    'armour_deck':     ('deck', 1, 1.0),
    'armour_bulkhead': ('bulk', 1, 1.0),
    'barbette':        ('all4side', 1, 1.0),
    'conning_tower':   ('all4side', 1, 1.0),
}
NOT_ARMOUR = ('main_gun_barrel', 'gun_elevation')   # 炮管不是装甲


def face_area(d, which):
    x, y, z = d
    return {'side': y * z, 'deck': x * y, 'bulk': x * z,
            'all4side': 2 * (x + y) * z}[which]


def main():
    zones = json.load(open(os.path.join(REPO, 'queen_mary_v3', 'armour_zones.json'), encoding='utf-8'))
    zone_mm = dict(zip(zones['zone_ids'], zones['zone_mm']))
    zone_src = dict(zip(zones['zone_ids'], zones['zone_source']))
    name_zone = dict(zip(zones['name_contains'], zones['name_zone']))
    manifest = json.load(open(os.path.join(REPO, 'queen_mary_v3', 'object_manifest.json'), encoding='utf-8'))

    items = []
    for o in manifest['objects']:
        role = o.get('role', '')
        if role in NOT_ARMOUR or role not in RULE or 'bounds_world_m' not in o:
            continue
        b = o['bounds_world_m']
        d = [b['max'][i] - b['min'][i] for i in range(3)]
        cz = 0.5 * (b['max'][2] + b['min'][2])          # 重心近似 = 包围盒中心
        zone = name_zone.get(next((n for n in zones['name_contains'] if n in o['name']), 'unknown'), 'unknown')
        t_m = zone_mm.get(zone, 0) / 1000.0
        if t_m <= 0:
            continue
        which, mult, curve = RULE[role]
        area = face_area(d, which) * mult * curve
        mass_t = area * t_m * STEEL_KG_M3 / 1000.0
        items.append({
            'id': o['name'],
            'mass_t': round(mass_t, 3),
            'kg_m': round(cz - KEEL_Z, 3),
            'source': ('thickness: %s | extent: object_manifest bounds (role=%s, '
                       'face=%s x%d, curve=%.2f) | rho=%.0f kg/m3'
                       % (zone_src.get(zone, zone), role, which, mult, curve, STEEL_KG_M3)),
            'estimate': True,
            '_area_m2': round(area, 2),
            '_thickness_mm': round(t_m * 1000, 1),
        })

    case = {
        'schema': 'plimsoll-weights-1',
        'ship': 'HMS Queen Mary (1913)',
        'datum': 'keel',
        '_note': ('L2 重量分组 v0：目前只有装甲组是几何推得的实数据（全 estimate）；'
                  '其余组为空，等数据采集。生成器 tools/plimsoll/tools/gen_weights_case.py。'),
        'groups': [
            {'id': 'armour', 'label': '装甲', 'items': items},
            {'id': 'armament', 'label': '武备', 'items': [],
             '_note': '缺：炮塔/炮架重量、副炮弹重、弹药容量。弹重 1400 lb 已在 penetration_main.json'},
            {'id': 'machinery', 'label': '动力', 'items': [],
             '_note': '全缺：功率/锅炉/燃料无任何数据，需外部采集'},
            {'id': 'hull_outfit', 'label': '船体与舾装', 'items': [],
             '_note': '缺：钢料重量（可由型值表湿面积推，未做）'},
        ],
        'reference': {
            'displacement_normal_t': 26770,
            'displacement_source': 'Navypedia / Tyne Built Ships',
            'kg_estimate_m': 8.6,
            'kg_source': 'estimate（L0 案例同款；待本文件合成后替换）',
        },
    }
    json.dump(case, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
