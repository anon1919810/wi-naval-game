"""The recovered empirical cost reading: million dollars and million pounds.

This is a pure function over a finite declared domain. It never touches a
project, a ledger or a file, it never clamps an out-of-domain value, and it never
reads an unknown input as zero: a missing fact produces a structured unavailable
diagnostic and a null reading.

It is deliberately **not** part of the adapted configuration method, and it is
deliberately **not** a mass model. The configuration keeps
``sps-3b3-adapted-v1``; this kernel carries its own ``sps-3b3-cost-v1``. There is
no ledger target, no cost adoption path and no proposal: money is a *reading*,
never a weight.

Numerical source
----------------
Recovered ``SpringSharpMono`` 3.0.3032.29945, the same original binary the
adapted concept kernels and :mod:`fixed_armour` use (identical assembly string
and SHA256, re-exported from :mod:`concept_estimates` so the two can never drift
apart):

* ``PerformanceControl.cs:534-544`` ``costCalc``
* ``EngineControl.cs:924-933`` ``loadWeightCalc``

Currency convention kept verbatim
---------------------------------
The source's own output labels are **million US dollars** and **million pounds**,
and it converts between them with a fixed historical ``costPounds = costDollars /
4`` ratio. That ratio is the original's own arithmetic, not a live exchange rate,
not a market price and not an inflation adjustment. Nothing here converts the
reading into a modern currency or claims a present-day price.

The ``hull_year + 2 > 1914`` year branch is the original's own dated correction.
It is a boundary, not a curve: it switches on between a hull year of 1912 and one
of 1913 and is exactly ``1`` below it.

Units
-----
Every project declaration stays canonical: metres and **metric tonnes**. The
recovered expression itself is written in long tons and is fed long tons, so each
mass is converted exactly once on the way in and the converted long-ton figure is
reported beside it.

Scope
-----
It is **not** a price index, a contract value, an inflation-adjusted modern cost,
a builder's estimate, a budget, a profit figure or a claim about any real ship.
The original's own ``float`` intermediates are ``float64`` here; the source's
``float32`` rounding is the stated tolerance, exactly as for
:mod:`concept_estimates`.

Determinism the original does not have
--------------------------------------
The source is a form: every field carries a value whether or not the reader meant
it. Here ``None`` means *unknown* and ``0`` means a determined zero. An unknown
mass, an unknown year, a non-positive displacement, an impossible negative light
basis, an unsupported year, an overflow and a non-finite result are all reported
unavailable and none of them becomes a plausible zero price.
"""

from __future__ import annotations

import copy
import math

try:
    from . import concept_estimates as kernels
except ImportError:                                   # pragma: no cover - direct import
    import concept_estimates as kernels

METHOD_VERSION = "sps-3b3-cost-v1"
SOURCE_LOCATION = "PerformanceControl.cs:534-544; EngineControl.cs:924-933"
SOURCE_ASSEMBLY = kernels.SOURCE_ASSEMBLY
SOURCE_SHA256 = kernels.SOURCE_SHA256
SOURCE_SCOPE = (
    "Independent empirical reading of the recovered 3b3 build cost of one declared "
    "condition, in the original's own historical million-US-dollar and million-pound "
    "labels with its own fixed 4:1 dollar-to-pound ratio and its own dated hull-year "
    "branch; reproduced from the recovered 3b3 costCalc expression read with the "
    "recovered loadWeightCalc load term. It is not a price index, not an "
    "inflation-adjusted modern value, not a live exchange rate, not a market price, "
    "not a builder's or a contract figure, not a budget, not whole-program parity and "
    "not validated against any real ship or any real contract."
)

LONG_TON_KG = kernels.LONG_TON_KG

