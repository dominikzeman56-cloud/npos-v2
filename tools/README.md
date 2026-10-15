# Nástroje

| Nástroj | Stav | Účel |
|---|---|---|
| `analyze_track.py` | hotovo | analýza plného mixu (ffmpeg → numpy/scipy) → návrh `analysis.json` podle `core/track-analysis.schema.json` |
| `check_repo.py` | hotovo | kontrola kontraktu `knowledge/` (frontmatter), odkazů na zdroje, `sources.jsonl` proti schématu, `data/tracks/*/meta.json` |
| `vault-app/` | hotovo | read-only prohlížeč vaultu a statický export pro sdílení (jen `Hudební produkce`, za heslem); viz README uvnitř |
| `rebuild_track_index.py` | plánováno | `data/tracks` + `data/presets` → `data/corpus/*.jsonl` |
| `query_tracks.py` | plánováno | dotazy nad korpusem |
| `analyze_preset.py` | plánováno | pomoc při zápisu `data/presets/*.json` |

Pravidla: BLUEPRINT kap. 9 (blocklist). `analyze_track.py` měří **plný mix** — basová modulace z něj je nejvýš `hypothesis`.
