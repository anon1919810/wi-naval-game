"""Independent sliced-ellipsoid integrals; this imports no Plimsoll code."""
import json
import math


def oracle():
    a, b, c = 20., 5., 5.
    p, q, d, rho, kg = .01, .1, 4., 1.025, 3.
    # x=a*X,y=b*Y,z=c+c*Z maps the ellipsoid to the unit sphere.
    # Its clipping plane is (-p*a,-q*b,c) dot (X,Y,Z) <= d-c.
    support = math.sqrt((p*a)**2+(q*b)**2+c*c)
    t = (d-c)/support
    fraction_polynomial = 2+3*t-t**3
    mu = -3*(1-t*t)**2/(4*fraction_polynomial)
    volume = math.pi*a*b*c*fraction_polynomial/3
    bx, by, bz = -mu*p*a*a/support, -mu*q*b*b/support, c+mu*c*c/support
    dz = bz-kg
    gz = .15
    return {
        'kind': 'continuous_analytic_oracle_not_solver_result',
        'geometry_m': {'semi_axes':[a,b,c], 'centre':[0,0,c], 'keel_offset':0},
        'waterplane': {'p':p, 'q':q, 'd_m':d,
                       'trim_deg':math.degrees(math.atan(p)),
                       'heel_deg':math.degrees(math.atan(q))},
        'volume_m3':volume, 'mass_t':rho*volume,
        'buoyancy_centre_m':[bx,by,bz],
        'free_equilibrium_cg_m':[bx+p*dz,by+q*dz,kg],
        'constrained_heel_cg_m':[
            bx+p*dz-p*q*gz/math.sqrt(1+q*q),
            by+q*dz-gz*math.sqrt(1+q*q), kg],
        'constrained_heel_gz_m':gz,
        'discretization_note':'Refine longitudinal stations and polygonal elliptical sections separately; this continuous oracle is not fitted to a sampled hull.',
    }


if __name__ == '__main__':
    print(json.dumps(oracle(), ensure_ascii=False, indent=2, allow_nan=False))
