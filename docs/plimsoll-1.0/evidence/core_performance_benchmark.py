#!/usr/bin/env python3
"""Core performance benchmark for the Plimsoll calculation core.

Protocol: docs/plimsoll-1.0/core-performance-validation.md
Every workload keeps >=3 raw elapsed samples plus median/max, records the
identity of what was computed, and stores machine-readable evidence next to
this script (core-performance-benchmark.json and .log).

Usage (from the work-tree root):
    PYTHONPATH=tools python -B docs/plimsoll-1.0/evidence/core_performance_benchmark.py

Design notes that matter for honesty:
* Timings use time.perf_counter_ns (monotonic, high resolution).
* In-process API timings measure the calculation call only: input parsing and
  output serialization are OUTSIDE the interval (they are measured separately
  by the cold-start and batch/CLI workloads).
* CLI (batch) timings measure the whole subprocess: parsing + calculation +
  serialization are INSIDE the interval. This is stated per workload.
* A workload that stops at a model boundary records that boundary; it is never
  relabelled as scheduled completion.
"""

from __future__ import annotations

import copy
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
TREE = HERE.parents[2]                       # work-tree root
TOOLS = TREE / "tools"
CASES = TOOLS / "plimsoll" / "cases" / "projects"
SAMPLES = 3

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plimsoll import analysis, flooding, project_store  # noqa: E402

PROJECTS = {
    "analytic-box-reference": CASES / "analytic_box.project.json",
    "generic-box-fixture": CASES / "generic_flooding_box.project.json",
    "generic-steamer-reference": CASES / "generic_steamer.project.json",
    "hms-queen-mary-1913": CASES / "queen_mary_1913.project.json",
}
BATCH_CASES = [
    ("analytic_box-loaded", "analytic-box-reference", "loaded"),
    ("analytic_box-light", "analytic-box-reference", "light"),
    ("steamer-coastal", "generic-steamer-reference", "coastal"),
    ("steamer-loaded", "generic-steamer-reference", "loaded"),
    ("queen_mary-normal", "hms-queen-mary-1913", "normal-engineering"),
    ("queen_mary-deep", "hms-queen-mary-1913", "deep-engineering"),
]
BASE_STAGES = ["loading", "systems", "equilibrium", "hydrostatics"]
GZ_ANGLES = list(range(0, 61, 5))


def sha256_file(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def total_ram_bytes():
    """Windows global memory status; None when unavailable."""
    try:
        class MemoryStatusEx(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        status = MemoryStatusEx()
        status.dwLength = ctypes.sizeof(status)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
        return int(status.ullTotalPhys)
    except Exception:
        return None


def environment():
    return {
        "python_version": sys.version,
        "python_executable": sys.executable,
        "python_executable_sha256": sha256_file(sys.executable),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "total_ram_bytes": total_ram_bytes(),
        "measured_clock": "time.perf_counter_ns",
        "samples_per_workload": SAMPLES,
    }


def sample_runs(run):
    """Return raw nanoseconds samples (SAMPLES runs) and the last result."""
    raw, last = [], None
    for _ in range(SAMPLES):
        start = time.perf_counter_ns()
        try:
            last = ("ok", run())
        except Exception as error:                # keep partial evidence
            last = ("error", {"error": f"{type(error).__name__}: {error}"})
        raw.append(time.perf_counter_ns() - start)
    return raw, last


def timing(raw, **extra):
    return {
        "samples_ns": raw,
        "samples_s": [round(value / 1e9, 6) for value in raw],
        "median_s": round(statistics.median(raw) / 1e9, 6),
        "min_s": round(min(raw) / 1e9, 6),
        "max_s": round(max(raw) / 1e9, 6),
        **extra,
    }


def project_facts(project_id):
    path = PROJECTS[project_id]
    payload = json.loads(path.read_text(encoding="utf-8"))
    geometry = payload.get("geometry", {})
    offsets = geometry.get("offsets") or {}
    stations = offsets.get("stations")
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "project_id": payload.get("id"),
        "conditions": [item["id"] for item in payload["loading_conditions"]],
        "geometry_kind": geometry.get("kind"),
        "station_count": len(stations) if isinstance(stations, list) else None,
        "schema": payload.get("schema"),
    }


def stage_summary(result):
    return {
        name: {"status": stage["status"], "complete": stage["validity"]["complete"]}
        for name, stage in result["stages"].items()
        if stage["status"] != "not_requested"
    }


def cold_start():
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=str(TOOLS))
    command = [sys.executable, "-B", "-c", "import plimsoll.analysis"]
    raw = []
    for _ in range(SAMPLES):
        start = time.perf_counter_ns()
        subprocess.run(command, cwd=str(TREE), env=env, capture_output=True, check=False)
        raw.append(time.perf_counter_ns() - start)
    return timing(raw, workload="cold_process_import_startup",
                  inside_interval="interpreter start + import of plimsoll.analysis")


