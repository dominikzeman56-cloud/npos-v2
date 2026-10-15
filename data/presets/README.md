# Presety

Jeden soubor na analyzovaný preset podle `core/preset-analysis.schema.json`. Strategie (proč je postaven tak), ne výpis parametrů. Každý preset odkazuje na `source_id` v `knowledge/sources.jsonl`.

**Postup:** `python tools/analyze_preset.py PRESET.SerumPreset --source-id <id> --out data/presets/<nazev>.json` přečte soubor (`basis: preset_file`, `reading`). Pole `archetype`, `function`, `lessons` a vysvětlení „proč“ doplňuje člověk; do té doby je záznam *draft* s `archetype: unclassified`.

**Pozor:** chybějící parametr v souboru = výchozí hodnota; hodnoty jsou normalizované a jednotky nejsou ověřené proti Serum UI. Soubory presetů z cizích packů se do repa nekopírují.