# PerformanceControl.cs:536 and EngineControl.cs:926.
LOAD_DISPLACEMENT_FRACTION = 0.02
LIGHT_USD_PER_LONGTON = 0.00014
MACHINERY_USD_PER_LONGTON = 0.00056
BORNE_MULTIPLIER = 8.0
BORNE_USD_PER_LONGTON = 0.00042
# PerformanceControl.cs:542, the source's own fixed ratio.
DOLLARS_PER_POUND = 4.0
# PerformanceControl.cs:537-539, the original's own dated correction.
YEAR_BOUNDARY = 1914
YEAR_OFFSET = 1.5
YEAR_SPAN = 5.5

MIN_YEAR = kernels.MIN_YEAR
MAX_YEAR = kernels.MAX_YEAR

INPUT_FIELDS = ("displacement_t", "hull_year", "machinery_mass_t", "ammunition_mass_t",
                "fuel_mass_t", "borne_mass_t")
MASS_FIELDS = ("displacement_t", "machinery_mass_t", "ammunition_mass_t", "fuel_mass_t",
               "borne_mass_t")
LONG_TON_BY_MASS = {
    "displacement_t": "displacement_long_tons",
    "machinery_mass_t": "machinery_long_tons",
    "ammunition_mass_t": "ammunition_long_tons",
    "fuel_mass_t": "fuel_long_tons",
    "borne_mass_t": "borne_long_tons",
}

CURRENCY_CONVENTION = (
    "empirical historical reading in the source's own labels: million US dollars and "
    "million pounds, converted with the source's own fixed 4:1 ratio rather than a live "
    "exchange rate, and not adjusted for inflation. It is not a modern price, a market "
    "quote, a budget or a claim about any real ship or contract.")
COST_FORMULA = (
    "PerformanceControl.cs:534-544 costCalc: load_lt = displacement_lt * 0.02 + "
    "ammunition_lt + fuel_lt; light_lt = displacement_lt - load_lt; base_usd_million = "
    "light_lt * 0.00014 + machinery_lt * 0.00056 + (borne_lt * 8) * 0.00042; "
    "year_factor = 1 + (hull_year + 1.5 - 1914) / 5.5 when hull_year + 2 > 1914 else 1; "
    "usd_million = base_usd_million * year_factor; gbp_million = usd_million / 4")

ASSUMPTIONS = (
    "every mass is the SELECTED mass of one loading condition, converted from metric "
    "tonnes to long tons exactly once; a proposed or estimated mass is never read as the "
    "selected one, and neither is another condition's mass",
    "the machinery, ammunition and fuel masses are the explicit declared balance roles, so "
    "an empty explicitly allocated role is a determined zero and an unclassified positive "
    "or unknown mass is unavailable instead of a silent zero",
    "the borne term is the selected bare-gun borne calculation; it never includes mounts, "
    "armour, ammunition or any proposed mass, and a guns-role item with a positive selected "
    "mass that is not bound to a declared battery leaves the borne term unavailable",
    "structural mass, freeboard, stern, screws and every other balance assumption is not "
    "required: this reading is a cost screen, not a strength or stability screen, and it "
    "stays available when those physical stages fail",
    "the recovered dollar-to-pound ratio is the source's own fixed 4:1 division, not a live "
    "exchange rate and not an inflation adjustment",
    "the hull-year correction is the source's own dated branch: it is exactly 1 for a hull "
    "year whose year + 2 does not exceed 1914 and otherwise 1 + (hull_year + 1.5 - 1914) / "
    "5.5; nothing between the two dates is interpolated",
    "there is no ledger target, no cost adoption path and no proposal: money is a reading "
    "and never a weight",
    "a non-positive displacement, an impossible negative light basis, an unsupported year, "
    "an overflow and a non-finite result are reported unavailable; none of them becomes a "
    "plausible zero price",
)


def _diag(code, field, path, message):
    """One non-blocking diagnostic: this reading is a display value, never a gate.

    Nothing here ever refuses a configuration. An unavailable cost is reported and
    the rest of the screen continues, exactly as an unavailable armour reading is.
    """
    return {"code": code, "severity": "warning", "field": field, "path": path,
            "message": message, "blocking": False}


