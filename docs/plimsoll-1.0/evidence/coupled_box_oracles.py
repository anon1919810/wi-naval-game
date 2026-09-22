"""Independent continuous-box integrals; this imports no Plimsoll code."""
import json
import math


def oracle():
    length, beam, draft, depth = 40.0, 10.0, 4.0, 10.0
    rho, kg, p, q = 1.025, 3.0, 0.01, 0.1
    volume = length * beam * draft
    bx = p * length**2 / (12 * draft)
    by = q * beam**2 / (12 * draft)
    bz = draft/2 + (p*p*length**2 + q*q*beam**2)/(24*draft)
    dz = bz-kg
    free_cg = [bx+p*dz, by+q*dz, kg]
    prescribed_gz = 0.25
    constrained_cg = [
        bx+p*dz-p*q*prescribed_gz/math.sqrt(1+q*q),
        by+q*dz-prescribed_gz*math.sqrt(1+q*q),
        kg,
    ]
    return {
        "kind": "continuous_analytic_oracle_not_solver_result",
        "geometry_m": {"length": length, "beam": beam, "depth": depth},
        "waterplane": {"p": p, "q": q, "d_m": draft,
                       "trim_deg": math.degrees(math.atan(p)),
                       "heel_deg": math.degrees(math.atan(q))},
        "mass_t": rho*volume,
        "volume_m3": volume,
        "buoyancy_centre_m": [bx, by, bz],
        "free_equilibrium_cg_m": free_cg,
        "constrained_heel_cg_m": constrained_cg,
        "constrained_heel_gz_m": prescribed_gz,
        "discretization_note": "Longitudinal station integration has a separate x-squared trapezoidal error; refine it instead of fitting this answer.",
    }


if __name__ == "__main__":
    print(json.dumps(oracle(), ensure_ascii=False, indent=2, allow_nan=False))
