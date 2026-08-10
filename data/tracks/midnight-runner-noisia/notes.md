# Midnight Runner — Noisia — Notes

**Not an `analysis.json`.** These are ear-based listening notes from before npos-v2's measurement tooling existed — no ffmpeg/RMS/FFT was run. Treat everything below as `hypothesis` until `tools/analyze_track.py` actually measures this track; do not feed these numbers into `tracks.jsonl` as `measured`.

## Structure (by ear)

Intro 16 bars → Build 16 → Drop A 32 → Breakdown 16 → Drop B 32 → Outro 8.

## Bass (by ear)

4–5 layers: sub, body (heavy FM), modulation, noise/texture. Sub described as staying "pure" and locked to kick pitch relationship — i.e. sub and kick fundamental chosen to not clash. Movement via LFO-filter with envelope shaping.

## Drums (by ear)

Punchy, compressed kick; heavily layered snare with reverb; hi-hats programmed with variation, tight timing, minimal swing.

## Stereo / dynamics (by ear)

Kick/snare/bass centered, atmosphere wide, mid-side processing for space. Heavy compression throughout but dynamic range reportedly preserved at drop hits.

## Production decisions (as originally guessed, unverified)

- Sub pitch locked relative to kick
- FM bass for harmonic character, not layering complexity
- Heavy compression across the bass bus for glue/impact
- Industrial FX (white noise risers, impact hits) for signature character

## Recreate workflow (as originally guessed, unverified)

1. Design a pure sub layer locked to the kick
2. Add an FM bass layer with modulation
3. Layer additional modulation on top
4. Add a noise/texture layer
5. Compress all bass elements together as one bus
6. Process drums for punch
7. Build the arrangement around the bass-drum relationship

## Lessons (as originally guessed, unverified)

- Sub clarity prioritized over layer complexity
- Bass processed as one glued unit, not independent layers
- Industrial FX add character without adding clutter
- Bus compression is what creates cohesion across bass layers

---
*Converted from `Case-Studies/Midnight-Runner-Noisia.md`, 2026-08-02. Original file self-tagged several claims "Measured"/"High confidence" — that predates any actual signal analysis, so every claim here is downgraded to `hypothesis` per BLUEPRINT §5 confidence rules. Re-run through `analyze_track.py` once it exists.*
