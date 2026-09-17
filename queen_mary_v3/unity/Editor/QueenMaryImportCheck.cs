using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

public static class QueenMaryImportCheck
{
    [Serializable] public class Module { public string name; public string parent; public string type; }
    [Serializable] public class Manifest { public int mesh_count; public Module[] objects; }
    [Serializable] public class RigProbe { public string turret; public string yawAxis; public int yawSign; public string pitchAxis; public int pitchSign; }
    [Serializable]
    public class Result
    {
        public string unityVersion;
        public string status;
        public string sourceFbxSha256;
        public Vector3 hullSizeMetres;
        public Vector3 hullMinMetres;
        public Vector3 hullMaxMetres;
        public Vector3 bowDirection;
        public Vector3 shipLocalUpInUnity;
        public Vector3 shipLocalRightInUnity;
        public Vector3 rootEuler;
        public Vector3 rootScale;
        public int meshCount;
        public bool yawAroundShipVertical;
        public bool positiveCommandTurnsStarboard;
        public bool elevationRaisesBarrel;
        public int unityLocalYawSign;
        public int unityLocalPitchSign;
        public List<string> failures = new List<string>();
        public string completedUtc;
        public int semanticModulesChecked;
        public int articulatedTurretsChecked;
        public Vector3 starboardDirection;
        public List<RigProbe> turretAxes = new List<RigProbe>();
        public bool latestDeepSeekContractParsed;
    }

