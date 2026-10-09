# Formfield interaction sounds

Approved for local product integration by the user on 2026-10-09. Original, deterministic synthesis with Python's standard library; no external samples or runtime dependencies. Render with `python tools/render_formfield_sounds.py` from the repository root.

These are byte-identical to the accepted local audition in `outputs/sound-study-2026-10-08/audio`. Touch / Detent / Resolve / Hold keep the first audition's synthesis; Passage uses revision 02 candidate A (fixed-band filtered noise, no pitched oscillator or glide). Candidate B is not deployed.

Default playback gain is 0.5, matching the audition player. Reading ticks use 0.32 of that gain. Mono 48 kHz, 16-bit PCM; silent endpoints and no clipping. Auditory approval and signal checks are separate.

| Cue | File | Length |
| --- | --- | --- |
| Touch | touch.wav | 80 ms |
| Detent | detent.wav | 112 ms |
| Passage A | passage-a-02.wav | 180 ms |
| Resolve | complete.wav | 240 ms |
| Hold | failure.wav | 232 ms |

Verified SHA-256:

```text
touch.wav: 80 ms, SHA256 a7b06e8180a65e55c045ac629c8af864fbd1a57dd7730ba6ba43b7f625a27ac2
detent.wav: 112 ms, SHA256 b2f9cd2ff2bec3c5189d93881accfafe188b450bbf3b5bdfab21d5ed8e61cb32
passage-a-02.wav: 180 ms, SHA256 8c910168c53181a51513a0a4e0726fc6b36e855bd00520e3df5d7a51a2b83583
complete.wav: 240 ms, SHA256 a2d38cf688c3e8f53b4f43fd6baa6daf31c702af041c7b9aa7649aa906234cbd
failure.wav: 232 ms, SHA256 61734830cb921f790bb889bad4110d1b157e4498787214008d2b3a21dab78493
```
