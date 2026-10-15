---
id: sidechain-trigger-template
type: method
title: Sidechain trigger skupiny a šablona bicích
status: canon
confidence: measured
source_type: producer_course
source_ids: [abis-start-to-finish, joe-ford-bassgorilla-course, pythius-template-workflow]
vault_note: 01 Principy
updated: 2026-10-15
---

# Sidechain trigger skupiny a šablona bicích

*Zdroj v repu:* `sidechain-trigger-template.md` · `producer_course` (Abis, DnB Academy; Drop 01/02) · `naměřeno`.
**Princip:** **fyzická struktura šablony vynucuje rozhodnutí o mixu dřív, než se stanou problémem mixu** („physical enforcement", VISION).
**Rozhodnutí:**
- **Tiché MIDI spouštěče místo sidechain kompresorů:** `KICK SC TRIGGER`, `SNARE SC TRIGGER` spouštějí ducking (LFO tool / ShaperBox / Duck) na sidechain group; nakreslená křivka dává víc kontroly než attack/release kompresoru.
- **Umístění trigger klipů *je* návrh sidechainu**, ne dodatečná věc.
- **Basy žijí v cílové sidechain group** by default — každý nový patch je ducknutý bez nastavování.
- **Minimální master během psaní:** Maximizer ve výchozím stavu + Utility ~−5 dB jen pro headroom; detailní mix později („volná paleta"). *Pozor:* Audio/Redpill píší s limiterem od první vteřiny (02 Šablona 9.1).
- **Ladění:** nejčastější „nefunguje sidechain" = trigger klipy nejsou zapnuté/routované.
- **Nevyřešeno:** klikání LFO toolu — smoothing křivky ho snižuje, ne odstraňuje (ShaperBox `Smooth` ~28 %).
**Konsenzus tří zdrojů (Abis, Pythius, Ford): dva tiché MIDI spouštěče, ne jeden audio sidechain.** `naměřeno`. Struktura: Kick SC Trigger, Snare SC Trigger → LFO tool na Bass/sidechain group; Kick, Snare, Hats pod Drums group.

> Strojově čitelná kopie z vaultu (`Hudební produkce`). Zdroje: `knowledge/sources.jsonl`. Neupravuj ručně — změny se dělají ve vaultu a regenerují.
