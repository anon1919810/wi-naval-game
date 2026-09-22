"""Evaluate the versioned Holtrop--Mennen 1982 full-resistance equations.

The implementation follows International Shipbuilding Progress 29 (1982),
pages 166--170. It does not mix in the 1984 form-factor or wave regressions.
All calculations use SI units internally and expose empirical applicability
separately from algebraic availability.
"""

from __future__ import annotations

import copy
import math
from numbers import Real

METHOD = "holtrop_mennen_1982"
KNOT_M_S = 1852.0 / 3600.0


class HoltropError(ValueError):
    """Base class for unavailable Holtrop calculations."""

    code = "holtrop.unavailable"

    def __init__(self, message: str, path: str = "$"):
        """Initialize an unavailable result with a structured diagnostic."""
        self.diagnostics = [
            {
                "code": self.code,
                "severity": "error",
                "path": path,
                "message": message,
                "blocking": True,
            }
        ]
        super().__init__(message)


class HoltropInputError(HoltropError):
    """Report an invalid or missing model input."""

    code = "holtrop.input_invalid"


class HoltropNumericalError(HoltropError):
    """Report arithmetic outside the supported floating-point domain."""

    code = "holtrop.numerical_domain"


def _diagnostic(code: str, severity: str, path: str, message: str, blocking: bool) -> dict:
    return {
        "code": code,
        "severity": severity,
        "path": path,
        "message": message,
        "blocking": blocking,
    }


def _number(
    inputs: dict,
    key: str,
    *,
    positive: bool = False,
    nonnegative: bool = False,
    path: str | None = None,
) -> float:
    diagnostic_path = path or f"$.{key}"
    value = inputs.get(key)
    if isinstance(value, bool) or not isinstance(value, Real):
        raise HoltropInputError(f"{key}: expected a finite real number", diagnostic_path)
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise HoltropInputError(
            f"{key}: outside the supported numeric range", diagnostic_path
        ) from exc
    if not math.isfinite(number):
        raise HoltropInputError(f"{key}: expected a finite real number", diagnostic_path)
    if positive and number <= 0.0 or nonnegative and number < 0.0:
        raise HoltropInputError(
            f"{key}: outside the positive/nonnegative domain", diagnostic_path
        )
    return number


def c12(draft_length_ratio: float) -> float:
    """Calculate the 1982 form-factor coefficient c12."""
    if draft_length_ratio < 0.02:
        return 0.479948
    if draft_length_ratio <= 0.05:
        return 48.2 * (draft_length_ratio - 0.02) ** 2.078 + 0.479948
    return draft_length_ratio**0.2228446


def c7(beam_length_ratio: float) -> float:
    """Calculate the 1982 wave coefficient c7."""
    if beam_length_ratio < 0.11:
        return 0.229577 * beam_length_ratio ** (1.0 / 3.0)
    if beam_length_ratio <= 0.25:
        return beam_length_ratio
    return 0.5 - 0.0625 / beam_length_ratio


def c15(length_cubed_volume_ratio: float) -> float:
    """Calculate the 1982 wave coefficient c15."""
    if length_cubed_volume_ratio < 512.0:
        return -1.69385
    if length_cubed_volume_ratio <= 1727.0:
        return -1.69385 + (length_cubed_volume_ratio ** (1.0 / 3.0) - 8.0) / 2.36
    return 0.0


def c16(prismatic_coefficient: float) -> float:
    """Calculate the 1982 wave coefficient c16."""
    if prismatic_coefficient <= 0.8:
        return (
            8.07981 * prismatic_coefficient
            - 13.8673 * prismatic_coefficient**2
            + 6.984388 * prismatic_coefficient**3
        )
    return 1.73014 - 0.7067 * prismatic_coefficient


def wave_lambda(prismatic_coefficient: float, length_beam_ratio: float) -> float:
    """Calculate the 1982 wave phase coefficient lambda."""
    if length_beam_ratio < 12.0:
        return 1.446 * prismatic_coefficient - 0.03 * length_beam_ratio
    return 1.446 * prismatic_coefficient - 0.36


