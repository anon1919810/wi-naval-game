# -*- coding: utf-8 -*-
"""通用性证明（2026-09-22）：Plimsoll 是通用求解器，不是 Queen Mary 专用机。

用一艘**与 QM 毫无关系的货船**（SS Testbed 1910，解析可控）走 L0/L2/Armour/Guns
全链路，全部锚在手算值上。若有人在核心里塞进任何具体船只的常量，本文件会变红。
"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

import hydrostatics as H  # noqa: E402
import weights as W       # noqa: E402
import armour as A        # noqa: E402
import guns as G          # noqa: E402

# ---- SS Testbed 1910：一艘 90 m 沿海货船（纯解析构造，无任何史实包袱）
L, B, T, CB, CWP = 90.0, 13.0, 5.5, 0.72, 0.82
RHO = 1.025

TESTBED_HULL = {
    "lwl_m": L, "loa_m": 92.0, "beam_m": B,
    "draught_normal_m": T, "block_coeff": CB, "waterplane_coeff": CWP,
}


def testbed_weights():
    """四组全覆盖：KG = 22670/4700 = 4.8234042553…（手算锚）。"""
    return {
        "schema": "plimsoll-weights-1",
        "datum": "keel",
        "groups": [
            {"id": "hull", "items": [
                {"id": "steel", "mass_t": 3000.0, "kg_m": 5.0, "source": "解析"}]},
            {"id": "machinery", "items": [
                {"id": "engine", "mass_t": 800.0, "kg_m": 4.0, "source": "解析"}]},
            {"id": "outfit", "items": [
                {"id": "fitting", "mass_t": 300.0, "kg_m": 6.5, "source": "解析"}]},
            {"id": "cargo", "items": [
                {"id": "load", "mass_t": 600.0, "kg_m": 4.2, "source": "解析"}]},
        ],
        "reference": {"displacement_normal_t": 4749.03},
    }


class TestL0AnalyticSteamer(unittest.TestCase):
    def setUp(self):
        self.r = H.compute(TESTBED_HULL)
        self.v = self.r["values"]

    def test_displacement_exact(self):
        """∇ = 0.72·90·13·5.5 = 4633.2 m³；Δ = ×1.025 = 4749.03 t。"""
        self.assertAlmostEqual(self.v["displacement_volume_m3"], 4633.2, places=9)
        self.assertAlmostEqual(self.v["displacement_t"], 4749.03, places=9)

    def test_awp_tpc_exact(self):
        """Awp = 0.82·90·13 = 959.4 m²；TPC = 959.4×1.025/100 = 9.83385。"""
        self.assertAlmostEqual(self.v["awp_m2"], 959.4, places=9)
        self.assertAlmostEqual(self.v["tpc_t_per_cm"], 9.83385, places=9)

    def test_km_kb_bm_consistent(self):
        """KM − KB = BM 必须精确成立（同一几何的两面）。"""
        self.assertAlmostEqual(self.v["km_m"] - self.v["kb_m"], self.v["bm_t_m"], places=9)

    def test_positive_stability_range(self):
        """小船也要有正的稳性范围：KB < KM，且 GM 随 KG 单调。"""
        self.assertLess(self.v["kb_m"], self.v["km_m"])
        rows = H.sensitivity_kg(TESTBED_HULL, [2.0, 3.0, 4.0])
        self.assertTrue(rows[0]["gm_m"] > rows[1]["gm_m"] > rows[2]["gm_m"])


class TestL2FullCoverageSteamer(unittest.TestCase):
    def test_synthesis_exact(self):
        r = W.synthesize(testbed_weights())
        self.assertAlmostEqual(r["values"]["total_mass_t"], 4700.0, places=9)
        self.assertAlmostEqual(r["values"]["kg_m"], 22670.0 / 4700.0, places=9)

    def test_full_coverage_allows_gm(self):
        """覆盖率 99.0% ≥ 95%：GM 闸门放行 —— 与 QM 的『拒绝算 GM』形成对照。"""
        r = W.gm_from_km(testbed_weights(), km_m=5.6)
        self.assertAlmostEqual(r["values"]["gm_m"], 5.6 - 22670.0 / 4700.0, places=9)
        self.assertEqual([w for w in r["warnings"] if "不能当全船" in w], [])


class TestArmourGunsGenericSteamer(unittest.TestCase):
    def test_armour_analytic(self):
        """带式装甲 100×6 m×152 mm + 甲板 90×13 m×25 mm，手算锚。"""
        case = {
            "schema": "plimsoll-armour-1",
            "rho_kg_m3": 7850.0,
            "rows": [
                {"id": "belt", "group": "main", "thickness_mm": 152,
                 "length_m": 100.0, "height_m": 6.0, "source": "解析"},
                {"id": "deck", "group": "armour_deck", "thickness_mm": 25,
                 "area_m2": 90.0 * 13.0, "source": "解析"},
            ],
        }
        r = A.compute(case)
        belt = 100.0 * 6.0 * 0.152 * 7850.0 / 1000.0
        deck = 1170.0 * 0.025 * 7850.0 / 1000.0
        self.assertAlmostEqual(r["rows"][0]["weight_t"], belt, places=9)
        self.assertAlmostEqual(r["rows"][1]["weight_t"], deck, places=9)
        self.assertAlmostEqual(r["values"]["total_armour_t"], belt + deck, places=9)

    def test_guns_analytic(self):
        """2 门 5 t 炮 + 1 座 20 t 炮座；齐射 2×50 lb；弹库 2×100×(50+10) lb。"""
        case = {
            "schema": "plimsoll-guns-1",
            "batteries": [{
                "id": "single", "column": "main",
                "guns": 2, "gun_weight_t": 5.0,
                "mounts": 1, "mount_weight_t": 20.0,
                "shell_lb": 50.0, "charge_lb": 10.0,
                "rounds_per_gun": 100, "broadside_guns": 2,
            }],
        }
        r = G.compute(case)
        self.assertAlmostEqual(r["values"]["guns_t"], 10.0, places=9)
        self.assertAlmostEqual(r["values"]["mounts_t"], 20.0, places=9)
        self.assertAlmostEqual(r["values"]["broadside_kg"], 100.0 * G.LB_TO_KG, places=9)
        self.assertAlmostEqual(r["values"]["magazine_t"],
                               2 * 100 * 60.0 * G.LB_TO_KG / 1000.0, places=9)


class TestGeneralityContract(unittest.TestCase):
    """契约本身也要有测试：核心模块里不许出现具体船只的字面常量。"""

    CORE_FILES = ("hydrostatics.py", "geometric.py", "geometry.py", "offsets.py",
                  "weights.py", "armour.py", "guns.py", "freesurface.py",
                  "damage.py", "hull.py", "cli.py")

    FORBIDDEN = ("26770", "31650", "76.102", "queen_mary_v4.py\",", "212.8")

    def test_no_ship_literals_in_core(self):
        """扫核心源码：QM 的位移/炮重/舰长等字面量不得出现（注释/文档除外由评审把关，
        这里拦的是会被当代码执行的数值与路径）。"""
        pkg = os.path.dirname(PKG)  # 仓库 tools/ 下层是 plimsoll 包
        for fn in self.CORE_FILES:
            path = os.path.join(PKG, fn)
            with open(path, encoding="utf-8") as f:
                src = f.read()
            for lit in self.FORBIDDEN:
                self.assertNotIn(lit, src, "%s 里出现了船只专属字面量 %r" % (fn, lit))

    def test_qm_offsets_materialized(self):
        """QM 的型线必须物化为案例 JSON，CLI 运行时不再解析生成脚本。"""
        p = os.path.join(PKG, "cases", "queen_mary_1913_offsets.json")
        with open(p, encoding="utf-8") as f:
            payload = json.load(f)
        self.assertEqual(payload["schema"], "plimsoll-offsets-1")
        self.assertGreaterEqual(len(payload["stations"]), 5)

    def test_second_ship_case_exists(self):
        """至少存在一个非 QM 的完整案例（通用性的活证据）。"""
        p = os.path.join(PKG, "cases", "generic_test_steamer_1910.json")
        with open(p, encoding="utf-8") as f:
            case = json.load(f)
        self.assertNotIn("Queen Mary", case.get("name", ""))
        r = H.compute(case["hull"])
        self.assertAlmostEqual(r["values"]["displacement_t"], 4749.03, places=9)


if __name__ == "__main__":
    unittest.main()
