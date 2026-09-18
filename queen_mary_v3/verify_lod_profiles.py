"""Offline check for lod_profiles.json + Unity-style relH mapping (no Unity required)."""
import json
import math
from pathlib import Path

root = Path(__file__).resolve().parent
data = json.loads((root / "lod_profiles.json").read_text(encoding="utf-8"))
assert data["ship_id"] == "HMS_Queen_Mary_1913"
assert len(data["profiles"]) >= 2
assert data["default_profile"] == "tactical_50_200m"

def relH(size, bias, d, fov):
    return size * bias / (2 * d * math.tan(math.radians(fov) / 2))

def level(rel, heights):
    for i, h in enumerate(heights):
        if rel >= h:
            return i
    return len(heights)

rows = []
for p in data["profiles"]:
    heights = p["screenHeights"][:4]
    assert len(heights) == 4
    bias = p["recommendedLodBias"]
    for e in p["expectedAt"]:
        # Use measured-size placeholder 40 m (bounds height) AND length-like 214 m for sensitivity.
        for size in (40.0, 214.0):
            r = relH(size, bias, e["distance_m"], e["fov_deg"])
            lv = level(r, heights)
            rows.append((p["id"], size, e["distance_m"], r, lv, e["expectedLod"]))

# Tactical at 50-200m with size=214 should stay LOD0 under default authoring.
tac = [r for r in rows if r[0] == "tactical_50_200m" and r[1] == 214.0]
assert all(r[4] == 0 for r in tac if r[2] <= 200), tac
# Fleet profile at 1700m size=214 bias=1 should reach at least LOD1 under fleet heights.
fleet = [r for r in rows if r[0] == "fleet_1_2km" and r[1] == 214.0 and r[2] == 1700.0][0]
assert fleet[4] >= 1, fleet

print("lod_profile_math_ok")
for row in rows:
    print("profile=%s size=%.0f d=%.0f relH=%.4f level=%s expected=%s" % row)
