import json
from pathlib import Path

src = Path(r"C:\Users\杨睿\Desktop\HMS_Queen_Mary_建模成果_2026-09-17\queen_mary_v3\firing_arcs.json")
data = json.loads(src.read_text(encoding="utf-8"))
out = {
    "method": data.get("method"),
    "accuracy": data.get("accuracy"),
    "clearance_required_m": data.get("clearance_required_m"),
    "increment_deg": data.get("increment_deg"),
    "note": data.get("note"),
    "turrets": [],
}
for key, t in data.get("turrets", {}).items():
    elevs = []
    for elev_s, payload in t.get("by_elevation", {}).items():
        intervals = [
            {"a": float(pair[0]), "b": float(pair[1])}
            for pair in payload.get("allowed_yaw_intervals_deg", [])
        ]
        elevs.append({
            "elevation_deg": float(elev_s),
            "clear_fraction": payload.get("clear_fraction"),
            "intervals": intervals,
        })
    elevs.sort(key=lambda e: e["elevation_deg"])
    out["turrets"].append({
        "key": key,
        "zero_bearing": t.get("zero_bearing"),
        "rest_yaw_deg": float(t.get("rest_yaw_deg", 0)),
        "by_elevation": elevs,
    })
text = json.dumps(out, indent=2, ensure_ascii=False)
for p in [
    Path(r"C:\Users\杨睿\Desktop\HMS_Queen_Mary_建模成果_2026-09-17\queen_mary_v3\firing_arcs.unity.json"),
    Path(r"D:\Unity\Projects\QueenMaryNaval\QueenMaryNaval\Assets\Resources\Ships\HMS_Queen_Mary_1913\firing_arcs.unity.json"),
]:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    print("wrote", p, p.stat().st_size)
print("turrets", [t["key"] for t in out["turrets"]])
