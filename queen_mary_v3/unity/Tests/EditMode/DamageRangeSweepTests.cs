using System.Collections.Generic;
using NUnit.Framework;
using Naval.DamageLab;

public sealed class DamageRangeSweepTests
{
    [Test]
    public void Sweep_ProducesAllCampaignsWithCases()
    {
        var report = DamageRangeSweep.RunAll();
        Assert.That(report.campaigns, Is.Not.Empty);
        int total = 0;
        foreach (var c in report.campaigns)
        {
            Assert.That(c.rows, Is.Not.Empty, c.name);
            total += c.rows.Count;
        }
        Assert.That(report.totalCases, Is.EqualTo(total));
        // C1 alone is 6*4*4 = 96
        Assert.That(report.campaigns[0].cases, Is.EqualTo(96));
        Assert.That(report.campaigns.Find(c => c.name == "C2_multilayer").cases, Is.EqualTo(27));
        Assert.That(report.campaigns.Find(c => c.name == "C3_fuse").cases, Is.EqualTo(36));
        Assert.That(report.campaigns.Find(c => c.name == "C4_resistance_angle").cases, Is.EqualTo(27));
        Assert.That(report.campaigns.Find(c => c.name == "C5_fragments").cases, Is.EqualTo(72));
        Assert.That(report.campaigns.Find(c => c.name == "C6_seed_stability").cases, Is.EqualTo(24));
    }

    [Test]
    public void Sweep_AllFiresAreDeterministic()
    {
        var report = DamageRangeSweep.RunAll();
        foreach (var camp in report.campaigns)
        foreach (var row in camp.rows)
            Assert.That(row.deterministicOk, Is.True, camp.name + "/" + row.caseId);
    }

    [Test]
    public void Sweep_ThickerArmour_DoesNotIncreasePenetrations()
    {
        var report = DamageRangeSweep.RunAll();
        var c1 = report.campaigns.Find(c => c.name == "C1_armour_speed_angle");
        Assert.That(c1, Is.Not.Null);
        int Pen(float outer)
        {
            int n = 0;
            foreach (var r in c1.rows)
            {
                if (r.config.speed != 600f) continue;
                if (System.Math.Abs(r.config.angleDeg) > 0.01f) continue;
                if (System.Math.Abs(r.config.outerMm - outer) > 0.01f) continue;
                foreach (var e in r.report.events)
                    if (e.kind == "penetrated") { n++; break; }
            }
            return n;
        }
        Assert.That(Pen(229f), Is.LessThanOrEqualTo(Pen(0f)));
        Assert.That(Pen(600f), Is.LessThanOrEqualTo(Pen(229f)));
    }

    [Test]
    public void Sweep_DudFuse_NeverDetonates()
    {
        var report = DamageRangeSweep.RunAll();
        var c3 = report.campaigns.Find(c => c.name == "C3_fuse");
        foreach (var r in c3.rows)
            if (r.config.fuseMode == 2)
                Assert.That(r.report.exploded, Is.False, r.caseId);
    }

    [Test]
    public void Sweep_FragmentWeightsStayNearUnity()
    {
        var report = DamageRangeSweep.RunAll();
        var c5 = report.campaigns.Find(c => c.name == "C5_fragments");
        foreach (var r in c5.rows)
        {
            if (r.report.fragments.Count == 0) continue;
            float w = 0;
            foreach (var f in r.report.fragments) w += f.weight;
            Assert.That(w, Is.EqualTo(1f).Within(0.001f), r.caseId);
        }
    }
}
