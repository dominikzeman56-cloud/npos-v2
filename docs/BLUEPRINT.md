# NPOS — Master Blueprint & Holy Grail

Single source of truth. The definitive document for the Neurofunk Production System.

## 1. Repo Structure (Strict & Enforced)

```
npos-v2/
├── docs/
│   ├── BLUEPRINT.md              ← This file
│   ├── VISION.md
│   ├── AGENT_RULES.md
│   └── PHASE_0_KNOWLEDGE_SYNC.md
├── core/
│   ├── ableton/                  ← ONE live template only
│   ├── build-sheet.schema.json
│   └── session.schema.json
├── knowledge/
│   ├── principles/                ← reese-vs-growl, fm-body, layers…
│   ├── archetypes/                ← controlled vocabulary
│   └── producers/                 ← philosophy only, no bios
├── data/
│   ├── tracks/
│   │   ├── meta.json
│   │   ├── analysis.json
│   │   └── notes.md               ← optional free text
│   ├── presets/
│   ├── sessions/
│   └── corpus/
│       ├── tracks.jsonl           ← THE HOLY GRAIL
│       └── presets.jsonl
├── tools/
│   ├── analyze_preset.py
│   ├── analyze_track.py
│   ├── rebuild_track_index.py
│   └── query_tracks.py
└── pyproject.toml
```

**Blocklist (Absolute Zero Tolerance):** web UI, Streamlit hub, auth, synth engine, second frontend, stems pipeline, new top-level folders without approval.

## 2. Principles (Non-Negotiable)

1. **Decision system, not documentation dump.**
2. **Sound design = mixing from the first moment.**
3. **Stay in MIDI as long as possible.**
4. **One layer = one function:** sub | body | movement | noise | stereo | air | texture | fx.
5. **Producers = philosophies, not copies.**
6. **Every claim tagged:** `measured` | `estimated` | `hypothesis`.
7. **Full-mix analysis only (no stems).**
8. **MIDI intent > note transcription** from masters.

## 3. Controlled Vocabularies

*These enums are locked. Do not extend without Architect approval.*

**Bass type:** `growl` | `reese` | `hybrid` | `sub_led` | `other`
**Bass energy profile:** `sub_dominant` | `fundament_dominant` | `balanced`
**Modulation grid:** `1/4` | `1/8` | `1/16` | `1/32` | `off_grid` | `unknown`
**Loudness strategy:** `crushed` | `controlled` | `open` *(guide: crest ~4 dB / 5–6 dB / >6 dB)*
**Layer function:** `sub` | `body` | `movement` | `noise` | `lead` | `pad` | `fx` | `other`
**Lead playing style:** `held_pad` | `short_stabs` | `riff` | `call_and_response` | `sparse_ornament` | `continuous_line` | `unknown`
**Lead roles (multi):** `hook` | `answer` | `riser` | `atmosphere` | `stab` | `counter_melody` | `none`
**Buildup type:** `held_drone_plus_harmonics` | `pitch_riser_gesture` | `filter_only` | `other`
**Breakdown type:** `atmosphere_no_bass` | `gated_sub_stutter` | `glitch_texture` | `other`
**Body design primary:** `fm` | `wavetable` | `detune_reese` | `filter_growl` | `sample` | `hybrid` | `other`
**Knowledge source type:** `producer_course` | `ableton_project` | `preset_pack` | `interview` | `personal_observation` | `other`

**Archetypes (Seed — extend only when repeated in data):**
`grid-locked-filter-growl` | `slow-grid-growl` | `detuned-unison-reese` | `fm-distorted-body` | `clean-sub-sine` | `serum-overlay-chords`

## 4. Schemas

### 4.1 Build Sheet (`core/build-sheet.schema.json`)

*Required: id, title, created, bpm, key, reference, goal*