    public static void Run()
    {
        Result result = new Result { unityVersion = Application.unityVersion };
        GameObject ship = null;
        try
        {
            using (var sha = System.Security.Cryptography.SHA256.Create())
                result.sourceFbxSha256 = BitConverter.ToString(sha.ComputeHash(
                    File.ReadAllBytes(Path.Combine(Application.dataPath, "QueenMary.fbx")))).Replace("-", "").ToLowerInvariant();
            AssetDatabase.ImportAsset("Assets/QueenMary.fbx", ImportAssetOptions.ForceSynchronousImport);
            ModelImporter importer = (ModelImporter)AssetImporter.GetAtPath("Assets/QueenMary.fbx");
            importer.globalScale = 1;
            importer.useFileScale = false;
            importer.bakeAxisConversion = false;
            importer.preserveHierarchy = true;
            importer.isReadable = true; // Validation reads mesh tip vertices.
            importer.weldVertices = false;
            importer.optimizeMeshVertices = false;
            importer.optimizeMeshPolygons = false;
            importer.meshCompression = ModelImporterMeshCompression.Off;
            importer.importCameras = false;
            importer.importLights = false;
            importer.materialImportMode = ModelImporterMaterialImportMode.None;
            importer.SaveAndReimport();
            GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/QueenMary.fbx");
            ship = UnityEngine.Object.Instantiate(prefab);
            Dictionary<string, Transform> names = new Dictionary<string, Transform>();
            foreach (Transform t in ship.GetComponentsInChildren<Transform>(true)) names[t.name] = t;
            Manifest manifest = JsonUtility.FromJson<Manifest>(File.ReadAllText(Path.Combine(Application.dataPath, "QueenMaryManifest.json")));
            foreach (Module module in manifest.objects)
            {
                if (!names.ContainsKey(module.name)) { result.failures.Add("Missing semantic module: " + module.name); continue; }
                Transform item = names[module.name];
                if (!String.IsNullOrEmpty(module.parent) && (item.parent == null || item.parent.name != module.parent))
                    result.failures.Add("Parent changed: " + module.name);
                result.semanticModulesChecked++;
            }
            Naval.ShipContractData contract = Naval.ShipContractData.Parse(File.ReadAllText(Path.Combine(Application.dataPath, "QueenMaryContract.json")));
            result.latestDeepSeekContractParsed = contract.asset_version == "v3" && contract.object_count == manifest.objects.Length
                && contract.mesh_count == manifest.mesh_count && contract.turrets.Length == 4
                && contract.secondary_guns.Length == 16 && contract.materials.Length == 6;
            foreach (var role in contract.module_roles) foreach (string name in role.names)
                result.latestDeepSeekContractParsed &= names.ContainsKey(name);
            if (!result.latestDeepSeekContractParsed) result.failures.Add("Latest DeepSeek contract does not resolve against this asset");
            Transform root = names["Queen_Mary"];
            Transform hull = names["Hull"];
            Bounds bounds = hull.GetComponent<MeshRenderer>().bounds;
            result.hullSizeMetres = bounds.size;
            result.hullMinMetres = bounds.min;
            result.hullMaxMetres = bounds.max;
            result.bowDirection = (names["Turret_A"].position - names["Turret_X"].position).normalized;
            result.starboardDirection = (names["Casemate_Starboard_1"].position - names["Casemate_Port_1"].position).normalized;
            result.shipLocalUpInUnity = root.TransformDirection(Vector3.forward);
            result.shipLocalRightInUnity = root.TransformDirection(Vector3.right);
            result.rootEuler = root.eulerAngles;
            result.rootScale = root.lossyScale;
            result.meshCount = ship.GetComponentsInChildren<MeshFilter>().Length;
            if (Mathf.Abs(bounds.size.x - 27.2f) > .005f || Mathf.Abs(bounds.size.y - 15f) > .005f ||
                Mathf.Abs(bounds.size.z - 213.4f) > .005f) result.failures.Add("Hull dimensions differ from 27.2 x 15 x 213.4 m");
            if (Mathf.Abs(bounds.min.y + 9.9f) > .005f || Mathf.Abs(bounds.max.y - 5.1f) > .005f)
                result.failures.Add("Waterline/keel/deck conversion is incorrect");
            result.yawAroundShipVertical = true;
            result.elevationRaisesBarrel = true;
            result.positiveCommandTurnsStarboard = true;
            foreach (string key in new [] { "A", "B", "Q", "X" })
            {
                Transform yaw = names["Turret_" + key];
                Transform pitch = names["Elevation_" + key];
                Transform barrel = names["Barrel_" + key + "_Port"];
                if (pitch.parent != yaw || barrel.parent != pitch) result.failures.Add("Rig hierarchy lost: " + key);
                Quaternion restYaw = yaw.localRotation;
                Quaternion restPitch = pitch.localRotation;
                Vector3 pivot = yaw.position;
                Vector3 barbettePosition = names["Barbette_" + key].position;
                Mesh mesh = barrel.GetComponent<MeshFilter>().sharedMesh;
                Vector3 tip = Vector3.zero;
                float farthest = -1;
                foreach (Vector3 vertex in mesh.vertices)
                {
                    if (vertex.sqrMagnitude > farthest) { farthest = vertex.sqrMagnitude; tip = vertex; }
                }
                Vector3 before = barrel.TransformPoint(tip);
                int yawSign, pitchSign;
                string yawAxis = Probe(yaw, barrel, tip, pivot, false, out yawSign);
                string pitchAxis = Probe(pitch, barrel, tip, pitch.position, true, out pitchSign);
                result.yawAroundShipVertical &= yawAxis != null;
                result.positiveCommandTurnsStarboard &= yawAxis != null;
                result.elevationRaisesBarrel &= pitchAxis != null;
                result.turretAxes.Add(new RigProbe { turret=key, yawAxis=yawAxis, yawSign=yawSign, pitchAxis=pitchAxis, pitchSign=pitchSign });
                if ((yaw.position-pivot).magnitude > .001f || (names["Barbette_" + key].position-barbettePosition).magnitude > .001f)
                    result.failures.Add("Mount moved during articulation: " + key);
                yaw.localRotation = restYaw;
                result.articulatedTurretsChecked++;
            }
            result.unityLocalYawSign = result.turretAxes[0].yawSign;
            result.unityLocalPitchSign = result.turretAxes[0].pitchSign;
            if (!result.yawAroundShipVertical) result.failures.Add("No valid local yaw axis found");
            if (!result.elevationRaisesBarrel) result.failures.Add("No valid elevation axis found");
            if (!result.positiveCommandTurnsStarboard) result.failures.Add("No valid clockwise yaw command found");
            if (result.meshCount != manifest.mesh_count) result.failures.Add("Mesh inventory differs from manifest");
            if (result.bowDirection.z < .99f) result.failures.Add("Bow does not face Unity +Z");
            if (result.starboardDirection.x < .99f) result.failures.Add("Physical starboard does not face Unity +X");
            result.status = result.failures.Count == 0 ? "passed" : "failed";
        }
        catch (Exception ex)
        {
            result.status = "failed";
            result.failures.Add(ex.ToString());
        }
        finally
        {
            if (ship != null) UnityEngine.Object.DestroyImmediate(ship);
            result.completedUtc = DateTime.UtcNow.ToString("o");
            string output = Path.GetFullPath(Path.Combine(Application.dataPath, "../QueenMary_UnityVerification.json"));
            string[] args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++)
                if (args[i] == "-queenMaryReport") output = Path.GetFullPath(args[i + 1]);
            File.WriteAllText(output, JsonUtility.ToJson(result, true));
        }
        EditorApplication.Exit(result.status == "passed" ? 0 : 1);
    }

    private static string Probe(Transform node, Transform barrel, Vector3 tip, Vector3 pivot, bool elevation, out int sign)
    {
        Quaternion rest = node.localRotation;
        Vector3 before = barrel.TransformPoint(tip);
        Vector3[] axes = { Vector3.right, Vector3.up, Vector3.forward };
        string[] labels = { "X", "Y", "Z" };
        for (int i=0; i<3; i++) foreach (int s in new[] {-1,1})
        {
            node.localRotation = rest * Quaternion.AngleAxis(s*15, axes[i]);
            Vector3 after = barrel.TransformPoint(tip);
            float bearing = Vector3.SignedAngle(Vector3.ProjectOnPlane(before-pivot,Vector3.up), Vector3.ProjectOnPlane(after-pivot,Vector3.up), Vector3.up);
            bool ok = elevation ? (after.y > before.y+1 && Mathf.Abs(bearing)<.2f)
                                : (bearing > 10 && Mathf.Abs(after.y-before.y)<.02f);
            node.localRotation = rest;
            if (ok) { sign=s; return labels[i]; }
        }
        sign=0;
        return null;
    }
}
