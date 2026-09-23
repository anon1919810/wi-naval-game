"""Finish only the bounded generic-flooding workload after the 60 s probe was canceled.

The first six workloads in core-performance-benchmark.json were already
measured before the hydraulic-equilibrium fix. Keep their exact measurements
and mark the source phase; do not silently present them as post-fix timings.
"""

import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

from core_performance_benchmark import TREE, flooding_workload


OUT = Path(__file__).with_name("core-performance-benchmark.json")


def sha256(path):
    return hashlib.sha256((TREE / path).read_bytes()).hexdigest()


def main():
    evidence = json.loads(OUT.read_text(encoding="utf-8"))
    evidence["workloads"]["flooding_generic_two_connected"] = flooding_workload(
        "generic-two-connected", "flooding_generic_two_connected", duration_s=10.0)
    evidence["measurement_phases"] = {
        "cold_start_through_flooding_queen_mary_single_proxy_10s":
            "pre_hydraulic_equilibrium_fix; retained as representative timings, not final-source benchmarks",
        "flooding_generic_two_connected":
            "post_fix_bounded_class_sps_workload",
    }
    evidence["short_finish_measured_at_utc"] = datetime.now(timezone.utc).isoformat()
    evidence["short_finish_source_sha256"] = {
        key: sha256(key) for key in (
            "tools/plimsoll/flooding.py",
            "tools/plimsoll/cases/projects/generic_flooding_box.project.json",
            "tools/plimsoll/cases/projects/damage-presets.json",
        )
    }
    OUT.write_bytes(json.dumps(evidence, ensure_ascii=False, indent=1).replace("\n", "\r\n").encode("utf-8"))
    result = evidence["workloads"]["flooding_generic_two_connected"]
    print(json.dumps({"median_s": result["median_s"], "max_s": result["max_s"],
                      "status": result["result"]["status"],
                      "stop_reason": result["result"]["stop_reason"],
                      "accepted_duration_s": result["result"]["accepted_duration_s"]}))


if __name__ == "__main__":
    main()