```json
{
  "id": "string",
  "title": "string",
  "created": "YYYY-MM-DD",
  "status": "idea|groove|drop|arrange|mix|master|done",
  "bpm": 0,
  "key": "string",
  "reference": { "track": "", "artist": "", "why": "" },
  "bass": {
    "archetype": "",
    "layers": ["sub", "body", "movement", "noise"]
  },
  "drums": { "kick_style": "", "snare_style": "" },
  "lead": { "playing_style": "", "roles": [] },
  "goal": "",
  "problem": "",
  "unique_idea": "",
  "notes": ""
}
```

### 4.2 Track Analysis (`data/tracks/<id>/analysis.json`)

```json
{
  "id": "",
  "mode": "quick|deep",
  "analyzed": "YYYY-MM-DD",
  "method": {
    "tooling": "ffmpeg -> numpy/scipy (RMS, STFT, band energy, crest, mid/side, envelope FFT, YIN optional)",
    "stems": false,
    "notes": "Full-mix only. Energy/spectral = high confidence. Pitch in dense polyphony = low."
  },
  "confidence_overall": "measured|estimated|mixed|hypothesis",

  "structure": {
    "sections": [{ "name": "", "start_sec": 0, "end_sec": 0 }],
    "notes": "",
    "confidence": "estimated"
  },

  "dynamics": {
    "crest_factor_drop_db": null,
    "loudness_strategy": "crushed|controlled|open",
    "notes": "",
    "confidence": "measured"
  },

  "bass": {
    "type": "growl|reese|hybrid|sub_led|other",
    "type_confidence": "measured|estimated|hypothesis",
    "archetype": "",
    "layers": ["sub", "body", "movement", "noise"],
    "energy": {
      "sub_rel_db": null,
      "fundament_rel_db": null,
      "profile": "sub_dominant|fundament_dominant|balanced",
      "notes": ""
    },
    "modulation": {
      "primary_hz": null,
      "grid_match": "1/8|1/16|off_grid|unknown",
      "secondary_hz": [],
      "detection": "bandpass 60-300 -> Hilbert envelope -> FFT"
    },
    "timbre": { "spectral_centroid_hz": null, "notes": "" },
    "stereo": { "sub_side_db": null, "fundament_side_db": null, "notes": "" },
    "reese_vs_growl_test": {
      "envelope_vs_grid": "",
      "hi_res_fft_350_900": "",
      "conclusion": ""
    },
    "body_design": {
      "primary": "fm|wavetable|detune_reese|filter_growl|hybrid|other",
      "post": [],
      "confidence": "estimated"
    },
    "confidence": "measured"
  },

  "lead": {
    "present": true,
    "roles": [],
    "register": "mid_high|high|mid",
    "playing_style": "call_and_response|sparse_ornament|riff|held_pad|continuous_line|unknown",
    "density": "sparse|medium|busy",
    "melodic_motion": "static|small_intervals|leaps|chromatic_run|unknown",
    "rhythm_vs_drums": "answers_space|locks_with|fills_holes|competes|unknown",
    "rhythm_vs_bass": "fills_holes|answers_space|competes|unknown",
    "call_and_response": {
      "active": true,
      "call": "bass|stab|drums|fx|other",
      "response": "lead_phrase|overlay_chords|other",
      "period_bars": 2,
      "overlap": false,
      "notes": ""
    },
    "timbre_family": "fm_metallic|saw_lead|pluck|other",
    "confidence": "estimated"
  },

  "midi_intent": {
    "bass": {
      "playing_style": "held_root|simple_riff|sparse_hits|moving_line|unknown",
      "rhythm": "continuous_with_sidechain|gated|offbeat_bursts|unknown",
      "note_area": "",
      "grid_lock": "1/16_mod|1/8_mod|off_grid_detune|none",
      "silence_on_kick": true
    },
    "lead": {
      "playing_style": "call_and_response",
      "phrase_length_beats": 2,
      "enters_on": "after_call|offbeat",
      "avoids": ["kick", "snare_downbeat"],
      "register": "above_body"
    },
    "buildup": { "type": "held_drone_plus_harmonics|pitch_riser_gesture|other" },
    "breakdown": { "type": "gated_sub_stutter|atmosphere_no_bass|other", "bass_present": true },
    "confidence": "estimated"
  },

  "drums": { "kick": "", "snare": "", "groove": "", "notes": "", "confidence": "hypothesis" },

  "stereo_global": {
    "low_mono_below_hz": 250,
    "rule": "mono low-end, open higher",
    "confidence": "measured"
  },

  "production_decisions": [],
  "recreate_workflow": [],
  "lessons": [],
  "related_archetypes": [],
  "usable_for": [],
  "fields_confidence": {
    "structure": "estimated",
    "dynamics": "measured",
    "bass": "measured",
    "lead": "estimated",
    "drums": "hypothesis"
  }
}
```

