"""Explicit parameter studies and selected-plane geometry, without a new solver."""

from __future__ import annotations

import copy
import hashlib
import json
import math

if __package__:
    from . import geometry, hydrostatics, stability
else:
    import geometry
    import hydrostatics
    import stability

METHOD_VERSION = "geometry-analysis-1"
MAX_GRID_SAMPLES = 201


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite real number")
    return float(value)


def _diagnostic(code, message, path="$.geometry", blocking=False):
    return dict(code=code, message=message, path=path,
                severity="error" if blocking else "warning", blocking=blocking)


def _envelope(status="completed", diagnostics=None):
    return dict(status=status, method_version=METHOD_VERSION,
                validity=dict(complete=status == "completed", numerical_convergence=None,
                              model_applicable=status == "completed", historical_validated=None),
                diagnostics=diagnostics or [])


def _finite_result(result):
    # Every public payload must be serializable without non-standard NaN tokens.
    json.dumps(result, allow_nan=False)
    return result


def _grid(values, name):
    if not isinstance(values, (list, tuple)) or not 1 <= len(values) <= MAX_GRID_SAMPLES:
        raise ValueError(f"{name} must contain 1..{MAX_GRID_SAMPLES} explicit samples")
    result = [_number(value, name) for value in values]
    if any(b <= a for a, b in zip(result, result[1:])):
        raise ValueError(f"{name} must be strictly increasing")
    return result


def _plane(value):
    if not isinstance(value, dict):
        raise ValueError("plane must be an object with p, q and waterline_d_m")
    if value.get("converged") is False:
        raise ValueError("a failed equilibrium cannot supply a selected plane")
    return {key: _number(value.get(key), key) for key in ("p", "q", "waterline_d_m")}


