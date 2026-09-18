"""Offline T9 penetration table checks (no Unity required)."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent
pen = json.loads((root / "penetration_main.json").read_text(encoding="utf-8"))
zones = json.loads((root / "armour_zones.json").read_text(encoding="utf-8"))

guns = {g["id"]: g for g in pen["guns"]}
assert "main_343mm" in guns and "secondary_102mm" in guns
main = guns["main_343mm"]
assert len(main["samples_m"]) == len(main["penetration_mm"])
assert main["penetration_mm"][0] > main["penetration_mm"][-1]

def interp(gun, r):
    s, p = gun["samples_m"], gun["penetration_mm"]
    if r <= s[0]:
        return p[0]
    if r >= s[-1]:
        return p[-1]
    for i in range(len(s) - 1):
        if s[i] <= r <= s[i + 1]:
            t = (r - s[i]) / max(1e-3, s[i + 1] - s[i])
            return p[i] + (p[i + 1] - p[i]) * t
    return p[-1]

# Near main gun penetrates 229mm belt; very far does not.
assert interp(main, 2000) > 229
assert interp(main, 20000) < 229
# Secondary cannot penetrate main belt at combat range.
assert interp(guns["secondary_102mm"], 3000) < 229
# Superstructure is soft.
assert interp(guns["secondary_102mm"], 2000) > 10

zone_ids = zones["zone_ids"]
zone_mm = zones["zone_mm"]
assert len(zone_ids) == len(zone_mm)
zm = dict(zip(zone_ids, zone_mm))
assert zm["belt_main"] == 229
assert zm["superstructure"] < zm["belt_main"]
assert len(zones["name_contains"]) == len(zones["name_zone"])
assert len(zones["compartment_key"]) == len(zones["compartment_mm"])
cm = dict(zip(zones["compartment_key"], zones["compartment_mm"]))
assert cm["Magazine_B"] == 229
assert cm["Steering_Gear"] == 25

def outcome(pen_mm, armour):
    if pen_mm >= armour:
        return "Penetrated"
    if pen_mm >= armour * 0.5:
        return "Partial"
    return "NoPenetration"

assert outcome(interp(main, 2000), zm["belt_main"]) == "Penetrated"
assert outcome(interp(main, 20000), zm["belt_main"]) == "NoPenetration"
assert outcome(interp(main, 20000), zm["superstructure"]) == "Penetrated"
assert outcome(interp(guns["secondary_102mm"], 2000), zm["superstructure"]) == "Penetrated"
assert outcome(interp(guns["secondary_102mm"], 2000), zm["belt_main"]) == "NoPenetration"

print("penetration_tables_ok")
print("main@2km pen=%.0fmm belt=%d -> %s" % (interp(main, 2000), zm["belt_main"], outcome(interp(main, 2000), zm["belt_main"])))
print("main@20km pen=%.0fmm belt=%d -> %s" % (interp(main, 20000), zm["belt_main"], outcome(interp(main, 20000), zm["belt_main"])))
print("sec@2km pen=%.0fmm belt=%d super=%d" % (interp(guns["secondary_102mm"], 2000), zm["belt_main"], zm["superstructure"]))
