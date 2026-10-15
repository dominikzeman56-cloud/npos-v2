---
id: preset-analysis-method
type: method
title: Metoda analýzy presetů
status: conditional
confidence: estimated
source_type: personal_observation
source_ids: []
vault_note: 10 Principy
updated: 2026-10-15
---

# Metoda analýzy presetů

*Zdroj v repu:* `preset-analysis-method.md` · `personal_observation` · `odhad` (0/30 presetů analyzováno *ve schématu*).
**Princip:** preset je výchozí bod; hledá se **vzor výroby** (proč je postaven tak), ne hodnoty parametrů. Schéma výstupu je v BLUEPRINTu §4.3.
**Postup:** (1) načíst ve zdroji, zdokumentovat po kategoriích: oscilátory, filtr, modulace, FX řetěz, makra · (2) zařadit podle výčtu `sub|body|movement|noise|lead|pad|fx|other` · (3) vytáhnout *jeden znovupoužitelný princip* · (4) jistota: `measured` jen pro hodnoty přečtené z UI synthu, „proč" je `estimated`/`hypothesis`, pokud nepochází z autorova vysvětlení.
**Stav dat:** ~15 presetů je zdokumentováno **v próze** (build sheety: Abis, Burr Oak, Ekwols ×3, Magnetude, Mefjus ×2, Pythius RE52REVIVE02 / Current Wompbassaarp3, Phenom roar, Skullstep, Prolix MID REESE, Operator FM, PitchBend, Stab) — úkol je převod do schématu (20 Basa, kap. 3. Archetypy basů, 70 Data a měření).
**Kategorie kandidátů archetypů (nepovyšovat, dokud se neopakují v datech):** bass — reese foundation, growl (filter LFO), mid-bass texturer (FM), sub vrstva; lead — acid, supersaw, digital, formant; FX — riser, downlifter, atmosférický pad, impact.
**Umístění presetů Serum:** cesty a oprava rozbitých odkazů na wavetables viz `07 Nástroje`.

> Strojově čitelná kopie z vaultu (`Hudební produkce`). Zdroje: `knowledge/sources.jsonl`. Neupravuj ručně — změny se dělají ve vaultu a regenerují.
