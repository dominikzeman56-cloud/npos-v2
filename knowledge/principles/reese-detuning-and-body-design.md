# Reese/Growl Detuning & Body Design

**Knowledge source type:** `producer_course` — Abis, DNB Academy (Bass Sound Design 01/02, Drop 02 re-engineering pass), transcribed 2026-08-01.

## Principle

Reese motion comes from phase relationships between detuned oscillators, not from an LFO or filter alone. Two identical saws with a random-phase-zero start, fine-tune detuned against each other (not semitone-detuned), produce the classic moving/beating reese texture through ongoing phase cancellation — the same physics as the general reese-vs-growl distinction in BLUEPRINT §5. `[measured, demonstrated live via phase-cancellation A/B]`

## Decisions (actionable)

- **Body design, saw-wave reese:** two saws, phase set to 0 (consistent, repeatable start — same habit used for kick/snare design), fine-tune detune between them for movement. Chain: distortion (amp sim) → filtering (band-pass/low-pass) → check stereo cabinet setting explicitly, since cabinet sims can accidentally narrow or widen a bass unpredictably. `[measured]`
- **Body design, wavetable/harmonic method:** Serum wavetable "bins" are integer multiples of the fundamental, not semitone steps — bin 3 lands on a different note than bin 2 because it's a harmonic, not an octave. To reverse-engineer a reference tone: find the dominant harmonic bin on a spectrum analyzer, rebuild with one fundamental oscillator + one oscillator tuned to just that bin. `[measured, demonstrated with frequency math]`
- **Distortion order matters more than distortion choice.** EQ-boosting the fundamental *before* distortion changes what the distortion stage reacts to (the boosted fundamental now dominates the signal), which can unexpectedly tame or kill the sub. Fix: EQ **after** distortion, not before. `[measured, diagnosed live as the actual cause of a "sounds terrible" bass]`
- **Sub-layering has to respect existing phase movement.** Adding a plain, non-detuned sine sub underneath an already phase-detuned reese can collapse the reese's LFO-like motion (the sub doesn't share the beating, so it "anchors" and flattens the perceived movement). Layer subs octave-down from a *stable* reference, and re-check the composite motion after adding the sub, not just before. `[measured]`
- **Automating the fundamental's level under heavy distortion creates evolving texture** — pushing louder makes the distortion stage "compensate" (saturate harder), shifting harmonic balance dynamically. Add an LFO to this level automation for a musical, rhythmic version of the effect. `[measured]`
- **Sample-to-wavetable technique:** Serum can import any audio sample into an oscillator and derive harmonic content automatically. Import as Pitch Track → use "Remove Multi-Section" to strip empty frames → automate wavetable position (e.g. via LFO at a 2-bar rate) to scrub through the sample for evolving texture. Layer with a plain sine sub an octave down, since sample-derived wavetables often lack low end. `[measured]`
- **Stereo imaging check on any bass layer:** solo the mono (sub) content via Mid-Side utility mode to confirm nothing conflicting is happening between a wide stereo top layer and the mono low end — do this whenever combining a stereo-widened body layer with a mono sub. `[measured]`
- **"Two basslines, no cohesion" is a real failure mode**, not just an aesthetic complaint — when two bass patches in the same section sound unrelated, glue them via matching processing and matching stereo width rather than picking one and discarding the other.

## Failure modes to catch

Boosted fundamental disappearing after distortion (EQ ordering bug), reese motion flattening after adding a sub, two bass layers in the same section feeling disconnected, sample-derived wavetable layers with no low-end weight.

## Confidence

`measured` for the distortion-order and phase/detuning claims (demonstrated live in the source); `estimated` for generalizing "always EQ after distortion" as a universal rule rather than a case-specific fix.

---
*Converted from `Producer-Knowledge/Abis-DNB-Academy-Bass-01.md`, `Abis-DNB-Academy-Bass-02.md`, and the bass re-engineering section of `Abis-DNB-Academy-Drop-02.md`, 2026-08-02.*