def single_condition():
    facts = project_facts("hms-queen-mary-1913")
    project = project_store.load(PROJECTS["hms-queen-mary-1913"])
    options = {"stages": list(BASE_STAGES)}
    raw, last = sample_runs(lambda: analysis.compute_project(project, "normal-engineering", options))
    kind, result = last
    entry = timing(raw, workload="single_condition", project="hms-queen-mary-1913",
                   condition_id="normal-engineering", options=options,
                   inside_interval="analysis.compute_project only (no parse/serialize)",
                   project_facts=facts)
    if kind == "ok":
        entry["result"] = {
            "status": result["status"], "stages": stage_summary(result),
            "project_fingerprint": result["project_fingerprint"],
            "input_fingerprint": result["input_fingerprint"],
            "request_fingerprint": result["request_fingerprint"],
            "diagnostic_codes": sorted({item["code"] for item in result["diagnostics"]}),
        }
    else:
        entry["result"] = result
    return entry


def per_case_in_process():
    """Per-case figures for the batch workload (the batch summary carries none)."""
    rows = []
    for label, project_id, condition in BATCH_CASES:
        project = project_store.load(PROJECTS[project_id])
        options = {"stages": list(BASE_STAGES)}
        raw, last = sample_runs(lambda p=project, c=condition, o=options:
                                analysis.compute_project(p, c, o))
        kind, result = last
        row = {"case": label, "project": project_id, "condition_id": condition,
               "in_process": timing(raw)}
        row["status"] = result["status"] if kind == "ok" else result
        if kind == "ok":
            row["stages"] = stage_summary(result)
        rows.append(row)
    return rows


def batch_cli():
    manifest = {"schema": "plimsoll-batch-1", "cases": [
        {"id": label, "project": str(PROJECTS[project_id]), "condition_id": condition,
         "options": {"stages": list(BASE_STAGES)}}
        for label, project_id, condition in BATCH_CASES]}
    workdir = HERE / "_bench_tmp"
    workdir.mkdir(exist_ok=True)
    manifest_path = workdir / "batch-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=str(TOOLS))
    raw, codes, summaries = [], [], []
    for index in range(SAMPLES):
        out = workdir / f"batch-out-{index + 1}"
        start = time.perf_counter_ns()
        completed = subprocess.run(
            [sys.executable, "-B", "-m", "plimsoll", "batch", str(manifest_path), "--out", str(out)],
            cwd=str(TREE), env=env, capture_output=True, text=True, encoding="utf-8", check=False)
        raw.append(time.perf_counter_ns() - start)
        codes.append(completed.returncode)
        summary_path = out / "batch-summary.json"
        if summary_path.exists():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summaries.append({
                "status": summary["status"], "case_count": summary["case_count"],
                "per_case": [{"id": row["id"], "status": row["status"],
                              "request_fingerprint": row["request_fingerprint"]}
                             for row in summary["cases"]],
            })
    identity = {row["id"]: row["request_fingerprint"] for row in summaries[0]["per_case"]} \
        if summaries else {}
    stable = bool(summaries) and all(
        {row["id"]: row["request_fingerprint"] for row in item["per_case"]} == identity
        for item in summaries)
    return timing(raw, workload="batch_cli", manifest=str(manifest_path),
                  exit_codes=codes, cases=len(BATCH_CASES),
                  inside_interval="whole subprocess: parse + calculate + serialize",
                  summary_statuses=[item["status"] for item in summaries],
                  identities_stable_across_samples=stable,
                  per_case_identity=identity,
                  per_case_timing_limitation=(
                      "the batch summary carries no per-case elapsed time; "
                      "per-case figures come from per_case_in_process below"))


