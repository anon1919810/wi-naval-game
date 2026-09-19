# Combat A-stage acceptance notes

Status after A01–A05 implementation on `feature/combat-a-stage`.

## What landed

| Area | Implementation |
|---|---|
| A01 | `Naval.Runtime` + Edit/Play test asmdefs; `verify_combat.ps1`; UTF-8 test XML gate |
| A02 | `ShipIdentity`, `ShipDamageApplication.Apply`; self-hit filter by instance id |
| A03 | `ShipPenetration.EffectiveArmourMm`; `ShipHitResolver` layered budget; surface hits no longer invent modules |
| A04 | `ShipSystemsState.ApplyModule` dedup; `ShipFloatPrototype.floatPose` child for flood pose |
| A05 | `ShipCombatAcceptance.BuildPlayerBatch`; `ShipCombatSmokeRunner`; lab ids `player_01`/`target_01` |

## Known limits (A-stage)

- Instant raycast mode remains; labelled as prototype (B03 later).
- Layered path resolver is unit-tested; live FireBarrel still uses single-zone Evaluate (not full multi-hit BVH).
- `historically_certified:false`.
- Test framework package `com.unity.test-framework@1.1.33` added to Unity manifest.

## Commands

```powershell
cd queen_mary_v3\unity
.\sync_to_unity.ps1 -ProjectPath D:/Unity/Projects/QueenMaryNaval/QueenMaryNaval
.\verify_combat.ps1 -ProjectPath D:/Unity/Projects/QueenMaryNaval/QueenMaryNaval
# optional player:
# Unity -executeMethod Naval.EditorTools.ShipCombatAcceptance.BuildPlayerBatch -shipReportDirectory <dir>
```
