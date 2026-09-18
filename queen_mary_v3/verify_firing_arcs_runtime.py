"""Offline checks for T6 firing-arc yaw queries (no Unity required)."""
import json
import math
from pathlib import Path

root = Path(__file__).resolve().parent
data = json.loads((root / "firing_arcs.unity.json").read_text(encoding="utf-8"))
turrets = {t["key"]: t for t in data["turrets"]}
assert set(turrets) == {"A", "B", "Q", "X"}

def normalize(v):
    v = v % 360.0
    return v + 360.0 if v < 0 else v

def contains(iv, yaw):
    a, b = normalize(iv["a"]), normalize(iv["b"])
    y = normalize(yaw)
    if abs(a - b) < 1e-6:
        return True
    if a <= b:
        return a - 1e-3 <= y <= b + 1e-3
    return y >= a - 1e-3 or y <= b + 1e-3

def is_clear(key, yaw, elev):
    t = turrets[key]
    samples = t["by_elevation"]
    best = min(samples, key=lambda e: abs(e["elevation_deg"] - elev))
    return any(contains(iv, yaw) for iv in best["intervals"])

# A at 0° elev: blocked roughly 130-215
assert is_clear("A", 0, 0)
assert is_clear("A", 90, 0)
assert not is_clear("A", 180, 0)
assert is_clear("A", 220, 0)
# Q rest 180, elev 0: intervals 0-140 and 205-355 → command 180 blocked
assert not is_clear("Q", 180, 0)
assert is_clear("Q", 0, 0)
assert is_clear("Q", 250, 0)
# X at high elev nearly all-around
assert is_clear("X", 180, 20)

print("firing_arcs_runtime_ok")
print("A@180/0 blocked, Q@180/0 blocked, X@180/20 clear")
