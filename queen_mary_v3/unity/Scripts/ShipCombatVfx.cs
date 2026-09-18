using System.Collections.Generic;
using UnityEngine;

namespace Naval
{
    /// <summary>
    /// T16 — Code-built combat VFX (muzzle, arc tracer, splash, impact).
    /// URP-friendly unlit/particle colors; no Asset Store dependency.
    /// Placeholder audio: clips optional; null = silent.
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
        public float tracerTime = 0.22f;
        public float tracerWidth = 0.12f;
        public float maxTracerVisualLength = 900f;
        public int maxConcurrentTracers = 4;
        public Color tracerColor = new Color(1f, 0.75f, 0.2f, 0.85f);

        [Header("Muzzle")]
        public float muzzleLife = 0.08f;
        public float muzzleScale = 0.35f;

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
        Material _glowMat;

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

        Material GlowMat(Color c)
        {
            // New instance per burst color family via shared two mats only — tint via LineRenderer colors.
            if (_glowMat == null)
            {
                var sh = Shader.Find("Universal Render Pipeline/Unlit") ?? Shader.Find("Sprites/Default");
                _glowMat = new Material(sh);
            }
            return _glowMat;
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

        /// <summary>Arc tracer from muzzle to impact/miss point (not a laser).</summary>
        public void PlayTracer(Vector3 origin, Vector3 end, Vector3 dir, bool willHit)
        {
            var go = new GameObject("ShellTracer");
            go.transform.SetParent(transform, false);
            var lr = go.AddComponent<LineRenderer>();
            lr.widthMultiplier = tracerWidth;
            lr.positionCount = 12;
            lr.material = LineMat();
            lr.startColor = tracerColor;
            lr.endColor = willHit
                ? new Color(1f, 0.45f, 0.15f, 0.9f)
                : new Color(0.95f, 0.85f, 0.4f, 0.35f);
            lr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            lr.receiveShadows = false;

            Vector3 flat = end - origin;
            float dist = Mathf.Max(1f, flat.magnitude);
            // Light ballistic arc (visual only).
            float arc = Mathf.Clamp(dist * 0.04f, 1.5f, 45f);
            Vector3 side = Vector3.Cross(Vector3.up, flat.sqrMagnitude > 1f ? flat.normalized : Vector3.forward);
            for (int i = 0; i < lr.positionCount; i++)
            {
                float t = i / (float)(lr.positionCount - 1);
                Vector3 p = Vector3.Lerp(origin, end, t);
                p.y += arc * 4f * t * (1f - t);
                p += side * (Mathf.Sin(t * Mathf.PI) * dist * 0.005f);
                lr.SetPosition(i, p);
            }

            PlayMuzzle(origin, dir);
            PlayClip(fireClip);

            var mover = go.AddComponent<ShipVfxTimedDespawn>();
            mover.life = tracerTime;
        }

        public void PlayMuzzle(Vector3 origin, Vector3 dir)
        {
            if (dir.sqrMagnitude < 1e-6f) dir = Vector3.forward;
            dir.Normalize();
            var go = new GameObject("MuzzleFlash");
            go.transform.SetParent(transform, false);
            go.transform.position = origin + dir * 2f;
            go.transform.rotation = Quaternion.LookRotation(dir);
            var ps = go.AddComponent<ParticleSystem>();
            var main = ps.main;
            main.startLifetime = muzzleLife;
            main.startSpeed = 12f;
            main.startSize = new ParticleSystem.MinMaxCurve(muzzleScale * 0.6f, muzzleScale);
            main.startColor = new Color(1f, 0.75f, 0.25f, 0.95f);
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.loop = false;
            var emission = ps.emission;
            emission.rateOverTime = 0f;
            emission.SetBursts(new[] { new ParticleSystem.Burst(0f, 18) });
            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Cone;
            shape.angle = 18f;
            shape.radius = 0.8f;
            var col = ps.colorOverLifetime;
            col.enabled = true;
            var grad = new Gradient();
            grad.SetKeys(
                new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(new Color(1f, 0.4f, 0.1f), 1f) },
                new[] { new GradientAlphaKey(0.95f, 0f), new GradientAlphaKey(0f, 1f) });
            col.color = grad;
            AssignDefaultParticleMat(ps, new Color(1f, 0.7f, 0.2f, 0.9f));
            var desp = go.AddComponent<ShipVfxTimedDespawn>();
            desp.life = muzzleLife + 0.15f;
        }

        public void PlaySplash(Vector3 point)
        {
            var go = new GameObject("ShellSplash");
            go.transform.SetParent(transform, false);
            go.transform.position = point;
            var ps = go.AddComponent<ParticleSystem>();
            var main = ps.main;
            main.startLifetime = splashLife;
            main.startSpeed = new ParticleSystem.MinMaxCurve(6f, 16f);
            main.startSize = new ParticleSystem.MinMaxCurve(1.2f, 3.5f);
            main.startColor = new Color(0.75f, 0.88f, 1f, 0.85f);
            main.gravityModifier = 1.2f;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.loop = false;
            var emission = ps.emission;
            emission.rateOverTime = 0f;
            emission.SetBursts(new[] { new ParticleSystem.Burst(0f, 40) });
            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Cone;
            shape.angle = 12f;
            shape.radius = 1.5f;
            go.transform.rotation = Quaternion.Euler(-90f, 0f, 0f);
            AssignDefaultParticleMat(ps, new Color(0.8f, 0.9f, 1f, 0.8f));
            go.AddComponent<ShipVfxTimedDespawn>().life = splashLife + 0.2f;
            PlayClip(splashClip);
        }

