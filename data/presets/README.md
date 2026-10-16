# Presety

Jeden soubor na analyzovaný preset podle `core/preset-analysis.schema.json`. Strategie (proč je postaven tak), ne výpis parametrů. Každý preset odkazuje na `source_id` v `knowledge/sources.jsonl`.

**Postup:** `python tools/analyze_preset.py PRESET.SerumPreset --source-id <id> --out data/presets/<nazev>.json` přečte soubor (`basis: preset_file`, `reading`). Pole `archetype`, `function`, `lessons` a vysvětlení „proč“ doplňuje člověk; do té doby je záznam *draft* s `archetype: unclassified`.

**Celé packy:** `py -3.12 tools/index_presets.py SLOŽKA --source-id <id> --out data/presets/index/<id>.jsonl --dump-dir data/presets/_local/<pack>` vyrobí kompaktní index (metadata + přečtené stopy + návrh funkce/archetypu, vždy `hypothesis`) do repa a plné analýzy do `_local/`, který je v `.gitignore`. Index kontroluje `tools/check_repo.py`.

**Pozor:** chybějící parametr v souboru = výchozí hodnota; hodnoty jsou normalizované a jednotky nejsou ověřené proti Serum UI. Soubory presetů z cizích packů se do repa nekopírují.

**Sdílení staveb (rozhodnutí 2026-10-15):** `tools/vault-app` exportuje podrobnou stavbu presetů (`data/builds/*.json`) jen s přepínačem `node export-static.mjs --builds`. Uživatel to na sdíleném neuro-vaultu zapnul (heslo, 2 lidé, použití jako učebnice). Pozor: jde o presety z placených/členských packů (`redistribution: none` v `sources.jsonl`); bez `--builds` zůstává stavba jen lokální. Plné dumpy v `_local/` se nikdy necommitují.

**Oscilátory v Serum 2:** tři wavetable oscilátory A–C (moduly `Oscillator0–2`) plus **Noise** (`NoiseOsc3`) a **Sub** (`SubOsc4`); názvy modulů jsou přímo v `.SerumPreset`. V indexu je `cues.active_osc` počet zapnutých wavetable oscilátorů a `cues.noise` / `cues.sub` říkají, zda běží Noise a Sub. Slot 0 je ve výchozím stavu zapnutý, ostatní vypnuté (v souboru je jen odchylka).

**Hromadně a feature vektory:** `py -3.12 tools/rebuild_preset_indexes.py` (bez `--write` jen porovná) přeindexuje všechny packy ze `_sources/presets/` (vzniká přes `tools/collect_local_sources.py`) a spočítá `data/presets/features/<source_id>.jsonl`: pro každý preset jen počty, příznaky a pár normalizovaných hodnot (osc, unison, warp, filtr, FX podle typu, počet modulací podle zdroje/cíle, LFO křivky, obálky), bez názvů wavetablů, přepisů modulací a hodnot parametrů. Vektory jsou vstup pro generátor presetů (M1), `confidence: hypothesis` jako návrhy funkce a archetypu. Plné analýzy placených packů zůstávají v `_local/` mimo git.

## Serum 1 `.fxp` (`data/presets/fxp/`)

Serum 2 načte `.fxp` ze Serum 1, ale `.fxp` je neveřejný binární stav. `tools/analyze_fxp.py` proto čte jen **kontejner** (VST2 hlavička, zlib-rozbalený stav, odkazy na `.wav`, jména maker) a navrhne `role` z názvu (`hypothesis`). Význam parametrů se tam **nečte**; čte ho `analyze_fxp_host.py` (níže). Plná analýza ve formátu Serum 2 (osc, warp, filtry, FX, modulace včetně zdrojů a cílů) zůstává cesta přes GUI: otevři `.fxp` v Serum 2, ulož jako `.SerumPreset` a pusť `index_presets.py` / `rebuild_preset_indexes.py`. Headless to nejde (Serum 2 `.fxp` importuje jen v GUI).

```
py -3.12 tools/analyze_fxp.py "…/S1 Presets/BO" --source-id s1-burr-oak --dedupe --out data/presets/fxp/s1-burr-oak.jsonl
```

`role` (bass, reese, neuro, sub, stab, lead, pluck, chords, pad, seq, synth, layer, guitar, perc, fx, other) je návrh z názvu u všech indexů. U presetů pojmenovaných jen „měsíc + číslo“ vyjde `other`.

### Serum 1 přes hostované Serum 1 VST3 (`tools/analyze_fxp_host.py`)

