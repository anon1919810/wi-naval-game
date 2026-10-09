# Interaction sound integration · 2026-10-09

> 2026-10-09 续记：用户已授权本轮提交并推送到 `feature/plimsoll-1.0`。下文“未提交/仅本地”记录原验收时状态；本次推送不包含生产部署。

The user approved applying the current audition. Codex integrated and reviewed this round directly, following the earlier authorised takeover. Local preview only; no staging, commit, push or production deployment. Existing Credits and font/global style work is preserved.

## Sound family

Five byte-identical audition assets in `web/frontend/public/audio/`: Touch 80 ms, Detent 112 ms, Passage A 180 ms, Resolve 240 ms, Hold 232 ms. Passage A uses fixed-band filtered noise without an identifiable pitched oscillator or glide. B remains an audition alternative. The original renderer is reproducible in `tools/render_formfield_sounds.py`; file hashes and provenance are in the asset README.

Default gain is 0.5, matching the listening page. Reading uses 0.32 of this gain.

## Actual event map

| Event | Cue / owner |
| --- | --- |
| Work / About / Credits or Plimsoll / View Project preview | Touch, once per audible preview; selected words and leave stay quiet |
| Accepted public/workspace navigation | Passage A from the transition's single committed update; navigation controls add no extra click Touch |
| Reference sheet, theme, chapter, stage, disclosure, checkbox/radio/select, reset | Detent; same selected chapter/reference stays quiet; continuous input remains quiet |
| Save / create / sign-in / copy | Command Touch where applicable; Resolve only after the actual response or clipboard write succeeds |
| Calculation queued or canceled | Command feedback; terminal result is observed separately |
| Observed terminal calculation result | Resolve only for completed run plus completed saved result; partial/canceled use Detent; failed uses Hold |
| Save conflict, rejected JSON/copy, failed explicit request | Hold after failure, protected by the page's existing lifetime/request guards |
| Existing terminal result first opened, initial load failure, polling errors | Silent; visible status and recovery remain authoritative |
| Settled reading section | Faint Detent; the reading controller prevents jump/arrival duplication |
| Replay, external link, download, print | Initiation Touch only; no claim that a download, print or destination finished |
| Typing, scroll motion, drawing/lens drag, formula animation | Silent |

The shared player lazily opens AudioContext only from a real gesture. Warm fetching creates no context. Cold previews never queue; cold commands expire after 180 ms. A bounded fresh-run marker covers a newly queued run that finishes before its first read, then is consumed. Stale/unmounted response guards precede outcome feedback. A terminal transition announces once per observation; revisiting a saved terminal result is silent.

One persisted mute preference (`formfield-preview-sound`) is used by the public and workspace speaker icons. Results outrank transitions/commands, which outrank preview/ruler feedback. Replacements fade the old source for 12 ms; mute/visibility changes cancel pending sounds. Disposal closes the context and disconnects current/retiring sources. Audio or storage failure cannot block the interface.

## Independent validation

- Full frontend suite: 30 files, 531/531 passed with `--maxWorkers=2`. After adding clipboard completion/lifetime coverage, the affected audio/run/public-content cluster passed 4 files, 70/70. No skipped tests. The final pre-push run passed all 30 files, 534/534, with the same concurrency limit.
- Final TypeScript/Vite build passed (100 modules), and `git diff --check` passed after the final edits.
- WAV format, silent endpoints, no clipping and DC checks passed. All five SHA-256 hashes match the audition. The renderer reproduced the exact deployed files.
- Real browser: all five WAVs HTTP 200; zero AudioContexts before a gesture; unmute creates one source; a project-row navigation creates one source; chapter selection creates one source; same-chapter reselection creates zero. Muted public-to-workspace navigation creates zero sources. Mute survives reload, and both speaker controls show the same state.
- 1024 px desktop header and document fit without horizontal overflow. Existing project opened read-only; no project revision was changed.
- Browser node/resource inspection verifies integration and playback scheduling, not an independent subjective listening assessment. Actual save/copy/calculation outcomes are covered with controlled API/clipboard tests; no new production operation or local worker calculation was run for acceptance.

Local preview: http://127.0.0.1:5173/#/work. Existing API/database are reused; no reset or migration. Calculations still require the separate worker described in the local operations guide.