def parameterized_hydrostatics(hull: dict) -> dict:
    """Adapt legacy L0 with explicit defaults, provenance and unknown quantities.

    Args:
        hull (dict): Design dimensions, coefficients and optional KG/reference mass.

    Returns:
        (dict): Traced parameter study; never a selected loaded equilibrium.
    """
    if not isinstance(hull, dict):
        raise ValueError("hull must be an object")
    _finite_result(hull)
    inputs = copy.deepcopy(hull)
    draft_key = "draught_normal_m" if "draught_normal_m" in hull else "draught_m"
    numeric = ("lwl_m", "beam_m", "draught_normal_m", "draught_m", "block_coeff", "waterplane_coeff",
               "kg_m", "roll_gyration_coeff", "displacement_normal_t", "depth_m")
    for key in numeric:
        if hull.get(key) is not None:
            value = _number(hull[key], key)
            if value < 0:
                raise ValueError(f"{key} must be nonnegative")
    flags = ("waterplane_coeff_is_estimate", "block_coeff_is_estimate",
             "kg_is_estimate", "displacement_unit_is_estimate")
    for flag in flags:
        if flag in hull and hull[flag] is not None and not isinstance(hull[flag], bool):
            raise ValueError(f"{flag} must be boolean or null")
    if hull.get("sources") is not None and not isinstance(hull["sources"], dict):
        raise ValueError("hull.sources must be an object")
    sources = copy.deepcopy(hull.get("sources") or {})
    diagnostics = []
    if not sources:
        diagnostics.append(_diagnostic("l0.sources_unknown",
            "input source metadata is unknown; the empty effective source map supplies no provenance",
            "$.hull.sources"))
    for key in numeric:
        source = sources.get(key)
        if hull.get(key) is not None and (source in (None, "", {}) or
                                         isinstance(source, str) and not source.strip()):
            diagnostics.append(_diagnostic("l0.input_source_unknown",
                f"direct input {key} has no source provenance", f"$.hull.sources.{key}"))
    base = dict(inputs=inputs, scenario="parameterized_design_waterline_not_loaded_equilibrium",
                estimate=True, units=dict(length="m", mass="t", density="t/m3"),
                rho_t_m3=hydrostatics.RHO_SEA, values=None, trace=[], assumptions=[])
    missing = [key for key in ("lwl_m", "beam_m", draft_key, "block_coeff") if hull.get(key) is None]
    if missing:
        return {**_envelope("unavailable", diagnostics + [
            _diagnostic("l0.input_unknown", f"{key} is unknown", f"$.hull.{key}") for key in missing
        ]), **base}
    effective = copy.deepcopy(hull)
    assumptions = [dict(field="rho_t_m3", value=hydrostatics.RHO_SEA, estimate=True,
                        source="hydrostatics.RHO_SEA: declared seawater assumption")]
    for key, default in (("waterplane_coeff", 0.8), ("roll_gyration_coeff", 0.38)):
        if effective.get(key) is None:
            effective[key] = default
            assumptions.append(dict(field=key, value=default, estimate=True,
                                    original_value=None, source="documented legacy L0 default"))
    for flag in flags:
        quantity = {"kg_is_estimate": "kg_m",
                    "displacement_unit_is_estimate": "displacement_normal_t"}.get(flag)
        if quantity is not None and effective.get(quantity) is None:
            continue
        if effective.get(flag) is None:
            effective[flag] = True
            assumptions.append(dict(field=flag, value=True, estimate=True,
                original_value=None, source="conservative legacy L0 estimate-state default"))
    diagnostics.extend(_diagnostic("l0.default_assumption",
                       f"{a['field']}={a['value']} used as an explicit estimated assumption",
                       f"$.hull.{a['field']}") for a in assumptions)
    base["assumptions"] = assumptions
    cb, cwp = effective["block_coeff"], effective["waterplane_coeff"]
    if (min(effective["lwl_m"], effective["beam_m"], effective[draft_key]) <= 0
            or not 0.2 <= cb <= cwp <= 1 or cwp < 0.3
            or (effective.get("depth_m") is not None and effective["depth_m"] <= effective[draft_key])):
        return {**_envelope("model_limit", diagnostics + [_diagnostic(
            "l0.shape_limit", "L0 needs positive dimensions, 0.2 <= Cb <= Cwp <= 1, "
            "Cwp >= 0.3 and a supplied deck strictly above the design draft", "$.hull"
        )]), **base}
    effective["sources"] = sources
    # Reference mass is a comparison, never a calculation authority. Handle its
    # explicit zero outside the legacy truthiness branch, retaining positive
    # reference discrepancy warnings and trace unchanged.
    reference = effective.get("displacement_normal_t")
    if reference == 0:
        effective.pop("displacement_normal_t")
    raw = hydrostatics.compute(effective)
    diagnostics.extend(_diagnostic("l0.legacy_warning", warning, f"$.hull.warnings[{i}]")
                       for i, warning in enumerate(raw["warnings"]))
    values = raw["values"]
    for key in ("kg_m", "gm_m", "roll_period_s"):
        values.setdefault(key, None)
    comparison = dict(mass_t=reference, deviation_pct=None,
                      source=copy.deepcopy(sources.get("displacement_normal_t")),
                      estimate=hull.get("displacement_unit_is_estimate"))
    if reference == 0:
        diagnostics.append(_diagnostic("l0.zero_reference_mass",
            "reference displacement is known zero; percentage deviation is undefined",
            "$.hull.displacement_normal_t"))
    elif reference is not None:
        comparison["deviation_pct"] = 100*(values["displacement_t"]-reference)/reference
    for item in raw["trace"]:
        if item["key"] not in ("waterplane_coeff", "kg_m", "displacement_input_t"):
            item["estimate"] = True  # Shape and Morrish output remain model estimates.
        elif item["key"] == "waterplane_coeff" and hull.get("waterplane_coeff") is not None:
            item["estimate"] = hull.get("waterplane_coeff_is_estimate")
        elif item["key"] == "kg_m":
            item["estimate"] = hull.get("kg_is_estimate")
        elif item["key"] == "displacement_input_t":
            item["estimate"] = hull.get("displacement_unit_is_estimate")
    return _finite_result({**_envelope(diagnostics=diagnostics), **base,
        "effective_inputs": effective, "values": values, "trace": raw["trace"],
        "shape_model": raw["shape_model"], "reference_displacement": comparison,
        "model_limits": ["one-parameter upright waterplane shape", "Morrish KB approximation",
                         "no materialized sealed geometry or loading equilibrium implied"]})


