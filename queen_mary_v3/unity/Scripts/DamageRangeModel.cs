using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace Naval.DamageLab
{
    [Serializable] public struct DVec
    {
        public float x,y,z;
        public DVec(float x,float y,float z) { this.x=x;this.y=y;this.z=z; }
        public static DVec operator +(DVec a,DVec b) { return new DVec(a.x+b.x,a.y+b.y,a.z+b.z); }
        public static DVec operator -(DVec a,DVec b) { return new DVec(a.x-b.x,a.y-b.y,a.z-b.z); }
        public static DVec operator *(DVec a,float b) { return new DVec(a.x*b,a.y*b,a.z*b); }
        public float Length { get { return (float)Math.Sqrt(x*x+y*y+z*z); } }
        public DVec Normal { get { return this*(1/Math.Max(Length,.000001f)); } }
    }
    [Serializable] public sealed class RangeConfig
    {
        public float outerMm=180, innerMm=25, rearMm=40;
        public float resistance=1, speed=600, referencePenMm=400;
        public float angleDeg=0, fuseDelay=.012f;
        public int fuseMode=1, fragmentSamples=192, seed=1913;
        public float blastStrength=1, fragmentPenMm=30;
        public RangeConfig Copy() { return (RangeConfig)MemberwiseClone(); }
        public void Validate()
        {
            float[] vals={outerMm,innerMm,rearMm,resistance,speed,referencePenMm,angleDeg,fuseDelay,blastStrength,fragmentPenMm};
            foreach(float v in vals) if(float.IsNaN(v)||float.IsInfinity(v)) throw new ArgumentException("Non-finite configuration");
            if(outerMm<0||outerMm>2000||innerMm<0||innerMm>2000||rearMm<0||rearMm>2000||resistance<.1||resistance>4||speed<10||speed>1500||referencePenMm<=0||referencePenMm>3000||Math.Abs(angleDeg)>35||fuseDelay<0||fuseDelay>.2||fuseMode<0||fuseMode>2||fragmentSamples<16||fragmentSamples>2048||blastStrength<0||blastStrength>5||fragmentPenMm<0||fragmentPenMm>300) throw new ArgumentException("Configuration outside experiment bounds");
        }
    }
    [Serializable] public sealed class RangePlate
    {
        public string id; public float x, mm;
        public RangePlate(string id,float x,float mm) { this.id=id;this.x=x;this.mm=mm; }
    }
    [Serializable] public sealed class RangeEvent
    {
        public string kind,id,note; public float time, beforeMm,afterMm,speed; public DVec point;
    }
    [Serializable] public sealed class RangeFragment
    {
        public DVec start,end; public float weight; public string hit;
    }
    [Serializable] public sealed class RangeModule
    {
        public string id; public DVec center,size; public float direct,blast,fragment,damage;
        public string state;
        public RangeModule(string id,DVec center,DVec size) { this.id=id;this.center=center;this.size=size;state="intact"; }
    }
    [Serializable] public sealed class RangeReport
    {
        public string schema="damage-range-1", model="experimental-resistance-v1";
        public bool historicallyCertified=false, exploded,stopped;
        public RangeConfig config; public DVec explosion; public float finalSpeed,duration;
        public List<RangeEvent> events=new List<RangeEvent>();
        public List<RangeFragment> fragments=new List<RangeFragment>();
        public List<RangeModule> modules=new List<RangeModule>();
        public string Signature()
        {
            var s=new StringBuilder();
            foreach(var e in events) s.Append(e.kind).Append(e.id).Append(e.time.ToString("R",CultureInfo.InvariantCulture)).Append(e.point.x.ToString("R",CultureInfo.InvariantCulture));
            foreach(var m in modules) s.Append(m.id).Append(m.damage.ToString("R",CultureInfo.InvariantCulture));
            foreach(var f in fragments) s.Append(f.hit).Append(f.end.x.ToString("R",CultureInfo.InvariantCulture)).Append(f.end.y.ToString("R",CultureInfo.InvariantCulture)).Append(f.end.z.ToString("R",CultureInfo.InvariantCulture));
            return s.ToString();
        }
    }
    /// <summary>Short-range, event-driven impact experiment. Not historical ballistics or blast CFD.
    /// Resistance mm is a v-squared surrogate at 600 m/s; no gravity over this short section.
    /// Plates are finite planes; thickness affects resistance, not time inside the plate.
    /// Blast is a dimensionless distance/occlusion proxy. Fragments are weighted straight-ray samples.</summary>
    public static class RangeSolver
    {
        public static List<RangePlate> Plates(RangeConfig c) { return new List<RangePlate>{new RangePlate("Outer_Belt",0,c.outerMm),new RangePlate("Inner_Bulkhead",3,c.innerMm),new RangePlate("Rear_Bulkhead",7,c.rearMm)}; }
        public static List<RangeModule> Modules() { return new List<RangeModule>{
            new RangeModule("Boiler_Room_1",new DVec(5,0,0),new DVec(1.4f,3,2.5f)),
            new RangeModule("Engine_Room_1",new DVec(9,0,0),new DVec(1.8f,2,2.5f)),
            new RangeModule("Feed_Pump",new DVec(5,-1,4),new DVec(1.3f,1.4f,1.5f))}; }
        public static float Clamp(float x,float a,float b) { return Math.Max(a,Math.Min(b,x)); }
        public static float Effective(float mm,float cos,float material) { return mm*material/Math.Max(.05f,Math.Abs(cos)); }
        // Interval parameter is world metres when direction is normalized.
        public static bool Box(DVec origin,DVec dir,DVec center,DVec size,out float entry)
        {
            float lo=0,hi=float.PositiveInfinity; float[] o={origin.x-center.x,origin.y-center.y,origin.z-center.z}; float[] d={dir.x,dir.y,dir.z};float[] s={size.x*.5f,size.y*.5f,size.z*.5f};
            for(int i=0;i<3;i++) { if(Math.Abs(d[i])<.000001) { if(Math.Abs(o[i])>s[i]) { entry=0;return false; } continue; } float a=(-s[i]-o[i])/d[i],b=(s[i]-o[i])/d[i];lo=Math.Max(lo,Math.Min(a,b));hi=Math.Min(hi,Math.Max(a,b)); if(lo>hi) {entry=0;return false;} }
            entry=lo;return hi>=0;
        }
        public static bool PlateHit(RangePlate p,DVec origin,DVec dir,out float d)
        {
            d=0;if(Math.Abs(dir.x)<.000001)return false; d=(p.x-origin.x)/dir.x;
            if(d<-.00001)return false;var hit=origin+dir*d;return Math.Abs(hit.y)<=4&&Math.Abs(hit.z)<=7;
        }
        static void Add(RangeReport r,string kind,string id,DVec point,float time,float before,float after,float speed,string note)
        { r.events.Add(new RangeEvent{kind=kind,id=id,point=point,time=time,beforeMm=before,afterMm=after,speed=speed,note=note}); }
        public static RangeReport Fire(RangeConfig input)
        {
            input.Validate(); var c=input.Copy();var r=new RangeReport{config=c,modules=Modules()};var plates=Plates(c);
            float ang=c.angleDeg*(float)Math.PI/180;DVec dir=new DVec((float)Math.Cos(ang),(float)Math.Sin(ang),0);
            // Aim remains centred at outer plate while incidence changes.
            DVec pos=dir*(-8);float time=0,speed=c.speed,budget=c.referencePenMm*speed*speed/(600*600);
            float detTime=float.PositiveInfinity;bool armed=false;var passed=new HashSet<string>();var hitModules=new HashSet<string>();
            Add(r,"launch","Shell",pos,0,budget,budget,speed,"controlled impact conditions");
            for(int step=0;step<32;step++)
            {
                float dist=(13-pos.x)/dir.x;RangePlate next=null;RangeModule equipment=null;
                foreach(var p in plates) { float d;if(!passed.Contains(p.id)&&PlateHit(p,pos,dir,out d)&&d>=0&&d<dist) {dist=d;next=p;equipment=null;} }
                foreach(var m in r.modules) { float d;if(!hitModules.Contains(m.id)&&Box(pos,dir,m.center,m.size,out d)&&d<dist) {dist=d;equipment=m;next=null;} }
                float arrival=time+dist/Math.Max(speed,.001f);
                if(detTime<=arrival) {pos=pos+dir*((detTime-time)*speed);time=detTime;Detonate(r,plates,pos,time);break;}
                pos=pos+dir*dist;time=arrival;
                if(next!=null)
                {
                    passed.Add(next.id);
                    if(!armed&&c.fuseMode!=2) {armed=true;detTime=time+(c.fuseMode==0?0:c.fuseDelay);}
                    if(c.fuseMode==0) {Add(r,"contact",next.id,pos,time,budget,budget,speed,"contact fuse");Detonate(r,plates,pos,time);break;}
                    float before=budget,eff=Effective(next.mm,dir.x,c.resistance);budget=Math.Max(0,budget-eff);
                    speed=c.speed*(float)Math.Sqrt(budget/(c.referencePenMm*c.speed*c.speed/(600*600)));
                    Add(r,budget<=0?"stopped":"penetrated",next.id,pos,time,before,budget,speed,"equivalent resistance "+eff.ToString("F1",CultureInfo.InvariantCulture)+" mm");
                    if(budget<=0) {r.stopped=true;if(armed) {time=detTime;Detonate(r,plates,pos,time);} break;}
                }
                else if(equipment!=null)
                {
                    hitModules.Add(equipment.id);equipment.direct=.45f;
                    Add(r,"equipment",equipment.id,pos,time,budget,budget,speed,"direct-path damage proxy; equipment does not stop shell");
                }
                else {Add(r,"exit","Section",pos,time,budget,budget,speed,"left experiment bounds; outstanding fuse not simulated");break;}
            }
            foreach(var m in r.modules) {m.damage=Clamp(m.direct+m.blast+m.fragment,0,1);m.state=m.damage>=.75f?"disabled":m.damage>=.15f?"damaged":"intact";}
            r.finalSpeed=speed;r.duration=time;return r;
        }
        static void Detonate(RangeReport r,List<RangePlate> plates,DVec pos,float time)
        {
            r.exploded=true;r.explosion=pos;var c=r.config;
            Add(r,"detonation","Shell",pos,time,0,0,0,"dimensionless blast + weighted fragments; not explosive physics");
            foreach(var m in r.modules)
            {
                DVec delta=m.center-pos;float distance=delta.Length,transmission=1;
                foreach(var p in plates) {float d;if(p.mm>0&&PlateHit(p,pos,delta.Normal,out d)&&d<distance-.001f) transmission*=1/(1+p.mm*c.resistance/20);}
                m.blast=Clamp(c.blastStrength/(1+distance*distance/9)*transmission,0,1);
            }
            uint state=unchecked((uint)c.seed)^0x9e3779b9u;
            for(int i=0;i<c.fragmentSamples;i++)
            {
                // Equal-weight stratified sphere; fixed PRNG rotation avoids frame/global RNG dependency.
                float y=1-2*(i+.5f)/c.fragmentSamples;
                state=1664525u*state+1013904223u;
                float phi=(i*2.39996323f)+(state&65535)/65535f*.2f;
                float radius=(float)Math.Sqrt(Math.Max(0,1-y*y));DVec dir=new DVec(radius*(float)Math.Cos(phi),y,radius*(float)Math.Sin(phi));
                var obstacles=new List<Tuple<float,RangePlate,RangeModule>>();
                foreach(var p in plates) {float d;if(PlateHit(p,pos,dir,out d)&&d<=16) obstacles.Add(Tuple.Create(d,p,(RangeModule)null));}
                foreach(var m in r.modules) {float d;if(Box(pos,dir,m.center,m.size,out d)&&d<=16) obstacles.Add(Tuple.Create(d,(RangePlate)null,m));}
                obstacles.Sort((a,b)=>a.Item1.CompareTo(b.Item1));float budget=c.fragmentPenMm;DVec end=pos+dir*16;string hit="escape";
                foreach(var o in obstacles)
                {
                    if(o.Item2!=null) {float eff=Effective(o.Item2.mm,dir.x,c.resistance);if(eff>=budget&&eff>0) {end=pos+dir*o.Item1;hit=o.Item2.id;break;}budget-=eff;}
                    else {end=pos+dir*o.Item1;hit=o.Item3.id;o.Item3.fragment+=8f/c.fragmentSamples*(c.fragmentPenMm>0?budget/c.fragmentPenMm:0);break;}
                }
                r.fragments.Add(new RangeFragment{start=pos,end=end,hit=hit,weight=1f/c.fragmentSamples});
            }
        }
    }
}
