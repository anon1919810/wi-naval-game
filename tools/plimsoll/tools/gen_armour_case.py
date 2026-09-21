# -*- coding: utf-8 -*-
"""从游戏模型数据生成 Armour 页案例（plimsoll-armour-1）。

**与 L2 同源**：直接 import gen_weights_case 的选面规则（RULE/face_area/密度/曲率），
保证本文件算出的装甲总重与 weights.py 装甲组一致（一致性由 test_armour.py 把守）。

来源链（每项都带 source，几何推得的一律 estimate）：
  厚度  queen_mary_v3/armour_zones.json   （wiki，per-zone source）
  范围  queen_mary_v3/object_manifest.json（包围盒按 role 选面 + 曲率系数，estimate）
  长高  同一包围盒在 zone 内取 union 的 Y 跨（长）/ Z 跨（高），只作展示口径
  钢密度 7850 kg/m3（教科书常量）

跑法：python tools/plimsoll/tools/gen_armour_case.py > tools/plimsoll/cases/queen_mary_1913_armour.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(PKG))
sys.path.insert(0, HERE)

from gen_weights_case import (  # noqa: E402  与 L2 同源，勿在此复制常量
    CURVE_FACTOR, KEEL_Z, NOT_ARMOUR, RULE, STEEL_KG_M3, face_area,
)

# zone → SPS 行/分组（armour.VALID_GROUPS 的子集；bulge 无对应分区，由核心报警告）
ZONE_TO_GROUP = {
    'belt_main': 'main',
    'belt_taper': 'ends',
    'upper_belt': 'upper',
    'bulkhead': 'torpedo_bulkhead',
    'deck_armour': 'armour_deck',
    'deck_lower': 'armour_deck',
    'barbette': 'barbette',
    'turret_face': 'turret',
    'conning_tower': 'conning_tower',
    'uptake': 'other',
    'secondary_casemate': 'other',
    'superstructure': 'other',
    'hull_unprotected': 'other',
    'unknown': 'other',
}


def main():
    zones = json.load(open(os.path.join(REPO, 'queen_mary_v3', 'armour_zones.json'), encoding='utf-8'))
    zone_mm = dict(zip(zones['zone_ids'], zones['zone_mm']))
    zone_src = dict(zip(zones['zone_ids'], zones['zone_source']))
    name_zone = dict(zip(zones['name_contains'], zones['name_zone']))
    order = {z: i for i, z in enumerate(zones['zone_ids'])}
    manifest = json.load(open(os.path.join(REPO, 'queen_mary_v3', 'object_manifest.json'), encoding='utf-8'))

    # 按 zone 聚合：面积累加（逐对象选面），长/高取 union 包围盒的 Y/Z 跨
    acc = {}
    for o in manifest['objects']:
        role = o.get('role', '')
        if role in NOT_ARMOUR or role not in RULE or 'bounds_world_m' not in o:
            continue
        zone = name_zone.get(next((n for n in zones['name_contains'] if n in o['name']), 'unknown'), 'unknown')
        t_m = zone_mm.get(zone, 0) / 1000.0
        if t_m <= 0:
            continue
        b = o['bounds_world_m']
        d = [b['max'][i] - b['min'][i] for i in range(3)]
        which, mult, curve = RULE[role]
        area = face_area(d, which) * mult * curve
        a = acc.setdefault(zone, {'area': 0.0, 'n': 0, 'roles': set(),
                                  'min_y': b['min'][1], 'max_y': b['max'][1],
                                  'min_z': b['min'][2], 'max_z': b['max'][2]})
        a['area'] += area
        a['n'] += 1
        a['roles'].add(role)
        a['min_y'] = min(a['min_y'], b['min'][1]); a['max_y'] = max(a['max_y'], b['max'][1])
        a['min_z'] = min(a['min_z'], b['min'][2]); a['max_z'] = max(a['max_z'], b['max'][2])

    rows = []
    for zone in sorted(acc, key=lambda z: order.get(z, 99)):
        a = acc[zone]
        rows.append({
            'id': zone,
            'group': ZONE_TO_GROUP[zone],
            'thickness_mm': zone_mm[zone],
            'area_m2': round(a['area'], 2),
            'length_m': round(a['max_y'] - a['min_y'], 2),   # 船长方向（Y 跨），展示口径
            'height_m': round(a['max_z'] - a['min_z'], 2),   # 垂向（Z 跨，模型坐标），展示口径
            'source': ('thickness: %s | extent: object_manifest bounds '
                       '(n=%d objects, roles=%s, face by role, curve=%.2f) | rho=%.0f kg/m3'
                       % (zone_src.get(zone, zone), a['n'], ','.join(sorted(a['roles'])),
                          CURVE_FACTOR, STEEL_KG_M3)),
            'estimate': True,
        })

    case = {
        'schema': 'plimsoll-armour-1',
        'ship': 'HMS Queen Mary (1913)',
        'rho_kg_m3': STEEL_KG_M3,
        'rho_source': '造船学教科书常量（低碳钢 7850 kg/m3）',
        '_note': ('Armour 页 v0：厚度带 wiki 来源；面积由模型包围盒按 role 选面（全 estimate），'
                  '与 L2 weights 装甲组同源同规则。Length/Height 为 zone 内 union 包围盒的'
                  '展示口径（SPS 里是用户输入，此处为推得值）。SPS Bulge 行无对应分区'
                  '（1913 设计无防雷凸舱）。Armour deck 按厚度层出两行（64/25 mm），'
                  '按位置分段（Forecastle/Fore&aft/Quarter）为已知缺口。'
                  'turret_face（9in 炮塔面）在 object_manifest 里无选面 role 对象，'
                  '炮塔装甲未计入（L2 同），待补炮塔重量数据。'),
        'rows': rows,
    }
    json.dump(case, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