def materialize_reference_hull(parameters: dict, *, keel_offset_m, source, estimate,
                               n_stations=81, n_section=48) -> dict:
    """Generate explicitly requested estimated polygons using the legacy shape model.

    Args:
        parameters (dict): lwl_m, beam_m, draught_m, block_coeff, waterplane_coeff,
            and depth_m (the flat closed deck height above keel), all required.
        keel_offset_m (float): Geometry ordinate of the declared keel.
        source (str | dict): Explicit provenance for the input parameter study.
        estimate (bool): Provenance status of the supplied parameters.
        n_stations (int): Number of cosine-spaced sections, between 3 and 401.
        n_section (int): Vertical section subdivision count, between 8 and 128.

    Returns:
        (dict): Materialized canonical geometry with estimated method provenance.
    """
    if not isinstance(parameters, dict):
        raise ValueError("parameters must be an object")
    if not isinstance(source, (str, dict)) or not source or (isinstance(source, str) and not source.strip()):
        raise ValueError("explicit nonempty source is required")
    if not isinstance(estimate, bool):
        raise ValueError("input estimate must be boolean")
    keel = _number(keel_offset_m, "keel_offset_m")
    keys = ("lwl_m", "beam_m", "draught_m", "block_coeff", "waterplane_coeff", "depth_m")
    p = {key: _number(parameters.get(key), key) for key in keys}
    if min(p.values()) <= 0 or p["depth_m"] <= p["draught_m"]:
        raise ValueError("positive complete parameters and a closed deck above draft are required")
    if not 0.2 <= p["block_coeff"] < p["waterplane_coeff"] <= 1 or p["waterplane_coeff"] < 0.3:
        raise ValueError("reference shape needs 0.2 <= Cb < Cwp <= 1 and Cwp >= 0.3")
    for name, value, low, high in (("n_stations", n_stations, 3, 401), ("n_section", n_section, 8, 128)):
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ValueError(f"{name} must be an integer in [{low}, {high}]")
    hull = geometry.make_reference_hull(p["lwl_m"], p["beam_m"], p["draught_m"],
        p["block_coeff"], p["waterplane_coeff"], depth=p["depth_m"], deck=p["depth_m"],
        n_stations=n_stations, n_section=n_section, spacing="cosine")
    payload = dict(schema="plimsoll-section-polygons-1", stations=[
        [x, [[y, z+keel] for y, z in poly]] for x, poly in hull.stations])
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                      allow_nan=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    result = dict(kind="offsets", keel_offset_m=keel, estimate=True, offsets=payload,
        source=dict(method="geometry.make_reference_hull", method_version=METHOD_VERSION,
                    input_source=copy.deepcopy(source), input_estimate=estimate,
                    parameters=copy.deepcopy(parameters), content_sha256=digest,
                    discretization=dict(n_stations=n_stations, n_section=n_section, spacing="cosine"),
                    assumptions=["flat sealed deck at explicit depth_m above keel",
                                 "one-parameter waterplane and power-law section model"]))
    stability.prepare_geometry(result)
    return _finite_result(result)


def _linear_integral(xs, values, power=0):
    # Integrate each linearly interpolated scalar times x**power analytically.
    # Plain trapezoids of x*x*width would give the wrong even-box longitudinal I.
    terms = []
    for a, b, va, vb in zip(xs, xs[1:], values, values[1:]):
        if power == 0:
            term = (b-a)*(va+vb)/2
        elif power == 1:
            term = (b-a)*((2*a+b)*va+(a+2*b)*vb)/6
        else:
            term = (b-a)*((3*a*a+2*a*b+b*b)*va+(a*a+2*a*b+3*b*b)*vb)/12
        terms.append(term)
    return math.fsum(terms)


