# Interaction sound · 2026-10-08 discussion

Status: on 2026-10-09 the user approved applying the current audition sounds. The public site and workspace now share those five files, with Passage revision 02 A as the transition. Local preview only; no staging, commit, push or production deployment. The discussion and audition sections below record the earlier design process. See [integration and acceptance](interaction-sound-integration-2026-10-09.md).

## Agreed direction

The user selected a mix: **instrument-like touch for operations; soft glass for transitions and completion**. Both belong to one quiet family: restrained volume, damped attacks, short tails, no sustained ambience. The original preview/ruler oscillators have now been replaced by the approved Touch and quieter Detent recordings.

## Proposed interaction map

These are proposed starting points for listening, not final acoustic specifications.

| Interaction | Voice and timing |
| --- | --- |
| Main navigation, Plimsoll, View Project preview | One soft instrument touch as the blue reveal begins; roughly 60–100 ms. The red dot adds no separate sound. Leaving is silent. |
| Circular page transition, entering/leaving the tool | A soft glass expansion or contraction, roughly 180–280 ms, aligned with the visual movement. A preview followed by a click does not add another touch. |
| Drawing selection, chapter selection, discrete option change | A short detent sound. Re-selecting the same value is silent; programmatic changes are silent. |
| Inspect, theme, disclosure and enabled-state toggles | Related opening/closing touches, differentiated by pitch or tail. Reset has a slightly lower settling sound. |
| Save, create, copy, export | A small acceptance touch where useful, followed by a brief glass completion only on a confirmed outcome. Browser downloads cannot be claimed complete merely because they were initiated. |
| Start/cancel calculation | A clear, restrained command touch; completion follows the real terminal result. No looping timer or progress ticking. Partial results must not use the complete-success sound. |
| Failure, conflict, rejected explicit action | A low, damped double pulse, once for that action. Initial offline loading and repeated background polling do not repeatedly alert. |
| Reading ruler | Keep one faint settled-section tick. Rapid travel through several sections only announces the final landing. A clicked jump and its arrival must not both sound. |
| Sound control, replay and external links | Enabling sound can demonstrate the chosen touch. Muting stops immediately. Explicit replay gets one start cue; automatic opening stays silent. External-link feedback is optional and never implies the destination loaded. |
| Typing, pointer/lens movement, dragging, continuous scroll, formula animation | Silent. A discrete commit or reset can sound, but motion itself does not continuously emit audio. |

## Shared rules

- A real user gesture unlocks sound. No autoplay or automatic attempts to defeat browser restrictions.
- One persisted mute preference applies across the public site and workspace. Audio failure cannot block interaction.
- Treat a gesture and its resulting navigation as one interaction. Prefer result/exception cues over previews and ruler ticks; do not let the existing single global throttle swallow an important result.
- Quick reversals retire the old transition tail. Leave, cancellation, hidden pages and unmount clean up scheduled nodes.
- Actual save/copy success, a returned result and a finished download are different events; attach cues to the strongest outcome the interface can observe.
- Sound supplements the visible state and text. It is never the only success, warning or error signal.

## Proposed next round

1. Prepare a small listening comparison: instrument touch, detent, glass transition, glass completion, and low failure cue. Compare at a common perceived volume before changing the live UI.
2. After listening approval, introduce the shared audio lifecycle and integrate one public flow: title preview → navigation → page arrival. Check sound/visual alignment and rapid reversals.
3. Apply the accepted family to workspace commands and confirmed outcomes, then test long editing sessions, mute persistence, hidden-page behavior and repeated failures as a single feature group.

## Local audition 01

The first listening prototype lives outside the product checkout at
`C:/Users/杨睿/Documents/Codex/2026-10-05/y-s-formfield-plimsoll-ui-c/outputs/sound-study-2026-10-08/`.
Serve that directory on loopback port 5174; `README.md` includes the command.

- Five original mono 48 kHz WAVs: Touch (80 ms), Detent (112 ms), Passage / transition (280 ms), Resolve / completion (240 ms), Hold / failure (232 ms).
- Independent play controls, volume, mute, stop / Escape, spaced comparison, a preview → transition → result sequence, and six repeated touches to judge fatigue.
- A deterministic standard-library Python renderer, the waveform/level manifest and PCM signal checks accompany the files.
- Files have silent endpoints and headroom. Technical measurements do not substitute for user listening approval, which remains the prerequisite for site integration.

At this prototype stage, the portfolio and workspace audio services were unchanged.

## Passage revision 02

The user rejected Passage because it sounded too tonal, like an electronic notification.
The standalone audition now replaces its oscillators and pitch glides with two
unpitched, fixed-band filtered-noise candidates: A (soft sweep, 180 ms) and B
(short dry pass, 140 ms). The page has individual A/B and sequential comparison
controls. The example flow and five-sound comparison use A. At revision time neither candidate
had listening approval. The later 2026-10-09 instruction approved integration of the current audition; its default A is now used in the product. Touch, Detent, Resolve and Hold are byte-identical
to the first audition. B remains an audition alternative; the retired pitched Passage is not used.
