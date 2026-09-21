# -*- coding: utf-8 -*-
"""生成 Weapons 页案例（plimsoll-weapons-1）—— Queen Mary 1913。

来源（逐项带出处）：
  鱼雷管  2 × 533 mm 水下舷侧（Navypedia「2 - 533 TT (beam)」；
          维基「two 21-inch submerged torpedo tubes, one on each broadside」）
  携带数  14 枚 Mk II***（维基 HMS Queen Mary）
  战斗部  400 lb (181 kg) TNT（维基）⚠️ 冲突：MaritimeQuest 记 515 lb TNT
  射程    4,500 yd @ 45 kn / 10,000 yd @ 29 kn（维基）⚠️ 冲突：MaritimeQuest 10,750 yd @ 31 kn

**未采集（置空，不猜）**：单雷全重、雷长（SPS 字段）、水雷、深弹、Misc weight 五分区。
  水雷/深弹 1913 年是否装备未见文献源 → 不给 0，置空由核心报警。

跑法：python tools/plimsoll/tools/gen_weapons_case.py > tools/plimsoll/cases/queen_mary_1913_weapons.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)

SRC_TUBES = "Navypedia: 2 - 533 TT (beam)；维基: two 21-inch submerged tubes, one each broadside"
SRC_CARRIED = "维基 HMS Queen Mary: Fourteen Mk II*** torpedoes were carried"
SRC_WARHEAD = ("维基: 400 lb (181 kg) TNT warhead；⚠️ 冲突 MaritimeQuest 记 515 lb TNT，"
               "取维基（1913 年状态）")
SRC_RANGE = ("维基: 4,500 yd @ 45 kn / 10,000 yd @ 29 kn；"
             "⚠️ 冲突 MaritimeQuest 10,750 yd @ 31 kn")


def main():
    case = {
        "schema": "plimsoll-weapons-1",
        "ship": "HMS Queen Mary (1913)",
        "displacement_normal_t": 26770,
        "_note": ("Weapons 页 v0：鱼雷数据有源（管数/携带数/战斗部），"
                  "**单雷全重与雷长未采集** → 置空（核心会警告：不能用装药重冒充全重）。"
                  "水雷/深弹 1913 年是否装备未见文献源 → 置空不给 0。"
                  "Misc weight 五分区全无数据 → 置空；且分区重量无 kg_m，接 L2 前必须先补重心高。"),
        "torpedo_batteries": [{
            "id": "main_torpedo",
            "tubes": 2,
            "carried": 14,
            "diameter_mm": 533.0,
            "warhead_kg": 181.0,
            "arrangement": "submerged beam（两舷各一）",
            "source": "管数: %s | 携带: %s | 战斗部: %s | 射程: %s" % (
                SRC_TUBES, SRC_CARRIED, SRC_WARHEAD, SRC_RANGE),
            "estimate": False,
        }],
    }
    json.dump(case, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
