---
id: archetypes-bass
type: archetype
title: Archetypy basů
status: canon
confidence: measured
source_type: track_analysis
source_ids: [abis-reese-fm-masterclass, pythius-reese-tutorial, pythius-fearless-remix, phenom-roar, letsynthesize-noisia-course, magnetude-neuro-basses, burr-oak-harmonic-growl, ekwols-reese-layering, prolix-been-about-this, letsynthesize-preset-files, pythius-patreon-presets, enta-serum-presets, notequal-serum-presets]
vault_note: 03 Zvuk a mix
updated: 2026-10-15
---

# Archetypy basů

Seed (řádky 1–5) je v kontraktu BLUEPRINT kap. 5; řádky 6–16 jsou **kandidáti** — do slovníku se povyšují až po opakování v datech.

Mapování na BLUEPRINT slovníky: `bass.type` (`growl`/`reese`/`hybrid`/`sub_led`/`other`), `body_design.primary` (`fm`/`wavetable`/`detune_reese`/`filter_growl`/`sample`/`hybrid`/`other`), seed archetypů (`grid-locked-filter-growl`, `slow-grid-growl`, `detuned-unison-reese`, `fm-distorted-body`, `clean-sub-sine`, `serum-overlay-chords`). **Nové kandidáty přidat jen po opakování v datech.**

| # | Archetyp | Princip | Základní recept | Zdroj | CPU | Jistota |
|---|---|---|---|---|---|---|
| 1 | **`detuned-unison-reese`** (fázový) | cancellation dvou saw | 2× saw, unison 3–4V, detune ±15–25 ct (Phenom 0,17/0,15), **random phase 0**, fine tune +3–5 ct, osc 1 bez detune; filtr BP12/HP12 ~3× fundament, key tracking; mono + legato, glide 15–30 ms | Abis, Pythius, Prolix, Phenom | nízké | `naměřeno` |
| 2 | **`fm-distorted-body`** | FM matice + distorze | Operator: nosič modulovaný 3 oscilátory, **obálky na modulátorech** (FM hodně na začátku, málo na konci), Noise Loop, retrigger OFF; Hard filtr; OTT ×2 Time; Saturator Color ~125 Hz | LS 02, Abis (FM biny) | nízké | `naměřeno` |
| 3 | **`grid-locked-filter-growl`** | LFO/sekvence na filtru zamčená do mřížky | Magnetude Preset 1: Sub + OSC A saw + OSC B `Resi Mass 1` Asymmetric, **Phaser 48+ jen na OSC B**; Preset 2 FM Squelch: BP24, **LFO1 nakreslená 1-bar sekvence → cutoff + mix filtru**; Trash „Bad Breakup"; triple OTT (69 %, Time ~1000 %) | Magnetude | střední | `estimated` |
| 4 | **`slow-grid-growl`** | pomalý pohyb, growl z harmonického bohatství | single-fundament: 1 osc, 2-stage waveshaping, filtr 0,8–1,5 kHz, pomalé LFO/ENV na drive | Burr Oak | nízké | `naměřeno` (spektrum) |
| 5 | **`clean-sub-sine`** | čistý sub | viz 02 Šablona 6.1; Prolix/Don't Play/Breach měřeno | všichni | minimální | `naměřeno` |
| 6 | **multi-pitch reese** (kandidát) | více nezávislých vrstev po tónech | Magnetude základ + MIDI po čtvrťových (F#2 F2 E2 G#2 G2 A2), glide 15–30 ms, LFO v Trigger módu, větší OSC B detune | Ekwols | střední | `naměřeno` |
| 7 | **wavetable z detunované saw** (kandidát) | reese zapečený do tabulky | `RE52REVIVE02`: WT z detune saw, **LFO4 custom ramp note-triggered cykluje WT pozici**, X-Shaper, multiband comp; venku Pitch/True EQ „Octave UP" (zvedne 2. harm, uber 1.), +7,27 dB @ 64,7 Hz, N-Spec smash, MWaveShaperMB, Comb na group | Pythius Fearless | střední | `naměřeno` (GUI) |
| 8 | **LFO-reese bez detune a FM** (kandidát) | pohyb jen z LFO | Serum Plaits WT, LFO → bend minus, rate 0, **note follow ~93 %**, **ghost sine** jen na vysokých notách; Bass Duwer + Morph EQ + Ripple Phaser | Pythius Reese | střední | `naměřeno` |
| 9 | **roar** (kandidát) | pitch obálka | 2× saw, unison 4 width 0, phase ~60°/180°, Flg HL6+, Overdrive stack 3; **LFO2 envelope → Main Tuning, 1/4, nahoru-dolů, 3 st** | Phenom roar | nízké | `naměřeno` |
| 10 | **pitch-bend „wom-wom"** | pitch obálka + EQ peak | Serum, LFO1 → Master Tune, EQ peak modulovaný stejným LFO, LFO2 → LP (konec filtrovaný), sub přes filtr | LS 09 | střední | `naměřeno` |
| 11 | **stab accent** | perkusivní vrstva NA reese | viz 02 Šablona 6.3 (Amp 0/80–150/0/30, BP 2–4 kHz) | Ekwols, Prolix | nízké | `naměřeno` |
| 12 | **harmonická plocha** (`serum-overlay-chords`) | bounce akordu → granulární čtení | viz 02 Šablona 7.2 | Ekwols | nízké | `estimated` |
| 13 | **switch bass** | modulace okolo distorze | `Phaser → Overdrive → Flanger → EQ8 → MBD ×2`; sestupná pitch obálka; vstupní gain −5 až −10 dB | LS 11, projekty | nízké | `naměřeno` |
| 14 | **overlay reese přes akord** | tenze nad basou | chord patch → Comb → Trash → Guitar Rig → hodně reverbu „far back"; 4 dropy A / 4 dropy B | Abis Grains | střední | `naměřeno` |
| 15 | **stack 30 vrstev** (výjimka) | extrémní vrstvení | 30× Serum, hero chain, gain balance; **jen s resamplem, jinak CPU/stabilita** | Phenom | **vysoké** | `naměřeno` (architektura) |
| 16 | **`osc-warp-body`** (kandidát) | tělo z warpu jiným oscilátorem | Serum 2: OSC A slyšitelný, warp `PD`/`AM`/`Sync` z OSC B/C; OSC B/C **zapnuté, hlasitost 0** (jen modulátory), často oktáva +1/+2 nebo fine −60 ct; unison 1; za tím distorze + EQ + comp ve FX | Letsynthesize presety (16 bas), Pythius ×2, ENTA, notequal (viz `data/presets/index/`) | nízké | `hypothesis` (stopy v souborech přečtené; zvuk a „hlasitost 0 = nehraje“ neověřeno A/B) |

**Rozhodovací pomůcka (decision heuristics, `estimated`):** reese/deep = sub + body (filtrovaná saw) · mid-bass/hyper = body + noise + movement · FM/metallic = FM osc + distorze + textura · wobble/growl = movement (LFO-filtr) + distorze.

> Strojově čitelná kopie z vaultu (`Hudební produkce`). Zdroje: `knowledge/sources.jsonl`. Neupravuj ručně — změny se dělají ve vaultu a regenerují.
