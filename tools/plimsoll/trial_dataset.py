"""The measured-trial dataset as a first-class asset.

The data lives in cases/trials/dataset.json, not in this module: this file only
knows how to read it, refuse an incomplete record, and describe its error. A
trial figure is only useful if the provenance, the trial kind and the load
condition travel with it — mixing those moved one ship's error by thirteen
points, so a record missing them is treated as invalid rather than defaulted.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

DATASET = Path(__file__).resolve().parent / "cases" / "trials" / "dataset.json"

SCHEMA = "plimsoll-trial-dataset-1"
TRIAL_KINDS = ("full_power", "measured_mile", "three_hour", "acceptance")
LENGTH_BASES = ("lbp", "loa")
VERIFICATION = ("hand_checked", "gated_auto")
SHIP_TYPES = ("battleship", "battlecruiser", "cruiser", "destroyer", "carrier")

# Plausibility band for a warship trial: a destroyer sits near 28 shp per tonne,
# a battleship near 3, so anything outside this is a parsing accident.
MIN_SPEED_KT, MAX_SPEED_KT = 15.0, 40.0
MIN_SHP_PER_T, MAX_SHP_PER_T = 0.5, 40.0


class DatasetError(ValueError):
    """A trial record that cannot be used as evidence."""


def load(path=None):
    """Read the dataset file and return it as a mapping."""
    target = Path(path) if path else DATASET
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except OSError as error:
        raise DatasetError("cannot read the trial dataset: %s" % error)


def validate(record):
    """Return the list of reasons one record cannot be used; empty means usable."""
    problems = []
    for key in ("id", "name", "navy", "ship_type", "year", "hull", "trial", "source", "verification"):
        if key not in record:
            problems.append("missing %s" % key)
    if problems:
        return problems
    if record["ship_type"] not in SHIP_TYPES:
        problems.append("ship_type %r is outside the known classes" % (record["ship_type"],))
    hull, trial, source, verify = record["hull"], record["trial"], record["source"], record["verification"]
    if hull.get("length_basis") not in LENGTH_BASES:
        problems.append("length_basis must say lbp or loa")
    for key in ("length_m", "beam_m", "draught_m", "displacement_t", "block_coeff"):
        if not isinstance(hull.get(key), (int, float)) or hull[key] <= 0:
            problems.append("hull.%s must be a positive number" % key)
    if hull.get("block_coeff", 0) >= 1.0:
        problems.append("hull.block_coeff must stay below 1")
    if trial.get("kind") not in TRIAL_KINDS:
        problems.append("trial.kind must be one of %s" % (", ".join(TRIAL_KINDS),))
    speed, shp = trial.get("speed_kt"), trial.get("shp")
    if not isinstance(speed, (int, float)) or not MIN_SPEED_KT <= speed <= MAX_SPEED_KT:
        problems.append("trial.speed_kt outside the plausible band %.0f-%.0f kn" % (MIN_SPEED_KT, MAX_SPEED_KT))
    if not isinstance(shp, (int, float)) or shp <= 0:
        problems.append("trial.shp must be positive")
    elif hull.get("displacement_t"):
        ratio = shp / hull["displacement_t"]
        if not MIN_SHP_PER_T <= ratio <= MAX_SHP_PER_T:
            problems.append("shp per tonne %.1f outside the plausible band" % ratio)
    if not str(source.get("url", "")).startswith("http"):
        problems.append("source.url must be a link")
    if not str(source.get("quote", "")).strip():
        problems.append("source.quote must carry the sentence the figure came from")
    if verify.get("status") not in VERIFICATION:
        problems.append("verification.status must say hand_checked or gated_auto")
    return problems


def usable_cases(dataset=None):
    """Every record that passes validation, refusing the file if any record fails."""
    data = dataset or load()
    if data.get("schema") != SCHEMA:
        raise DatasetError("unexpected schema %r" % (data.get("schema"),))
    seen, out = set(), []
    for record in data.get("cases", []):
        problems = validate(record)
        if problems:
            raise DatasetError("%s: %s" % (record.get("name", "?"), "; ".join(problems)))
        if record["id"] in seen:
            raise DatasetError("duplicate case id %r" % (record["id"],))
        seen.add(record["id"])
        out.append(record)
    return out


def _stats(errors):
    """Errors arrive already in percent; nothing is rescaled here."""
    absolute = [abs(e) for e in errors]
    return dict(n=len(errors), mape=sum(absolute) / len(absolute),
                median=statistics.median(absolute),
                low=min(errors), high=max(errors))


def summary(cases=None):
    """Error of the model over the dataset, overall and split two ways.

    The split matters more than the mean: the error follows the hull form, so a
    single number hides exactly the structure the blend rule is meant to use.
    """
    rows = cases if cases is not None else usable_cases()
    errors = [record["model"]["error_pct"] for record in rows]
    out = dict(overall=_stats(errors), by_type={}, by_speed={}, by_block={}, by_fr={}, by_basis={})
    for record in rows:
        out["by_type"].setdefault(record["ship_type"], []).append(record["model"]["error_pct"])
        speed = record["trial"]["speed_kt"]
        band = "30+ kn" if speed >= 30 else ("24-30 kn" if speed >= 24 else "under 24 kn")
        out["by_speed"].setdefault(band, []).append(record["model"]["error_pct"])
        cb = record["hull"]["block_coeff"]
        cband = "Cb>=0.55" if cb >= 0.55 else ("0.50<=Cb<0.55" if cb >= 0.50 else "Cb<0.50")
        out["by_block"].setdefault(cband, []).append(record["model"]["error_pct"])
        # Froude number is the variable the resistance tables are indexed by in
        # practice, so the error is split on it as well as on the block
        # coefficient: a constant correction cannot fit a curve that changes
        # sign across it.
        length = record["hull"]["length_m"]
        froude = (0.514444 * record["trial"]["speed_kt"]) / (9.81 * length) ** 0.5
        fband = "Fr>=0.28" if froude >= 0.28 else ("0.24<=Fr<0.28" if froude >= 0.24 else "Fr<0.24")
        out["by_fr"].setdefault(fband, []).append(record["model"]["error_pct"])
        out["by_basis"].setdefault(record["hull"]["length_basis"], []).append(record["model"]["error_pct"])
    for group in ("by_type", "by_speed", "by_block", "by_fr", "by_basis"):
        out[group] = {key: _stats(value) for key, value in sorted(out[group].items())}
    return out