### 4.3 Preset Analysis (Summary)

*Required: id, name, source, archetype, function (layer function enum)*
*Fields: oscillator_strategy, routing, filter_strategy, distortion_strategy, modulation, fx_chain, macros, mix_role, lessons, confidence, tags*

### 4.4 Session Log (`data/sessions/`)

```json
{
  "date": "YYYY-MM-DD",
  "track_id": "",
  "goal": "",
  "done": [],
  "blocked": "",
  "learned": "",
  "next": ""
}
```

## 5. Measurement Methods (Full Mix)

**Reliable (prefer `measured`)**
- RMS energy curve / section times (approx)
- Crest factor in drop window
- Band energy: sub 20–60 vs fundament 60–250
- Mid/side ratio per band
- Spectral centroid
- Bass envelope modulation rate (60–300 Hz -> Hilbert -> FFT) vs tempo grid

**Weak (max `estimated` / `hypothesis`)**
- Note-by-note pitch of leads in dense mix
- Exact FM ratio/index from master
- Drum sample identity

**Reese vs Growl Test (Mandatory for Deep Analysis)**
1. Envelope FFT on bass band, stable drop hold.
2. Peaks lock to 1/8 or 1/16 at track BPM -> **growl** / LFO path.
3. Off-grid, BPM-independent rates -> detune beating -> **reese**.
4. Hi-res FFT 350–900 Hz on held note:
   - Clean harmonic spikes -> few oscillators + mod.
   - Dense peak forest (~2–10 Hz spacing) -> **reese**.

*Stems are disabled. MIDI intent comes from roles, gaps, and design path.*

## 6. Agent System & Skill Rules

See [`docs/AGENT_RULES.md`](./AGENT_RULES.md).

## 7. The "Skateboard" Implementation Order (v1)

Do not skip ahead. Prove the value at each step.

1. **The Skeleton:** Repo structure + `BLUEPRINT.md` + `VISION.md` + `AGENT_RULES.md` + Schemas. (1 day)
2. **The First Decision:** Open Ableton. Start a track. Write a `build-sheet.json` by hand. (1 session)
3. **The First Analysis:** Write `analyze_track.py` (CLI fill) + 1 gold track analysis (e.g., Prolix). (2 days)
4. **The Holy Grail:** Write `rebuild_track_index.py` -> generates `data/corpus/tracks.jsonl`. Write `query_tracks.py`. (2 days)
5. **Daily Dogfooding:** Session log + build sheet on ALL real work. Expand knowledge files (`principles/`, `archetypes/`) only when actually stuck.
6. **The Vault:** ~30 presets + ~20 tracks with type/crest/grid analyzed. (Ongoing)

## 8. Definition of Done (v1)

- [ ] One Ableton template in daily use (physically enforcing layer rules).
- [ ] Build sheet on every new track.
- [ ] ≥20 track analyses (mix of quick/deep) with `bass.type` + confidence.
- [ ] ≥30 preset analyses with function + archetype.
- [ ] `tracks.jsonl` queryable by type / `usable_for` / C&R.
- [ ] Zero UI components, zero dual frontends, zero stems pipelines, zero scope creep.
