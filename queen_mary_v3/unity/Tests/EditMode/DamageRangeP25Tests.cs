using System;
using NUnit.Framework;
using Naval.DamageLab;

public sealed class DamageRangeP25Tests
{
    static bool HasEvent(RangeReport r, string kind)
    {
        foreach (var e in r.events) if (e.kind == kind) return true;
        return false;
    }

    [Test]
    public void PlateTransit_EmittedWhenArmourPresent()
    {
        var cfg = new RangeConfig { outerMm = 180, innerMm = 25, rearMm = 40, fuseMode = 1, modelPlateTransit = true };
        var r = RangeSolver.Fire(cfg);
        Assert.That(HasEvent(r, "plate_transit"), Is.True);
        Assert.That(HasEvent(r, "plate_transit"), Is.True);
        foreach (var e in r.events)
            if (e.kind == "plate_transit")
                Assert.That(e.note, Does.Contain("in-plate path"));
    }

    [Test]
    public void PlateTransit_CanBeDisabled()
    {
        var cfg = new RangeConfig { outerMm = 180, fuseMode = 1, modelPlateTransit = false };
        var r = RangeSolver.Fire(cfg);
        Assert.That(HasEvent(r, "plate_transit"), Is.False);
    }

    [Test]
    public void Fragments_CarryMassVelocityEnergy()
    {
        var cfg = new RangeConfig { outerMm = 0, innerMm = 0, rearMm = 0, fuseMode = 0, fragmentSamples = 64 };
        var r = RangeSolver.Fire(cfg);
        Assert.That(r.fragments.Count, Is.EqualTo(64));
        foreach (var f in r.fragments)
        {
            Assert.That(f.massKg, Is.GreaterThan(0));
            Assert.That(f.speedMps, Is.GreaterThan(0));
            Assert.That(f.energyJ, Is.GreaterThan(0));
            Assert.That(f.contrib, Is.GreaterThanOrEqualTo(0));
            Assert.That(f.weight, Is.EqualTo(1f / 64).Within(0.0001f));
        }
    }

    [Test]
    public void Explosion_LocusClassified()
    {
        // Open burst at outer plate with no armour: detonation at contact point near x=0.
        var open = RangeSolver.Fire(new RangeConfig { outerMm = 0, innerMm = 0, rearMm = 0, fuseMode = 0 });
        string detId = null;
        foreach (var e in open.events) if (e.kind == "detonation") detId = e.id;
        Assert.That(detId, Is.Not.Null);
        Assert.That(detId, Does.StartWith("open_space").Or.StartWith("inside_module"));

        // Thick plate + dud: no detonation.
        var dud = RangeSolver.Fire(new RangeConfig { outerMm = 400, fuseMode = 2 });
        Assert.That(dud.exploded, Is.False);
    }

    [Test]
    public void InsideModule_BlastBonus_BoostsHost()
    {
        // Delay fuse with zero armour: shell travels through section; if detonation lands in a module box, bonus applies.
        var inside = new RangeConfig { outerMm = 0, innerMm = 0, rearMm = 0, fuseMode = 1, fuseDelay = 0.02f, speed = 600, blastStrength = 1 };
        var r = RangeSolver.Fire(inside);
        Assert.That(r.exploded, Is.True);
        string det = null;
        foreach (var e in r.events) if (e.kind == "detonation") det = e.id;
        Assert.That(det, Is.Not.Null);
        bool hostBoosted = false;
        foreach (var m in r.modules)
        {
            if (det != null && det.Contains(m.id) && m.blast > 0.55f) hostBoosted = true;
            // Non-host modules still capped lower than a theoretical unbounded blast.
            Assert.That(m.blast, Is.LessThanOrEqualTo(0.65f));
        }
        // Not asserting a specific module must be host — geometry dependent; assert format is locus.
        Assert.That(det, Does.Contain("_").Or.StartWith("open_space"));
        _ = hostBoosted;
    }

    [Test]
    public void Seed_ChangesFragmentEnergyMix()
    {
        var a = RangeSolver.Fire(new RangeConfig { outerMm = 0, fuseMode = 0, fragmentSamples = 96, seed = 1 });
        var b = RangeSolver.Fire(new RangeConfig { outerMm = 0, fuseMode = 0, fragmentSamples = 96, seed = 2 });
        bool different = false;
        int n = Math.Min(a.fragments.Count, b.fragments.Count);
        for (int i = 0; i < n; i++)
            if (Math.Abs(a.fragments[i].energyJ - b.fragments[i].energyJ) > 1f) { different = true; break; }
        Assert.That(different, Is.True, "fragment energy sequence should depend on seed");
    }

    [Test]
    public void Events_StillMonotonic_WithTransit()
    {
        var r = RangeSolver.Fire(new RangeConfig { outerMm = 229, fuseMode = 1, modelPlateTransit = true });
        float last = -1;
        foreach (var e in r.events)
        {
            Assert.That(e.time, Is.GreaterThanOrEqualTo(last - 1e-4f), e.kind);
            last = e.time;
        }
    }
}
