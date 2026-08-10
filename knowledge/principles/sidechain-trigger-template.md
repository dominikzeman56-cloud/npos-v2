# Sidechain Trigger Groups & Drum Arrangement Template

**Knowledge source type:** `producer_course` — Abis, DNB Academy (Drop 01/02), transcribed 2026-08-01.

## Principle

Physical template structure enforces mix decisions before they become mixing problems — matches BLUEPRINT's "physical enforcement" mandate directly. This is the strongest candidate source found so far for `core/ableton/`'s actual layer-rule enforcement (see task: inspect existing template).

## Decisions (actionable)

- **Silent MIDI trigger tracks instead of sidechain compressors.** Dedicated "Kick SC Trigger" / "Snare SC Trigger" tracks fire an LFO-based ducking tool on a target sidechain group, instead of routing a compressor's sidechain input directly. Reasoning given: a drawn LFO curve gives more control over the ducking shape than attack/release knobs on a compressor. `[measured]`
- **Trigger clip placement is the actual "mix" decision.** Where a MIDI trigger clip sits on the timeline determines what gets ducked and when — positioning the clips *is* the sidechain design, not an afterthought after the ducking tool is configured.
- **Bass sounds live in a dedicated sidechain-target group** by default, so any new bass patch is automatically ducked without per-patch setup.
- **Minimal master-bus engineering during the writing phase**: a Maximizer at default settings + a Utility pulling ~5 dB gain before the master, purely for headroom so nothing hits the limiter while ideas are still being tested. Detailed mix engineering is explicitly deferred to a later pass — "free palette" first. `[measured]`
- **Debug sidechain issues by checking the obvious first**: an entire "not working" sidechain turned out to be trigger clips simply not enabled — check trigger presence/routing before assuming a plugin or bus problem.
- **Known unresolved issue: sidechain/LFO-tool clicking.** Smoothing the ducking tool's function curve reduces but doesn't eliminate audible clicks — flagged as a recurring annoyance across sessions, not a solved problem. `[measured, explicitly unresolved]`

## Group structure observed

Kick SC Trigger, Snare SC Trigger (silent triggers) → feed LFO tool on a Bass/sidechain group. Kick group, Snare group, Hats group, all under a parent Drums group.

## Related

- `knowledge/principles/reese-detuning-and-body-design.md`
- Candidate reference for `core/ableton/` template build (Skateboard step 2) — see task to inspect `Templates/NPOS-Ableton-Template-Full/Project8_3/Session.als`

---
*Converted from `Producer-Knowledge/Abis-DNB-Academy-Drop-01.md` and the snare-design portion of `Abis-DNB-Academy-Drop-02.md`, 2026-08-02.*
