using System.Collections.Generic;
using UnityEngine;

namespace Naval
{
    /// <summary>
    /// T16 — Code-built combat VFX (muzzle, short arc tracer, splash, impact).
    /// Tuned for 200 m capital ships: thin tracers, tiny muzzle puffs, no horizon lasers.
    /// </summary>
    [AddComponentMenu("Naval/Ship Combat VFX")]
    public sealed class ShipCombatVfx : MonoBehaviour
    {
        public static ShipCombatVfx FindOrGlobal()
        {
            var local = FindObjectOfType<ShipCombatVfx>();
            if (local != null) return local;
            var go = GameObject.Find("CombatVFX");
            if (go == null) go = new GameObject("CombatVFX");
            var vfx = go.GetComponent<ShipCombatVfx>();
            if (vfx == null) vfx = go.AddComponent<ShipCombatVfx>();
            return vfx;
        }

        public static ShipCombatVfx EnsureOn(GameObject ship)
        {
            if (ship == null) return FindOrGlobal();
            var vfx = ship.GetComponent<ShipCombatVfx>();
            if (vfx == null) vfx = ship.AddComponent<ShipCombatVfx>();
            return vfx;
        }

        [Header("Tracer")]
        public float tracerTime = 0.12f;
        public float tracerWidth = 0.06f;
        public float maxTracerVisualLength = 250f;
        public int maxConcurrentTracers = 8;
        public Color tracerColor = new Color(1f, 0.8f, 0.3f, 0.55f);

        [Header("Muzzle")]
        public float muzzleLife = 0.05f;
        public float muzzleScale = 0.15f;

        [Header("Impact / splash")]
        public float impactLife = 0.45f;
        public float splashLife = 0.55f;

        [Header("Placeholder audio (optional)")]
        public AudioClip fireClip;
        public AudioClip hitClip;
        public AudioClip splashClip;
        public float audioVolume = 0.8f;

        AudioSource _audio;
        bool _warnedNoAudio;
        Material _lineMat;
        readonly List<ShipVfxTimedDespawn> _liveTracers = new List<ShipVfxTimedDespawn>();

        void Awake()
        {
            _audio = GetComponent<AudioSource>();
            if (_audio == null) _audio = gameObject.AddComponent<AudioSource>();
            _audio.playOnAwake = false;
            _audio.spatialBlend = 0.35f;
        }

        Material LineMat()
        {
            if (_lineMat == null)
            {
                var sh = Shader.Find("Universal Render Pipeline/Unlit") ?? Shader.Find("Sprites/Default");
                _lineMat = new Material(sh);
                _lineMat.SetColor("_BaseColor", tracerColor);
                _lineMat.SetColor("_Color", tracerColor);
            }
            return _lineMat;
        }

        void PlayClip(AudioClip clip)
        {
            if (clip == null)
            {
                if (!_warnedNoAudio)
                {
                    _warnedNoAudio = true;
                    Debug.Log("[Naval] Combat VFX placeholder audio clips not assigned; visual-only.");
                }
                return;
            }
            _audio.PlayOneShot(clip, audioVolume);
        }

