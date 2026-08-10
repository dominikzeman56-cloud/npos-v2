# Quick Decision Heuristics

**Knowledge source type:** `personal_observation` — accumulated rules of thumb, not from a single cited source. This is the actionable core of what the old system's "Decision Tree" / "Checklists" pages tried to be — the `npos-session` agent skill (see `docs/AGENT_RULES.md`) is the intended replacement for the old dashboard UI version of this; this file is its reference material, not a UI.

## Principle

When stuck, subtract before adding. Most "sounds generic"/"everything competing" problems are fixed by removing or re-balancing an existing element, not layering in something new.

## Situation → next action

| Situation | Next action |
|---|---|
| Kick masking bass | Sidechain bass to kick, 2–4 dB, or pitch-lock the two |
| Kick masking pads/synths | Sidechain to kick, 1–3 dB |
| Muddy mix (150–400 Hz) | High-pass non-bass elements; cut 200–400 Hz on the bass/kick specifically, not globally |
| Weak/thin bass | Check sub level and mono-compatibility first, before adding layers |
| Sounds generic | Add a noise/texture layer — but only after confirming sub+body are solid, not as a first fix |
| Energy dropping mid-track | Add a riser/transitional FX, or re-check the arrangement's section contrast |
| Mix not translating on other systems | Check mono compatibility before re-EQing |
| Loop feels stale | Change hi-hat rhythm before touching anything else — cheapest variation lever |
| Everything competing | Subtract an element; don't add a fix on top |
| Need to decide "render or stay in MIDI" | Render only for CPU relief, external processing, or delivery — otherwise stay in MIDI as long as possible (BLUEPRINT principle 3) |

## Bass archetype → layer recipe (candidate, cross-check against `knowledge/principles/reese-detuning-and-body-design.md`)

- **Reese/deep:** sub + body (filtered saw)
- **Mid-bass/hyper:** body + noise + movement
- **FM/metallic:** FM oscillator + distortion + texture
- **Wobble/growl:** movement (LFO-filter) + distortion

## Compression by goal (starting points, not rules)

- Control peaks: ratio 4:1+, fast attack, fast release
- Add punch: ratio 4–6:1, attack 1–10ms, release 50–100ms
- Glue the mix: ratio 2:1, attack ~10ms, release 100–200ms
- Add character: parallel compression, ratio varies

## Confidence

`estimated` throughout — these are accumulated rules of thumb from production practice, not measured from specific track analysis. Treat as a starting heuristic to test against a reference, not a fixed rule.

---
*Converted and consolidated from `Framework/Decision-Tree.md` and `Workflows/Decision-Trees.md`, 2026-08-02. `Framework/Checklists.md`, `Framework/Workflow-Map.md`, `Workflows/Daily-Workflow.md`, and `Workflows/Session-Workflow.md` were skipped — they describe session-ritual/pomodoro-style workflow (already covered by the separate `Ableton_Production_System.md` plan, section 6) and generic empty checklists, not production decision content. `Framework/Reference-Analysis-Framework.md` was skipped as an empty template redundant with the Case-Studies template already handled.*
