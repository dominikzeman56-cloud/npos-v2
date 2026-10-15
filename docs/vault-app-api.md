# vault-app: API a provoz

Čtecí prohlížeč vaultu a stránek NPOS (`tools/vault-app`). Dva režimy: **živý** (`node server.mjs`, indexuje vault v paměti a obsluhuje JSON API) a **statický export** (`node export-static.mjs`, výstup `site/`, nasazuje se na Vercel za Basic Auth). Server je **jen pro čtení**, nic nezapisuje do vaultu ani do repa.

## Spuštění

| Příkaz | Co dělá |
|---|---|
| `npm start` (ve `tools/vault-app`) | živý server na `http://localhost:4747` |
| `npm test` | testy serveru a knihoven (`node --test`, bez sítě a bez skutečného vaultu) |
| `node export-static.mjs` | export do `site/` (poznámky, indexy; bez plných staveb presetů) |
| `node export-static.mjs --builds` | totéž + `data/builds/<id>.json` (stavby presetů z placených packů, jen se souhlasem majitele) |

Proměnné prostředí: `VAULT_PATH` (cesta ke vaultu, výchozí `D:\ObsidianVault`), `PORT` (výchozí 4747), `VAULT_IGNORE` (složky vynechané z indexu, oddělené čárkou; výchozí viz `lib/vault-index.mjs`). Heslo sdíleného webu je `VAULT_PASSWORD` na Vercelu (bez něj web odmítá vše, fail-closed).

## Endpointy živého serveru

Všechny vracejí JSON s `Cache-Control: no-store`, pokud není uvedeno jinak.

| Metoda a cesta | Parametry | Odpověď |
|---|---|---|
| `GET /api/index` | | seznam poznámek (cesta, název, tagy) a souborů |
| `GET /api/note` | `path` (relativní cesta, např. `20 Basa.md`) | poznámka: tělo, frontmatter, osnova, odkazy, zpětné odkazy. `404 {"error":"not found"}`, pokud neexistuje |
| `GET /api/search` | `q` (text; `tag:nazev` filtruje podle tagu) | `{ total, terms, results: [{ path, snippet, … }] }` |
| `GET /api/tags` | | `[{ tag, count }]` |
| `GET /api/graph` | | `{ nodes: [{ id, name, group, deg }], links: [[zdroj, cíl]] }` |
| `GET /api/next-step` | | strom „Co dál?“ (`knowledge/guides/next-step.json`): `phases`, `items` |
| `GET /api/presets` | | kompaktní index presetů (`data/presets/index/*.jsonl`) s metadaty packů |
| `GET /api/preset` | `id` (`^[a-z0-9][a-z0-9-]*$`) | stavba presetu z lokálního dumpu; `404`, pokud id neexistuje nebo má neplatný tvar |
| `GET /asset` | `path` (relativní k vaultu) | obrázek, PDF a podobné soubory z vaultu; `403` mimo vault a pro složky z `VAULT_IGNORE` |
| `GET /vendor/markdown-it.min.js`, `/vendor/d3.min.js` | | knihovny z `node_modules` |
| `GET /…` | | statické soubory z `public/`; `/` je `index.html`; `403` při pokusu vyjít z `public/` |

Index se přestaví automaticky po změně souboru ve vaultu (sledování souborového systému s krátkým zpožděním).

## Statický export

`site/` obsahuje stránky, `data/vault.json` (index + poznámky + tagy + graf), `data/presets.json`, `data/next-step.json` a volitelně `data/builds/`. Z exportu se odstraňují lokální cesty (`D:\…`, viz `lib/scrub-paths.mjs`). Složky `workshop videos` a `ai-memory-vault` se nevyvážejí, stejně tak poznámky s `share: false`.

Přístup na Vercelu hlídá `deploy/middleware.js` (Basic Auth proti `VAULT_PASSWORD`).

## Stránky

| Cesta | Obsah |
|---|---|
| `/` | Kánon (poznámky), levá lišta: Soubory, Hledat, Tagy |
| `/dashboard.html` | aktuální track, fáze, poznámky, priority, Co dál?, sessions (stav jen v `localStorage`) |
| `/presets.html` | prohlížeč a stavba presetů (parametry `?id=&q=&fn=&arch=`) |
| `/dal.html` | Co dál? (parametry `?p=fáze&s=situace&q=hledání`) |

Hluboký odkaz na nadpis v poznámce: `/#cesta.md::Text nadpisu` (text nadpisu se hledá přesně, zpětné apostrofy se odstraňují).

## Úložiště v prohlížeči (`localStorage`)

| Klíč | Obsah |
|---|---|
| `vault.skin` | `samurai`, `dark` nebo `light` |
| `vault.dash` | stav Dashboardu: `track`, `stage`, `notes`, `tasks`, `sessions`, `last`, `next` |
| `vault.scroll`, `vault.tabs`, `vault.leftMode`, `vault.noLeft` | stav Kánonu |

Sessions z Dashboardu se exportují tlačítkem **export** jako pole objektů podle `core/session.schema.json` a ukládají do repa příkazem `py -3.12 tools/import_sessions.py ~/Downloads/sessions.json` (jeden soubor na session v `data/sessions/`).

## Testy

- `server.test.mjs`: spustí server na náhodném portu proti dočasnému vaultu a ověří endpointy, `VAULT_IGNORE` a odmítnutí `..`.
- `lib/presets-data.test.mjs`: `buildView`, validace id, načtení indexu.
- `lib/scrub-paths.test.mjs`: odstraňování cest při exportu.

CI (`.github/workflows/ci.yml`) pouští `pytest tools`, `tools/check_repo.py` a `npm test`.
