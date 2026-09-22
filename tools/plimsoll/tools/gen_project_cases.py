# -*- coding: utf-8 -*-
"""Generate deterministic, self-contained canonical Plimsoll projects."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
PKG = HERE.parent
REPO = PKG.parent.parent
sys.path.insert(0, str(PKG))

import geometry  # noqa: E402
import offsets  # noqa: E402


LONG_TON_TO_T = 1.0160469088
LB_TO_T = 0.45359237 / 1000.0
ALGEBRAIC_TOLERANCE = {"relative": 1e-10, "absolute_t": 1e-10}
UNITS = {"length": "m", "mass": "t", "speed": "kn", "power": "kW", "angle": "deg"}
COORDINATES = {
    "x_positive": "forward",
    "x_origin": "midships",
    "y_positive": "starboard",
    "z_origin": "keel",
}
GROUP_LABELS = {
    "hull": "Hull structure",
    "armour": "Fixed armour",
    "armament": "Installed armament",
    "machinery": "Installed dry machinery",
    "outfit": "Fixed outfit",
    "ammunition": "Ammunition",
    "fuel": "Fuel",
    "water": "Water",
    "other_loads": "Other variable loads",
}


def _source(formula: str, citation: str, dependencies: list[str], boundary: str) -> dict:
    return {
        "formula": formula,
        "citation": citation,
        "dependencies": dependencies,
        "boundary": boundary,
    }


def _item(
    item_id: str,
    mass_t: float,
    x_m: float,
    y_m: float,
    kg_m: float,
    source: dict,
    includes: list[str],
    uncertainty: dict[str, list[float]],
) -> dict:
    return {
        "id": item_id,
        "mass_t": mass_t,
        "x_m": x_m,
        "y_m": y_m,
        "kg_m": kg_m,
        "source": source,
        "estimate": True,
        "uncertainty": uncertainty,
        "includes": includes,
    }


def _bounded(mass: float, x: float, y: float, kg: float, mass_bounds=None, dx=5.0, dy=0.5, dz=1.5):
    if mass_bounds is None:
        mass_bounds = [0.75 * mass, 1.25 * mass]
    return {
        "mass_t": list(mass_bounds),
        "x_m": [x - dx, x + dx],
        "y_m": [y - dy, y + dy],
        "kg_m": [max(0.0, kg - dz), kg + dz],
    }


def _serialize_hull(hull: geometry.StationedHull) -> dict:
    return {
        "schema": "plimsoll-section-polygons-1",
        "stations": [
            [x, [[y, z] for y, z in polygon]]
            for x, polygon in hull.stations
        ],
    }


def _project(project_id: str, name: str, hull: dict, geometry_payload: dict) -> dict:
    return {
        "schema": "plimsoll-project-1",
        "id": project_id,
        "name": name,
        "revision": 0,
        "units": UNITS,
        "coordinates": COORDINATES,
        "hull": hull,
        "geometry": geometry_payload,
        "weight_groups": [],
        "loading_conditions": [],
        "systems": {},
        "compartments": [],
        "openings": [],
        "sources": {},
    }


def _groups(items_by_group: dict[str, list[dict]], required: set[str], absent: dict[str, str] | None = None):
    absent = absent or {}
    return [
        {
            "id": group_id,
            "label": GROUP_LABELS[group_id],
            "required": group_id in required,
            "items": items_by_group.get(group_id, []),
            **({"absence_reason": absent[group_id]} if group_id in absent else {}),
        }
        for group_id in GROUP_LABELS
    ]


def _add_intact_damage_preset(project: dict) -> None:
    project["damage_presets"] = [
        {
            "id": "intact",
            "label": "Intact dry-compartment initial state",
            "initial_water_volumes_m3": {
                compartment["id"]: 0.0 for compartment in project["compartments"]
            },
            "opening_overrides": {},
            "source": "Explicit Task 3 initial-state fixture; zero is known, not missing.",
            "estimate": True,
        }
    ]


def _manifest_centres() -> dict[str, tuple[float, float, float]]:
    payload = json.loads((REPO / "queen_mary_v3" / "object_manifest.json").read_text(encoding="utf-8"))
    centres = {}
    for obj in payload["objects"]:
        bounds = obj.get("bounds_world_m")
        if not bounds:
            continue
        centre = [(low + high) / 2.0 for low, high in zip(bounds["min"], bounds["max"])]
        centres[obj["name"]] = (centre[1], centre[0], centre[2] + 9.9)
    return centres


def _qm_geometry() -> dict:
    payload = json.loads((PKG / "cases" / "queen_mary_1913_offsets.json").read_text(encoding="utf-8"))
    stationed = offsets.build_hull(payload["stations"], payload["deck_z_m"], n_stations=121, n_section=96)
    return {
        "kind": "offsets",
        "source": {
            "method": "materialized model-offset engineering geometry",
            "citation": "tools/plimsoll/cases/queen_mary_1913_offsets.json",
            "limitations": "Estimated model offsets; volume agreement does not validate sectional shape.",
        },
        "estimate": True,
        "keel_offset_m": -9.9,
        "offsets": _serialize_hull(stationed),
    }


def queen_mary_project() -> dict:
    project = _project(
        "hms-queen-mary-1913",
        "HMS Queen Mary (1913) engineering reference",
        {
            "lwl_m": 212.8,
            "loa_m": 214.4,
            "beam_m": 27.1,
            "draught_normal_m": 8.5,
            "draught_deep_m": 9.9,
            "block_coeff": 0.5328005513580124,
            "waterplane_coeff": 0.8,
        },
        _qm_geometry(),
    )
    centres = _manifest_centres()
    legacy = json.loads((PKG / "cases" / "queen_mary_1913_weights.json").read_text(encoding="utf-8"))
    armour_items = []
    armour_models = []
    for raw in legacy["groups"][0]["items"]:
        x, y, kg = centres[raw["id"]]
        item_id = raw["id"].lower().replace("_", "-")
        token = "armour.fixed." + item_id
        armour_items.append(
            _item(
                item_id,
                raw["mass_t"],
                x,
                y,
                kg,
                _source(
                    "area_m2 * thickness_mm / 1000 * 7.85 t/m3",
                    "tools/plimsoll/cases/queen_mary_1913_weights.json and queen_mary_v3/object_manifest.json",
                    ["published nominal thickness", "model bounding-box extent", "steel density"],
                    "Fixed protection proxy only; excludes rotating turret armour.",
                ),
                [token],
                _bounded(raw["mass_t"], x, y, kg, [0.55 * raw["mass_t"], 1.25 * raw["mass_t"]], dx=3.0),
            )
        )
        area_m2 = raw["_area_m2"]
        area_resolution_m2 = 0.1 if area_m2 == round(area_m2, 1) else 0.01
        armour_models.append(
            {
                "id": item_id + "-plate-mass-check",
                "method": "plate_area_thickness_density_mass",
                "linked_weight_item_id": item_id,
                "inputs": {
                    "area_m2": area_m2,
                    "thickness_m": raw["_thickness_mm"] / 1000.0,
                    "density_kg_m3": 7850.0,
                },
                "input_provenance": {
                    "area_m2": {
                        "source": raw["source"],
                        "estimate": True,
                        "rounded": True,
                        "displayed_resolution_m2": area_resolution_m2,
                    },
                    "thickness_m": {
                        "source": raw["source"],
                        "estimate": False,
                        "nominal": True,
                        "original_value": raw["_thickness_mm"],
                        "original_unit": "mm",
                    },
                    "density_kg_m3": {
                        "source": "declared legacy steel-density assumption",
                        "estimate": True,
                    },
                },
                "comparison_tolerance": dict(ALGEBRAIC_TOLERANCE),
                "comparison_policy": (
                    "Algebraic identity only. Rounded legacy area and 0.001 t ledger "
                    "precision are disclosed; differences remain review proposals and are not fitted."
                ),
                "source": raw["source"],
                "boundary": (
                    "Fixed protection plate represented by this existing ledger item; "
                    "excludes rotating turret armour."
                ),
                "estimate": True,
            }
        )

    hull_mass = 0.35 * 27_000 * LONG_TON_TO_T
    gun_mass = 8 * 167_776 * LB_TO_T
    mount_mass = 4 * 600 * LONG_TON_TO_T
    secondary_mass = 16 * 42 * 112 * LB_TO_T
    machinery_mass = 75_000 / 15 * LONG_TON_TO_T
    boiler_mass = 0.45 * machinery_mass
    engine_mass = 0.55 * machinery_mass
    outfit_mass = 0.03 * 27_000 * LONG_TON_TO_T
    main_ammo = 8 * 80 * (1400 + 297) * LB_TO_T
    secondary_ammo = 16 * 150 * (31 + 9 + (5 + 15 / 16) / 16) * LB_TO_T
    normal_feed_water = 0.015 * 27_000 * LONG_TON_TO_T
    deep_feed_water = 0.025 * 27_000 * LONG_TON_TO_T

    hull = _item(
        "hull-structure", hull_mass, 0.0, 0.0, 7.5,
        _source(
            "0.35 * 27000 long_ton * 1.0160469088 t/long_ton",
            "J. J. Welch, A Text Book of Naval Architecture (1891), pp. 79-80",
            ["assumed-long-ton design displacement", "35% screening midpoint"],
            "Shell, decks, framing, structural bulkheads and fixed foundations; excludes protection, plant, weapons, outfit and consumables.",
        ),
        ["hull.primary-structure", "hull.structural-bulkheads", "hull.fixed-foundations"],
        _bounded(hull_mass, 0.0, 0.0, 7.5, [6858.317, 11521.972], dx=8.0, dy=1.0, dz=2.5),
    )
    main_guns = _item(
        "main-guns", gun_mass, 8.0, 0.0, 20.141,
        _source(
            "8 installed guns * 167776 lb/gun * 0.45359237 kg/lb / 1000",
            "NavWeaps WNBR_135-45_mk5 (secondary compilation)",
            ["installed gun count", "gun weight without breech convention", "manifest role centroid for position"],
            "Intended complete gun-tube/breech boundary; the published nominal explicitly excludes breech mass, so that contribution remains unresolved inside the applicability interval. Excludes mounts and ammunition.",
        ),
        ["armament.main.gun-tubes-breeches"],
        _bounded(gun_mass, 8.0, 0.0, 20.141, [600.0, 620.0], dx=35.0, dz=3.0),
    )
    main_mounts = _item(
        "main-mounts", mount_mass, 8.0, 0.0, 20.541,
        _source(
            "4 mounts * 600 long_ton/mount * 1.0160469088 t/long_ton",
            "NavWeaps Mark II value used as a Mark II* proxy (secondary compilation)",
            ["four mount count", "Mark II proxy", "assumed complete revolving-mount boundary", "manifest role centroid for position"],
            "Complete revolving mount including rotating gunhouse armour and hoists above fixed trunk; excludes guns, ammunition and fixed barbettes.",
        ),
        ["armament.main.revolving-mounts", "armour.main-turret.rotating", "armament.main.loading-hoists-above-fixed-trunk"],
        _bounded(mount_mass, 8.0, 0.0, 20.541, [2073.0, 2804.0], dx=35.0, dz=3.0),
    )
    secondary_guns = _item(
        "secondary-guns", secondary_mass, 33.0, 0.0, 16.15,
        _source(
            "16 guns * 42 cwt/gun * 112 lb/cwt * 0.45359237 kg/lb / 1000",
            "Admiralty Gunnery Branch G.8652/13, 4-inch Mark VII/VIII handbook",
            ["installed gun count", "handbook gun mass", "manifest role centroid for position"],
            "Gun tubes and breeches only.",
        ),
        ["armament.secondary.gun-tubes-breeches"],
        _bounded(secondary_mass, 33.0, 0.0, 16.15, [33.0, 35.0], dx=35.0, dz=3.0),
    )
    secondary_mounts = _item(
        "secondary-mounts", 16.0, 33.0, 0.0, 15.5,
        _source(
            "16 mounts * 1.0 t/mount engineering allowance",
            "Declared Task 3 engineering assumption; no mounting handbook located",
            ["installed gun count", "assumed pedestal and shield mass", "manifest role centroid for position"],
            "Pedestals and shields; excludes guns and ammunition.",
        ),
        ["armament.secondary.mounts-shields"],
        _bounded(16.0, 33.0, 0.0, 15.5, [8.0, 32.0], dx=35.0, dz=3.0),
    )
    torpedo_outfit = _item(
        "torpedo-launch-outfit", 50.0, -5.0, 0.0, 4.0,
        _source(
            "2 submerged tubes * 25 t/tube-system engineering allowance",
            "Declared Task 3 engineering assumption; tube count inherited from ship references",
            ["two-tube count", "assumed launch-system mass and centre"],
            "Fixed tubes, doors, handling and air gear; excludes torpedoes.",
        ),
        ["armament.torpedo.fixed-launch-gear"],
        _bounded(50.0, -5.0, 0.0, 4.0, [20.0, 100.0], dx=25.0, dy=3.0, dz=2.0),
    )
    boilers = _item(
        "boilers-uptakes", boiler_mass, -0.429, 0.0, 5.9,
        _source(
            "45% * (75000 shp / 15 shp/long_ton) * 1.0160469088",
            "C. S. McDowell, USNI Proceedings (1912), lines 193-236; 45/55 split is an assumption",
            ["design shaft power", "contemporary cross-navy screening rule", "45% allocation", "manifest boiler-room centroid"],
            "Installed dry boilers, uptakes and boiler auxiliaries; excludes fuel and working water.",
        ),
        ["machinery.boilers", "machinery.uptakes", "machinery.boiler-auxiliaries"],
        _bounded(boiler_mass, -0.429, 0.0, 5.9, [0.8 * boiler_mass, 1.2 * boiler_mass], dx=18.0, dy=2.0, dz=2.0),
    )
    engines = _item(
        "turbines-shafting", engine_mass, -53.75, 0.0, 5.9,
        _source(
            "55% * (75000 shp / 15 shp/long_ton) * 1.0160469088",
            "C. S. McDowell, USNI Proceedings (1912), lines 193-236; 45/55 split is an assumption",
            ["design shaft power", "contemporary cross-navy screening rule", "55% allocation", "manifest engine-room centroid"],
            "Installed dry turbines, shafting, propellers, condensers, pumps and auxiliaries; excludes fuel, water, lubricants and stores.",
        ),
        ["machinery.turbines", "machinery.shafting-propellers", "machinery.condensers-pumps", "machinery.engine-auxiliaries"],
        _bounded(engine_mass, -53.75, 0.0, 5.9, [0.8 * engine_mass, 1.2 * engine_mass], dx=18.0, dy=2.0, dz=2.0),
    )
    outfit = _item(
        "fixed-outfit", outfit_mass, 2.0, 0.0, 12.0,
        _source(
            "0.03 * 27000 long_ton * 1.0160469088",
            "Declared Task 3 engineering screening assumption",
            ["assumed-long-ton design displacement", "3% midpoint", "declared engineering centre"],
            "Anchors/chains, boats/davits, accommodation, electrical distribution, communications and non-propulsion auxiliaries.",
        ),
        ["outfit.anchors-chains", "outfit.boats-davits", "outfit.accommodation", "outfit.electrical", "outfit.communications"],
        _bounded(outfit_mass, 2.0, 0.0, 12.0, [411.0, 1372.0], dx=35.0, dy=2.0, dz=4.0),
    )
    main_ammunition = _item(
        "main-ammunition", main_ammo, 7.25, 0.0, 5.35,
        _source(
            "8 guns * 80 rounds/gun * (1400 + 297) lb/round * exact lb conversion",
            "NavWeaps WNBR_135-45_mk5 (secondary compilation)",
            ["installed guns, not broadside count", "80-round outfit", "projectile and charge masses", "manifest magazine centroid"],
            "Projectiles and service propellant; excludes magazine structure, packing and hoists.",
        ),
        ["consumable.ammo.main.projectiles", "consumable.ammo.main.propellant"],
        _bounded(main_ammo, 7.25, 0.0, 5.35, [480.0, 520.0], dx=40.0, dy=2.0, dz=2.0),
    )
    secondary_ammunition = _item(
        "secondary-ammunition", secondary_ammo, 25.0, 0.0, 7.0,
        _source(
            "16 guns * 150 rounds/gun * (31 lb projectile + 9 lb 5 15/16 oz charge) * exact lb conversion",
            "Admiralty G.8652/13 handbook for round masses; 150-round outfit is inherited secondary data",
            ["installed guns, not broadside count", "150-round outfit", "handbook projectile and charge masses", "declared magazine centre"],
            "Projectiles and charges; excludes structure, packing and hoists.",
        ),
        ["consumable.ammo.secondary.projectiles", "consumable.ammo.secondary.propellant"],
        _bounded(secondary_ammo, 25.0, 0.0, 7.0, [42.0, 46.0], dx=45.0, dy=3.0, dz=3.0),
    )
    torpedoes = _item(
        "torpedoes", 12.0, -5.0, 0.0, 4.5,
        _source(
            "8 complete rounds * 1.5 t/round placeholder",
            "Declared Task 3 engineering assumption; primary confirmation unresolved",
            ["assumed eight-round outfit", "assumed complete-round mass", "declared magazine centre"],
            "Complete torpedo rounds; excludes fixed launch gear.",
        ),
        ["consumable.ammo.torpedoes"],
        _bounded(12.0, -5.0, 0.0, 4.5, [6.0, 20.0], dx=25.0, dy=3.0, dz=2.0),
    )

    variable_specs = [
        ("coal", 900.0, -0.429, 0.0, 5.5, [450.0, 3600.0], "25% of inherited 3600 t maximum", "consumable.coal"),
        ("fuel-oil", 292.5, -22.0, 0.0, 4.5, [146.25, 1170.0], "25% of inherited 1170 t maximum", "consumable.oil"),
        ("reserve-feed-water", normal_feed_water, -22.0, 0.0, 4.5, [0.01 * 27_000 * LONG_TON_TO_T, deep_feed_water], "1.5% of assumed-long-ton design displacement", "consumable.feed-water"),
        ("potable-water", 70.0, 0.0, 0.0, 6.0, [35.0, 178.5], "1000 persons * 14 days * 5 kg/person/day", "consumable.potable-water"),
        ("provisions-stores", 56.0, 5.0, 0.0, 10.0, [28.0, 142.8], "1000 persons * 14 days * 4 kg/person/day", "consumable.provisions-spares"),
        ("crew-effects", 100.0, 5.0, 0.0, 12.0, [50.0, 127.5], "1000 persons * 0.10 t/person", "variable.crew-effects"),
    ]
    variable = {}
    for item_id, mass, x, y, kg, bounds, formula, token in variable_specs:
        variable[item_id] = _item(
            item_id, mass, x, y, kg,
            _source(
                formula,
                "Declared Task 3 normal engineering scenario",
                ["scenario parameters", "inherited maximum where named", "declared or manifest-derived centre"],
                "Scenario consumable/load only; no displacement-balancing margin.",
            ),
            [token],
            _bounded(mass, x, y, kg, bounds, dx=20.0, dy=3.0, dz=2.0),
        )

    project["weight_groups"] = _groups(
        {
            "hull": [hull],
            "armour": armour_items,
            "armament": [main_guns, main_mounts, secondary_guns, secondary_mounts, torpedo_outfit],
            "machinery": [boilers, engines],
            "outfit": [outfit],
            "ammunition": [main_ammunition, secondary_ammunition, torpedoes],
            "fuel": [variable["coal"], variable["fuel-oil"]],
            "water": [variable["reserve-feed-water"], variable["potable-water"]],
            "other_loads": [variable["provisions-stores"], variable["crew-effects"]],
        },
        set(GROUP_LABELS),
    )
    deep = {
        "coal": {"mass_t": 3600.0, "x_m": -0.429, "y_m": 0.0, "kg_m": 5.5},
        "fuel-oil": {"mass_t": 1170.0, "x_m": -22.0, "y_m": 0.0, "kg_m": 4.5},
        "reserve-feed-water": {"mass_t": deep_feed_water, "x_m": -22.0, "y_m": 0.0, "kg_m": 4.5},
        "potable-water": {"mass_t": 178.5, "x_m": 0.0, "y_m": 0.0, "kg_m": 6.0},
        "provisions-stores": {"mass_t": 142.8, "x_m": 5.0, "y_m": 0.0, "kg_m": 10.0},
        "crew-effects": {"mass_t": 127.5, "x_m": 5.0, "y_m": 0.0, "kg_m": 12.0},
    }
    project["loading_conditions"] = [
        {
            "id": "normal-engineering",
            "label": "Normal engineering scenario",
            "reference_displacement_t": None,
            "overrides": {},
            "scenario_provenance": {
                "status": "engineering scenario, not a historical loading condition",
                "parameters": "1000 persons, 14 days; 25% maximum coal and oil; 1.5% design displacement feed water",
            },
        },
        {
            "id": "deep-engineering",
            "label": "Deep engineering scenario",
            "reference_displacement_t": None,
            "overrides": deep,
            "scenario_provenance": {
                "status": "engineering scenario, not a historical loading condition",
                "parameters": "1275 persons, 28 days; maximum inherited coal and oil; 2.5% design displacement feed water",
                "uncertainty": "Overrides intentionally clear base bounds; scenario-specific interval support remains incomplete.",
            },
        },
    ]
    project["systems"] = {
        "armour": {
            "fixed": {
                "weight_item_ids": [item["id"] for item in armour_items],
                "source": (
                    "tools/plimsoll/cases/queen_mary_1913_weights.json; rounded model "
                    "bounding-box areas and published nominal thicknesses"
                ),
                "estimate": True,
                "mass_models": armour_models,
            }
        },
        "weapons": {
            "main": {
                "weight_item_ids": ["main-guns", "main-mounts", "main-ammunition"],
                "installed_guns": 8,
                "broadside_guns": 8,
                "rounds_per_gun": 80,
                "mass_models": [
                    {
                        "id": "main-installed-guns-mass-check",
                        "method": "counted_unit_mass",
                        "linked_weight_item_id": "main-guns",
                        "inputs": {
                            "unit_mass_t": 167_776 * LB_TO_T,
                            "count_field": "installed_guns",
                        },
                        "comparison_tolerance": dict(ALGEBRAIC_TOLERANCE),
                        "source": "NavWeaps WNBR_135-45_mk5 (secondary compilation)",
                        "boundary": "Eight installed gun tubes; published nominal excludes breech mass; excludes mounts and ammunition.",
                        "estimate": True,
                    },
                    {
                        "id": "main-installed-mounts-mass-check",
                        "method": "counted_unit_mass",
                        "linked_weight_item_id": "main-mounts",
                        "inputs": {
                            "unit_mass_t": 600 * LONG_TON_TO_T,
                            "count_value": 4,
                            "count_basis": "installed_twin_mounts",
                        },
                        "comparison_tolerance": dict(ALGEBRAIC_TOLERANCE),
                        "source": "NavWeaps Mark II value used as a Mark II* proxy (secondary compilation)",
                        "boundary": "Four complete revolving mounts including rotating gunhouse armour and hoists above fixed trunk; excludes guns, ammunition, and fixed barbettes.",
                        "estimate": True,
                    },
                    {
                        "id": "main-ammunition-outfit-mass-check",
                        "method": "counted_ammunition_mass",
                        "linked_weight_item_id": "main-ammunition",
                        "inputs": {
                            "count_field": "installed_guns",
                            "rounds_field": "rounds_per_gun",
                            "projectile_mass_kg": 1400 * 0.45359237,
                            "charge_mass_kg": 297 * 0.45359237,
                        },
                        "comparison_tolerance": dict(ALGEBRAIC_TOLERANCE),
                        "source": "NavWeaps ammunition outfit and projectile/charge values (secondary compilation)",
                        "boundary": "Eighty complete projectile-plus-charge rounds for each of eight installed guns.",
                        "estimate": True,
                    },
                ],
            },
            "secondary": {
                "weight_item_ids": ["secondary-guns", "secondary-mounts", "secondary-ammunition"],
                "installed_guns": 16,
                "broadside_guns": 8,
                "rounds_per_gun": 150,
                "mass_models": [
                    {
                        "id": "secondary-installed-guns-mass-check",
                        "method": "counted_unit_mass",
                        "linked_weight_item_id": "secondary-guns",
                        "inputs": {
                            "unit_mass_t": 42 * 112 * LB_TO_T,
                            "count_field": "installed_guns",
                        },
                        "comparison_tolerance": dict(ALGEBRAIC_TOLERANCE),
                        "source": "Admiralty Gunnery Branch G.8652/13, 4-inch Mark VII/VIII handbook",
                        "boundary": "Sixteen installed gun tubes and breeches; excludes mounts and ammunition.",
                        "estimate": True,
                    },
                    {
                        "id": "secondary-installed-mounts-mass-check",
                        "method": "counted_unit_mass",
                        "linked_weight_item_id": "secondary-mounts",
                        "inputs": {
                            "unit_mass_t": 1.0,
                            "count_field": "installed_guns",
                        },
                        "comparison_tolerance": dict(ALGEBRAIC_TOLERANCE),
                        "source": "Declared Task 3 engineering assumption; no mounting handbook located",
                        "boundary": "One pedestal-and-shield allowance per installed gun; excludes gun and ammunition.",
                        "estimate": True,
                    },
                    {
                        "id": "secondary-ammunition-outfit-mass-check",
                        "method": "counted_ammunition_mass",
                        "linked_weight_item_id": "secondary-ammunition",
                        "inputs": {
                            "count_field": "installed_guns",
                            "rounds_field": "rounds_per_gun",
                            "projectile_mass_kg": 31 * 0.45359237,
                            "charge_mass_kg": (9 + (5 + 15 / 16) / 16) * 0.45359237,
                        },
                        "comparison_tolerance": dict(ALGEBRAIC_TOLERANCE),
                        "source": "Task 3 exact projectile and charge formula from cited ammunition references",
                        "boundary": "One hundred fifty complete projectile-plus-charge rounds for each of sixteen installed guns.",
                        "estimate": True,
                    },
                ],
            },
            "torpedo": {"weight_item_ids": ["torpedo-launch-outfit", "torpedoes"], "installed_tubes": 2},
        },
        "propulsion": {
            "weight_item_ids": ["boilers-uptakes", "turbines-shafting"],
            "raw_design_power": {"value": 75000, "unit": "shp", "source": "Navypedia and inherited engines case"},
            "boilers": 42,
        },
    }
    project["compartments"] = [
        {"id": "boiler-room-fixture", "label": "Boiler-room proxy", "length_m": 55.0, "beam_m": 18.0, "height_m": 7.0, "x_m": -0.429, "y_m": 0.0, "keel_to_bottom_m": 2.0, "permeability": 0.85, "free_surface": False, "source": "Task 3 engineering fixture from model role extents; not surveyed subdivision", "estimate": True},
        {"id": "engine-room-fixture", "label": "Engine-room proxy", "length_m": 30.0, "beam_m": 17.0, "height_m": 7.0, "x_m": -53.75, "y_m": 0.0, "keel_to_bottom_m": 2.0, "permeability": 0.85, "free_surface": False, "source": "Task 3 engineering fixture from model role extents; not surveyed subdivision", "estimate": True},
        {"id": "forward-magazine-fixture", "label": "Forward magazine proxy", "length_m": 20.0, "beam_m": 9.0, "height_m": 6.0, "x_m": 53.0, "y_m": 0.0, "keel_to_bottom_m": 2.3, "permeability": 0.70, "free_surface": False, "source": "Task 3 engineering fixture from model role extents; not surveyed subdivision", "estimate": True},
    ]
    project["openings"] = [
        {"id": "boiler-sea-hole-fixture", "label": "Boiler-room damage aperture proxy", "kind": "connection", "x_m": -0.429, "y_m": -9.0, "z_m": 4.0, "open": False, "from": "sea", "to": "boiler-room-fixture", "area_m2": 1.0, "discharge_coefficient": 0.62, "aperture_height_m": 1.0, "source": "Task 3 engineering fixture; not a surveyed Queen Mary opening", "estimate": True},
        {"id": "weather-deck-downflooding-fixture", "label": "Weather-deck downflooding proxy", "kind": "downflooding", "x_m": 20.0, "y_m": 0.0, "z_m": 14.5, "open": True, "source": "Task 3 engineering fixture; not a surveyed Queen Mary opening", "estimate": True},
    ]
    _add_intact_damage_preset(project)
    project["sources"] = {
        "historical_validation": {"validated": False, "reason": "No builder weight return, Ship's Book, inclining report, or Queen Mary-specific machinery schedule was located in the bounded audit."},
        "comparisons": [
            {"label": "published normal displacement lead", "raw_value": 26770, "raw_unit": "tons (unresolved)", "additive": False, "source": "Navypedia / Tyne Built Ships inherited lead"},
            {"label": "published deep displacement lead", "raw_value": 31650, "raw_unit": "tons (unresolved)", "additive": False, "source": "Navypedia / Tyne Built Ships inherited lead"},
            {"label": "Jellicoe Queen Mary comparison", "raw_value": 27000, "raw_unit": "tons (assumed long ton only for displayed comparison)", "assumed_metric_t": 27000 * LONG_TON_TO_T, "additive": False, "source": "Jellicoe, The Grand Fleet 1914-1916, Table V"},
        ],
        "limitations": ["Fixture estimates are proposals, not historical certification.", "No residual mass or displacement-balancing item is present.", "Model geometry supports estimated positions only, never masses."],
    }
    return project


def _explicit_item(item_id, mass, x, y, kg, source, token):
    return {"id": item_id, "mass_t": mass, "x_m": x, "y_m": y, "kg_m": kg, "source": source, "estimate": False, "includes": [token]}


def _fixture_compartment(item_id, label, length, beam, height, x, bottom, permeability=0.85):
    return {"id": item_id, "label": label, "length_m": length, "beam_m": beam, "height_m": height, "x_m": x, "y_m": 0.0, "keel_to_bottom_m": bottom, "permeability": permeability, "free_surface": False, "source": "Analytic engineering fixture geometry; not surveyed ship data", "estimate": True}


def generic_steamer_project() -> dict:
    stationed = geometry.make_reference_hull(90.0, 13.0, 5.5, 0.72, 0.82, depth=8.0, n_stations=81, n_section=32)
    project = _project(
        "generic-steamer-reference",
        "Generic 1910 coastal steamer reference",
        {"lwl_m": 90.0, "loa_m": 92.0, "beam_m": 13.0, "draught_normal_m": 5.5, "block_coeff": 0.72, "waterplane_coeff": 0.82},
        {"kind": "offsets", "source": {"method": "parameter-derived reference geometry", "parameters": {"L_m": 90.0, "B_m": 13.0, "T_m": 5.5, "Cb": 0.72, "Cwp": 0.82}, "citation": "geometry.make_reference_hull"}, "estimate": True, "keel_offset_m": 0.0, "offsets": _serialize_hull(stationed)},
    )
    items = {
        "hull": [_explicit_item("steamer-structure", 2800.0, 0.0, 0.0, 5.0, "Analytic fixture allocation", "hull.structure")],
        "machinery": [_explicit_item("steamer-machinery", 800.0, -18.0, 0.0, 4.0, "Analytic fixture allocation", "machinery.plant")],
        "outfit": [_explicit_item("steamer-outfit", 300.0, 2.0, 0.0, 6.5, "Analytic fixture allocation", "outfit.fixed")],
        "fuel": [_explicit_item("steamer-fuel", 200.0, -12.0, 0.0, 3.0, "Analytic normal fixture load", "consumable.fuel")],
        "water": [_explicit_item("steamer-water", 100.0, -5.0, 0.0, 2.5, "Analytic normal fixture load", "consumable.water")],
        "other_loads": [_explicit_item("steamer-cargo", 500.0, 8.0, 0.0, 4.2, "Analytic normal fixture load", "variable.cargo")],
    }
    absent = {key: "Explicitly absent in this unarmed analytic cargo-steamer fixture." for key in ("armour", "armament", "ammunition")}
    project["weight_groups"] = _groups(items, {"hull", "machinery", "outfit", "fuel", "water", "other_loads"}, absent)
    project["loading_conditions"] = [
        {"id": "coastal", "label": "Coastal analytic load", "reference_displacement_t": 4749.03, "overrides": {}},
        {"id": "loaded", "label": "Loaded analytic voyage", "reference_displacement_t": None, "overrides": {"steamer-fuel": {"mass_t": 400.0}, "steamer-water": {"mass_t": 150.0}, "steamer-cargo": {"mass_t": 800.0}}, "scenario_provenance": "Analytic mutation for loading-resolution tests; not historical."},
    ]
    project["systems"] = {"propulsion": {"weight_item_ids": ["steamer-machinery"]}, "cargo": {"weight_item_ids": ["steamer-cargo"]}}
    project["compartments"] = [
        _fixture_compartment("steamer-engine-room", "Engine-room fixture", 18.0, 9.0, 4.5, -20.0, 0.5),
        _fixture_compartment("steamer-cargo-hold", "Cargo-hold fixture", 36.0, 10.0, 5.0, 12.0, 0.5, 0.70),
    ]
    project["openings"] = [
        {"id": "steamer-hold-hole", "label": "Cargo-hold damage aperture", "kind": "connection", "x_m": 12.0, "y_m": 5.0, "z_m": 2.0, "open": False, "from": "sea", "to": "steamer-cargo-hold", "area_m2": 0.5, "discharge_coefficient": 0.62, "source": "Analytic engineering fixture; not surveyed ship data", "estimate": True},
        {"id": "steamer-hatch", "label": "Cargo hatch downflooding point", "kind": "downflooding", "x_m": 12.0, "y_m": 0.0, "z_m": 7.0, "open": True, "source": "Analytic engineering fixture; not surveyed ship data", "estimate": True},
    ]
    _add_intact_damage_preset(project)
    project["sources"] = {"historical_validation": {"validated": False, "reason": "Purpose-built analytic reference, not a historical vessel."}}
    return project


def analytic_box_project() -> dict:
    rectangle = [[-5.0, 0.0], [5.0, 0.0], [5.0, 8.0], [-5.0, 8.0]]
    stations = [[-10.0, rectangle], [0.0, rectangle], [10.0, rectangle]]
    project = _project(
        "analytic-box-reference",
        "Analytic rectangular box reference",
        {"lwl_m": 20.0, "loa_m": 20.0, "beam_m": 10.0, "draught_normal_m": 4.0, "block_coeff": 1.0, "waterplane_coeff": 1.0},
        {"kind": "offsets", "source": {"method": "explicit rectangular sections", "citation": "Task 3 analytic definition", "formula": "three identical 10 m by 8 m transverse rectangles over 20 m length"}, "estimate": False, "keel_offset_m": 0.0, "offsets": {"schema": "plimsoll-section-polygons-1", "stations": stations}},
    )
    items = {
        "hull": [_explicit_item("box-structure", 700.0, 0.0, 0.0, 3.0, "Analytic fixture definition", "hull.structure")],
        "water": [_explicit_item("box-ballast", 120.0, 0.0, 0.0, 2.0, "Analytic loaded-condition ballast", "consumable.ballast-water")],
    }
    absent = {key: "Explicitly absent in the unpropelled analytic-box fixture." for key in ("armour", "armament", "machinery", "outfit", "ammunition", "fuel", "other_loads")}
    project["weight_groups"] = _groups(items, {"hull", "water"}, absent)
    project["loading_conditions"] = [
        {"id": "loaded", "label": "Four-metre analytic draught", "reference_displacement_t": 820.0, "overrides": {}},
        {"id": "light", "label": "Ballast discharged", "reference_displacement_t": None, "overrides": {"box-ballast": {"mass_t": 0.0}}, "scenario_provenance": "Analytic zero-ballast mutation; zero is known, not missing."},
    ]
    project["systems"] = {"ballast": {"weight_item_ids": ["box-ballast"]}}
    project["compartments"] = [_fixture_compartment("box-tank", "Central tank fixture", 10.0, 8.0, 3.0, 0.0, 0.5, 1.0)]
    project["openings"] = [
        {"id": "box-tank-hole", "label": "Tank aperture", "kind": "connection", "x_m": 0.0, "y_m": 4.0, "z_m": 1.5, "open": False, "from": "sea", "to": "box-tank", "area_m2": 0.25, "discharge_coefficient": 0.62, "source": "Analytic engineering fixture; not surveyed ship data", "estimate": True},
        {"id": "box-rim", "label": "Box rim downflooding point", "kind": "downflooding", "x_m": 0.0, "y_m": 0.0, "z_m": 8.0, "open": True, "source": "Analytic engineering fixture; not surveyed ship data", "estimate": True},
    ]
    _add_intact_damage_preset(project)
    project["sources"] = {"historical_validation": {"validated": False, "reason": "Exact analytic fixture; no historical claim."}, "analytic_anchor": {"volume_at_draught_4_m_m3": 800.0, "mass_at_rho_1_025_t_m3_t": 820.0}}
    return project


def generate_projects(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    projects = {
        "queen_mary_1913.project.json": queen_mary_project(),
        "generic_steamer.project.json": generic_steamer_project(),
        "analytic_box.project.json": analytic_box_project(),
    }
    for filename, payload in projects.items():
        text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
        (output_dir / filename).write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=PKG / "cases" / "projects")
    args = parser.parse_args()
    generate_projects(args.output_dir)


if __name__ == "__main__":
    main()
