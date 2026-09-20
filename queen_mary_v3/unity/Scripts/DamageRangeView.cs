using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace Naval.DamageLab
{
    /// <summary>
    /// P2 — Damage range as a playable codex/compendium: presets, A/B compare,
    /// readable event timeline, module cards. Presentation only; report is immutable.
    /// </summary>
    [ExecuteAlways]
    public sealed class DamageRangeView : MonoBehaviour
    {
        public RangeConfig config=new RangeConfig();
        public RangeReport report;
        public RangeReport compareReport;
        public RangeLayout layout;
        public Camera labCamera;
        public bool cutaway=true,showFragments=true,playing;
        public float playback;
        public int codexIndex;
        string[] presetTitles=new string[0];
        RangeCodexPreset[] presets=new RangeCodexPreset[0];

        Transform geometry,traces,shell;
        readonly List<GameObject> covers=new List<GameObject>();
        readonly Dictionary<string,Renderer> equipment=new Dictionary<string,Renderer>();
        readonly Dictionary<string,string> moduleNames=new Dictionary<string,string>();
        readonly Dictionary<string,string> moduleNotes=new Dictionary<string,string>();
        readonly List<Material> materials=new List<Material>();
        Vector2 scroll,controlScroll,codexScroll,eventScroll;
        string message="图鉴：选左侧条目 → FIRE。结果为实验模型，非史实认证。";
        string outputDir;
        float viewYaw=-52,viewPitch=28;
        int captureFrames; bool captureRequested,editorPreviewQueued;
        GUIStyle heading,small,stat,card;
        string lastShotPath;
        bool showHelp=true;
        int highlightEvent=-1;

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
            LoadLayout();
            Rebuild();Fire();
        }

        void LoadLayout()
        {
            layout=null;
            var candidates=new[]{
                Path.Combine(Application.dataPath,"../QueenMaryNaval_dummy"),
                null
            };
            var ta=Resources.Load<TextAsset>("DamageRange/range_layout");
            if(ta!=null) layout=JsonUtility.FromJson<RangeLayout>(ta.text);
            if(layout==null)
            {
                // Asset repo layout next to scripts is synced to Resources; also try absolute project-relative.
                string guess=Path.Combine(Application.dataPath,"Resources/DamageRange/range_layout.json");
                if(File.Exists(guess)) layout=RangeLayout.LoadFromFile(guess);
            }
            if(layout!=null)
            {
                var mods=layout.BuildModules();
                moduleNames.Clear();moduleNotes.Clear();
                foreach(var p in layout.plates)
                    if(p!=null&&!string.IsNullOrEmpty(p.display_name)) moduleNames["plate:"+p.id]=p.display_name;
                foreach(var m in mods)
                {
                    var def=Array.Find(layout.modules,x=>x!=null&&x.id==m.id);
                    if(def!=null)
                    {
                        if(!string.IsNullOrEmpty(def.display_name)) moduleNames[m.id]=def.display_name;
                        if(!string.IsNullOrEmpty(def.codex_note)) moduleNotes[m.id]=def.codex_note;
                    }
                }
                presets=layout.codex_presets??new RangeCodexPreset[0];
            }
            else
            {
                presets=new RangeCodexPreset[0];
            }
            presetTitles=new string[presets.Length];
            for(int i=0;i<presets.Length;i++) presetTitles[i]=(presets[i]!=null?presets[i].title:("preset"+i));
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

        public float EffectiveMm(float plateMm)
        {
            float cos=(float)Math.Abs(Math.Cos(config.angleDeg*Math.PI/180.0));
            return plateMm*config.resistance/Math.Max(0.05f,cos);
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
            labCamera.rect=new Rect(.28f,0,.46f,1);
        }

        public void Fire()
        {
            try {
                report=RangeSolver.Fire(config);
                Rebuild();playback=0;playing=true;
                message="FIRE 完成。报告不可被 UI 改写；可 Compare / 回放 / 导出。";
                DrawPaths();
            } catch(Exception e) {message=e.Message;}
        }

        public void ApplyPreset(int index)
        {
            if(presets==null||index<0||index>=presets.Length||presets[index]==null) return;
            codexIndex=index;
            var p=presets[index];
            if(p.config!=null) config=p.config.Copy();
            if(p.compare_config!=null)
            {
                try { compareReport=RangeSolver.Fire(p.compare_config.Copy()); }
                catch(Exception e) { compareReport=null; message="Compare failed: "+e.Message; }
            }
            else compareReport=null;
            Fire();
            message="图鉴["+p.title+"] "+p.teach;
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
            foreach(var m in report.modules) {
                if(!equipment.ContainsKey(m.id)) continue;
                var c=Color.Lerp(new Color(.19f,.42f,.43f),new Color(.82f,.18f,.09f),m.damage*Mathf.Max(playback,.001f));
                equipment[m.id].sharedMaterial.color=c;
            }
            if(Input.GetKeyDown(KeyCode.Space))playing=!playing;
            if(Input.GetMouseButton(1)) {viewYaw+=Input.GetAxis("Mouse X")*3;viewPitch=Mathf.Clamp(viewPitch-Input.GetAxis("Mouse Y")*3,8,75);UpdateCamera();}
            if(Input.GetKeyDown(KeyCode.H))showHelp=!showHelp;
            if(captureRequested)
            {
                captureFrames++;
                if(captureFrames==60) {playback=1;Export();Directory.CreateDirectory(outputDir);ScreenCapture.CaptureScreenshot(Path.Combine(outputDir,"DamageRange_UI.png"));}
                if(captureFrames>=180)Application.Quit(0);
            }
        }

        public void Export()
        {
            try {
                Directory.CreateDirectory(outputDir);
                string stamp=DateTime.UtcNow.ToString("yyyyMMddTHHmmssfffZ");
                string json=JsonUtility.ToJson(report,true);
                File.WriteAllText(Path.Combine(outputDir,"shot_"+stamp+".json"),json);
                File.WriteAllText(Path.Combine(outputDir,"last_shot.json"),json);
                lastShotPath=Path.Combine(outputDir,"last_shot.json");
                message="已导出 "+lastShotPath;
            } catch(Exception e) {message="导出失败: "+e.Message;}
        }

        string ModuleLabel(string id)
        {
            string n;
            return moduleNames.TryGetValue(id,out n)&&!string.IsNullOrEmpty(n)?n:id;
        }

        string EventKindLabel(string kind)
        {
            switch(kind)
            {
                case "launch":return "出膛";
                case "contact":return "接触引信";
                case "plate_transit":return "穿板行程";
                case "penetrated":return "穿透";
                case "stopped":return "被挡停";
                case "detonation":return "起爆";
                case "equipment":return "擦过设备";
                case "exit":return "飞出剖段";
                default:return kind;
            }
        }

        void OnGUI()
        {
            if (!Application.isPlaying) return;
            if(heading==null) {
                heading=new GUIStyle(GUI.skin.label){fontSize=20,fontStyle=FontStyle.Bold,wordWrap=true};
                small=new GUIStyle(GUI.skin.label){fontSize=12,wordWrap=true};
                stat=new GUIStyle(GUI.skin.label){fontSize=14,wordWrap=true};
                card=new GUIStyle(GUI.skin.label){fontSize=13,wordWrap=true,alignment=TextAnchor.UpperLeft};
            }
            float scale=Screen.width/1600f;GUI.matrix=Matrix4x4.TRS(Vector3.zero,Quaternion.identity,new Vector3(scale,scale,1));float height=Screen.height/scale;

            // Left: codex + controls
            GUI.Box(new Rect(0,0,400,height),GUIContent.none);
            GUILayout.BeginArea(new Rect(14,10,372,height-20));
            GUILayout.Label("损伤试验场 · 图鉴",heading);
            GUILayout.Label("experimental-resistance-v1 · 非史实认证",small);
            GUILayout.Label("—— 图鉴条目 ——",stat);
            codexScroll=GUILayout.BeginScrollView(codexScroll,GUILayout.Height(Mathf.Min(220,height*0.28f)));
            if(presets!=null&&presets.Length>0)
            {
                for(int i=0;i<presets.Length;i++)
                {
                    var p=presets[i];if(p==null)continue;
                    string mark=i==codexIndex?"▶ ":"  ";
                    if(GUILayout.Button(mark+"["+p.tag+"] "+p.title,GUILayout.Height(26)))
                        ApplyPreset(i);
                }
            }
            else GUILayout.Label("未加载 range_layout.json",small);
            GUILayout.EndScrollView();
            if(presets!=null&&codexIndex>=0&&codexIndex<presets.Length&&presets[codexIndex]!=null)
                GUILayout.Label(presets[codexIndex].teach??"",small);

            GUILayout.Space(6);GUILayout.Label("—— 参数 ——",stat);
            controlScroll=GUILayout.BeginScrollView(controlScroll,GUILayout.Height(Mathf.Max(160,height-520)));
            config.outerMm=Slider("外带 mm",config.outerMm,0,600,"F0");
            config.innerMm=Slider("内舱壁 mm",config.innerMm,0,250,"F0");
            config.rearMm=Slider("后舱壁 mm",config.rearMm,0,250,"F0");
            config.resistance=Slider("材料阻力",config.resistance,.5f,1.5f,"F2");
            config.speed=Slider("撞击速度 m/s",config.speed,200,1000,"F0");
            config.referencePenMm=Slider("600m/s 参考穿深 mm",config.referencePenMm,100,800,"F0");
            config.angleDeg=Slider("入射角°",config.angleDeg,-30,30,"F0");
            config.fuseDelay=Slider("引信延迟 s",config.fuseDelay,0,.04f,"F3");
            config.fuseMode=GUILayout.SelectionGrid(config.fuseMode,new[]{"接触","延迟","哑弹"},3);
            config.fragmentPenMm=Slider("破片阻力预算 mm",config.fragmentPenMm,0,80,"F0");
            config.blastStrength=Slider("爆炸代理强度",config.blastStrength,0,2,"F2");
            GUILayout.Label("Seed "+config.seed+"  样本 "+config.fragmentSamples,small);
            GUILayout.BeginHorizontal();
            if(GUILayout.Button("开火 FIRE"))Fire();
            if(GUILayout.Button("Next seed")){config.seed++;Fire();}
            if(GUILayout.Button("重放参数"))Fire();
            GUILayout.EndHorizontal();
            GUILayout.BeginHorizontal();
            if(GUILayout.Button("Compare 副炮案")) {
                if(presets!=null&&codexIndex>=0&&codexIndex<presets.Length&&presets[codexIndex]!=null&&presets[codexIndex].compare_config!=null)
                {compareReport=RangeSolver.Fire(presets[codexIndex].compare_config.Copy());message="已生成对比报告（接触引信等）。";}
                else message="本图鉴条目无预设 compare_config";
            }
            if(GUILayout.Button(showHelp?"隐藏操作":"操作说明 H"))showHelp=!showHelp;
            GUILayout.EndHorizontal();
            GUILayout.EndScrollView();
            GUILayout.EndArea();

            // Right: inspector / codex readout
            GUI.Box(new Rect(1200,0,400,height),GUIContent.none);
            GUILayout.BeginArea(new Rect(1214,10,372,height-20));
            GUILayout.Label("SHOT INSPECTOR",heading);
            if(report!=null)
            {
                string outcome=report.exploded?(report.stopped?"被挡停+起爆":"起爆"):(report.stopped?"被挡停":"飞出");
                GUILayout.Label(outcome+"  ·  "+report.duration.ToString("F3")+" s  ·  末速 "+report.finalSpeed.ToString("F0")+" m/s",stat);
                GUILayout.Label("等效装甲（当前角/材料）: 外带 "+EffectiveMm(config.outerMm).ToString("F0")+" · 内壁 "+EffectiveMm(config.innerMm).ToString("F0")+" · 后壁 "+EffectiveMm(config.rearMm).ToString("F0")+" mm",small);

                GUILayout.Label("MODULE CARDS",stat);
                float fragEnergySum=0;int fragHits=0;
                if(report.fragments!=null)
                    foreach(var f in report.fragments){fragEnergySum+=f.energyJ;if(f.hit!="escape"&&f.hit!="Section"&&f.hit!=null)fragHits++;}
                GUILayout.Label(string.Format("破片: {0} 发 · 命中设备 {1} · 能量合计 {2:F0} J（实验代理）",report.fragments!=null?report.fragments.Count:0,fragHits,fragEnergySum),small);
                foreach(var m in report.modules)
                {
                    string note;moduleNotes.TryGetValue(m.id,out note);
                    GUILayout.BeginVertical(GUI.skin.box);
                    GUILayout.Label(ModuleLabel(m.id)+"  ["+m.state+"]",card);
                    GUILayout.Label(string.Format("直伤 {0:0.00} / 爆 {1:0.00} / 破片 {2:0.00} → {3:P0}",m.direct,m.blast,m.fragment,m.damage),small);
                    if(!string.IsNullOrEmpty(note))GUILayout.Label(note,small);
                    GUILayout.EndVertical();
                }

                if(compareReport!=null)
                {
                    GUILayout.Label("COMPARE（图鉴副案）",stat);
                    foreach(var m in compareReport.modules)
                        GUILayout.Label(ModuleLabel(m.id)+": "+m.damage.ToString("P0")+" / "+m.state,small);
                    GUILayout.Label("主案 vs 副案仅演示；非平衡表。",small);
                }

                GUILayout.Label("EVENT TIMELINE",stat);
                GUILayout.BeginHorizontal();
                GUILayout.Label("回放",small);playback=GUILayout.HorizontalSlider(playback,0,1);
                GUILayout.EndHorizontal();
                GUILayout.BeginHorizontal();
                if(GUILayout.Button(playing?"暂停":"播放"))playing=!playing;
                if(GUILayout.Button("下一步")){playing=false;float t=report.duration*playback;for(int i=0;i<report.events.Count;i++)if(report.events[i].time>t+.000001f){playback=report.events[i].time/Mathf.Max(report.duration,.000001f);highlightEvent=i;break;}}
                if(GUILayout.Button("重播")){playback=0;playing=true;}
                GUILayout.EndHorizontal();
                eventScroll=GUILayout.BeginScrollView(eventScroll,GUILayout.Height(Mathf.Max(120,height-620)));
                for(int i=0;i<report.events.Count;i++)
                {
                    var e=report.events[i];
                    string hi=i==highlightEvent?"▶ ":"  ";
                    if(GUILayout.Button(hi+e.time.ToString("F3")+"s "+EventKindLabel(e.kind)+" · "+e.id+
                        "  "+e.beforeMm.ToString("F0")+"→"+e.afterMm.ToString("F0")+"mm",GUILayout.Height(22)))
                    {
                        highlightEvent=i;
                        if(report.duration>0) playback=e.time/report.duration;
                    }
                    if(!string.IsNullOrEmpty(e.note))GUILayout.Label("    "+e.note,small);
                }
                GUILayout.EndScrollView();

                bool cut=GUILayout.Toggle(cutaway,"剖视（去顶/前盖）");if(cut!=cutaway){cutaway=cut;ApplyCover();}
                bool fr=GUILayout.Toggle(showFragments,"显示破片路径");if(fr!=showFragments){showFragments=fr;var f=traces!=null?traces.Find("FragmentPaths"):null;if(f!=null)f.gameObject.SetActive(fr);}
                if(GUILayout.Button("导出 JSON"))Export();
            }
            GUILayout.Label(message,small);
            GUILayout.EndArea();

            // Center top: help + plate legend
            if(showHelp)
            {
                GUI.Box(new Rect(420,8,760,110),GUIContent.none);
                GUI.Label(new Rect(432,14,740,100),
                    "图鉴操作: 左侧条目=教学预设 · 中键拖动=环绕 · Space=回放暂停 · H=本帮助\n"+
                    "火炮: 改参数后 FIRE · Compare 生成副案对照 · 点事件跳时间轴\n"+
                    "观测: 砖色=起爆 · 黄=穿透/接触 · 模块卡片直/爆/破片分量 · 末尾导出 JSON\n"+
                    "边界: 实验代理模型，结果不可直接当作主战斗数值",small);
            }
            GUI.Label(new Rect(420,height-28,760,24),"剖段: 外带 → 内舱壁 → 后舱壁 → 设备区   |   橙壳标弹道   红点=起爆",small);
        }

        float Slider(string label,float value,float min,float max,string format)
        {GUILayout.Label(label+"  "+value.ToString(format));return GUILayout.HorizontalSlider(value,min,max);}

        void OnDisable()
        {
#if UNITY_EDITOR
            UnityEditor.EditorApplication.delayCall -= BuildEditorPreview;
#endif
        }
        void OnDestroy() {foreach(var m in materials)if(m!=null){if(Application.isPlaying)Destroy(m);else DestroyImmediate(m);}}
    }
}