        public void PlayImpact(Vector3 point, ShipPenOutcome outcome)
        {
            Color core, smoke;
            float scale = 1f;
            float life = impactLife;
            switch (outcome)
            {
                case ShipPenOutcome.Penetrated:
                    core = new Color(1f, 0.55f, 0.15f, 1f);
                    smoke = new Color(0.25f, 0.22f, 0.2f, 0.7f);
                    scale = 1.6f;
                    life = impactLife * 1.4f;
                    break;
                case ShipPenOutcome.Partial:
                    core = new Color(1f, 0.75f, 0.35f, 1f);
                    smoke = new Color(0.4f, 0.38f, 0.35f, 0.55f);
                    scale = 1.1f;
                    break;
                case ShipPenOutcome.NoPenetration:
                    core = new Color(0.9f, 0.9f, 0.85f, 0.9f);
                    smoke = new Color(0.55f, 0.55f, 0.55f, 0.45f);
                    scale = 0.7f;
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
            main.startSpeed = new ParticleSystem.MinMaxCurve(4f * scale, 14f * scale);
            main.startSize = new ParticleSystem.MinMaxCurve(1.5f * scale, 4f * scale);
            main.startColor = core;
            main.gravityModifier = 0.4f;
            main.loop = false;
            var emission = ps.emission;
            emission.rateOverTime = 0f;
            emission.SetBursts(new[] { new ParticleSystem.Burst(0f, Mathf.RoundToInt(35 * scale)) });
            AssignDefaultParticleMat(ps, core);

            var smokeGo = new GameObject("ShellSmoke");
            smokeGo.transform.SetParent(go.transform, false);
            var sps = smokeGo.AddComponent<ParticleSystem>();
            var sm = sps.main;
            sm.startLifetime = life * 1.8f;
            sm.startSpeed = 2f * scale;
            sm.startSize = new ParticleSystem.MinMaxCurve(2f * scale, 6f * scale);
            sm.startColor = smoke;
            sm.loop = false;
            var se = sps.emission;
            se.rateOverTime = 0f;
            se.SetBursts(new[] { new ParticleSystem.Burst(0.05f, Mathf.RoundToInt(20 * scale)) });
            AssignDefaultParticleMat(sps, smoke);

            go.AddComponent<ShipVfxTimedDespawn>().life = life * 2f;
            PlayClip(hitClip);

            // L3: darken hit ship renderers briefly if we can find them.
            var cols = Physics.OverlapSphere(point, 12f);
            foreach (var c in cols)
            {
                var rr = c.GetComponentInParent<Renderer>();
                if (rr == null) continue;
                var flash = rr.gameObject.GetComponent<ShipVfxRendererFlash>();
                if (flash == null) flash = rr.gameObject.AddComponent<ShipVfxRendererFlash>();
                flash.Flash(outcome == ShipPenOutcome.Penetrated ? 1.4f : 0.7f);
                break;
            }
        }

        static void AssignDefaultParticleMat(ParticleSystem ps, Color color)
        {
            var r = ps.GetComponent<ParticleSystemRenderer>();
            if (r == null) return;
            var sh = Shader.Find("Universal Render Pipeline/Particles/Unlit")
                     ?? Shader.Find("Universal Render Pipeline/Unlit")
                     ?? Shader.Find("Sprites/Default");
            var mat = new Material(sh);
            mat.SetColor("_BaseColor", color);
            mat.SetColor("_Color", color);
            r.sharedMaterial = mat;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            r.receiveShadows = false;
        }
    }

    /// <summary>Despawn helper for one-shot VFX objects.</summary>
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

    /// <summary>Short renderer darkening on damage hit (readability, not material art).</summary>
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
                var m = _renderers[i].material;
                _base[i] = m != null && m.HasProperty("_BaseColor") ? m.GetColor("_BaseColor")
                    : (m != null ? m.color : Color.white);
            }
        }

        public void Flash(float duration)
        {
            _dur = Mathf.Max(0.3f, duration);
            _t = 0f;
            Apply(0.45f);
        }

        void Update()
        {
            if (_dur <= 0f) return;
            _t += Time.deltaTime;
            if (_t >= _dur)
            {
                Apply(1f);
                _dur = 0f;
                return;
            }
            float k = Mathf.Lerp(0.45f, 1f, _t / _dur);
            Apply(k);
        }

        void Apply(float scale)
        {
            if (_renderers == null) return;
            for (int i = 0; i < _renderers.Length; i++)
            {
                if (_renderers[i] == null) continue;
                var mats = _renderers[i].materials;
                foreach (var m in mats)
                {
                    if (m == null) continue;
                    var c = _base[i] * scale;
                    if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", c);
                    m.color = c;
                }
            }
        }
    }
}
