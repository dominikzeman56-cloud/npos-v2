# Preset Analysis Method

**Knowledge source type:** `personal_observation` — methodology notes, no presets actually analyzed yet under this framework (0/30 toward the BLUEPRINT §8 Definition of Done target).

## Principle

Presets are starting points — extract the production *pattern* (why it's built that way), not just parameter values. The full output schema is already locked in `docs/BLUEPRINT.md` §4.3 (Preset Analysis Summary) — don't re-derive a separate template here.

## Method (per preset)

1. Load in the source synth, document by category: oscillator strategy, filter strategy, modulation, FX chain, macro design.
2. Categorize by BLUEPRINT layer function enum (`sub|body|movement|noise|lead|pad|fx|other`), not a free-text label.
3. Extract one production principle: what does this preset demonstrate that's reusable, not what its literal parameter values are.
4. Tag confidence (`measured` only applies to parameter values actually read off the synth UI; anything about *why* it was designed that way is `estimated`/`hypothesis` unless it's from a producer's own explanation).

## Known preset locations (Serum)

- Serum 2: `D:\VST\Xfer\Serum 2 Presets\Presets`
- Serum 1: `D:\VST\Xfer\Serum Presets\Presets`

## Neurofunk preset category taxonomy (candidate archetypes)

Useful starting vocabulary for `knowledge/archetypes/` once patterns actually repeat in analyzed data (BLUEPRINT §3 rule: extend only when repeated, not speculatively):

- **Bass:** reese foundation (detuned unison), growl (filter LFO), mid-bass texturer (FM), sub layer (sine, pitch-locked)
- **Lead:** acid-style (envelope mod), supersaw (stack + widen), digital (wavetable), formant (vocal-like)
- **FX:** riser (pitch envelope), downlifter (reverse), atmospheric pad (reese-derived), impact (transient-heavy)

None of these are promoted to the locked archetype seed list yet — they're candidates to watch for once `tools/analyze_preset.py` exists and real presets are run through it.

---
*Converted and consolidated from `Presets/Preset-Analysis-Framework.md`, `Presets/Serum-Analysis-Framework.md`, and `Presets/Preset-Analysis-Template.md`, 2026-08-02. The three source files were largely duplicate/empty templates (0 presets actually analyzed) — kept only the non-redundant methodology and the category taxonomy.*
