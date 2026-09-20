using System;
using Naval.DamageLab;
public static class RangeChecks
{
    static int count;
    static void Check(bool ok, string name) { if(!ok) throw new Exception(name); count++; Console.WriteLine("PASS " + name); }
    public static int Main() {
        try {
            var c = new RangeConfig();
            var a = RangeSolver.Fire(c);
            Check(a.events.Count > 2, "ordered events exist");
            Check(a.exploded, "default delayed detonation");
            Check(a.fragments.Count == c.fragmentSamples, "sample count");
            var b = RangeSolver.Fire(c);
            Check(a.Signature() == b.Signature(), "deterministic report");
            c.outerMm = 2000;
            c.fuseMode = 2;
            var blocked = RangeSolver.Fire(c);
            Check(blocked.stopped && !blocked.exploded, "thick plate stops dud");
            Check(blocked.fragments.Count == 0, "dud produces no fragments");
            c = new RangeConfig(); c.fuseMode = 0;
            var instant = RangeSolver.Fire(c);
            Check(instant.exploded && Math.Abs(instant.explosion.x) < .001, "contact detonation at outer plate");
            c = new RangeConfig(); c.innerMm = 0; c.outerMm = 0; c.rearMm = 0; c.fuseMode = 2;
            var clear = RangeSolver.Fire(c);
            Check(Math.Abs(clear.finalSpeed-c.speed) < .01, "zero resistance preserves speed");
            c = new RangeConfig(); c.speed = float.NaN;
            bool rejected=false; try { RangeSolver.Fire(c); } catch(ArgumentException) { rejected=true; }
            Check(rejected, "reject nonfinite input");
            c = new RangeConfig(); c.fuseMode=0;
            var shield=RangeSolver.Fire(c); c.outerMm=0; c.innerMm=0;
            var open=RangeSolver.Fire(c);
            Check(open.modules[0].blast >= shield.modules[0].blast, "plates attenuate blast");
            c = new RangeConfig(); var r=RangeSolver.Fire(c);
            double weight=0; foreach(var f in r.fragments) weight+=f.weight;
            Check(Math.Abs(weight-1)<.00001,"fragment weights conserve total");
            double last=-1; foreach(var e in r.events) { Check(e.time>=last,"event time monotonic"); last=e.time; }
            foreach(var m in r.modules) Check(m.damage>=0 && m.damage<=1,"bounded module damage");
            Console.WriteLine("RESULT " + count + " passed"); return 0;
        } catch(Exception e) { Console.Error.WriteLine(e); return 1; }
    }
}
