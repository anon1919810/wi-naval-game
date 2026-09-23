"""Write the 45-item core-only evidence audit without hiding deferred work."""

from collections import Counter
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[3]
DOCS = ROOT / "docs/plimsoll-1.0"
INVENTORY = DOCS / "evidence/core-acceptance-inventory.json"

EVIDENCE = {
    "A1": ["evidence/initial-worktree-snapshot.json", "交接_Plimsoll核心_2026-09-23.md"],
    "A2": ["current-core-scope.md", "current-status.md", "evidence/seven-page-binding-proposal.json"],
    "A3": ["data-contract.md", "../../tools/plimsoll/tests/test_project_io.py", "../../tools/plimsoll/tests/test_analysis.py"],
    "A4": ["project-extensions.md", "page-rows-contract.md", "../../tools/plimsoll/tests/test_completion_weapons.py"],
    "A5": ["cli.md", "../../tools/plimsoll/tests/test_core_cli.py", "../../tools/plimsoll/tests/test_exports.py"],
    "A6": ["project-store.md", "../../tools/plimsoll/tests/test_project_io.py", "../../tools/plimsoll/tests/test_project_store.py"],
    "B1": ["loading-contract.md", "../../tools/plimsoll/tests/test_weights.py", "../../tools/plimsoll/tests/test_completion_weapons.py"],
    "B2": ["../../tools/plimsoll/tests/test_loading.py", "../../tools/plimsoll/tests/test_project_store.py"],
    "B3": ["page-rows-contract.md", "../../tools/plimsoll/tests/test_systems_integration.py", "../../tools/plimsoll/tests/test_completion_weapons.py"],
    "B4": ["../../tools/plimsoll/tests/test_loading.py", "../../tools/plimsoll/tests/test_analysis_cases.py"],
    "B5": ["case-sources.md", "../../tools/plimsoll/tests/test_calculation_integrity.py"],
    "B6": ["case-sources.md", "../../tools/plimsoll/tests/test_project_cases.py", "../../tools/plimsoll/tests/test_completion_engines.py"],
    "C1": ["geometry-analysis-validation.md", "../../tools/plimsoll/tests/test_geometry_analysis.py"],
    "C2": ["coupled-stability-contract.md", "../../tools/plimsoll/tests/test_trim_equilibrium.py"],
    "C3": ["../../tools/plimsoll/tests/test_analysis_cases.py", "../../tools/plimsoll/tests/test_stability_loading.py"],
    "C4": ["stability-api.md", "../../tools/plimsoll/tests/test_freesurface.py", "../../tools/plimsoll/tests/test_freeboard.py"],
    "C5": ["../../tools/plimsoll/tests/test_stability_loading.py", "../../tools/plimsoll/tests/test_analysis.py"],
    "C6": ["../../tools/plimsoll/tests/test_analysis.py", "coupled-stability-contract.md"],
    "D1": ["tank-contract.md", "flooding-api.md", "../../tools/plimsoll/tests/test_flooding.py"],
    "D2": ["../../tools/plimsoll/tests/test_damage_loop.py", "../../tools/plimsoll/tests/test_analysis_flooding.py"],
    "D3": ["flooding-validation-design.md", "../../tools/plimsoll/tests/test_flood_combination.py", "../../tools/plimsoll/tests/test_completion_flooding.py"],
    "D4": ["flooding-api.md", "../../tools/plimsoll/tests/test_flooding.py", "../../tools/plimsoll/tests/test_completion_flooding.py"],
    "D5": ["tank-validation-design.md", "../../tools/plimsoll/tests/test_tank_geometry.py"],
    "D6": ["flooding-api.md", "../../tools/plimsoll/tests/test_analysis_flooding.py"],
    "E1": ["evidence/seven-page-binding-proposal.json", "page-rows-contract.md"],
    "E2": ["systems-resistance-contract.md", "page-rows-contract.md", "../../tools/plimsoll/tests/test_completion_belt.py"],
    "E3": ["../../tools/plimsoll/tests/test_completion_engines.py", "../../tools/plimsoll/tests/test_engines.py"],
    "E4": ["taylor-benchmark-design.md", "../../tools/plimsoll/tests/test_resistance.py", "../../tools/plimsoll/tests/test_analysis_resistance.py"],
    "E5": ["resistance-benchmark-design.md", "../../tools/plimsoll/tests/test_holtrop.py"],
    "E6": ["systems-resistance-contract.md", "../../tools/plimsoll/tests/test_analysis_resistance.py"],
    "F1": ["analysis-api.md", "cli.md", "../../tools/plimsoll/tests/test_core_cli.py"],
    "F4": ["export-api.md", "../../tools/plimsoll/tests/test_exports.py"],
    "F6": ["package-api.md", "../../tools/plimsoll/tests/test_package_imports.py"],
    "G1": ["../../tools/plimsoll/run_all_tests.py", "../../tools/plimsoll/tests/test_generic_ship.py", "../../tools/plimsoll/tests/test_analysis_cases.py", "evidence/core-final-regression.log"],
    "G2": ["resistance-benchmark-design.md", "geometry-analysis-validation.md", "evidence/task-4-numerical-evidence.json"],
    "G3": ["equilibrium-validation-design.md", "flooding-validation-design.md"],
    "G4": ["evidence/task-4-mutation-evidence.json", "evidence/task-4-numerical-evidence.json"],
    "G5": ["core-performance-validation.md", "evidence/core-performance-benchmark.json"],
    "G6": ["../../tools/plimsoll/tools/gen_project_cases.py", "../../tools/plimsoll/tests/test_project_store.py", "../../tools/plimsoll/tests/test_core_cli.py"],
    "G7": ["current-core-scope.md", "analysis-api.md", "data-contract.md", "交接_Plimsoll核心_2026-09-23.md"],
    "G8": ["evidence/initial-worktree-snapshot.json", "交接_类SPS计算核心_2026-09-23.md"],
}
DEFERRED = {"F2", "F3", "F5", "F7"}
CORE_PRESENTATION = {"A5", "D6", "F4", "F6", "G5", "G7"}
LIMITS = {
    "A4": "Derived views retain method/source where available; unknown values stay null. No claim of historical certification.",
    "B5": "Queen Mary allocations remain engineering estimates with provenance, not a builder's weight return.",
    "B6": "Queen Mary positional miscellaneous stores and some historical centroids remain unknown; the ledger is operable, not historically validated.",
    "C4": "Selected small-angle roll is unavailable when GM or the sourced gyration radius is missing.",
    "D6": "Timeline and remaining-GZ data are delivered; graphical cutaway/highlighting is deferred with the UI.",
    "E1": "Four observed SPS fields remain explicitly unavailable or unobserved; this is class-SPS core coverage, not full SPS parity.",
    "E2": "Turret rotating armour is included in mount mass; no independent sourced gunhouse subtotal is invented.",
    "E4": "Strict Taylor lookup returns unavailable outside populated axes; no clipping or tuned historical match.",
    "E5": "Holtrop on selected trimmed proxies is marked nonprimary; only eligible upright method results can be primary.",
    "F4": "JSON/CSV only; HTML report is outside the current user scope.",
    "F6": "Python library/CLI offline; Windows installer and launcher are deferred.",
    "G5": "Core timings only; browser responsiveness and visual progress are later-phase obligations.",
    "G7": "Core docs and handoff only; no packaged release directory is claimed.",
}


