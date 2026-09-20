# Damage Range Sweep Report

- runId: `20260920T064657Z`
- utc: 2026-09-20T06:46:57.2817697Z
- model: experimental-resistance-v1 · historically_certified: false
- totalCases: 282

## Campaigns

| Campaign | cases | stopped | detonated | exited |
|---|---:|---:|---:|---:|
| C1_armour_speed_angle | 96 | 40 | 96 | 0 |
| C2_multilayer | 27 | 0 | 27 | 0 |
| C3_fuse | 36 | 8 | 23 | 9 |
| C4_resistance_angle | 27 | 6 | 27 | 0 |
| C5_fragments | 72 | 0 | 72 | 0 |
| C6_seed_stability | 24 | 0 | 24 | 0 |

## Findings
- C1 speed600 angle0 outer0 penetrations=1 outer229=1 outer600=0 (monotone non-increasing expected)
- C3 detonations contact=12 delay=11 dud=0 (dud expected 0)
- C5 fragment_weight_violations=0
- C6 boiler damage across 24 seeds: min=1.000 median=1.000 max=1.000

## Notes
- Resistance model is an experimental v² surrogate, not WWI ballistic tables.
- Module ids in the range are experiment contracts (Feed_Pump not in main ship contract).
- Serial solver timing is not game FPS.
