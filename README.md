# NPOS — Neurofunk Production System

Rozhodovací systém a datový stroj pro produkci neurofunku/DnB v Ableton Live. Není to encyklopedie, webová aplikace ani chatbot.

**Začni tady:**

- [`docs/VISION.md`](docs/VISION.md) — proč to existuje a co z toho plyne
- [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md) — struktura repa, principy, slovníky, měření, blocklist, pořadí práce
- [`docs/AGENT_RULES.md`](docs/AGENT_RULES.md) — pravidla pro AI agenty (včetně pravidla pravdivosti)
- [`docs/KNOWLEDGE_PIPELINE.md`](docs/KNOWLEDGE_PIPELINE.md) — jak se zdroj stane poznatkem v kánonu
- [`knowledge/README.md`](knowledge/README.md) — kontrakt znalostní vrstvy a registr zdrojů

**Kde co žije**

| Co | Kde |
|---|---|
| surové zdroje (videa, přepisy) | jen lokálně, nikdy v repu |
| destilace zdrojů a lidský kánon | vault `Hudební produkce` (Obsidian) |
| strojově čitelný kánon | `knowledge/` |
| schémata | `core/*.schema.json` |
| data | `data/` (tracky, presety, sessions, korpus) |
| nástroje | `tools/` (přehled se stavem v [`tools/README.md`](tools/README.md)) |

**Kontrola:** `python tools/check_repo.py` (Python 3.12 jako v CI, minimum 3.11; testy: `pip install pytest numpy scipy cbor2 zstandard soundfile` (= extra `dev` v `pyproject.toml`) a `python -m pytest tools -q`)

**Stav (2026-10-17):** kánon v češtině hotový, šablona Ableton mimo kánon, datová vrstva se teprve plní (BLUEPRINT kap. 10).
