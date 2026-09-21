# -*- coding: utf-8 -*-
"""生成 Guns 页案例（plimsoll-guns-1）—— Queen Mary 1913。

数量来自 queen_mary_v3/ship_contract.json（4 塔 × 2 管、16 门副炮，模型有源）；
单炮/炮座/弹/装药重量为外部文献值（NavWeaps / 维基 / Jutland 参战名录），逐项带出处。

已知矛盾（诚实记录）：
  - BII* 炮座 NavWeaps 未单列（Mark II = 600 t，BII* 为 N/A）→ 沿用 600 t，estimate。
  - 设计储弹 80 发/门（NavWeaps as-built）vs 战时 110 发/门（Jutland 名录）；
    Jutland 名录另称全舰弹药 allowance 661 t —— 与设计口径不符（战时加装所致）。
    本案例按 as-built 80 发/门（SPS 是设计工具，设计状态为基准口径）。
  - 副炮装药重未采集 → Magazine 只算弹重，偏低（核心会警告）。

跑法：python tools/plimsoll/tools/gen_guns_case.py > tools/plimsoll/cases/queen_mary_1913_guns.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

SRC_GUN = "NavWeaps WNBR_135-45_mk5: Gun Weight Without Breech 167,776 lbs (76,102 kg)"
SRC_MOUNT = ("NavWeaps Mount/Turret Data: Mark II 600 tons (610 mt)；"
             "BII* 未单列（N/A），沿用 Mark II 数值 —— estimate")
SRC_SHELL = "NavWeaps/维基: 1,400 lb (635.03 kg) Mk V(H) heavy shell；口径/门数: ship_contract.json"
SRC_CHARGE = "NavWeaps Propellant Charge - Ships: APC (Heavy) 297 lbs (135 kg) MD45"
SRC_GUN2 = "Military Wiki (BL 4-inch Mk VII): Mass 4,704 pounds (2,130 kg) (barrel & breech)"
SRC_SHELL2 = "维基/MaritimeQuest: 31 lb (14.06 kg)；16 门 casemate：ship_contract.json + 维基"
SRC_AMMO2 = "维基 (HMS Queen Mary): 150 rounds per gun"


def main():
    contract = json.load(open(os.path.join(REPO, 'queen_mary_v3', 'ship_contract.json'),
                              encoding='utf-8'))
    n_turrets = len(contract.get('turrets', []))
    n_barrels = sum(len(t.get('barrels', [])) for t in contract.get('turrets', []))

    case = {
        'schema': 'plimsoll-guns-1',
        'ship': 'HMS Queen Mary (1913)',
        '_note': ('Guns 页 v0：数量来自模型契约（%d 塔 × 2 管 = %d 管）；重量/弹药为文献值，逐项带出处。'
                  'Mounts 行 estimate（BII* 未单列）；Armour 行（炮塔装甲）缺 —— 模型无炮塔装甲对象；'
                  '副炮 Magazine 只算弹重（装药未采集）。战时口径（110 发/门 → 主炮 Magazine '
                  '≈ 677.6 t）与 Jutland 名录的 661 t 全舰弹药 allowance 见 PLAN/COVERAGE 讨论。'
                  % (n_turrets, n_barrels)),
        'batteries': [
            {
                'id': 'main_135mk5',
                'column': 'main',
                'label': '13.5in/45 BL Mk V(H)',
                'guns': n_barrels,
                'gun_weight_t': 76.102,
                'gun_source': SRC_GUN,
                'gun_estimate': False,
                'mounts': n_turrets,
                'mount_weight_t': 600.0,
                'mount_source': SRC_MOUNT,
                'mount_estimate': True,
                'shell_lb': 1400.0,
                'shell_source': SRC_SHELL,
                'shell_estimate': False,
                'charge_lb': 297.0,
                'rounds_per_gun': 80,
                'ammo_source': SRC_CHARGE + ' | 储弹: NavWeaps as-built 80 rounds/gun',
                'ammo_estimate': False,
                'broadside_guns': n_barrels,
                '_broadside_note': '四塔全中线布置，单舷 8 门齐射（狮级布局，academic/维基）',
            },
            {
                'id': 'secondary_4mk7',
                'column': '2nd',
                'label': '4in/50 BL Mk VII casemate',
                'guns': 16,
                'gun_weight_t': 2.134,
                'gun_source': SRC_GUN2,
                'gun_estimate': False,
                'shell_lb': 31.0,
                'shell_source': SRC_SHELL2,
                'shell_estimate': False,
                'rounds_per_gun': 150,
                'ammo_source': SRC_AMMO2,
                'ammo_estimate': False,
                'broadside_guns': 16,
                '_broadside_note': 'casemate 单舷齐射门数未单独考证，暂按 16 —— estimate',
            },
        ],
    }
    json.dump(case, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
