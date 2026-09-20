using NUnit.Framework;
using Naval.DamageLab;
using UnityEngine;

public sealed class RangeLayoutTests
{
    [Test]
    public void Layout_Json_ParsesPresetsAndModules()
    {
        var ta = Resources.Load<TextAsset>("DamageRange/range_layout");
        Assert.That(ta, Is.Not.Null, "range_layout.json must be under Assets/Resources/DamageRange/");
        var layout = JsonUtility.FromJson<RangeLayout>(ta.text);
        Assert.That(layout, Is.Not.Null);
        Assert.That(layout.historically_certified, Is.False);
        Assert.That(layout.plates, Is.Not.Null);
        Assert.That(layout.plates.Length, Is.GreaterThanOrEqualTo(3));
        Assert.That(layout.modules, Is.Not.Null);
        Assert.That(layout.modules.Length, Is.EqualTo(3));
        Assert.That(layout.codex_presets, Is.Not.Null);
        Assert.That(layout.codex_presets.Length, Is.GreaterThanOrEqualTo(6));
        var mods = layout.BuildModules();
        Assert.That(mods.Count, Is.EqualTo(3));
        Assert.That(mods[0].id, Is.EqualTo("Boiler_Room_1"));
        var preset = layout.FindPreset("thick_plate");
        Assert.That(preset, Is.Not.Null);
        Assert.That(preset.config.outerMm, Is.EqualTo(600f).Within(0.01f));
    }

    [Test]
    public void Solver_UsesLayoutModules()
    {
        var mods = RangeSolver.Modules();
        Assert.That(mods.Count, Is.EqualTo(3));
        Assert.That(mods[2].id, Is.EqualTo("Feed_Pump"));
        var plates = RangeSolver.Plates(new RangeConfig());
        Assert.That(plates.Count, Is.EqualTo(3));
        Assert.That(plates[0].id, Is.EqualTo("Outer_Belt"));
    }

    [Test]
    public void CodexPreset_ContactVsDelay_HasTwoConfigs()
    {
        var ta = Resources.Load<TextAsset>("DamageRange/range_layout");
        Assert.That(ta, Is.Not.Null);
        var layout = JsonUtility.FromJson<RangeLayout>(ta.text);
        var p = layout.FindPreset("contact_vs_delay");
        Assert.That(p, Is.Not.Null);
        Assert.That(p.compare_config, Is.Not.Null);
        Assert.That(p.compare_config.fuseMode, Is.EqualTo(0));
        Assert.That(p.config.fuseMode, Is.EqualTo(1));
        var a = RangeSolver.Fire(p.config.Copy());
        var b = RangeSolver.Fire(p.compare_config.Copy());
        Assert.That(a.exploded, Is.True);
        Assert.That(b.exploded, Is.True);
        // Delayed shot should generally travel deeper before detonation than contact at outer plate.
        Assert.That(a.duration, Is.GreaterThan(b.duration));
    }
}