        public void PlayTracer(Vector3 origin, Vector3 end, Vector3 dir, bool willHit)
        {
            _liveTracers.RemoveAll(t => t == null);
            if (_liveTracers.Count >= maxConcurrentTracers) return;

            Vector3 delta = end - origin;
            float dist = delta.magnitude;
            // Clip to water plane impact if ray ended far above sea (avoid horizon lasers).
            if (!willHit && end.y > 0.5f && dir.y < -0.001f)
            {
                float tWater = (0f - origin.y) / dir.y;
                if (tWater > 2f && tWater < maxTracerVisualLength)
                {
                    end = origin + dir * tWater;
                    dist = tWater;
                }
            }
            if (dist > maxTracerVisualLength)
            {
                end = origin + delta.normalized * maxTracerVisualLength;
                dist = maxTracerVisualLength;
            }
            if (dist < 2f) dist = 2f;

            var go = new GameObject("ShellTracer");
            go.transform.SetParent(transform, false);
            var lr = go.AddComponent<LineRenderer>();
            lr.widthMultiplier = tracerWidth;
            lr.numCapVertices = 2;
            lr.numCornerVertices = 2;
            lr.positionCount = 8;
            lr.material = LineMat();
            lr.startColor = tracerColor;
            lr.endColor = willHit
                ? new Color(1f, 0.4f, 0.12f, 0.7f)
                : new Color(1f, 0.9f, 0.55f, 0.15f);
            lr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            lr.receiveShadows = false;
            lr.textureMode = LineTextureMode.Stretch;

            float arc = Mathf.Clamp(dist * 0.008f, 0.4f, 8f);
            for (int i = 0; i < lr.positionCount; i++)
            {
                float t = i / (float)(lr.positionCount - 1);
                Vector3 p = Vector3.Lerp(origin, end, t);
                p.y += arc * 4f * t * (1f - t);
                lr.SetPosition(i, p);
            }

            PlayMuzzle(origin, dir);
            PlayClip(fireClip);

            var mover = go.AddComponent<ShipVfxTimedDespawn>();
            mover.life = tracerTime;
            _liveTracers.Add(mover);
        }

        public void PlayMuzzle(Vector3 origin, Vector3 dir)
        {
            if (dir.sqrMagnitude < 1e-6f) dir = Vector3.forward;
            dir.Normalize();
            var go = new GameObject("MuzzleFlash");
            go.transform.SetParent(transform, false);
            go.transform.position = origin + dir * 0.5f;
            go.transform.rotation = Quaternion.LookRotation(dir);
            var ps = go.AddComponent<ParticleSystem>();
            var main = ps.main;
            main.startLifetime = muzzleLife;
            main.startSpeed = 1.5f;
            main.startSize = new ParticleSystem.MinMaxCurve(muzzleScale * 0.3f, muzzleScale);
            main.startColor = new Color(1f, 0.75f, 0.3f, 0.25f);
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.loop = false;
            var emission = ps.emission;
            emission.rateOverTime = 0f;
            emission.SetBursts(new[] { new ParticleSystem.Burst(0f, 3) });
            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Sphere;
            shape.radius = 0.05f;
            AssignDefaultParticleMat(ps, new Color(1f, 0.7f, 0.25f, 0.2f));
            go.AddComponent<ShipVfxTimedDespawn>().life = muzzleLife + 0.03f;
        }

        public void PlaySplash(Vector3 point)
        {
            var go = new GameObject("ShellSplash");
            go.transform.SetParent(transform, false);
            point.y = Mathf.Max(0f, point.y);
            go.transform.position = point;
            var ps = go.AddComponent<ParticleSystem>();
            var main = ps.main;
            main.startLifetime = splashLife;
            main.startSpeed = new ParticleSystem.MinMaxCurve(2.5f, 6f);
            main.startSize = new ParticleSystem.MinMaxCurve(0.35f, 0.9f);
            main.startColor = new Color(0.8f, 0.9f, 1f, 0.4f);
            main.gravityModifier = 0.8f;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.loop = false;
            var emission = ps.emission;
            emission.rateOverTime = 0f;
            emission.SetBursts(new[] { new ParticleSystem.Burst(0f, 12) });
            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Cone;
            shape.angle = 8f;
            shape.radius = 0.35f;
            go.transform.rotation = Quaternion.Euler(-90f, 0f, 0f);
            AssignDefaultParticleMat(ps, new Color(0.85f, 0.92f, 1f, 0.35f));
            go.AddComponent<ShipVfxTimedDespawn>().life = splashLife + 0.08f;
            PlayClip(splashClip);
        }