def _finite(value, path):
    if isinstance(value, complex) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("%s: the derived result is not a finite real number" % (path,))
    return float(value)


def _long_tons(value_t):
    return value_t * 1000.0 / LONG_TON_KG


def _fact(inputs, name):
    """Read one canonical input together with its own provenance, if it has one."""
    raw = inputs.get(name) if isinstance(inputs, dict) else None
    if raw is None:
        return None, None
    if isinstance(raw, dict):
        value = raw.get("value")
        origin = {"source": raw.get("source"), "estimate": raw.get("estimate")}
    else:
        value, origin = raw, None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None, origin
    try:
        number = float(value)
    except (OverflowError, ValueError):
        return None, origin
    if not math.isfinite(number):
        return None, origin
    return number, origin


def _year_factor(hull_year, path, diagnostics):
    """PerformanceControl.cs:537-539, the source's own dated branch."""
    if hull_year is None:
        diagnostics.append(_diag("concept_cost.unknown",  "hull_year",  path + ".hull_year", 
                                 "the recovered year correction needs a hull year, which is "
                                 "unknown; it is not read as a zero year"))
        return None
    if isinstance(hull_year, float) and not hull_year.is_integer():
        diagnostics.append(_diag("concept_cost.invalid",  "hull_year", 
                                 path + ".hull_year", 
                                 "the recovered year branch is defined on whole hull years, so "
                                 "a fractional hull year is refused rather than truncated"))
        return None
    year = int(hull_year)
    if not MIN_YEAR <= year <= MAX_YEAR:
        diagnostics.append(_diag("concept_cost.domain",  "hull_year",  path + ".hull_year", 
                                 "hull year %d is outside the supported %d..%d domain"
                                 % (year, MIN_YEAR, MAX_YEAR)))
        return None
    if year + 2 > YEAR_BOUNDARY:
        return 1.0 + ((year + YEAR_OFFSET) - float(YEAR_BOUNDARY)) / YEAR_SPAN
    return 1.0


