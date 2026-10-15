# Presety

Jeden soubor na analyzovaný preset podle `core/preset-analysis.schema.json`. Strategie (proč je postaven tak), ne výpis parametrů. Každý preset odkazuje na `source_id` v `knowledge/sources.jsonl`.

**Postup:** `python tools/analyze_preset.py PRESET.SerumPreset --source-id <id> --out data/presets/<nazev>.json` přečte soubor (`basis: preset_file`, `reading`). Pole `archetype`, `function`, `lessons` a vysvětlení „proč“ doplňuje člověk; do té doby je záznam *draft* s `archetype: unclassified`.

**Celé packy:** `py -3.12 tools/index_presets.py SLOŽKA --source-id <id> --out data/presets/index/<id>.jsonl --dump-dir data/presets/_local/<pack>` vyrobí kompaktní index (metadata + přečtené stopy + návrh funkce/archetypu, vždy `hypothesis`) do repa a plné analýzy do `_local/`, který je v `.gitignore`. Index kontroluje `tools/check_repo.py`.

**Pozor:** chybějící parametr v souboru = výchozí hodnota; hodnoty jsou normalizované a jednotky nejsou ověřené proti Serum UI. Soubory presetů z cizích packů se do repa nekopírují.

**Sdílení staveb (rozhodnutí 2026-10-15):** `tools/vault-app` exportuje podrobnou stavbu presetů (`data/builds/*.json`) jen s přepínačem `node export-static.mjs --builds`. Uživatel to na sdíleném neuro-vaultu zapnul (heslo, 2 lidé, použití jako učebnice). Pozor: jde o presety z placených/členských packů (`redistribution: none` v `sources.jsonl`); bez `--builds` zůstává stavba jen lokální. Plné dumpy v `_local/` se nikdy necommitují.

**Oscilátory v Serum 2:** tři wavetable oscilátory A–C (moduly `Oscillator0–2`) plus **Noise** (`NoiseOsc3`) a **Sub** (`SubOsc4`); názvy modulů jsou přímo v `.SerumPreset`. V indexu je `cues.active_osc` počet zapnutých wavetable oscilátorů a `cues.noise` / `cues.sub` říkají, zda běží Noise a Sub. Slot 0 je ve výchozím stavu zapnutý, ostatní vypnuté (v souboru je jen odchylka).
