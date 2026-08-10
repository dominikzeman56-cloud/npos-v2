# Stink — Mefjus — Notes

**Not an `analysis.json`.** These are ear-based listening notes from before npos-v2's measurement tooling existed — no ffmpeg/RMS/FFT was run. Treat everything below as `hypothesis` until `tools/analyze_track.py` actually measures this track; do not feed these numbers into `tracks.jsonl` as `measured`.

## Structure (by ear)

Intro 8 bars → Build 8 → Drop A 24 → Breakdown 8 → Drop B 24 → Outro 4.

## Bass (by ear)

3–4 layers: sub (sine), body (saw/FM), texture (processed noise). Resonant filter sweeps for movement; wobble-type modulation, but controlled rather than extreme.

## Drums (by ear)

Punchy but not aggressive kick; tight, layered snare; complex hi-hat patterns with percussion accents.

## Stereo / dynamics (by ear)

Bass mostly mono, FX/pads wide, good reported mono compatibility. Controlled compression; breakdown intentionally has less compression and more space than the drops.

## Production decisions (as originally guessed, unverified)

- Clean sub layer, more heavily processed body layer
- Filter movement treated as the primary source of interest, not the layer count
- Drum programming preferred over drum sampling
- Warmth achieved via saturation, not by softening/rolling off highs

## Recreate workflow (as originally guessed, unverified)

1. Design a clean sub sine layer
2. Build a body layer with FM/modulation
3. Add a processed-noise texture layer
4. Route all bass to one bus, compress together
5. Design drums prioritizing punch
6. Add filter automation for movement
7. Keep FX minimal and deliberate

## Lessons (as originally guessed, unverified)

- A clean sub is what allows the body layer to be processed heavily without losing low-end clarity
- Filter movement alone can create interest without adding more layers
- Programmed drums can read as more impactful than sampled ones
- Warmth comes from saturation, not from removing top end

## Related

- `knowledge/producers/mefjus.md` — this track is one of Mefjus's listed reference tracks; the "clean sub + processed body + filter movement" pattern here matches that profile's stated philosophy directly.

---
*Converted from `Case-Studies/Stink-Mefjus.md`, 2026-08-02. Original file self-tagged several claims "Measured"/"High confidence" — that predates any actual signal analysis, so every claim here is downgraded to `hypothesis` per BLUEPRINT §5 confidence rules. Re-run through `analyze_track.py` once it exists.*