def main():
    data = json.loads(INVENTORY.read_text(encoding="utf-8"))
    rows = data["requirements"]
    if len(rows) != 45 or len({row["id"] for row in rows}) != 45:
        raise ValueError("expected 45 distinct acceptance requirements")
    for row in rows:
        identity = row["id"]
        if identity in DEFERRED:
            row.update(status="deferred_by_user", evidence=["current-core-scope.md"],
                       limitations=["UI, deployment, package and game integration are later-phase work."])
            continue
        paths = EVIDENCE[identity]
        for path in paths:
            if not (DOCS / path).exists():
                raise FileNotFoundError(f"{identity}: {path}")
        status = "passed_core_scope" if identity in CORE_PRESENTATION else "passed_with_limit" if identity in LIMITS else "passed"
        row.update(status=status, evidence=paths,
                   limitations=[LIMITS[identity]] if identity in LIMITS else [])
    data["audit_status_counts"] = dict(sorted(Counter(row["status"] for row in rows).items()))
    log = (DOCS / "evidence/core-final-regression.log").read_text(encoding="utf-8")
    match = re.search(r"PLIMSOLL_REGRESSION run=(\d+) fail=(\d+)", log)
    if not match or int(match.group(2)) != 0:
        raise ValueError("final regression has no passing machine-readable summary")
    data["final_regression"] = {"run": int(match.group(1)), "fail": int(match.group(2)),
                                "evidence": "evidence/core-final-regression.log"}
    data["note"] = ("Core-only acceptance audited below. Deferred application and presentation "
                    "requirements do not constitute a full Plimsoll 1.0 release or SPS parity.")
    data["audit_note"] = ("Path evidence is attached per requirement. Historical input accuracy and full SPS "
                          "field parity are not claimed. The local commit is verified from Git history; "
                          "final regression and bounded flooding timing are separately recorded.")
    INVENTORY.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + "\n").replace("\n", "\r\n").encode("utf-8"))
    print(json.dumps(data["audit_status_counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
