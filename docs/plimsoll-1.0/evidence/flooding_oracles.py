"""Independent reservoir and floating-prism ODE integrals, no Plimsoll import."""
import json
import math


def coupled_heave_oracle():
    """Integrate sea inflow with buoyancy-induced heave of a centred box."""
    ship_length, ship_beam, ship_height = 20., 10., 6.
    waterplane_area = ship_length * ship_beam
    tank_length, tank_beam, tank_height = 4., 2., 4.
    tank_area = tank_length * tank_beam
    density_t_m3, initial_draft, volume0 = 1.025, 2., 8.
    base_mass_t = density_t_m3 * (waterplane_area * initial_draft - volume0)
    cd, aperture_area, gravity, duration = .6, .1, 9.80665, 5.
    k = cd * aperture_area * math.sqrt(2 * gravity)
    a = 1 / tank_area - 1 / waterplane_area
    head0 = initial_draft - volume0 / tank_area
    # d = M_base/(rho*Awp) + V/Awp; H=d-V/S, hence dH/dt=-a*k*sqrt(H).
    head = (math.sqrt(head0) - a * k * duration / 2) ** 2
    influx = (head0 - head) / a
    volume = volume0 + influx
    return {
        'kind': 'continuous_coupled_heave_ODE_oracle_not_solver_result',
        'ship_dimensions_m': [ship_length, ship_beam, ship_height],
        'ship_centres_xy_m': [0., 0.], 'ship_keel_z_m': 0.,
        'base_mass_t': base_mass_t, 'base_cg_keel_m': [0., 0., 1.],
        'tank_dimensions_m': [tank_length, tank_beam, tank_height],
        'tank_centres_xy_m': [0., 0.], 'tank_bottom_z_m': 0.,
        'permeability': 1., 'fluid_density_t_m3': density_t_m3,
        'initial_water_volume_m3': volume0, 'initial_draft_m': initial_draft,
        'initial_differential_head_m': head0,
        'aperture_xyz_m': [0., 0., .1], 'orifice_area_m2': aperture_area,
        'discharge_coefficient': cd, 'gravity_m_s2': gravity,
        'time_s': duration, 'net_sea_inflow_m3': influx,
        'final_water_volume_m3': volume,
        'final_draft_m': initial_draft + influx / waterplane_area,
        'final_tank_level_m': volume / tank_area,
        'final_differential_head_m': head,
        'final_heel_deg': 0., 'final_trim_deg': 0.,
        'equalization_time_s': 2 * math.sqrt(head0) / (a * k),
        'limitations': 'Centred symmetric box/tank, identical fluid, vented '
                       'point orifice continuously submerged on both sides, '
                       'constant Cd, no capacity or deck boundary reached.',
    }


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
    # Adjacent tanks share an aperture. Equal body-frame fill heights do not
    # imply equal world-vertical pressure heads when the body is inclined.
    p, q = .1, .2
    normal_scale = math.sqrt(1+p*p+q*q)
    port_head = (1.5+.5*q-.25)/normal_scale
    starboard_head = (1.5-.5*q-.25)/normal_scale
    inclined_rate = k*math.sqrt(port_head-starboard_head)
    return {
        'kind':'continuous_flooding_ODE_oracles_not_solver_results',
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
        'inclined_instantaneous':{
            'tank_dimensions_m':[10.,1.,3.], 'tank_bottom_z_m':0.,
            'tank_centres_xy_m':[[0.,-.5],[0.,.5]],
            'water_volume_each_m3':15., 'permeability':1.,
            'aperture_xyz_m':[0.,0.,.25],
            'trim_deg':math.degrees(math.atan(p)),
            'heel_deg':math.degrees(math.atan(q)),
            'port_head_m':port_head,'starboard_head_m':starboard_head,
            'flow_port_to_starboard_m3_s':inclined_rate},
        'coupled_heave': coupled_heave_oracle(),
        'limitations':'Pair/sea/inclined anchors use fixed attitude; coupled_heave includes symmetric buoyancy feedback. Identical fluid, vented reservoirs, constant Cd and orifice area; these answers test the chosen ODE, not real ship flooding accuracy.',
    }


if __name__ == '__main__':
    print(json.dumps(oracle(), ensure_ascii=False, indent=2, allow_nan=False))