def gz_workload():
    facts = project_facts("hms-queen-mary-1913")
    project = project_store.load(PROJECTS["hms-queen-mary-1913"])
    options = {"stages": ["loading", "geometry", "equilibrium", "gz"],
               "gz_angles_deg": list(GZ_ANGLES)}
    raw, last = sample_runs(lambda: analysis.compute_project(project, "normal-engineering", options))
    kind, result = last
    entry = timing(raw, workload="gz_curve", project="hms-queen-mary-1913",
                   condition_id="normal-engineering", angles_deg=GZ_ANGLES,
                   inside_interval="analysis.compute_project only (no parse/serialize)",
                   project_facts=facts)
    if kind != "ok":
        entry["result"] = result
        return entry
    stage = result["stages"]["gz"]
    rows = (stage["data"] or {}).get("rows") or []

    def scaled_residual(row):
        residuals = ((row.get("equilibrium") or {}).get("residuals") or {}).get("scaled") or {}
        values = [abs(value) for value in residuals.values()
                  if isinstance(value, (int, float))]
        return max(values) if values else None

    residuals = [value for value in (scaled_residual(row) for row in rows)
                 if value is not None]
    boundaries = [row.get("angle_deg") for row in rows
                  if not (row.get("validity") or {}).get("model_applicable", True)
                  or not (row.get("validity") or {}).get("intact_valid", True)]
    entry["result"] = {
        "status": stage["status"], "complete": stage["validity"]["complete"],
        "converged": stage["validity"]["converged"],
        "model_applicable": stage["validity"]["model_applicable"],
        "row_count": len(rows),
        "angles_deg": [row.get("angle_deg") for row in rows],
        "rows_without_equilibrium": [row.get("angle_deg") for row in rows
                                     if not row.get("equilibrium")],
        "boundary_angles_deg": boundaries,
        "row_validity_summary": sorted({
            (bool((row.get("validity") or {}).get("model_applicable")),
             bool((row.get("validity") or {}).get("intact_valid")),
             (row.get("validity") or {}).get("deck_edge_status"))
            for row in rows
        }),
        "max_abs_scaled_residual": max(residuals) if residuals else None,
        "gz_m_range": [min(row["gz_m"] for row in rows), max(row["gz_m"] for row in rows)]
        if rows and all(isinstance(row.get("gz_m"), (int, float)) for row in rows) else None,
        "maximum": (stage["data"] or {}).get("maximum"),
        "avs_deg": (stage["data"] or {}).get("avs_deg"),
        "zero_crossings": (stage["data"] or {}).get("zero_crossings"),
        "initial_stiffness_m": (stage["data"] or {}).get("initial_stiffness_m"),
        "endpoint": (stage["data"] or {}).get("endpoint"),
        "degraded_rows_note": ("rows without equilibrium or with model_applicable/intact_valid "
                               "false are retained above, not discarded"),
        "overall_status": result["status"],
        "request_fingerprint": result["request_fingerprint"],
        "diagnostic_codes": sorted({item["code"] for item in stage["diagnostics"]}),
        "curve_note": ("processing completion is reported separately from physical validity: "
                       "see complete/model_applicable above"),
    }
    return entry


def flooding_preset(preset_id, duration_s=None):
    presets = json.loads((CASES / "damage-presets.json").read_text(encoding="utf-8"))["presets"]
    preset = copy.deepcopy(next(item for item in presets if item["id"] == preset_id))
    if duration_s is not None:
        preset["scenario"]["duration_s"] = float(duration_s)
    return preset


