using System;
using System.IO;
using System.Reflection;
using System.Diagnostics;
using System.Globalization;
using Naval.DamageLab;
public static class RunNunit
{
    public static int Main(string[] args)
    {
        int passed=0,failed=0;var details=new System.Collections.Generic.List<string>();
        foreach(var m in typeof(DamageRangeTests).GetMethods())
        {
            if(m.GetCustomAttributes(typeof(NUnit.Framework.TestAttribute),false).Length==0)continue;
            try {m.Invoke(new DamageRangeTests(),null);passed++;Console.WriteLine("PASS "+m.Name);details.Add("{\"test\":\""+m.Name+"\",\"passed\":true}");}
            catch(Exception e) {failed++;Console.WriteLine("FAIL "+m.Name+" "+e);details.Add("{\"test\":\""+m.Name+"\",\"passed\":false}");}
        }
        for(int i=0;i<10;i++)RangeSolver.Fire(new RangeConfig());
        var times=new double[200];for(int i=0;i<times.Length;i++){var s=Stopwatch.StartNew();RangeSolver.Fire(new RangeConfig{seed=i});s.Stop();times[i]=s.Elapsed.TotalMilliseconds;}Array.Sort(times);
        string json="{\"utc\":\""+DateTime.UtcNow.ToString("o")+"\",\"method\":\"NUnit assertions invoked through reflection under Unity bundled Mono; not Unity Test Runner\",\"passed\":"+passed+",\"failed\":"+failed+",\"tests\":["+string.Join(",",details)+"],\"solverSamples\":200,\"medianMs\":"+times[100].ToString("R",CultureInfo.InvariantCulture)+",\"p95Ms\":"+times[189].ToString("R",CultureInfo.InvariantCulture)+",\"scope\":\"Serial solver only, full diagnostic allocations, 192 fragments each; not rendering or fleet FPS\",\"unityRuntimeVerified\":false}";
        if(args.Length>0)File.WriteAllText(args[0],json);Console.WriteLine(json);return failed==0?0:1;
    }
}
