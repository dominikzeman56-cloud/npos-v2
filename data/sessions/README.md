# Sessions

Logy produkčních session podle `core/session.schema.json`, jeden soubor na session (`<datum>-<track_id>.json`). Záměrně prázdné, dokud nevznikne skutečná práce: nic se sem nepíše „na zkoušku“.

Jak se sem session dostanou:

1. Na Dashboardu (`/dashboard.html`) přidej session tlačítkem **+ nová** (cíl, hotovo, co blokuje, co ses naučil, další krok).
2. Tlačítkem **export** stáhni `sessions.json`.
3. `py -3.12 tools/import_sessions.py ~/Downloads/sessions.json` je zvaliduje a zapíše sem (nic nepřepisuje, `--dry-run` jen ukáže cíle).
