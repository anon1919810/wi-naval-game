using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace Naval.DamageLab
{
    [ExecuteAlways]
    public sealed class DamageRangeView : MonoBehaviour
    {
        public RangeConfig config=new RangeConfig();
        public RangeReport report;
        public Camera labCamera;
        public bool cutaway=true,showFragments=true,playing;
        public float playback;
        Transform geometry,traces,shell;
        readonly List<GameObject> covers=new List<GameObject>();
        readonly Dictionary<string,Renderer> equipment=new Dictionary<string,Renderer>();
        readonly List<Material> materials=new List<Material>();
        Vector2 scroll,controlScroll;
        string message="Adjust conditions, then FIRE. All values are experimental.";
        string outputDir;
        float viewYaw=-52,viewPitch=28;
        int captureFrames;
        bool captureRequested;
        bool editorPreviewQueued;
        GUIStyle heading,small,stat;
        static Vector3 V(DVec p) { return new Vector3(p.x,p.y,p.z); }
        public void Start()
        {
            outputDir=Path.Combine(Application.persistentDataPath,"DamageRange");
            var args=Environment.GetCommandLineArgs();
            for(int i=0;i+1<args.Length;i++) if(args[i]=="-labOutput") outputDir=args[i+1];
            captureRequested=Array.IndexOf(args,"-labCapture")>=0;
            if(labCamera==null) labCamera=Camera.main;
            if(labCamera==null)
            {
                labCamera=new GameObject("InspectionCamera").AddComponent<Camera>();labCamera.tag="MainCamera";
                labCamera.clearFlags=CameraClearFlags.SolidColor;labCamera.backgroundColor=new Color(.025f,.055f,.085f);labCamera.fieldOfView=48;labCamera.farClipPlane=150;
                labCamera.gameObject.AddComponent<AudioListener>();
                var light=new GameObject("InspectionKeyLight").AddComponent<Light>();light.type=LightType.Directional;light.intensity=1.7f;light.transform.rotation=Quaternion.Euler(45,-30,0);
                RenderSettings.ambientMode=UnityEngine.Rendering.AmbientMode.Flat;RenderSettings.ambientLight=new Color(.4f,.45f,.5f);
            }
            Rebuild();Fire();
        }

        public void OnEnable()
        {
#if UNITY_EDITOR
            if (!Application.isPlaying && !editorPreviewQueued)
            {
                editorPreviewQueued=true;
                UnityEditor.EditorApplication.delayCall += BuildEditorPreview;
            }
#endif
        }

#if UNITY_EDITOR
        public void BuildEditorPreview()
        {
            editorPreviewQueued=false;
            if (this==null || Application.isPlaying || !gameObject.scene.IsValid()) return;
            ResolveGeneratedRoots();
            if (geometry==null || report==null)
            {
                Rebuild();
                report=RangeSolver.Fire(config);
                Rebuild();
                playback=1; playing=false; DrawPaths();
                UnityEditor.EditorUtility.SetDirty(this);
            }
            else ApplyCover();
        }
#endif

        void ResolveGeneratedRoots()
        {
            if (geometry==null) geometry=transform.Find("Experimental_Hull_Section");
            if (traces==null) traces=transform.Find("Report_Visuals_Only");
        }

        void DisposeObject(GameObject go)
        {
            if (go==null) return;
            if (Application.isPlaying) Destroy(go); else DestroyImmediate(go);
        }
        Material Mat(Color c,bool unlit=false)
        {
            var shader=Shader.Find(unlit?"Universal Render Pipeline/Unlit":"Universal Render Pipeline/Lit");
            if(shader==null)shader=Shader.Find("Standard");
            var m=new Material(shader);m.color=c;if(m.HasProperty("_BaseColor"))m.SetColor("_BaseColor",c);
            if(m.HasProperty("_Smoothness"))m.SetFloat("_Smoothness",.28f);materials.Add(m);return m;
        }
        GameObject Solid(string name,PrimitiveType type,Vector3 p,Vector3 scale,Color colour,Transform parent)
        {
            var g=GameObject.CreatePrimitive(type);g.name=name;g.transform.SetParent(parent,false);g.transform.localPosition=p;g.transform.localScale=scale;
            var col=g.GetComponent<Collider>();if(col!=null)Destroy(col);g.GetComponent<Renderer>().sharedMaterial=Mat(colour);return g;
        }
        void Rebuild()
        {
            ResolveGeneratedRoots();
            if(geometry!=null)DisposeObject(geometry.gameObject);if(traces!=null)DisposeObject(traces.gameObject);
            foreach(var m in materials)if(m!=null){if(Application.isPlaying)Destroy(m);else DestroyImmediate(m);}materials.Clear();covers.Clear();equipment.Clear();
            geometry=new GameObject("Experimental_Hull_Section").transform;geometry.SetParent(transform,false);
            traces=new GameObject("Report_Visuals_Only").transform;traces.SetParent(transform,false);
            Color steel=new Color(.23f,.32f,.39f),deck=new Color(.30f,.34f,.35f),copper=new Color(.70f,.40f,.17f);
            Solid("Foundation",PrimitiveType.Cube,new Vector3(4,-4.5f,0),new Vector3(20,.7f,16),new Color(.08f,.13f,.18f),geometry);
            Solid("Inner_Deck",PrimitiveType.Cube,new Vector3(5,-3.8f,0),new Vector3(14,.2f,14),deck,geometry);
            covers.Add(Solid("Inspection_Roof",PrimitiveType.Cube,new Vector3(5,4.2f,0),new Vector3(14,.18f,14),steel,geometry));
            covers.Add(Solid("Inspection_Front",PrimitiveType.Cube,new Vector3(5,0,-7.1f),new Vector3(14,8,.12f),steel,geometry));
            Solid("Back_Wall",PrimitiveType.Cube,new Vector3(5,0,7.1f),new Vector3(14,8,.15f),steel,geometry);
            foreach(var p in RangeSolver.Plates(config))
            {
                if(p.mm<=0)continue;
                // True resistance remains in mm; displayed thickness minimum is labelled in the UI.
                Solid(p.id,PrimitiveType.Cube,new Vector3(p.x,0,0),new Vector3(Mathf.Max(.04f,p.mm/1000),8,14),p.x==0?new Color(.46f,.55f,.61f):steel,geometry);
                for(int z=-6;z<=6;z+=3)Solid(p.id+"_Frame",PrimitiveType.Cube,new Vector3(p.x+.12f,0,z),new Vector3(.16f,8,.14f),deck,geometry);
            }
            foreach(var m in RangeSolver.Modules())
            {
                var g=Solid(m.id,PrimitiveType.Cube,V(m.center),V(m.size),new Color(.19f,.42f,.43f),geometry);equipment[m.id]=g.GetComponent<Renderer>();
                for(int z=-1;z<=1;z++)
                {
                    var body=Solid(m.id+"_Casing",PrimitiveType.Cylinder,V(m.center)+new Vector3(0,.4f,z*.6f),new Vector3(.65f,1.1f,.65f),new Color(.28f,.42f,.44f),geometry);
                    body.transform.rotation=Quaternion.Euler(0,0,90);
                }
                Solid(m.id+"_SteamHeader",PrimitiveType.Cylinder,V(m.center)+Vector3.up*1.9f,new Vector3(.16f,1.5f,.16f),copper,geometry).transform.rotation=Quaternion.Euler(90,0,0);
            }
            Solid("LauncherBase",PrimitiveType.Cube,new Vector3(-8,-3,0),new Vector3(2,.5f,2),steel,geometry);
            var barrel=Solid("TestLauncher",PrimitiveType.Cylinder,new Vector3(-8,0,0),new Vector3(.45f,1.5f,.45f),copper,geometry);barrel.transform.rotation=Quaternion.Euler(0,0,-90);
            shell=Solid("Shell_Marker",PrimitiveType.Sphere,new Vector3(-8,0,0),Vector3.one*.25f,new Color(1,.76f,.2f),traces).transform;
            ApplyCover();UpdateCamera();
        }
        void ApplyCover() {foreach(var c in covers)c.SetActive(!cutaway);}
        void UpdateCamera()
        {
            if(labCamera==null)return;
            labCamera.transform.position=new Vector3(3,0,0)+Quaternion.Euler(viewPitch,viewYaw,0)*new Vector3(0,0,-31);
            labCamera.transform.LookAt(new Vector3(3,0,0));
            labCamera.rect=new Rect(.255f,0,.50f,1);
        }
        public void Fire()
        {
            try {report=RangeSolver.Fire(config);Rebuild();playback=0;playing=true;message="Shot ready. Replay is presentation only; report is immutable.";DrawPaths();}
            catch(Exception e) {message=e.Message;}
        }
        void Line(string name,Vector3 a,Vector3 b,Color colour,float width,Transform parent)
        {
            var g=new GameObject(name);g.transform.SetParent(parent,false);var line=g.AddComponent<LineRenderer>();line.useWorldSpace=true;line.positionCount=2;line.SetPosition(0,a);line.SetPosition(1,b);line.startWidth=width;line.endWidth=width;line.sharedMaterial=Mat(colour,true);
        }
        void DrawPaths()
        {
            if(report==null)return;
            for(int i=1;i<report.events.Count;i++)Line("ShellPath",V(report.events[i-1].point),V(report.events[i].point),new Color(1,.72f,.2f),.055f,traces);
            foreach(var e in report.events)
            {
                if(e.kind=="launch"||e.kind=="equipment")continue;
                Solid(e.kind,PrimitiveType.Sphere,V(e.point),Vector3.one*(e.kind=="detonation"?.5f:.22f),e.kind=="detonation"?new Color(1,.25f,.12f):new Color(1,.7f,.1f),traces);
            }
            var frag=new GameObject("FragmentPaths").transform;frag.SetParent(traces,false);
            // Display a subset, but simulation always retains every weighted sample.
            for(int i=0;i<report.fragments.Count;i+=Mathf.Max(1,report.fragments.Count/96))
            {var f=report.fragments[i];Line("Fragment",V(f.start),V(f.end),f.hit=="escape"?new Color(.35f,.48f,.53f):new Color(1,.35f,.16f),.012f,frag);}
            frag.gameObject.SetActive(showFragments);
        }
        void Update()
        {
            if (!Application.isPlaying) return;
            if(report==null)return;
            if(playing)playback=Mathf.Min(1,playback+Time.unscaledDeltaTime/4);
            if(playback>=1)playing=false;
            float time=report.duration*playback;
            if(playback>=1&&report.events.Count>0)shell.position=V(report.events[report.events.Count-1].point);
            for(int i=1;i<report.events.Count;i++)if(time<=report.events[i].time)
            {var a=report.events[i-1];var b=report.events[i];shell.position=Vector3.Lerp(V(a.point),V(b.point),Mathf.InverseLerp(a.time,b.time,time));break;}
            foreach(var m in report.modules) {var c=Color.Lerp(new Color(.19f,.42f,.43f),new Color(.82f,.18f,.09f),m.damage*playback);equipment[m.id].sharedMaterial.color=c;}
            if(Input.GetKeyDown(KeyCode.Space))playing=!playing;
            if(Input.GetMouseButton(1)) {viewYaw+=Input.GetAxis("Mouse X")*3;viewPitch=Mathf.Clamp(viewPitch-Input.GetAxis("Mouse Y")*3,8,75);UpdateCamera();}
            if(captureRequested)
            {
                captureFrames++;
                if(captureFrames==60) {playback=1;Export();Directory.CreateDirectory(outputDir);ScreenCapture.CaptureScreenshot(Path.Combine(outputDir,"DamageRange_UI.png"));}
                if(captureFrames>=180)Application.Quit(0);
            }
        }
        public void Export()
        {
            try {Directory.CreateDirectory(outputDir);string stamp=DateTime.UtcNow.ToString("yyyyMMddTHHmmssfffZ");string json=JsonUtility.ToJson(report,true);File.WriteAllText(Path.Combine(outputDir,"shot_"+stamp+".json"),json);File.WriteAllText(Path.Combine(outputDir,"last_shot.json"),json);message="Exported to "+outputDir;}
            catch(Exception e) {message="Export failed: "+e.Message;}
        }
        void LoadLast()
        {
            try {var saved=JsonUtility.FromJson<RangeReport>(File.ReadAllText(Path.Combine(outputDir,"last_shot.json")));if(saved==null||saved.schema!="damage-range-1"||saved.config==null)throw new InvalidDataException("Unsupported shot file");config=saved.config;Fire();message=report.Signature()==saved.Signature()?"Replay matches saved report.":"Replay differs from saved report.";}catch(Exception e){message="Load failed: "+e.Message;}
        }
        float Slider(string label,float value,float min,float max,string format)
        {GUILayout.Label(label+"  "+value.ToString(format));return GUILayout.HorizontalSlider(value,min,max);}
        void OnGUI()
        {
            if (!Application.isPlaying) return;
            if(heading==null) {heading=new GUIStyle(GUI.skin.label){fontSize=22,fontStyle=FontStyle.Bold,wordWrap=true};small=new GUIStyle(GUI.skin.label){fontSize=12,wordWrap=true};stat=new GUIStyle(GUI.skin.label){fontSize=14,wordWrap=true};}
            float scale=Screen.width/1440f;GUI.matrix=Matrix4x4.TRS(Vector3.zero,Quaternion.identity,new Vector3(scale,scale,1));float height=Screen.height/scale;
            GUI.Box(new Rect(0,0,362,height),GUIContent.none);GUI.Box(new Rect(1090,0,350,height),GUIContent.none);
            GUILayout.BeginArea(new Rect(18,16,325,height-32));controlScroll=GUILayout.BeginScrollView(controlScroll);GUILayout.Label("QUEEN MARY",heading);GUILayout.Label("DAMAGE RANGE / 01",heading);GUILayout.Label("Experimental section · metres / millimetres\nNot historically certified",small);GUILayout.Space(12);
            config.outerMm=Slider("Outer belt mm",config.outerMm,0,600,"F0");config.innerMm=Slider("Inner bulkhead mm",config.innerMm,0,250,"F0");config.rearMm=Slider("Rear bulkhead mm",config.rearMm,0,250,"F0");
            config.resistance=Slider("Material resistance factor",config.resistance,.5f,1.5f,"F2");config.speed=Slider("Impact speed m/s",config.speed,200,1000,"F0");config.referencePenMm=Slider("Resistance budget at 600 m/s",config.referencePenMm,100,800,"F0");config.angleDeg=Slider("Incidence deg",config.angleDeg,-30,30,"F0");config.fuseDelay=Slider("Fuse delay seconds",config.fuseDelay,0,.04f,"F3");
            config.fuseMode=GUILayout.SelectionGrid(config.fuseMode,new[]{"Contact","Delay","Dud"},3);config.fragmentPenMm=Slider("Fragment resistance budget",config.fragmentPenMm,0,80,"F0");config.blastStrength=Slider("Blast proxy strength",config.blastStrength,0,2,"F2");
            GUILayout.Label("Fixed seed "+config.seed+"  /  samples "+config.fragmentSamples,small);
            GUILayout.BeginHorizontal();if(GUILayout.Button("Repeat shot"))Fire();if(GUILayout.Button("Next seed"))config.seed++;GUILayout.EndHorizontal();
            if(GUILayout.Button("FIRE / RECOMPUTE",GUILayout.Height(34)))Fire();
            GUILayout.BeginHorizontal();if(GUILayout.Button("Baseline")){config=new RangeConfig();Fire();}if(GUILayout.Button("Thick plate")){config.outerMm=600;config.fuseMode=2;Fire();}if(GUILayout.Button("Open walls")){config.outerMm=config.innerMm=config.rearMm=0;Fire();}GUILayout.EndHorizontal();
            GUILayout.Label("Changes apply on FIRE. Plate display thickness min 40 mm. Walls are finite 8 × 14 m planes.",small);GUILayout.EndScrollView();GUILayout.EndArea();
            GUILayout.BeginArea(new Rect(1107,16,315,height-32));GUILayout.Label("SHOT INSPECTOR",heading);
            if(report!=null)
            {
                GUILayout.Label((report.exploded?"DETONATED":report.stopped?"STOPPED":"EXITED")+"  /  "+report.duration.ToString("F4")+" s",stat);
                GUILayout.Label("Final shell speed "+report.finalSpeed.ToString("F1")+" m/s",small);
                GUILayout.Label("REPLAY · 4 seconds presentation",small);playback=GUILayout.HorizontalSlider(playback,0,1);
                GUILayout.BeginHorizontal();if(GUILayout.Button(playing?"Pause":"Play"))playing=!playing;if(GUILayout.Button("Step event")){playing=false;float t=report.duration*playback;foreach(var e in report.events)if(e.time>t+.000001f){playback=e.time/Mathf.Max(report.duration,.000001f);break;}}if(GUILayout.Button("Restart")){playback=0;playing=true;}GUILayout.EndHorizontal();
                bool cut=GUILayout.Toggle(cutaway,"Cutaway / remove inspection covers");if(cut!=cutaway){cutaway=cut;ApplyCover();}
                bool fr=GUILayout.Toggle(showFragments,"Weighted fragment paths");if(fr!=showFragments){showFragments=fr;var f=traces.Find("FragmentPaths");if(f!=null)f.gameObject.SetActive(fr);}
                GUILayout.Label("MODULE RESULT",stat);
                foreach(var m in report.modules)GUILayout.Label(m.id+"  "+m.state+"\nDirect "+m.direct.ToString("F2")+" / Blast "+m.blast.ToString("F2")+" / Fragments "+m.fragment.ToString("F2")+"\nDamage "+m.damage.ToString("P0"),small);
                GUILayout.Space(10);GUILayout.Label("ORDERED EVENTS",stat);scroll=GUILayout.BeginScrollView(scroll,GUILayout.Height(Mathf.Max(95,height-510)));
                foreach(var e in report.events)GUILayout.Label(e.time.ToString("F4")+"s  "+e.kind+"\n"+e.id+"  "+e.beforeMm.ToString("F0")+" → "+e.afterMm.ToString("F0")+" mm\n"+e.note,small);GUILayout.EndScrollView();
                if(GUILayout.Button("EXPORT SHOT JSON"))Export();if(GUILayout.Button("LOAD LAST SHOT"))LoadLast();
            }
            GUILayout.Label(message,small);GUILayout.EndArea();
            GUI.Label(new Rect(385,18,675,36),"ARMOUR  →  BULKHEAD  →  MACHINERY",heading);GUI.Label(new Rect(385,height-45,675,35),"RMB drag: orbit   |   Space: pause   |   orange: shell   red: fragments",small);
        }
        void OnDisable()
        {
#if UNITY_EDITOR
            UnityEditor.EditorApplication.delayCall -= BuildEditorPreview;
#endif
        }
        void OnDestroy() {foreach(var m in materials)if(m!=null){if(Application.isPlaying)Destroy(m);else DestroyImmediate(m);}}
    }
}