        public void PlayImpact(Vector3 point, ShipPenOutcome outcome)
        {
            Color core;
            float scale, life;
            switch (outcome)
            {
                case ShipPenOutcome.Penetrated:
                    core = new Color(1f, 0.45f, 0.1f, 0.65f);
                    scale = 0.65f;
                    life = impactLife;
                    break;
                case ShipPenOutcome.Partial:
                    core = new Color(1f, 0.7f, 0.3f, 0.5f);
                    scale = 0.4f;
                    life = impactLife * 0.8f;
                    break;
                case ShipPenOutcome.NoPenetration:
                    core = new Color(0.95f, 0.92f, 0.8f, 0.4f);
                    scale = 0.28f;
                    life = impactLife * 0.55f;
                    break;
                default:
                    PlaySplash(point);
                    return;
            }

            var go = new GameObject("ShellImpact");
            go.transform.SetParent(transform, false);
            go.transform.position = point;
            var ps = go.AddComponent<ParticleSystem>();
            var main = ps.main;
            main.startLifetime = life;
            main.startSpeed = new ParticleSystem.MinMaxCurve(1.5f * scale, 5f * scale);
            main.startSize = new ParticleSystem.MinMaxCurve(0.3f * scale, 0.9f * scale);
            main.startColor = core;
            main.gravityModifier = 0.15f;
            main.loop = false;
            var emission = ps.emission;
            emission.rateOverTime = 0f;
            emission.SetBursts(new[] { new ParticleSystem.Burst(0f, Mathf.Max(6, Mathf.RoundToInt(10 * scale))) });
            AssignDefaultParticleMat(ps, core);
            go.AddComponent<ShipVfxTimedDespawn>().life = life * 1.4f;
            PlayClip(hitClip);

            foreach (var c in Physics.OverlapSphere(point, 6f))
            {
                var rr = c.GetComponentInParent<Renderer>();
                if (rr == null) continue;
                var flash = rr.gameObject.GetComponent<ShipVfxRendererFlash>();
                if (flash == null) flash = rr.gameObject.AddComponent<ShipVfxRendererFlash>();
                flash.Flash(outcome == ShipPenOutcome.Penetrated ? 0.7f : 0.35f);
                break;
            }
        }

        static void AssignDefaultParticleMat(ParticleSystem ps, Color color)
        {
            var r = ps.GetComponent<ParticleSystemRenderer>();
            if (r == null) return;
            var sh = Shader.Find("Universal Render Pipeline/Unlit") ?? Shader.Find("Sprites/Default");
            var mat = new Material(sh);
            mat.SetColor("_BaseColor", color);
            mat.SetColor("_Color", color);
            r.sharedMaterial = mat;
            r.renderMode = ParticleSystemRenderMode.Billboard;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            r.receiveShadows = false;
        }
    }

    public sealed class ShipVfxTimedDespawn : MonoBehaviour
    {
        public float life = 1f;
        float _t;
        void Update()
        {
            _t += Time.deltaTime;
            if (_t >= life) Destroy(gameObject);
        }
    }

    public sealed class ShipVfxRendererFlash : MonoBehaviour
    {
        Renderer[] _renderers;
        Color[] _base;
        float _t;
        float _dur;

        void Awake()
        {
            _renderers = GetComponentsInChildren<Renderer>();
            _base = new Color[_renderers.Length];
            for (int i = 0; i < _renderers.Length; i++)
            {
                var mats = _renderers[i].sharedMaterials;
                _base[i] = Color.white;
                if (mats != null && mats.Length > 0 && mats[0] != null)
                {
                    var m = mats[0];
                    if (m.HasProperty("_BaseColor")) _base[i] = m.GetColor("_BaseColor");
                    else _base[i] = m.color;
                }
            }
        }

        public void Flash(float duration)
        {
            _dur = Mathf.Max(0.25f, duration);
            _t = 0f;
        }

        void Update()
        {
            if (_dur <= 0f || _renderers == null) return;
            _t += Time.deltaTime;
            float k = _t >= _dur ? 1f : Mathf.Lerp(0.55f, 1f, _t / _dur);
            for (int i = 0; i < _renderers.Length; i++)
            {
                if (_renderers[i] == null) continue;
                var mats = _renderers[i].materials;
                if (mats == null) continue;
                foreach (var m in mats)
                {
                    if (m == null) continue;
                    var c = _base[i] * k;
                    if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", c);
                    m.color = c;
                }
            }
            if (_t >= _dur) _dur = 0f;
        }
    }
}