def _wet_girth(poly, q, d):
    lengths = []
    for (y0, z0), (y1, z1) in zip(poly, poly[1:]+poly[:1]):
        f0, f1 = z0-q*y0-d, z1-q*y1-d
        fraction = 1 if max(f0, f1) <= 0 else 0
        if min(f0, f1) < 0 < max(f0, f1):
            fraction = abs(min(f0, f1))/(abs(f0)+abs(f1))
        lengths.append(math.hypot(y1-y0, z1-z0)*fraction)
    return math.fsum(lengths)


def _measures(prepared, plane, rho):
    hull, vertices, _, metadata = prepared
    p, q, d = plane["p"], plane["q"], plane["waterline_d_m"]
    keel = metadata["keel_offset_m"]
    s, t = math.hypot(1, p, q), math.hypot(1, q)
    supports = [z-p*x-q*y for x, y, z in vertices]
    partial = min(supports) < d < max(supports)
    envelope_state = "partial" if partial else (
        "lower_contact" if d == min(supports) else "upper_contact" if d == max(supports)
        else "dry" if d < min(supports) else "fully_submerged")
    hydro = hull.integrate(math.atan(q), d, math.atan(p))
    sections, intervals, girths, moments = [], [], [], []
    boundary_contact = False
    for x, poly in hull.stations:
        intercept = d+p*x
        area, _, _ = hull.section_under_line(poly, q, intercept)
        spans = geometry.waterline_intervals(poly, q, intercept)
        boundary_contact |= any(z0-q*y0-intercept == 0 and z1-q*y1-intercept == 0
                                and (y0, z0) != (y1, z1)
                                for (y0, z0), (y1, z1) in zip(poly, poly[1:]+poly[:1]))
        sections.append(dict(x_m=x, intercept_m=intercept, area_m2=area))
        intervals.append(spans)
        moments.append([math.fsum((b**(k+1)-a**(k+1))/(k+1) for a, b in spans) for k in range(3)])
        girths.append(_wet_girth(poly, q, intercept))
    xs = [x for x, _ in hull.stations]
    width, first, second = zip(*moments)
    projected_area = _linear_integral(xs, width)
    cx = _linear_integral(xs, width, 1)/projected_area if projected_area > 0 else None
    cy = _linear_integral(xs, first)/projected_area if projected_area > 0 else None
    it = il = product = None
    if projected_area > 0:
        xx = _linear_integral(xs, width, 2)-projected_area*cx*cx
        yy = _linear_integral(xs, second)-projected_area*cy*cy
        xy = _linear_integral(xs, first, 1)-projected_area*cx*cy
        # On the plane, u=s/t*x and v=p*q/t*x+t*y; physical dA=s*dx*dy.
        il = s*(s/t)**2*xx
        it = s*((p*q/t)**2*xx+2*p*q*xy+t*t*yy)
        product = s*(s/t)*((p*q/t)*xx+t*xy)
    active = [i for i in range(len(xs)-1) if width[i] > 0 or width[i+1] > 0]
    length = xs[active[-1]+1]-xs[active[0]] if active else None
    endpoints = [y for spans in intervals for pair in spans for y in pair]
    beam = max(endpoints)-min(endpoints) if endpoints else None
    draft = d-keel
    area_mid = None
    for i in range(len(xs)-1):
        if xs[i] <= 0 <= xs[i+1]:
            a0, a1 = sections[i]["area_m2"], sections[i+1]["area_m2"]
            area_mid = a0+(a1-a0)*(-xs[i])/(xs[i+1]-xs[i])
            break
    volume = hydro["volume"]
    upright = p == 0 and q == 0
    valid_derivatives = partial and upright and not boundary_contact and volume > 0 and projected_area > 0
    values = dict(volume_m3=volume, displacement_t=volume*rho,
        lcb_m=hydro["xlcb"] if volume > 0 else None,
        tcb_m=hydro["yb"] if volume > 0 else None,
        kb_m=hydro["zb"]-keel if volume > 0 else None,
        awp_m2=projected_area*s, awp_projected_xy_m2=projected_area,
        it_m4=it, il_m4=il, waterplane_product_m4=product,
        waterplane_centroid_x_m=cx, waterplane_centroid_y_m=cy,
        bm_t_m=it/volume if valid_derivatives else None,
        bm_l_m=il/volume if valid_derivatives else None,
        km_t_m=(hydro["zb"]-keel+it/volume) if valid_derivatives else None,
        tpc_t_per_cm=projected_area*rho/100 if valid_derivatives else None,
        waterline_length_body_x_m=length, waterline_beam_body_y_m=beam,
        reference_draft_midships_m=draft)
    coefficients = dict(cb=None, cm=None, cp=None, cwp=None)
    if partial and length and beam and draft > 0:
        coefficients.update(cb=volume/(length*beam*draft),
                            cm=area_mid/(beam*draft) if area_mid is not None else None,
                            cp=volume/(length*area_mid) if area_mid else None,
                            cwp=projected_area/(length*beam))
    diagnostics = [_diagnostic("geometry.sealed_envelope",
        "section polygons define a sealed integration envelope, not evidence of a watertight deck")]
    if not partial:
        diagnostics.append(_diagnostic("geometry.envelope_limit",
            f"plane is {envelope_state}; waterplane derivatives and stability radii are unavailable"))
    if not upright:
        diagnostics.append(_diagnostic("geometry.inclined_reference",
            "inclined body-axis ratios are not upright empirical resistance inputs; BM/TPC are unavailable"))
    if boundary_contact:
        diagnostics.append(_diagnostic("geometry.waterplane_contact",
            "a boundary edge coincides with the plane; geometric intersection is not a one-sided derivative"))
    if any(value is None for value in coefficients.values()):
        diagnostics.append(_diagnostic("geometry.form_reference_unavailable",
            "coefficient references require partial immersion, positive waterline length/beam/midships draft "
            "and known midships section area"))
    result = {**_envelope("completed" if partial else "model_limit", diagnostics),
        "geometry": copy.deepcopy(metadata), "plane": plane, "rho_t_m3": rho, "estimate": True,
        "envelope_state": envelope_state, "values": values, "sections": sections,
        "units": dict(length="m", area="m2", volume="m3", inertia="m4", mass="t", density="t/m3"),
        "waterplane_frame": "orthonormal_plane_u_longitudinal_v_transverse_centroidal_moments",
        "waterplane_axes": dict(u=[(1+q*q)/(s*t), -p*q/(s*t), p/(s*t)], v=[0, 1/t, q/t]),
        "upright_empirical_eligible": valid_derivatives,
        "form_coefficients": dict(values=coefficients,
            applicability="upright_body_axis_coefficients" if upright else
                          "inclined_body_axis_ratios_not_upright_empirical_inputs",
            reference="station-support x length, extreme waterline y beam, midships plane draft; "
                      "Cm and Cp use linearly interpolated submerged area at x=0",
            length_method="support_of_piecewise_linear_station_chords"),
        "wetted_surface": dict(area_m2=_linear_integral(xs, girths),
            method="longitudinal_station_girth_integral", estimate=True, end_faces="excluded",
            units="m2", approximation="ignores longitudinal shell slope and finite end faces",
            station_girths_m=girths),
        "trace": dict(submerged_moments="geometry.StationedHull.integrate: station trapezoids",
            clipping="geometry.clip_below_line via section_under_line",
            waterplane="geometry.waterline_intervals; exact x-polynomial moments of linear station scalars",
            wetted_surface="trapezoidal integral of submerged original boundary edges; no closing waterline edge")}
    return _finite_result(result)


