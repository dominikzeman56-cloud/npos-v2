# Nástroje

| Nástroj | Stav | Účel |
|---|---|---|
| `analyze_track.py` | hotovo | analýza plného mixu (ffmpeg → numpy/scipy) → návrh `analysis.json` podle `core/track-analysis.schema.json` |
| `analyze_preset.py` | hotovo | čtečka Serum 2 `.SerumPreset` (oscilátory, filtry, FX, modulační matice) → návrh `data/presets/*.json` s `basis: preset_file`; vyžaduje `pip install cbor2 zstandard`; archetyp a funkci zadává člověk |
| `check_repo.py` | hotovo | kontrola kontraktu `knowledge/` (frontmatter), odkazů na zdroje, `sources.jsonl` proti schématu, `data/tracks/*/meta.json`, `data/presets/*.json` proti schématu |
| `vault-app/` | hotovo | read-only prohlížeč vaultu a statický export pro sdílení (jen `Hudební produkce`, za heslem); viz README uvnitř |
| `rebuild_track_index.py` | plánováno | `data/tracks` + `data/presets` → `data/corpus/*.jsonl` |
| `query_tracks.py` | plánováno | dotazy nad korpusem |

Pravidla: BLUEPRINT kap. 9 (blocklist). `analyze_track.py` měří **plný mix** — basová modulace z něj je nejvýš `hypothesis`.
