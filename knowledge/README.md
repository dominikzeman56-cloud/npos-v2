# Znalostní vrstva (`knowledge/`)

Strojově čitelný kánon NPOS (vrstva 2). Lidská podoba žije ve vaultu `Hudební produkce` (kap. 00–08); soubory tady se z ní **generují** (`python tools/sync_knowledge.py`, vault z env `NPOS_VAULT`) a ručně se needitují. Tok a podmínky povýšení: `docs/KNOWLEDGE_PIPELINE.md`.

## Pravidlo pravdivosti

Žádný track, producent, kurz ani číslo bez ověřeného zdroje. Každý soubor odkazuje na záznamy v [`sources.jsonl`](sources.jsonl) (schéma `core/source.schema.json`). Neověřené se nepíše; `hypothesis` je štítek pro *výklad*, ne pro *existenci zdroje*. Kontrola: `python tools/check_repo.py`.

## Obsah

| Adresář / soubor | Co |
|---|---|
| `sources.jsonl` | registr ověřených zdrojů (jeden JSON na řádek) |
| `principles/` | principy P1–P9, šest metod z vrstvy 1, kandidáti |
| `archetypes/` | archetypy basy s receptem, zdrojem a jistotou |
| `producers/` | filozofie producentů (jen se zdrojem) |
| `guides/` | návody vytěžené z rozborů (zatím aranž) |

## Kontrakt frontmatteru

Každý `.md` soubor v `knowledge/` začíná YAML blokem:

| Pole | Povinné | Hodnoty |
|---|---|---|
| `id` | ano | unikátní řetězec |
| `type` | ano | `principle` · `method` · `candidate` · `archetype` · `producer` · `guide` · `index` |
| `title` | ano | text |
| `status` | ano | `canon` · `candidate` · `conditional` · `deprecated` |
| `confidence` | ano | `measured` · `estimated` · `hypothesis` |
| `source_type` | ano | `producer_course` · `ableton_project` · `preset_pack` · `interview` · `track_analysis` · `personal_observation` · `other` |
| `source_ids` | ano (seznam; prázdný jen u `personal_observation`/`other`) | id ze `sources.jsonl` |
| `rule_label` | ne | `consensus` · `conditional` · `school` · `dogma_unverified` |
| `vault_note` | ne | nota ve vaultu, ze které soubor vznikl |
| `updated` | ano | datum `YYYY-MM-DD` |

`status: canon` nesmí mít prázdné `source_ids`. Degradované pravidlo se nemaže: dostane `status: deprecated` a odkaz na důkaz.

## Poznámka k hodnotám jistoty

Mimo frontmatter se v próze používají české štítky `[naměřeno]` / `[odhad]` / `[hypotéza]` (= `measured` / `estimated` / `hypothesis`) a rule labels `[K]` konsenzus, `[P]` podmíněné, `[Š]` škola, `[D]` dogma k ověření.