`.fxp` jde načíst do samotného Serum 1 (VST3, přes `pedalboard`, bez GUI; `pip install pedalboard`): stav z `.fxp` se vloží do VST3 state a skript čte ~350 hostovských parametrů tak, jak je Serum 1 zobrazuje, ~0,1 s na preset (všech 823 presetů TK, BO a Redpill ~3 min). Do indexu (`data/presets/fxp/<id>.jsonl`, `reader: serum1_host`, `cues_basis: preset_file`) a feature vektorů (`data/presets/features/<id>.jsonl`, `basis: preset_file`, `reader: serum1_host`) jdou jen odvozená čísla a příznaky stejného tvaru jako u Serum 2 (stejné klíče features, jen s `null` tam, kde to host nedá). Plné parametry (raw + text) a odkazy na wavetably (jména z placených packů) jsou jen v `data/presets/_local/<id>-host/` mimo git; v `container` zůstává jen `wav_count`.

Naměřeno hostem: oscilátory A/B (zapnuto, unison, detune z displeje, oktáva, Fine, hlasitost, typ warpu), Noise a Sub zapnuté, filtr (zapnut, cutoff normalizovaný 0–1, reso a drive v procentech 0–100 jako ve Serum 2), zapnuté FX (v `fx_chain` abecedně, pořadí v Serum 1 hostem nejde zjistit), počet obsazených slotů mod matice (amount ≠ 0). Cutoff a všechny sdílené feature (`osc_on` … `fx_*`, `mod_slots`) se shodují s převodem v Serum 2 (pár `TSP_REDPILL_Bass_lazer`, test `test_host_reads_bass_lazer_like_the_serum2_conversion`; reso a drive jsou v páru 0, jejich škála je odvozená ze Serum 2 vektorů, ne z páru).

**Nezjistitelné z hostu (`null`):** zdroj a cíl modulace (leží ve stavu, ne v hostovských parametrech; čeká na kalibraci z ≥ 10 převedených presetů), proto `mod_lfo`, `mod_env`, `mod_macro`, `mod_to_osc`, `mod_to_filter`, `cues.lfo_to_filter` a `cues.silent_mod_osc` jsou `null`; dále křivky LFO a obálek, `env_count`, `macro_count`, mono/legato, jména wavetablů a maker. Funkce, role a archetyp jsou návrh z jména a naměřených stop (`hypothesis`); archetyp se z hostu navrhuje jen tam, kde ho stopy dokládají (FM z jiného zapnutého zdroje, rozladěné Fine, čistý sub), jinak `unclassified`.

**Rozdíly proti řádkům Serum 2** (kvůli nimž se Serum 1 řádky nemají míchat bez kontroly `reader`): `cues.cross_warp` nese text menu Serum 1 („FM (from B)“) jen pro FM/AM/RM/PM z *zapnutého* zdroje; Serum 2 při převodu mění FM (from B) na `kPD_OSC`, takže archetyp z hostu u FM není vždy shodný s indexem převedeného souboru. `cues.warp_modes` a `cues.zero_vol_osc` jsou jen u Serum 1. `detune_max` je UniDet z displeje jen u oscilátorů s unison > 1 (Serum 2: uložený `kParamDetune` všech zapnutých). `filter_drive` je `0.0`, kde ho převedený `.SerumPreset` neuvádí (`null`). FM ze zdroje, který je vypnutý, se do `cross_warp` nepočítá (u 15 z ~580 presetů; jestli ho Serum 1 vypnutým zdrojem opravdu neovládá, nebylo ověřeno).

```
py -3.12 tools/analyze_fxp_host.py "…/S1 Presets/BO" --source-id s1-burr-oak --match-index data/presets/fxp/s1-burr-oak.jsonl --out-index data/presets/fxp/s1-burr-oak.jsonl --out-features data/presets/features/s1-burr-oak.jsonl --dump-dir data/presets/_local/s1-burr-oak-host
```

`--match-index` drží stejnou sadu souborů (podle sha256) a stejná id jako dosavadní index; kolidující id (stejné jméno ve stejné skupině, jiný obsah) dostanou příponu ze sha256 (u `s1-teddy-killerz` 15 dvojic, tedy 30 id). Zápis je atomický a menší výstup, než je `--match-index`, se nezapíše (`--allow-partial`). `analyze_fxp.py` (výše) zapisuje do stejných souborů jen kontejner: použij ho pro nový pack, na pack, který už má řádky z hostu, ne (přepsal by je a vrátil kolidující id). Bez pluginu se test hostu přeskočí.
