#!/usr/bin/env python3
"""阶段 4.4：批量跑 damage_scenarios.json 并落盘（可复现）。"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import damage as D  # noqa: E402
import geometry as G  # noqa: E402


def load_hull(hull_cfg: dict):
    kind = hull_cfg.get("kind", "reference")
    if kind == "reference":
        return G.make_reference_hull(
            L=hull_cfg["L"], B=hull_cfg["B"], T=hull_cfg["T"],
            Cb=hull_cfg["Cb"], Cwp=hull_cfg["Cwp"],
            depth=hull_cfg.get("depth"),
            n_stations=int(hull_cfg.get("n_stations", 81)),
        )
    raise ValueError("未知 hull.kind=%r" % kind)


def run_all(scenarios_path=None, out_dir=None):
    if scenarios_path is None:
        scenarios_path = os.path.join(HERE, "cases", "damage_scenarios.json")
    if out_dir is None:
        out_dir = os.path.join(HERE, "cases", "out")
    os.makedirs(out_dir, exist_ok=True)
    with open(scenarios_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    hull = load_hull(data["hull"])
    ship = data["ship_baseline"]
    results = []
    for sc in data["scenarios"]:
        sc_full = {"id": sc["id"], "ship": ship, "tanks": sc["tanks"]}
        out = D.run_damage_scenario(hull, sc_full)
        path = os.path.join(out_dir, "%s.result.json" % sc["id"])
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2, sort_keys=True)
        results.append({"id": sc["id"], "path": path, "stable": out["stable"]})
        print("scenario %s -> %s stable=%s" % (sc["id"], path, out["stable"]))
    return results


if __name__ == "__main__":
    run_all()