def c4(fore_draft_length_ratio: float) -> float:
    """Calculate the 1982 correlation coefficient c4."""
    return min(fore_draft_length_ratio, 0.04)


def c6(transom_froude: float) -> float:
    """Calculate the 1982 immersed-transom coefficient c6."""
    if transom_froude < 5.0:
        return 0.2 * (1.0 - 0.2 * transom_froude)
    return 0.0


def compute(inputs: dict) -> dict:
    """Calculate full 1982 resistance components from explicit hull inputs.

    Args:
        inputs (dict): Hull, operating-point, fluid, scenario, and provenance inputs.

    Returns:
        (dict): Component forces, coefficients, diagnostics, and method metadata.

    Raises:
        HoltropInputError: If required data are missing or outside the real equation domain.
        HoltropNumericalError: If finite inputs exceed the supported arithmetic domain.
    """
    if not isinstance(inputs, dict):
        raise HoltropInputError("inputs: expected an object")
    try:
        return _compute(inputs)
    except HoltropError:
        raise
    except (ArithmeticError, OverflowError, ValueError) as exc:
        raise HoltropNumericalError(f"{METHOD}: numerical-domain failure: {exc}") from exc


def _compute(inputs: dict) -> dict:
    length = _number(inputs, "lwl_m", positive=True)
    beam = _number(inputs, "beam_m", positive=True)
    tf = _number(inputs, "draft_fore_m", positive=True)
    ta = _number(inputs, "draft_aft_m", positive=True)
    draft = (tf + ta) / 2.0
    volume = _number(inputs, "displacement_volume_m3", positive=True)
    cm = _number(inputs, "midship_coeff", positive=True)
    cwp = _number(inputs, "waterplane_coeff", positive=True)
    lcb = _number(inputs, "lcb_percent_lwl")
    cstern = _number(inputs, "c_stern")
    abt = _number(inputs, "bulb_area_m2", nonnegative=True)
    at = _number(inputs, "transom_area_m2", nonnegative=True)
    speed = _number(inputs, "speed_kn", positive=True) * KNOT_M_S
    rho = _number(inputs, "density_kg_m3", positive=True)
    gravity = _number(inputs, "gravity_m_s2", positive=True)
    nu = _number(inputs, "kinematic_viscosity_m2_s", positive=True)

    if not 0.0 < cm <= 1.0 or not 0.0 < cwp < 1.0:
        raise HoltropInputError("midship/waterplane coefficient outside supported domain")
    cb = volume / (length * beam * draft)
    cp = cb / cm
    if not 0.0 < cb <= 1.0 or not 0.0 < cp < 0.95 or cp == 0.25:
        raise HoltropInputError("block/prismatic coefficient outside equation domain")

    lr = length * (1.0 - cp + 0.06 * cp * lcb / (4.0 * cp - 1.0))
    fore_lcb_base = 1.0 - cp + 0.0225 * lcb
    aft_lcb_base = 1.0 - cp - 0.0225 * lcb
    if lr <= 0.0 or fore_lcb_base <= 0.0 or aft_lcb_base <= 0.0:
        raise HoltropInputError("LCB/run-length fractional-power domain")
    coefficient_c13 = 1.0 + 0.003 * cstern
    if coefficient_c13 <= 0.0:
        raise HoltropInputError("stern coefficient gives non-positive form factor")
    coefficient_c12 = c12(draft / length)
    form_factor = coefficient_c13 * (
        0.93
        + coefficient_c12
        * (beam / lr) ** 0.92497
        * (0.95 - cp) ** -0.521448
        * fore_lcb_base**0.6906
    )

    if "wetted_surface_m2" in inputs:
        area = _number(inputs, "wetted_surface_m2", positive=True)
        area_method = "explicit_input"
    else:
        area = length * (2.0 * draft + beam) * math.sqrt(cm) * (
            0.453
            + 0.4425 * cb
            - 0.2862 * cm
            - 0.003467 * beam / draft
            + 0.3696 * cwp
        )
        area += 2.38 * abt / cb
        area_method = "holtrop_1982_wetted_surface_regression"
    if area <= 0.0:
        raise HoltropInputError("wetted surface outside supported domain")

    reynolds = speed * length / nu
    if not math.isfinite(reynolds) or reynolds <= 100.0:
        raise HoltropInputError("Reynolds number outside algebraic support policy (Re > 100)")
    log_term = math.log10(reynolds) - 2.0
    if log_term == 0.0:
        raise HoltropInputError("ITTC-1957 friction denominator is singular")
    cf = 0.075 / log_term**2
    dynamic_pressure = 0.5 * rho * speed**2
    rf = dynamic_pressure * area * cf

    appendages = inputs.get("appendages")
    if not isinstance(appendages, list):
        raise HoltropInputError(
            "appendages: explicit array required, [] for none", "$.appendages"
        )
    effective_appendage_area = 0.0
    for index, appendage in enumerate(appendages):
        if not isinstance(appendage, dict):
            raise HoltropInputError(
                f"appendages[{index}]: expected an object", f"$.appendages[{index}]"
            )
        effective_appendage_area += _number(
            appendage,
            "area_m2",
            nonnegative=True,
            path=f"$.appendages[{index}].area_m2",
        ) * _number(
            appendage,
            "factor",
            positive=True,
            path=f"$.appendages[{index}].factor",
        )
    rapp = dynamic_pressure * cf * effective_appendage_area

    fn = speed / math.sqrt(gravity * length)
    beam_length = beam / length
    coefficient_c7 = c7(beam_length)
    entrance_angle = 1.0 + 89.0 * math.exp(
        -(length / beam) ** 0.80856
        * (1.0 - cwp) ** 0.30484
        * aft_lcb_base**0.6367
        * (lr / beam) ** 0.34574
        * (100.0 * volume / length**3) ** 0.16302
    )
    if entrance_angle >= 90.0 or coefficient_c7 <= 0.0:
        raise HoltropInputError("entrance angle or wave coefficient outside domain")
    coefficient_c1 = (
        2_223_105.0
        * coefficient_c7**3.78613
        * (draft / beam) ** 1.07961
        * (90.0 - entrance_angle) ** -1.37565
    )

    pb = None
    fni = None
    if abt == 0.0:
        coefficient_c3 = 0.0
        coefficient_c2 = 1.0
        rb = 0.0
    else:
        hb = _number(inputs, "bulb_height_m", nonnegative=True)
        coefficient_denominator = beam * draft * (0.31 * math.sqrt(abt) + tf - hb)
        bulb_depth = tf - 1.5 * hb
        immersion = gravity * (tf - hb - 0.25 * math.sqrt(abt)) + 0.15 * speed**2
        if coefficient_denominator <= 0.0 or bulb_depth == 0.0 or immersion <= 0.0:
            raise HoltropInputError("bulb geometry outside the real 1982 algebraic domain")
        coefficient_c3 = 0.56 * abt**1.5 / coefficient_denominator
        coefficient_c2 = math.exp(-1.89 * math.sqrt(coefficient_c3))
        pb = 0.56 * math.sqrt(abt) / bulb_depth
        fni = speed / math.sqrt(immersion)
        inverse_pb_square_log = (
            math.log(3.0)
            + 2.0 * math.log(abs(bulb_depth))
            - 2.0 * math.log(0.56)
            - math.log(abt)
        )
        bulb_attenuation = 0.0 if inverse_pb_square_log > 700.0 else math.exp(-math.exp(inverse_pb_square_log))
        rb = (
            0.11
            * bulb_attenuation
            * fni**3
            * abt**1.5
            * rho
            * gravity
            / (1.0 + fni**2)
        )

    coefficient_c5 = 1.0 - 0.8 * at / (beam * draft * cm)
    if coefficient_c5 < 0.0:
        raise HoltropInputError("transom area gives negative wave-resistance factor c5")
    coefficient_lambda = wave_lambda(cp, length / beam)
    coefficient_c16 = c16(cp)
    m1 = (
        0.0140407 * length / draft
        - 1.75254 * volume ** (1.0 / 3.0) / length
        - 4.79323 * beam / length
        - coefficient_c16
    )
    slenderness = length**3 / volume
    coefficient_c15 = c15(slenderness)
    m2 = coefficient_c15 * cp**2 * math.exp(-0.1 * fn**-2)
    rw = coefficient_c1 * coefficient_c2 * coefficient_c5 * volume * rho * gravity * math.exp(
        m1 * fn**-0.9 + m2 * math.cos(coefficient_lambda * fn**-2)
    )

    transom_froude = None
    if at == 0.0:
        coefficient_c6 = 0.0
        rtr = 0.0
    else:
        transom_radicand = 2.0 * gravity * at / (beam * (1.0 + cwp))
        if transom_radicand <= 0.0:
            raise HoltropNumericalError("transom Froude denominator underflowed")
        transom_froude = speed / math.sqrt(transom_radicand)
        coefficient_c6 = c6(transom_froude)
        rtr = dynamic_pressure * at * coefficient_c6

    coefficient_c4 = c4(tf / length)
    ca = (
        0.006 * (length + 100.0) ** -0.16
        - 0.00205
        + 0.003
        * math.sqrt(length / 7.5)
        * cb**4
        * coefficient_c2
        * (0.04 - coefficient_c4)
    )
    ra = dynamic_pressure * area * ca

    diagnostics = []
    optional_terms_known = True
    bow_thruster = inputs.get("bow_thruster")
    rbto = 0.0
    if bow_thruster is None:
        optional_terms_known = False
    elif not isinstance(bow_thruster, dict) or not isinstance(bow_thruster.get("present"), bool):
        raise HoltropInputError("bow_thruster: expected {'present': boolean, ...}")
    elif bow_thruster["present"]:
        diameter = _number(
            bow_thruster, "diameter_m", positive=True, path="$.bow_thruster.diameter_m"
        )
        coefficient = _number(
            bow_thruster, "coefficient", positive=True, path="$.bow_thruster.coefficient"
        )
        rbto = rho * speed**2 * math.pi * diameter**2 * coefficient
        if not 0.003 <= coefficient <= 0.012:
            diagnostics.append(
                _diagnostic(
                    "holtrop.bow_thruster_coefficient_outside_source_range",
                    "warning",
                    "$.bow_thruster.coefficient",
                    "The declared coefficient is outside the 0.003--0.012 tentative 1982 range.",
                    False,
                )
            )

    if "additional_roughness_delta_ca" not in inputs or inputs["additional_roughness_delta_ca"] is None:
        optional_terms_known = False
        roughness_delta_ca = 0.0
    else:
        roughness_delta_ca = _number(inputs, "additional_roughness_delta_ca", nonnegative=True)
    roughness = dynamic_pressure * area * roughness_delta_ca
    if not optional_terms_known:
        diagnostics.append(
            _diagnostic(
                "holtrop.optional_terms_unknown",
                "warning",
                "$",
                "Bow-thruster and additional-roughness scenario choices must be declared for a complete vessel scenario.",
                False,
            )
        )

    total = rf * form_factor + rapp + rw + rb + rtr + ra + rbto + roughness
    effective_power = total * speed
    values = {
        "rf_kn": rf / 1000.0,
        "rapp_kn": rapp / 1000.0,
        "rw_kn": rw / 1000.0,
        "rb_kn": rb / 1000.0,
        "rtr_kn": rtr / 1000.0,
        "ra_kn": ra / 1000.0,
        "rbto_kn": rbto / 1000.0,
        "roughness_kn": roughness / 1000.0,
        "total_resistance_kn": total / 1000.0,
        "effective_power_kw": effective_power / 1000.0,
        "one_plus_k1": form_factor,
        "wetted_surface_m2": area,
        "effective_appendage_area_m2": effective_appendage_area,
        "c1": coefficient_c1,
        "c2": coefficient_c2,
        "c3": coefficient_c3,
        "c4": coefficient_c4,
        "c5": coefficient_c5,
        "c6": coefficient_c6,
        "c7": coefficient_c7,
        "c12": coefficient_c12,
        "c13": coefficient_c13,
        "c15": coefficient_c15,
        "c16": coefficient_c16,
        "ca": ca,
        "cf": cf,
        "cb": cb,
        "cp": cp,
        "m1": m1,
        "m2": m2,
        "wave_lambda": coefficient_lambda,
        "run_length_m": lr,
        "entrance_angle_deg": entrance_angle,
        "froude": fn,
        "reynolds": reynolds,
        "pb": pb,
        "fni": fni,
        "transom_froude": transom_froude,
    }
    if any(value is not None and not math.isfinite(value) for value in values.values()):
        raise HoltropNumericalError("nonfinite model result")
    if total <= 0.0:
        raise HoltropNumericalError("non-positive total resistance")

    if fn > 0.5:
        diagnostics.append(
            _diagnostic(
                "holtrop.high_froude_1982",
                "warning",
                "$.speed_kn",
                "The 1982 paper reports unreliable high-speed predictions above about Fn=0.5.",
                False,
            )
        )
    turbulent_policy_met = reynolds >= 1e5
    if not turbulent_policy_met:
        diagnostics.append(
            _diagnostic(
                "holtrop.low_reynolds_project_policy",
                "warning",
                "$.kinematic_viscosity_m2_s",
                "The finite calculation is below the project's Re>=1e5 turbulent-result policy; this is not a Holtrop 1982 limit.",
                False,
            )
        )
    if ca < 0.0:
        diagnostics.append(
            _diagnostic(
                "holtrop.negative_correlation",
                "warning",
                "$.lwl_m",
                "The 1982 regression returned a signed negative correlation allowance.",
                False,
            )
        )
    if not -10.0 <= cstern <= 10.0:
        diagnostics.append(
            _diagnostic(
                "holtrop.stern_factor_outside_examples",
                "warning",
                "$.c_stern",
                "The stern factor is outside the paper's tentative -10, 0, and +10 examples.",
                False,
            )
        )

    empirical_eligible = fn <= 0.5 and turbulent_policy_met and optional_terms_known
    return {
        "schema": "plimsoll-holtrop-result-1",
        "method": METHOD,
        "values": values,
        "units": {
            "resistance": "kN",
            "power": "kW",
            "length": "m",
            "area": "m2",
            "density": "kg/m3",
            "speed_input": "kn",
        },
        "diagnostics": diagnostics,
        "applicability": {
            "algebraic_status": "valid",
            "empirical_status": "eligible_with_method_caveats" if empirical_eligible else "outside_or_incomplete",
            "primary_result": empirical_eligible,
            "turbulent_policy": "project_policy_reynolds_ge_1e5",
            "general_caveat": "Tentative regression for hulls resembling the method's average forms; no universal CB>=0.55 cutoff is asserted.",
        },
        "scenario": {
            "complete": optional_terms_known,
            "conditions": "Deep calm water; declared fluid constants; clean-hull base CA plus any declared additions.",
            "bow_thruster": copy.deepcopy(bow_thruster),
            "additional_roughness_delta_ca": (
                roughness_delta_ca if "additional_roughness_delta_ca" in inputs else None
            ),
        },
        "wetted_surface_method": area_method,
        "input_provenance": copy.deepcopy(inputs.get("input_provenance", {})),
        "constants": {
            "knot_m_s": KNOT_M_S,
            "density_kg_m3": rho,
            "gravity_m_s2": gravity,
            "kinematic_viscosity_m2_s": nu,
        },
        "source": {
            "authority": "Holtrop and Mennen, International Shipbuilding Progress 29(335), 166-170, 1982",
            "version_note": "No 1984 form-factor or wave terms are mixed into this method.",
        },
    }
