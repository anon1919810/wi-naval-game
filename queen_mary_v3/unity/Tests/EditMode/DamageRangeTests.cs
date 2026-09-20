using System;
using NUnit.Framework;
using Naval.DamageLab;
public sealed class DamageRangeTests
{
    [Test] public void SameSeedSameReport() {Assert.AreEqual(RangeSolver.Fire(new RangeConfig()).Signature(),RangeSolver.Fire(new RangeConfig()).Signature());}
    [Test] public void ThickPlateStopsDud() {var r=RangeSolver.Fire(new RangeConfig{outerMm=2000,fuseMode=2});Assert.IsTrue(r.stopped);Assert.IsFalse(r.exploded);Assert.AreEqual(0,r.fragments.Count);}
    [Test] public void ZeroResistancePreservesSpeed() {var r=RangeSolver.Fire(new RangeConfig{outerMm=0,innerMm=0,rearMm=0,fuseMode=2});Assert.AreEqual(600,r.finalSpeed,.001);}
    [Test] public void FuseDelayControlsDetonationPosition() {var contact=RangeSolver.Fire(new RangeConfig{fuseMode=0});var delayed=RangeSolver.Fire(new RangeConfig());Assert.AreEqual(0,contact.explosion.x,.001);Assert.Greater(delayed.explosion.x,contact.explosion.x);Assert.Greater(delayed.duration,contact.duration);}
    [Test] public void PlateShieldingReducesBlast() {var a=RangeSolver.Fire(new RangeConfig{fuseMode=0});var b=RangeSolver.Fire(new RangeConfig{fuseMode=0,outerMm=0,innerMm=0,rearMm=0});Assert.Greater(b.modules[0].blast,a.modules[0].blast);}
    [Test] public void FragmentsCarryUnitTotalWeight() {foreach(int n in new[]{16,192,1024}) {var r=RangeSolver.Fire(new RangeConfig{fragmentSamples=n});float sum=0;foreach(var f in r.fragments)sum+=f.weight;Assert.AreEqual(1,sum,.0001);}}
    [Test] public void InvalidConfigurationRejected() {Assert.Throws<ArgumentException>(()=>RangeSolver.Fire(new RangeConfig{speed=float.NaN}));Assert.Throws<ArgumentException>(()=>RangeSolver.Fire(new RangeConfig{fragmentSamples=0}));Assert.Throws<ArgumentException>(()=>RangeSolver.Fire(new RangeConfig{innerMm=-1}));}
    [Test] public void EventsMonotonicAndDamageBounded() {var r=RangeSolver.Fire(new RangeConfig());float t=-1;foreach(var e in r.events){Assert.GreaterOrEqual(e.time,t);t=e.time;}foreach(var m in r.modules)Assert.That(m.damage,Is.InRange(0f,1f));}
    [Test] public void BoxIntervalHandlesInsideOrigin() {float d;Assert.IsTrue(RangeSolver.Box(new DVec(0,0,0),new DVec(1,0,0),new DVec(0,0,0),new DVec(2,2,2),out d));Assert.AreEqual(0,d);}
    [Test] public void ConfigSnapshotDoesNotChangeAfterFire() {var c=new RangeConfig();var r=RangeSolver.Fire(c);c.outerMm=999;Assert.AreEqual(180,r.config.outerMm);}
}