def measures_at_plane(hull, plane, *, rho_t_m3=1.025, geometry_options=None) -> dict:
    """Measure validated geometry at exactly the supplied p/q/intercept plane.

    Args:
        hull (dict | object): Materialized canonical geometry or stationed hull.
        plane (dict): Finite p, q and waterline_d_m in the geometry datum.
        rho_t_m3 (float): Positive density, serialized explicitly.
        geometry_options (dict, optional): Explicit keel datum for stationed objects.

    Returns:
        (dict): Selected-plane measures, body-axis coefficients and method limitations.
    """
    rho = _number(rho_t_m3, "rho_t_m3")
    if rho <= 0:
        raise ValueError("rho_t_m3 must be positive")
    return _measures(stability.prepare_geometry(hull, geometry_options), _plane(plane), rho)


def bonjean_table(hull, waterlines_above_keel_m, *, geometry_options=None) -> dict:
    """Evaluate explicitly requested upright section areas in the declared keel datum."""
    levels = _grid(waterlines_above_keel_m, "waterlines_above_keel_m")
    obj, _, _, metadata = stability.prepare_geometry(hull, geometry_options)
    keel = metadata["keel_offset_m"]
    z_levels = [h+keel for h in levels]
    curves = [obj.bonjean_curve(i, z_levels) for i in range(len(obj.stations))]
    lower, upper = metadata["bounds_m"][2]
    rows = []
    for i, (height, z) in enumerate(zip(levels, z_levels)):
        partial = lower < z < upper
        outside = z < lower or z > upper
        rows.append({**_envelope("completed" if partial else "model_limit", [] if partial else [
            _diagnostic("geometry.envelope_limit", "requested ordinate contacts or exceeds the sealed envelope")]),
            "waterline_above_keel_m": height, "waterline_z_m": z,
            "sections": [dict(x_m=x, area_m2=None if outside else curves[j][i][1])
                         for j, (x, _) in enumerate(obj.stations)]})
    return _finite_result(dict(method_version=METHOD_VERSION, geometry=metadata,
        waterline_datum="above_declared_keel", scenario="upright_station_section_areas",
        units=dict(length="m", section_area="m2"), requested_waterlines_above_keel_m=levels, rows=rows))


