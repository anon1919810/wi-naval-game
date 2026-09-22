"""Independent fixed-attitude two-reservoir ODE integrals, no Plimsoll import."""
import json
import math


def oracle():
    area, discharge_coefficient, gravity = .1, .6, 9.80665
    surface_area, time_s = 10., 5.
    k = discharge_coefficient * area * math.sqrt(2*gravity)
    # Equal tank surface areas: dH/dt=-2k sqrt(H)/S.
    difference0 = 1.
    pair_difference = (math.sqrt(difference0)-k*time_s/surface_area)**2
    transferred = surface_area*(difference0-pair_difference)/2
    # Constant sea: dH/dt=-k sqrt(H)/S, H=sea_head-tank_head.
    sea_head, tank_head0 = 3., 1.
    sea_difference = (math.sqrt(sea_head-tank_head0)-k*time_s/(2*surface_area))**2
    final_tank_head = sea_head-sea_difference
    return {
        'kind':'continuous_fixed_attitude_ODE_oracle_not_solver_result',
        'inputs':{'orifice_area_m2':area, 'discharge_coefficient':discharge_coefficient,
                  'gravity_m_s2':gravity, 'tank_surface_area_m2':surface_area,
                  'time_s':time_s, 'aperture_centre_z_m':0., 'tank_height_m':5.},
        'pair':{'initial_heads_m':[2.,1.], 'final_head_difference_m':pair_difference,
                'transferred_m3':transferred,
                'final_volumes_m3':[20.-transferred,10.+transferred],
                'total_volume_m3':30.,
                'equalization_time_s':surface_area*math.sqrt(difference0)/k},
        'sea':{'sea_head_m':sea_head, 'initial_tank_head_m':tank_head0,
               'final_tank_head_m':final_tank_head,
               'net_sea_inflow_m3':surface_area*(final_tank_head-tank_head0),
               'final_tank_volume_m3':surface_area*final_tank_head},
        'limitations':'Fixed attitude, identical fluid, vented reservoirs, constant Cd and orifice area; these answers test the chosen ODE, not real ship flooding accuracy.',
    }


if __name__ == '__main__':
    print(json.dumps(oracle(), ensure_ascii=False, indent=2, allow_nan=False))