def evaluate(inputs, path="$.concept_design.cost"):
    """Evaluate the recovered empirical cost reading.

    ``inputs`` carries the optional **canonical** selected-condition facts:
    ``displacement_t``, ``hull_year``, ``machinery_mass_t``,
    ``ammunition_mass_t``, ``fuel_mass_t`` and ``borne_mass_t``. Each is either a
    number or a ``{"value", "source", "estimate"}`` record whose own provenance
    travels into the result.

    This never raises and never substitutes a default: an unknown fact produces
    ``status == "unavailable"``, null values and a structured diagnostic.
    """
    diagnostics = []
    values = {key: None for key in (
        "usd_million", "gbp_million", "base_usd_million", "light_basis_long_tons",
        "load_long_tons", "year_factor", "light_usd_million", "machinery_usd_million",
        "borne_usd_million")}
    facts, origins = {}, {}
    for name in INPUT_FIELDS:
        value, origin = _fact(inputs, name)
        facts[name] = value
        origins[name] = origin
    missing = [name for name in MASS_FIELDS if facts[name] is None]
    if missing:
        diagnostics.append(_diag(
            "concept_cost.unknown",  missing[0],  path, 
            "the recovered cost expression needs the selected displacement, machinery, "
            "ammunition, fuel and borne masses; %s is unknown and is never read as zero"
            % (", ".join(missing),)))
    negative = [name for name in MASS_FIELDS
                if facts[name] is not None and facts[name] < 0.0]
    if negative:
        diagnostics.append(_diag(
            "concept_cost.domain",  negative[0], 
            path, 
            "the selected masses %s are negative, which no loading condition can carry; the "
            "reading is unavailable rather than a plausible price" % (", ".join(negative),)))
    factor = _year_factor(facts["hull_year"], path, diagnostics)
    values["year_factor"] = factor
    if missing or negative or factor is None:
        return _result(values, facts, origins, diagnostics)

    try:
        long_tons = {name: _long_tons(facts[name]) for name in MASS_FIELDS}
        displacement_lt = long_tons["displacement_t"]
        if displacement_lt <= 0.0:
            diagnostics.append(_diag(
                "concept_cost.domain",  "displacement_t",  path, 
                "the declared displacement is not positive, so the recovered cost expression "
                "has no physical basis; it is unavailable and never a zero price"))
            return _result(values, facts, origins, diagnostics)
        load_lt = (displacement_lt * LOAD_DISPLACEMENT_FRACTION
                   + long_tons["ammunition_mass_t"] + long_tons["fuel_mass_t"])
        light_lt = displacement_lt - load_lt
        if light_lt < 0.0:
            diagnostics.append(_diag(
                "concept_cost.domain",  "displacement_t",  path, 
                "the recovered load of %.3f long tons exceeds the declared displacement of "
                "%.3f long tons, so the light basis would be negative; it is reported and "
                "never clamped to zero" % (load_lt, displacement_lt)))
            return _result(values, facts, origins, diagnostics)
        light_usd = light_lt * LIGHT_USD_PER_LONGTON
        machinery_usd = long_tons["machinery_mass_t"] * MACHINERY_USD_PER_LONGTON
        borne_usd = (long_tons["borne_mass_t"] * BORNE_MULTIPLIER) * BORNE_USD_PER_LONGTON
        base_usd = light_usd + machinery_usd + borne_usd
        usd = _finite(base_usd * factor, path + ".usd_million")
        gbp = _finite(usd / DOLLARS_PER_POUND, path + ".gbp_million")
    except (ArithmeticError, ValueError) as error:
        diagnostics.append(_diag(
            "concept_cost.unavailable",  None,  path, 
            "the recovered cost expression cannot be evaluated as a finite real number: %s; it "
            "never becomes a plausible zero price" % (error,)))
        return _result(values, facts, origins, diagnostics)

    values.update(light_basis_long_tons=light_lt, load_long_tons=load_lt,
                  light_usd_million=light_usd, machinery_usd_million=machinery_usd,
                  borne_usd_million=borne_usd, base_usd_million=base_usd,
                  usd_million=usd, gbp_million=gbp)
    return _result(values, facts, origins, diagnostics)


def _result(values, facts, origins, diagnostics):
    inputs = dict(facts)
    for name, reading in LONG_TON_BY_MASS.items():
        if facts[name] is not None:
            converted = _long_tons(facts[name])
            # The arithmetic may have been refused above. Its receipt must also
            # remain valid JSON rather than reintroducing the rejected infinity.
            inputs[reading] = converted if math.isfinite(converted) else None
    if values["load_long_tons"] is not None:
        inputs["load_long_tons"] = values["load_long_tons"]
    status = "available" if values["usd_million"] is not None else "unavailable"
    provenance = {
        "kernel": "empirical_cost_usd_million",
        "source_location": SOURCE_LOCATION,
        "source_assembly": SOURCE_ASSEMBLY,
        "source_sha256": SOURCE_SHA256,
        "source_scope": SOURCE_SCOPE,
        "method_version": METHOD_VERSION,
        "formula": COST_FORMULA,
        "currency_convention": CURRENCY_CONVENTION,
        "mass_basis": ("selected-condition metric tonnes converted exactly once to the "
                       "source's own long tons"),
        "assumptions": list(ASSUMPTIONS),
        "facts": origins,
        "units": {"inputs": {name: "t" for name in MASS_FIELDS}, "hull_year": "year",
                  "usd_million": "million USD", "gbp_million": "million GBP",
                  "load_long_tons": "long ton", "light_basis_long_tons": "long ton",
                  "year_factor": "dimensionless"},
    }
    return {
        "method_version": METHOD_VERSION,
        "method_scope": SOURCE_SCOPE,
        "status": status,
        "currency_convention": CURRENCY_CONVENTION,
        "inputs": inputs,
        "values": values,
        "diagnostics": diagnostics,
        "provenance": copy.deepcopy(provenance),
    }