def hydrostatic_table(hull, waterlines_above_keel_m, *, rho_t_m3=1.025, geometry_options=None) -> dict:
    """Evaluate bounded upright reference planes without asserting loading equilibrium."""
    levels = _grid(waterlines_above_keel_m, "waterlines_above_keel_m")
    rho = _number(rho_t_m3, "rho_t_m3")
    if rho <= 0:
        raise ValueError("rho_t_m3 must be positive")
    prepared = stability.prepare_geometry(hull, geometry_options)
    rows = []
    for height in levels:
        z = height+prepared[3]["keel_offset_m"]
        rows.append({**_measures(prepared, dict(p=0, q=0, waterline_d_m=z), rho),
                     "waterline_above_keel_m": height, "waterline_z_m": z})
    return _finite_result(dict(method_version=METHOD_VERSION,
        scenario="constrained_upright_reference_waterlines", loading_equilibrium_claim=False,
        waterline_datum="above_declared_keel", rho_t_m3=rho,
        requested_waterlines_above_keel_m=levels, rows=rows))


def _validated_deck_points(deck):
    """Validate supplied deck data independently of any equilibrium outcome."""
    if deck is None:
        return None
    if not isinstance(deck, dict) or not isinstance(deck.get("points"), (list, tuple)):
        raise ValueError("deck must contain an explicit points array")
    if (not isinstance(deck.get("source"), (str, dict)) or not deck["source"]
            or isinstance(deck["source"], str) and not deck["source"].strip()):
        raise ValueError("deck needs explicit source provenance")
    if not isinstance(deck.get("estimate"), bool):
        raise ValueError("deck estimate must be boolean")
    if not 1 <= len(deck["points"]) <= 10000:
        raise ValueError("deck must contain 1..10000 supplied points")
    ids, points = set(), []
    for point in deck["points"]:
        if not isinstance(point, dict) or not isinstance(point.get("id"), str) or not point["id"].strip() or point["id"] in ids:
            raise ValueError("deck points need unique nonempty string IDs")
        ids.add(point["id"])
        x, y, z = [_number(point.get(key), key) for key in ("x_m", "y_m", "z_m")]
        points.append((point["id"], x, y, z))
    _finite_result(deck)
    return points


