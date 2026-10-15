---
id: reese-detuning-and-body-design
type: method
title: "Reese a growl: detuning a návrh těla"
status: canon
confidence: measured
source_type: producer_course
source_ids: [abis-reese-fm-masterclass, pythius-reese-tutorial, phenom-roar]
vault_note: 01 Principy
updated: 2026-10-15
---

# Reese a growl: detuning a návrh těla

*Zdroj v repu:* `reese-detuning-and-body-design.md` · typ `producer_course` (Abis, DnB Academy) · `naměřeno` (demonstrováno živě); zobecnění „vždy EQ po distorzi" je `odhad`.
**Princip:** pohyb reese vzniká **fázovými vztahy mezi detunovanými oscilátory**, ne z LFO nebo filtru samotného. Dvě stejné saw, random phase 0, **jemně** (ne po půltónech) rozladěné proti sobě dávají klasický „beating" reese díky průběžné fázové kancelaci — stejná fyzika jako reese × growl test v BLUEPRINTu §5.
**Rozhodnutí:**
- **Saw reese:** 2× saw, phase 0 (konzistentní, opakovatelný start), fine-tune detune; řetěz distorze (amp sim) → filtrování (BP/LP) → **vždy zkontrolovat stereo nastavení cabinetu** (může basu nepředvídatelně zúžit či rozšířit).
- **Wavetable/harmonická metoda:** biny Serum = násobky fundamentu, ne půltóny (bin 3 ≠ bin 2 + oktáva); tón z reference rozložit analyzátorem: dominantní bin → jeden fundamentální osc + jeden naladěný na ten bin.
- **Pořadí distorze rozhoduje víc než volba distorze:** EQ-boost fundamentu *před* distorzí mění, na co distorze reaguje (fundament dominuje a může zabít sub) → **EQ po distorzi**; doplněk z Pythiuse: EQ před distorzí volí, které harmonické sežere drive — obojí, záměrně.
- **Sub vrstvený pod fázově detunovanou reese může zploštit její pohyb** (sub nesdílí beating, „ukotví" ji): sub oktávu níž od *stabilního* zdroje a **po přidání subu znovu zkontrolovat kompozitní pohyb**.
- **Automace levelu fundamentu pod těžkou distorzí** dělá vyvíjející se texturu (distorze „kompenzuje"); LFO na této automaci = rytmická verze.
- **Sample → wavetable:** import audia (Pitch Track), `Remove Multi-Section`, automatizovat WT pozici (LFO ~2 bary), sine sub o oktávu níž (samplové wavetables často nemají low end).
- **Stereo kontrola každé basové vrstvy:** v Mid-Side utilitě sólovat mono (sub) složku — zda se nehádá široká horní vrstva s mono low endem.
- **„Dvě basové linky bez soudržnosti"** je skutečné selhání: spojit shodným zpracováním a šířkou (sdílený chorus na groupě; Abis).
**Selhání:** boostnutý fundament mizí po distorzi (chyba pořadí EQ), reese po přidání subu plochá, dvě basy v jedné sekci nesouvisí, samplové wavetables bez low endu.
**Doplnění z konsolidace:** tři mechanismy pohybu (detune / detune + moderní post / LFO bez detune a FM; Pythius Reese); `RE52REVIVE02` (WT z detunované saw s note-triggered LFO); roar = pitch obálka nahoru-dolů 3 st (Phenom) — archetypy v 03 Zvuk a mix kap. 3.

> Strojově čitelná kopie z vaultu (`Hudební produkce`). Zdroje: `knowledge/sources.jsonl`. Neupravuj ručně — změny se dělají ve vaultu a regenerují.
