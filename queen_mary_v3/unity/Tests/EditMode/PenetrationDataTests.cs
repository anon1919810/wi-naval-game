using NUnit.Framework;
using Naval;
using UnityEngine;

public sealed class PenetrationDataTests
{
    [Test]
    public void Parse_MainGunTable_InterpolatesMonotonic()
    {
        const string json = @"{
          ""gins"": null
        }";
        // Use assembly resource path style parse on inline valid schema:
        string valid = @"{
  ""asset"": ""test"",
  ""historically_certified"": false,
  ""gins_placeholder"": null,
  ""guns"": [
    { ""id"": ""main_343mm"", ""calibre_mm"": 343,
      ""samples_m"": [0, 2000, 8000],
      ""penetration_mm"": [500, 400, 200] }
  ],
  ""thresholds"": { ""penetrate_ratio"": 1.0, ""partial_ratio"": 0.5 },
  ""flood_m3"": { ""magazine"": 400, ""boiler_room"": 200, ""engine_room"": 250, ""steering_gear"": 120, ""hull_generic"": 150, ""partial"": 40, ""no_penetration"": 0 }
}";
        var data = ShipPenetrationFile.Parse(valid);
        Assert.That(data, Is.Not.Null);
        var gun = data.Gun("main_343mm");
        Assert.That(gun, Is.Not.Null);
        Assert.That(ShipPenetrationFile.PenetrationMm(gun, 0f), Is.EqualTo(500f).Within(0.01f));
        Assert.That(ShipPenetrationFile.PenetrationMm(gun, 2000f), Is.EqualTo(400f).Within(0.01f));
        float mid = ShipPenetrationFile.PenetrationMm(gun, 1000f);
        Assert.That(mid, Is.EqualTo(450f).Within(0.01f));
        Assert.That(ShipPenetrationFile.PenetrationMm(gun, 99999f), Is.EqualTo(200f).Within(0.01f));
        _ = json;
    }

    [Test]
    public void EffectiveArmour_Grazing_DoesNotLoseResistance()
    {
        Assert.That(ShipPenetration.EffectiveArmourMm(229f, 1f), Is.EqualTo(229f).Within(0.001f));
        Assert.That(ShipPenetration.EffectiveArmourMm(229f, 0.5f), Is.EqualTo(458f).Within(0.001f));
        Assert.That(ShipPenetration.EffectiveArmourMm(229f, 0.051f), Is.EqualTo(916f).Within(0.001f));
        Assert.That(ShipPenetration.EffectiveArmourMm(229f, 0.05f), Is.EqualTo(916f).Within(0.001f));
        Assert.That(ShipPenetration.EffectiveArmourMm(229f, 0f), Is.EqualTo(916f).Within(0.001f));
    }

    [Test]
    public void HitPath_LayerBudget()
    {
        var layers = new System.Collections.Generic.List<ShipHitResolver.LayerHit>();
        var go = new GameObject("mod");
        try
        {
            var c = go.AddComponent<ShipCompartment>();
            c.compartmentId = "Magazine_B";
            c.role = "magazine";
            layers.Add(new ShipHitResolver.LayerHit { layerId = "deck", armourMm = 40f });
            layers.Add(new ShipHitResolver.LayerHit { layerId = "inner", armourMm = 30f });
            layers.Add(new ShipHitResolver.LayerHit { layerId = "mag", armourMm = 0f, compartment = c });
            var ok = ShipHitResolver.ResolveBudget(layers, 100f, 1f);
            Assert.That(ok.damagedModule, Is.SameAs(c));
            layers.Clear();
            layers.Add(new ShipHitResolver.LayerHit { layerId = "deck", armourMm = 40f });
            layers.Add(new ShipHitResolver.LayerHit { layerId = "inner", armourMm = 30f });
            layers.Add(new ShipHitResolver.LayerHit { layerId = "mag", armourMm = 0f, compartment = c });
            var stop = ShipHitResolver.ResolveBudget(layers, 60f, 1f);
            Assert.That(stop.damagedModule, Is.Null);
            // duplicate layer id costs once
            layers.Clear();
            layers.Add(new ShipHitResolver.LayerHit { layerId = "belt", armourMm = 50f });
            layers.Add(new ShipHitResolver.LayerHit { layerId = "belt", armourMm = 50f });
            layers.Add(new ShipHitResolver.LayerHit { layerId = "mag", armourMm = 0f, compartment = c });
            var once = ShipHitResolver.ResolveBudget(layers, 60f, 1f);
            Assert.That(once.damagedModule, Is.SameAs(c));
        }
        finally { UnityEngine.Object.DestroyImmediate(go); }
    }
}