def deck_clearance(deck, plane, *, keel_offset_m) -> dict:
    """Measure explicitly supplied deck points using signed waterplane-normal distance."""
    selected = _plane(plane)
    keel = _number(keel_offset_m, "keel_offset_m")
    points = _validated_deck_points(deck)
    if points is None:
        return {**_envelope("unavailable", [_diagnostic("geometry.deck_unknown",
            "deck geometry was not supplied", "$.deck")]), "minimum_clearance_m": None,
            "points": [], "event_type": "deck_geometry_only_not_downflooding"}
    p, q, d = selected["p"], selected["q"], selected["waterline_d_m"]
    rows = []
    for point_id, x, y, z in points:
        clearance = (z+keel-p*x-q*y-d)/math.hypot(1, p, q)
        rows.append(dict(id=point_id, normal_clearance_m=clearance,
                         state="dry" if clearance > 0 else "immersed" if clearance < 0 else "contact"))
    minimum = min(rows, key=lambda row: row["normal_clearance_m"])
    return _finite_result({**_envelope(), "minimum_clearance_m": minimum["normal_clearance_m"],
        "limiting_point_id": minimum["id"], "points": rows, "plane": selected,
        "deck": copy.deepcopy(deck), "keel_offset_m": keel, "units": "m",
        "event_type": "deck_geometry_only_not_downflooding"})


def deck_immersion_events(deck, samples, *, keel_offset_m) -> dict:
    """Report deck contacts and sign brackets from existing equilibrium samples only."""
    _number(keel_offset_m, "keel_offset_m")
    _validated_deck_points(deck)
    if not isinstance(samples, (list, tuple)) or any(not isinstance(s, dict) for s in samples):
        raise ValueError("samples must be an array of angle/equilibrium objects")
    _grid([s.get("angle_deg") for s in samples], "angle_deg")
    rows, events, previous = [], [], None
    for sample in samples:
        angle, equilibrium = sample["angle_deg"], sample.get("equilibrium")
        if not isinstance(equilibrium, dict) or equilibrium.get("converged") is not True:
            row = {**_envelope("unavailable", [_diagnostic("geometry.deck_sample_unavailable",
                "no converged plane exists at this sample", "$.deck")]),
                "minimum_clearance_m": None}
        else:
            row = deck_clearance(deck, equilibrium, keel_offset_m=keel_offset_m)
        rows.append({**row, "angle_deg": angle})
        value = row["minimum_clearance_m"]
        if value is None:
            previous = None
            continue
        if value == 0:
            events.append(dict(kind="sampled_contact", angle_deg=angle, point_id=row["limiting_point_id"]))
        elif previous is not None and previous[1]*value < 0:
            events.append(dict(kind="sampled_sign_bracket", bracket_deg=[previous[0], angle],
                angle_deg=None, direction="dry_to_immersed" if value < 0 else "immersed_to_dry",
                endpoint_point_ids=[previous[2], row["limiting_point_id"]]))
        elif value < 0 and previous is None:
            events.append(dict(kind="already_immersed_sample", angle_deg=angle,
                               point_id=row["limiting_point_id"]))
        previous = (angle, value, row["limiting_point_id"])
    last = rows[-1]
    endpoint = "failed_or_unknown_sample" if last["minimum_clearance_m"] is None else (
        "dry_at_last_sample_event_unknown" if last["minimum_clearance_m"] > 0 else "contact_or_immersed_sample")
    return _finite_result(dict(method_version=METHOD_VERSION, rows=rows, events=events,
        endpoint=dict(kind=endpoint, angle_deg=last["angle_deg"]), refined_events=False,
        event_type="deck_geometry_only_not_downflooding", safe_angle_deg=None,
        diagnostics=[_diagnostic("geometry.sampled_deck_events",
            "sparse samples may miss intermediate contact; no refined angle or watertightness is inferred", "$.deck")]))