def flooding_workload(preset_id, label, duration_s=None):
    preset = flooding_preset(preset_id, duration_s)
    raw_project = json.loads(PROJECTS[preset["project_id"]].read_text(encoding="utf-8"))
    raw, last = sample_runs(lambda: flooding.simulate_flooding(
        raw_project, preset["condition_id"], preset["scenario"]))
    kind, result = last
    entry = timing(raw, workload=label, preset=preset_id,
                   project=preset["project_id"], condition_id=preset["condition_id"],
                   requested_duration_s=preset["scenario"]["duration_s"],
                   requested_time_step_s=preset["scenario"]["time_step_s"],
                   inside_interval="flooding.simulate_flooding only (no parse/serialize)",
                   scenario_sha256=hashlib.sha256(json.dumps(
                       preset["scenario"], sort_keys=True, ensure_ascii=False,
                       separators=(",", ":")).encode("utf-8")).hexdigest(),
                   scenario_source=preset["scenario"]["source"])
    if kind != "ok":
        entry["result"] = result
        return entry
    timeline = result.get("timeline") or []
    final_state = result.get("final_state") or {}
    equilibrium = final_state.get("equilibrium") or {}
    time_steps = [row.get("actual_dt_s") for row in timeline
                  if isinstance(row.get("actual_dt_s"), (int, float)) and row["actual_dt_s"] > 0]
    entry["result"] = {
        "status": result.get("status"),
        "stop_reason": result.get("stop_reason"),
        "validity": result.get("validity"),
        "requested_duration_s": preset["scenario"]["duration_s"],
        "accepted_duration_s": timeline[-1].get("time_s") if timeline else None,
        "step_count": (len(timeline) - 1) if timeline else None,
        "actual_dt_s_min": min(time_steps) if time_steps else None,
        "actual_dt_s_max": max(time_steps) if time_steps else None,
        "step_halving_detected": bool(time_steps) and min(time_steps) < max(time_steps),
        "failed_attempt": result.get("failed_attempt"),
        "initial_water_volume_m3": result.get("initial_total_water_volume_m3"),
        "initial_water_mass_t": result.get("initial_total_water_mass_t"),
        "final_onboard_water_mass_t": final_state.get("total_onboard_water_mass_t"),
        "mass_conservation_error_t": result.get("mass_conservation_error_t"),
        "volume_conservation_error_m3": result.get("volume_conservation_error_m3"),
        "final_state_conservation_errors": {
            "mass_t": final_state.get("mass_conservation_error_t"),
            "volume_m3": final_state.get("volume_conservation_error_m3"),
        },
        "equilibrium_keys": sorted(equilibrium),
        "equilibrium_residuals": equilibrium.get("residuals"),
        "equilibrium_converged": equilibrium.get("converged"),
        "downflooding": result.get("downflooding"),
        "diagnostic_codes": sorted({item["code"] for item in result.get("diagnostics", [])}),
        "method_version": result.get("method_version"),
        "kernel_method_version": result.get("kernel_method_version"),
        "project_fingerprint": result.get("project_fingerprint"),
        "input_fingerprint": result.get("input_fingerprint"),
        "timeline_length": len(timeline),
    }
    return entry


def main():
    evidence = {
        "schema": "plimsoll-core-performance-benchmark-1",
        "protocol": "docs/plimsoll-1.0/core-performance-validation.md",
        "measured_at_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "worktree_head_commit": subprocess.run(
            ["git", "-c", "safe.directory=*", "rev-parse", "HEAD"], cwd=str(TREE),
            capture_output=True, text=True, encoding="utf-8", check=False).stdout.strip() or None,
        "environment": environment(),
        "workloads": {},
    }
    steps = [
        ("cold_start", cold_start),
        ("single_condition", single_condition),
        ("batch_cli", batch_cli),
        ("per_case_in_process", per_case_in_process),
        ("gz_curve", gz_workload),
        ("flooding_queen_mary_single_proxy_10s",
         lambda: flooding_workload("queen-mary-single-proxy",
                                   "flooding_queen_mary_single_proxy_10s", duration_s=10.0)),
        ("flooding_generic_two_connected",
         lambda: flooding_workload("generic-two-connected", "flooding_generic_two_connected", duration_s=10.0)),
    ]
    # Write after every workload: an interruption must not lose earlier evidence.
    out_json = HERE / "core-performance-benchmark.json"
    for name, run in steps:
        print(f"== {name} ...", flush=True)
        started = time.perf_counter_ns()
        try:
            evidence["workloads"][name] = run()
        except Exception as error:
            evidence["workloads"][name] = {"workload": name,
                                           "error": f"{type(error).__name__}: {error}"}
        elapsed = round((time.perf_counter_ns() - started) / 1e9, 3)
        entry = evidence["workloads"][name]
        if isinstance(entry, dict):
            entry.setdefault("elapsed_s", elapsed)
        else:
            # Some workloads (per-case tables) are arrays; keep them addressable.
            evidence["workloads"][name] = {"workload": name, "elapsed_s": elapsed,
                                           "cases": entry}
        out_json.write_bytes(json.dumps(evidence, ensure_ascii=False, indent=1).replace("\n", "\r\n").encode("utf-8"))
        print(json.dumps(evidence["workloads"][name], ensure_ascii=False)[:300], flush=True)

    print(f"\nwritten {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
