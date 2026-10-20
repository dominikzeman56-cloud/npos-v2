# Nástroje

| Nástroj | Stav | Účel |
|---|---|---|
| `analyze_track.py` | hotovo | analýza plného mixu (ffmpeg → numpy/scipy) → návrh `analysis.json` podle `core/track-analysis.schema.json` |
| `analyze_preset.py` | hotovo | čtečka Serum 2 `.SerumPreset` (oscilátory, filtry, FX, modulační matice) → návrh `data/presets/*.json` s `basis: preset_file`; vyžaduje `pip install cbor2 zstandard`; archetyp a funkci zadává člověk |
| `index_presets.py` | hotovo | celý pack `.SerumPreset` → kompaktní index `data/presets/index/<source_id>.jsonl` (stopy + návrh funkce/archetypu, vždy `hypothesis`); plné analýzy do `data/presets/_local/` (gitignored) |
| `analyze_fxp.py` | hotovo | Serum 1 `.fxp`: jen kontejner (hlavička, zlib stav, maka, počet `.wav`) + role z názvu → `data/presets/fxp/<source_id>.jsonl` (`hypothesis`) |
| `analyze_fxp_host.py` | hotovo | Serum 1 `.fxp` přes hostované Serum 1 VST3 (`pip install pedalboard`, jen lokálně): oscilátory, filtr, FX, amounty modulací → `fxp/` + `features/`; zdroj/cíl modulace, pořadí FX, mono a křivky LFO se nečtou |
| `check_repo.py` | hotovo | kontrola kontraktu `knowledge/` (frontmatter), odkazů na zdroje, `sources.jsonl` proti schématu (a `vault_note` proti vaultu, je-li dostupný), `knowledge/guides/next-step.json`, `data/tracks/*/meta.json` (a platný JSON v `analysis.json` / `build-sheet.json`), `data/presets/*.json` proti schématu, indexy presetů, platnost JSON schémat v `core/`; lokální cesty v `data/tracks` a `data/local-sources.json` jen jako upozornění |
| `render_preset.py` | hotovo | render presetu jednou notou (Serum 1 `.fxp`, Serum 2 `.SerumPreset`; jen lokálně, `pedalboard`) a deskriptory zvuku → `data/presets/audio*/` (čísla; wav jen v `_local`) |
| `preset_roles.py` | hotovo | role ze zvuku (kNN nad deskriptory, leave-one-out): rodina bass/tonal/perc/fx ano, podtypy basů ne → `data/presets/roles/` (`estimated`) |
| `preset_stats.py` | hotovo | medián a kvartily parametrů a zvuku po rolích a packách, kontrast rolí (Cliffovo delta); skupina s n < 10 jen počet → `data/presets/stats/` |
| `serum_preset_io.py` | hotovo | čtení a zápis `.SerumPreset` (XferJson + zstd + CBOR, přepočet md5 hashe); bez `neuroman/` |
| `preset_seed.py` | hotovo | startovní bod: reálný Serum 2 preset dané role + pár zmutovaných spojitých parametrů (rozsah p10–p90 z presetů role od 10 kusů, jinak z celého korpusu; bez celočíselných, křivek obálek, bez obrácení znaménka); výstup jen lokálně (`_local` nebo mimo repo), `derived_from`, `hypothesis`; `--check` vyrenderuje zdroj a mutant a zahodí nepovedené (potřebuje lokálně `pedalboard`, GPL-3.0) ; `--export-seeds` poskládá malou sadu semínek (20–30), místní stránka `/generator.html` ve vault-app |
| `als_stats.py` | hotovo | struktura Live setů (`.als`, jen čtení): počty tracků, skupin, returnů, Utility s ubraným gainem, HP na kicku, pluginy → `data/als/als-stats.json` (jen čísla, bez cest a názvů; vlastní tvorba zvlášť, skupina n < 10 jen počet); VST EQ nečte |
| `midi_stats.py` | hotovo | MIDI vzory z klipů v `.als` (jen reference) a z `.mid` packů: hustota, mřížka, kroky mezi tóny, pauzy → `data/midi/midi-stats.json` (jen čísla, bez cest a názvů packů; role z názvů = hypotéza; call/response se neměří; skupina n < 10 vzorů nebo < 3 zdroje jen počet) |
| `midi_project.py` | hotovo | rozbor MIDI jednoho `.als`: vzory po stopách v mřížce 1/16 a kde se v aranži použijí; `--bars 33-64` spojí klipy do aranžního času a vypíše mřížku po taktech, `--audio` přidá audio stopy (klip = úder na začátku), `--chops` vypíše audio stopy s mnoha krátkými klipy (nasekané samply a resamply) (jen čtení, výstup na obrazovku nebo JSON) |
| `midi_batch.py` | hotovo | dávka přes celou složku `.als`: nejčastější takt kicku, snaru a basy po projektech a jeho „podpis mezer“ → `data/midi/batch-*.json` (souhrn bez názvů), podrobnosti po projektech jen lokálně (`data/midi/_local`, gitignorováno); soubory nad `--max-mb` se přeskočí; role z názvů = hypotéza |
| `stem_grid.py` | hotovo | rytmus a stavba z odseparovaných stemů (Demucs, RipX, oficiální): kick, snare a basa po taktech na mřížce 1/16, energie stemů po taktech, přesné BPM a první doba z měření; jen čtení, výstup na obrazovku nebo lokální JSON (`data/stems/_local`, gitignorováno); hi-haty a klik kicku prosakují do pásem (`odhad`) |
| `rebuild_preset_indexes.py` | hotovo | hromadné přeindexování packů z `_sources/presets/<source_id>/`: index a feature vektory, porovnání s commitovanými soubory; s `--write` je přepíše (plné dumpy do `data/presets/_local/`) |
| `collect_local_sources.py` | hotovo | manifest `data/local-sources.json` (kde leží surové zdroje) a kopie malých zdrojů do `_sources/` (gitignorováno); cesty jsou v kódu (`D:\`) |
| `sync_knowledge.py` | hotovo | vygeneruje `knowledge/` (kromě `sources.jsonl`) z kánonu ve vaultu; vault z env `NPOS_VAULT` |
| `import_sessions.py` | hotovo | export sessions z Dashboardu (`sessions.json`) → `data/sessions/` podle `core/session.schema.json`, nic nepřepisuje |
| `midi_common.py` | hotovo | sdílené pomocné funkce pro `als_stats`, `midi_stats`, `midi_project`, `midi_batch`, `stem_grid` (kvartily, podpis mezer, noty klipu) |
| `check_presets.py` | hotovo | konzistence dat presetů (unikátní id, typy, sha256, bez lokálních cest); běží v CI |
| `vault-app/` | hotovo | read-only prohlížeč vaultu a statický export pro sdílení (jen `Hudební produkce`, za heslem); viz README uvnitř |
| `rebuild_track_index.py` | hotovo | `data/tracks/*/{meta,analysis}.json` → `data/corpus/tracks.jsonl` (ploché klíče pro dotazy; vlastní tvorba `own_work` se vynechá) |
| `query_tracks.py` | plánováno | dotazy nad korpusem |

Python 3.12 (CI; minimum podle `pyproject.toml` je 3.11). Závislosti pro testy jako v CI: `pip install pytest numpy scipy cbor2 zstandard soundfile` (extra `dev` v `pyproject.toml`; `pip install -e .[dev]` zatím nejde, repo nemá nastavené balíčky pro setuptools).

Pravidla: BLUEPRINT kap. 9 (blocklist). `analyze_track.py` měří **plný mix** — basová modulace z něj je nejvýš `hypothesis`.
