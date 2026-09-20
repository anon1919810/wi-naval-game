using System;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Naval.DamageLab;

namespace Naval.EditorTools
{
    public static class DamageRangeBuilder
    {
        public const string ScenePath="Assets/Scenes/DamageRange.unity";
        [MenuItem("Tools/Naval/Build damage range")]
        public static void BuildMenu()
        {
            if(!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo())return;
            BuildScene();
        }
        [MenuItem("Tools/Naval/Open damage range")]
        public static void OpenMenu()
        {
            if(!File.Exists(ScenePath)) BuildScene();
            else EditorSceneManager.OpenScene(ScenePath,OpenSceneMode.Single);
        }
        static void BuildScene()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            var root=new GameObject("DamageRange");var view=root.AddComponent<DamageRangeView>();
            var camera=new GameObject("InspectionCamera").AddComponent<Camera>();camera.tag="MainCamera";camera.backgroundColor=new Color(.025f,.055f,.085f);camera.clearFlags=CameraClearFlags.SolidColor;camera.fieldOfView=48;camera.nearClipPlane=.1f;camera.farClipPlane=150;camera.gameObject.AddComponent<AudioListener>();view.labCamera=camera;
            var sun=new GameObject("KeyLight").AddComponent<Light>();sun.type=LightType.Directional;sun.intensity=1.7f;sun.transform.rotation=Quaternion.Euler(45,-30,0);sun.shadows=LightShadows.Soft;
            RenderSettings.ambientLight=new Color(.4f,.45f,.5f);RenderSettings.ambientMode=UnityEngine.Rendering.AmbientMode.Flat;
            view.BuildEditorPreview();
            Directory.CreateDirectory("Assets/Scenes");EditorSceneManager.SaveScene(EditorSceneManager.GetActiveScene(),ScenePath);
        }
        public static void BuildBatch()
        {
            string output=Path.GetFullPath("DamageRangeBuild");var args=Environment.GetCommandLineArgs();for(int i=0;i+1<args.Length;i++)if(args[i]=="-labOutput")output=args[i+1];Directory.CreateDirectory(output);
            try
            {
                BuildScene();
                var report=RangeSolver.Fire(new RangeConfig());File.WriteAllText(Path.Combine(output,"baseline.json"),JsonUtility.ToJson(report,true));
                var sw=System.Diagnostics.Stopwatch.StartNew();for(int i=0;i<200;i++)RangeSolver.Fire(new RangeConfig{seed=i});sw.Stop();
                File.WriteAllText(Path.Combine(output,"solver_benchmark.txt"),"200 serial shots, 192 fragments per shot, allocating full diagnostic reports. Total ms="+sw.Elapsed.TotalMilliseconds+"; mean ms="+sw.Elapsed.TotalMilliseconds/200+". Not game FPS or GPU time.");
                var build=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{ScenePath},locationPathName=Path.Combine(output,"player/QueenMaryDamageRange.exe"),target=BuildTarget.StandaloneWindows64,options=BuildOptions.None});
                File.WriteAllText(Path.Combine(output,"build_result.txt"),DateTime.UtcNow.ToString("o")+"\n"+build.summary.result+" errors="+build.summary.totalErrors);
                if(Application.isBatchMode)EditorApplication.Exit(build.summary.result==UnityEditor.Build.Reporting.BuildResult.Succeeded?0:1);
            }
            catch(Exception e) {File.WriteAllText(Path.Combine(output,"build_error.txt"),e.ToString());Debug.LogException(e);if(Application.isBatchMode)EditorApplication.Exit(1);}
        }
    }
}
