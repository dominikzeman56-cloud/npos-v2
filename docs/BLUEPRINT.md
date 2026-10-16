# NPOS — Blueprint (v2)

> **Jediný zdroj pravdy o struktuře a kontraktech projektu.** Text je česky. **Identifikátory, výčty, klíče JSON a názvy souborů jsou kontrakt kódu a zůstávají anglicky.**
> v2 přepsáno 2026-10-15. Nahrazuje v1 (skeleton ze 2026-08-02), která vznikla dřív než znalostní konsolidace: obsahovala profily bez zdroje, odkazy na neexistující tracky a mandát „spálené země", který se ukázal nepoužitelný. Co se změnilo, je na konci (kap. 12).

---

## 1. Co NPOS je

**NPOS (Neurofunk Production System)** je **rozhodovací systém a datový stroj** pro neurofunk/DnB v Ableton Live. Uživatel je jeden (Domin, Architekt), spolupracují s ním AI agenti.

**Měřítko úspěchu:** lepší rozhodnutí za kratší čas v každé session. Ne počet souborů, ne objem znalostí.

**NPOS je:** kánon znalostí s důkazy a mírou jistoty · datová vrstva (analýzy tracků a presetů se schématem) · sada nástrojů nad tím. Součástí je i **výukový trenažér syntézy** (kap. 9, výjimka z blocklistu).
**NPOS není:** encyklopedie · web/dashboard pro produkční rozhodování · chatbot · generátor celých tracků · náhrada sound designu.

**Stav (2026-10-15):** kánon v češtině je napsaný (vault `Hudební produkce`, sekce 00–90: vstup `00 Start`); šablona Ableton mimo kánon (kap. 8); `analyze_track.py` funguje; datová vrstva je téměř prázdná (1 analýza ve schématu) a **je to další práce** (kap. 10).

---

## 2. Vrstvy znalosti a kam patří

| Vrstva | Obsah | Kde žije | Pravidlo |
|---|---|---|---|
| **0 · surové zdroje** | videa, přepisy, PDF, referenční audio | lokální disk | **nikdy v repu ani ve sdíleném exportu** (placený cizí obsah) |
| **1 · destilace** | rozbory vlastními slovy, jeden zdroj = jeden rozbor | vault `60 Rozbory` (Kurzy, Tracky, Redpill manuál) | archiv zdrojů, odkazuje se na něj |
| **2 · kánon** | principy, basa, bicí, lead/pad/vokál, aranž, mix a master, producenti | vault `10–50`, `70–80` (pro lidi) a `knowledge/` (strojově čitelná podoba) | povyšuje se jen přes pipeline (`docs/KNOWLEDGE_PIPELINE.md`) |
| **3 · data a nástroje** | analýzy, presety, session logy, korpus, skripty | `data/`, `core/`, `tools/` | schémata jsou v `core/*.schema.json` |

**Tok:** 0 → 1 → 2 → 3. Nový poznatek nejde přímo do kánonu.
**Jazyk:** próza česky, identifikátory a výčty anglicky. Překlad nikdy nemění kontrakt.

### 2.1 Pravidlo pravdivosti (zavedeno kvůli incidentu v1)
V1 `knowledge/` obsahovalo profily vygenerované ze šablony a seznamy „referenčních tracků", které neexistují. Proto:
1. **Žádný odkaz na track, producenta, kurz ani číslo bez ověřeného zdroje.** Zdroj je záznam v `knowledge/sources.jsonl` (schéma `core/source.schema.json`) nebo adresář `data/tracks/<id>`.
2. **Ověření** = `local_file` (soubor na disku) · `transcript` · `project_file` · `web` (s URL) · `screen` · `own_work`. Zapisuje se, jak a kdy.
3. **Neověřené = nezapsané.** Ne „hypotéza se štítkem", ale vůbec ne. Štítek `hypothesis` je pro *interpretaci*, ne pro *existenci zdroje*.
4. `tools/check_repo.py` toto vynucuje (kap. 9).

---

## 3. Struktura repa (závazná)

```
npos-v2/
├── README.md
├── docs/
│   ├── VISION.md
│   ├── BLUEPRINT.md                 ← tento soubor
│   ├── AGENT_RULES.md
│   └── KNOWLEDGE_PIPELINE.md        ← jak se znalost povyšuje do kánonu
├── core/
│   ├── ableton/                     ← poznámka: šablona mimo kánon
│   ├── source.schema.json
│   ├── build-sheet.schema.json
│   ├── track-analysis.schema.json
│   ├── preset-analysis.schema.json
│   └── session.schema.json
├── knowledge/
│   ├── README.md                    ← kontrakt frontmatteru
│   ├── sources.jsonl                ← registr ověřených zdrojů
│   ├── principles/                  ← principy (P1–P9 + šest z vrstvy 1 + kandidáti)
│   ├── archetypes/                  ← slovník archetypů s důkazy
│   ├── producers/                   ← filozofie, jen se zdrojem
│   └── guides/                      ← návody vytěžené z rozborů (aranž)
├── data/
│   ├── tracks/<id>/{meta.json, analysis.json, notes.md}
│   ├── presets/<id>.json
│   ├── sessions/
│   └── corpus/{tracks.jsonl, presets.jsonl}   ← generované
├── tools/
│   ├── analyze_track.py             ← hotové
│   ├── check_repo.py                ← kontrola kontraktu a zdrojů
│   ├── sync_knowledge.py            ← vygeneruje knowledge/ z kánonu ve vaultu
│   ├── vault-app/                   ← read-only prohlížeč a export vaultu (viz kap. 9)
│   ├── analyze_preset.py            ← čtečka .SerumPreset (basis: preset_file)
│   └── (plánováno: rebuild_track_index.py, query_tracks.py)
├── neuroman/                        ← legacy, neoživovat (kap. 9)
└── pyproject.toml
```
**Nové adresáře nejvyšší úrovně jen se souhlasem Architekta** (výjimky: `neuroman/` a `tools/vault-app/`).

---

## 4. Principy

Plné znění s důkazy a mezemi: `knowledge/principles/` (lidská podoba: vault `10 Principy`). Zde jen znění závazných principů.

1. **Rozhodovací systém, ne skládka dokumentace.** Při volbě mezi „víc informací" a „lepší workflow" vyhrává workflow.
2. **Sound design = mixdown od první vteřiny.** Nový zvuk se hned usadí (hlasitost, frekvence, stereo) a nehýbe se s ním; aranž a mix se nedělí.
3. **V MIDI, dokud se zvuk rozhoduje; resamplovat vědomě.** Resample je tvůrčí krok (groove z bounce), fázový zámek, úleva CPU nebo dodání — ne ústup.
4. **Jedna vrstva = jedna funkce.** `sub` · `body` · `movement` · `noise` · `texture` (basa) a `lead` · `pad` · `fx`. Zvuk pokrývá záměrně úzké pásmo.
5. **Producenti jsou filozofie, ne předlohy.** Žádné životopisy, žádné kopie zvuku.
6. **Každé tvrzení nese jistotu a zdroj.** `measured` · `estimated` · `hypothesis` + odkaz na zdroj (kap. 2.1).
7. **Měřit tam, kde měření platí.** Výchozí je plný mix (dynamika, spektrum, struktura). **Basové pásmo (modulace, harmonické) se zapisuje ze stemů nebo bass-mute; z plného mixu je to nejvýš `hypothesis`** (hi-haty kontaminují obálku, kap. 7). Zakázáno je budování stem-separation pipeline, ne analýza stemů, které existují.
8. **Záměr v MIDI má přednost před přepisem not.** Z mastera se berou role, mezery a design.
9. **Hodnoty jsou startovní body, ne zákon.** EQ, OTT, šířky a hloubky ducku z jednoho zdroje nebo z jiného žánru se nepřenášejí jako pravidlo; platí jen s důkazem a rule labelem (konsenzus / podmíněné / škola / dogma k ověření).

---

## 5. Slovníky (kontrakt)

Hodnoty jsou **zamčené**. Změna jen se souhlasem Architekta.

| Slovník | Hodnoty |
|---|---|
| `confidence` | `measured` · `estimated` · `hypothesis` |
| `basis` (z čeho je to změřeno) | `full_mix` · `stems` · `project_file` · `preset_file` · `course_video` · `course_files` · `listening` · `own_work` |
| `rule_label` (kánon) | `consensus` · `conditional` · `school` · `dogma_unverified` |
| `knowledge status` | `canon` · `candidate` · `deprecated` |
| `bass.type` | `growl` · `reese` · `hybrid` · `sub_led` · `other` |
| `bass energy profile` | `sub_dominant` · `fundament_dominant` · `balanced` |
| `modulation grid` | `1/4` · `1/8` · `1/16` · `1/32` · `off_grid` · `unknown` |
| `modulation source` | `lfo_grid` · `note_rhythm` · `kick_sidechain` · `detune_beating` · `unknown` |
| `loudness_strategy` | `crushed` · `controlled` · `open` |
| `layer function` | `sub` · `body` · `movement` · `noise` · `texture` · `lead` · `pad` · `fx` · `other` |
| `lead playing style` | `held_pad` · `short_stabs` · `riff` · `call_and_response` · `sparse_ornament` · `continuous_line` · `unknown` |
| `lead roles` | `hook` · `answer` · `riser` · `atmosphere` · `stab` · `counter_melody` · `none` |
| `buildup type` | `held_drone_plus_harmonics` · `pitch_riser_gesture` · `filter_only` · `other` |
| `breakdown type` | `atmosphere_no_bass` · `gated_sub_stutter` · `glitch_texture` · `other` |
| `body design primary` | `fm` · `wavetable` · `detune_reese` · `filter_growl` · `sample` · `hybrid` · `other` |
| `knowledge source type` | `producer_course` · `ableton_project` · `preset_pack` · `interview` · `track_analysis` · `personal_observation` · `other` |
| `source kind` | `course` · `video` · `track` · `podcast` · `project` · `manual` · `memory` · `preset_pack` |
| **seed archetypů** | `grid-locked-filter-growl` · `slow-grid-growl` · `detuned-unison-reese` · `fm-distorted-body` · `clean-sub-sine` · `serum-overlay-chords` |

**Referenční hodnoty `loudness_strategy`** (crest v okně dropu): `crushed` ≈ 4 dB · `controlled` 5–6 dB · `open` > 6 dB. Naměřeno u hotových tracků: Restless 5 dB, Breach 6,4–7 dB, Hands Up 8,4 dB, First Contact 6,1 dB (`knowledge/archetypes`, vault `03 Zvuk a mix` kap. 12).
**Archetypy:** seed se rozšiřuje jen tím, co se opakuje v datech. Kandidáti jsou v `knowledge/archetypes/bass.md` se stavem `candidate`.
**Co se změnilo ve slovnících proti v1:** `layer function` sjednocen (princip 4 v v1 uváděl jiný seznam než slovník), přibyl `texture`; přibyly `basis`, `modulation source`, `rule_label`, `knowledge status`, `track_analysis` u typů zdrojů.

---

## 6. Schémata

**Schémata nejsou opsaná v tomto dokumentu.** Jediný zdroj jsou soubory v `core/`; BLUEPRINT drží jen jejich účel.

| Soubor | Účel |
|---|---|
| `source.schema.json` | registr ověřených zdrojů (`knowledge/sources.jsonl`) |
| `build-sheet.schema.json` | rozhodnutí o jednom tracku (povinné: `id, title, created, bpm, key, reference, goal`) |
| `track-analysis.schema.json` | analýza tracku (`data/tracks/<id>/analysis.json`), každé pole s `confidence` a `basis` |
| `preset-analysis.schema.json` | strategie presetu (`data/presets/<id>.json`), ne výpis parametrů |
| `session.schema.json` | log session (`date, track_id, goal, done, blocked, learned, next`) |

Pravidla: `lessons` nejvýš 5 a proveditelné v jedné session · `recreate_workflow` = seřazené kroky Ableton/MIDI/synth · u každého důležitého pole `confidence`.

---

## 7. Měření

**Metody spolehlivé z plného mixu (`measured`):** RMS křivka (okna 20 ms) a časy sekcí (přibližně) · crest faktor v okně dropu · energie pásem sub 20–60 Hz vs. fundament 60–250 Hz · poměr mid/side po pásmech · spektrální centroid.

**Metody slabé z plného mixu (nejvýš `estimated`/`hypothesis`):** výška not leadu v husté polyfonii · přesný FM poměr a index · identita bicích samplů · **modulace basy (obálka 60–300 Hz → Hilbert → FFT vs. mřížka)**.

**Proč je modulace basy z plného mixu nespolehlivá.** Hi-haty a kick vyrábějí v basové obálce falešné 16tinové pruhy. Důkaz: u *Don't Play* dala analýza plného mixu „AM 11,5 Hz = 1/16", ale **izolované stemy žádnou 1/16 modulaci nemají** (obálka 0,72 a 2,15 Hz = rytmus not). U *Breach* jsou obálky 2,90 / 1,45 / 0,72 Hz = kick sidechain. Dále: pyin na basu v plném mixu je kvantizovaný model; „střídání F/A/C" v FFT byl artefakt binu 10,8 Hz (energie kicku).

**Protokol pro basové pásmo:**
1. Existují-li oficiální stemy nebo jde bass-mute → měřit na izolovaném pásmu a zapsat `basis: stems`.
2. Jinak low-pass ~300 Hz před Hilbertem, výsledek ověřit proti spektrogramu a zapsat `basis: full_mix`, `confidence: hypothesis`, `modulation.source: unknown`.
3. Na izolovaném pásmu měřit: H2/H3 úroveň subu, mono (side dB), HP bod mid basu (H1/H2 vyříznuté?), liché harmonické, stereo pod/nad 300 Hz a 1 kHz, crossover sub/mid (u *Don't Play* ~62 / ~120 Hz).

**Test reese vs. growl** (pro hlubokou analýzu, jen z izolovaného pásma): vrcholy obálky zamčené na 1/8 nebo 1/16 vůči tempu → growl (LFO) · mimo mřížku a nezávislé na tempu → reese (detune beating) · hi-res FFT 350–900 Hz na držené notě: čisté špičky = pár oscilátorů + modulace, „les" špiček s rozestupem ~2–10 Hz = reese.

**Nástroj:** `tools/analyze_track.py` (ffmpeg → numpy/scipy), plný mix, `basis: full_mix`.

### 7.1 Presety Serum 2 (`basis: preset_file`)
`.SerumPreset` je XferJson → Zstd → CBOR; `tools/analyze_preset.py` ho **čte** (oscilátory, filtry, FX řetěz, modulační matici, voice, LFO, makra) a vyrábí návrh `data/presets/<id>.json`. Pravidla:
- Soubor ukládá jen hodnoty, které se liší od výchozích. **Chybějící parametr = výchozí, ne nula.**
- Hodnoty jsou normalizované (např. frekvence filtru 0–1) a **jednotky nejsou ověřené proti UI**. Do Hz/dB se přepočítávají až po A/B ověření v Serum.
- Zdroje modulace jsou zmapované jen pro doložené rozsahy (Env, LFO, Macro); ostatní ID se **nehádají**.
- Přečtené hodnoty jsou `measured` s `basis: preset_file`. **Archetyp, funkce vrstvy a „proč“ jsou ruční interpretace** (`estimated`/`hypothesis`), skript je nevyplňuje.
- Preset pack je zdroj (`kind: preset_pack`) a soubory presetů se do repa nekopírují; do `data/presets` jde jen vlastní analýza.
- **Povolený offline zápis:** `tools/preset_seed.py` (kodek `tools/serum_preset_io.py`) vezme reálný Serum 2 preset a změní jen pár spojitých parametrů v rozsahu pozorovaném v korpusu (hodnoty včetně amountů modulací, nikdy tvar křivek obálek, celočíselné parametry ani počet hlasů; amount nemění znaménko). Není to synth engine, náhrada sound designu ani generátor tracků: konstrukci (oscilátory, routing mod matice, FX řetěz) zdědí ze skutečného presetu. Výstup je jen lokální (mimo repo nebo `data/presets/_local/`), odvozený z placených packů se nikdy nenahrává ani necommituje, nese `derived_from` a `hypothesis`; jediné potvrzení je poslech člověka.

---

## 8. Šablona Ableton — mimo kánon

**Stav (2026-10-15):** šablona `NEUROFUNK_TEMPLATE_FINAL` byla uživatelem označena za nedobrou a **není součástí kánonu NPOS**. Poznámky o šabloně byly smazány; vault `02 Šablona` zůstává jako **archivní poznámka** (kritika dogmat v10 a pasti sestavování `.als` v ní jsou užitečné, ale nejsou závazné). Nová šablona vznikne až z ověřených rozhodnutí (rozbory, `data/`), ne obráceně.
Zbývá platit: `.als` generovat jen routing, klipy a prázdné sloty; plugin XML se nepřenáší z cizích setů (pády).

---

## 9. Nástroje a blocklist

**Hotové:** `tools/analyze_track.py` · `tools/analyze_preset.py` · `tools/check_repo.py` · `tools/sync_knowledge.py` (generuje `knowledge/` z vaultu, vault z env `NPOS_VAULT`) · `tools/vault-app/` (read-only prohlížeč vaultu v prohlížeči a statický export do sdílené kopie; **nezapisuje** do vaultu ani do dat).
**Plánované (pořadí v kap. 10):** `rebuild_track_index.py` → `data/corpus/tracks.jsonl` · `query_tracks.py`.

**`tools/check_repo.py` kontroluje:** frontmatter každého souboru v `knowledge/` (kontrakt v `knowledge/README.md`) · že každý `source_ids` odkaz vede do `sources.jsonl` · platnost `sources.jsonl` proti `core/source.schema.json` · že `data/tracks/<id>` mají `meta.json`.

**Blocklist (absolutní nulová tolerance):**
- UI pro produkční rozhodování, dashboard, druhý frontend (výjimka: `tools/vault-app`, jen čtení; od 2026-10-16 smí v místním serveru zapisovat výstup generátoru presetů do složky mimo repo, viz kap. 7.1, a nikdy ve statickém exportu).
- Stem-separation pipeline (použití stemů, které existují, je povolené).
- Synth engine pro produkci. **Výjimka (Architekt, 2026-10-16):** výukový trenažér `tools/vault-app/public/trenazer.html`, jednoúčelová stránka Web Audio (oscilátor s wavetable, AM, FM, filtr, LFO, distorze) k učení, jak se parametry projeví. Nic nezapisuje, nevyváží zvuk ani presety, nepřehrává data presetů a nenahrazuje Serum. Receptury v něm nesou míru jistoty a odkaz do kánonu.
- **Druhý Ableton MCP most** (jediný je Producer Pal); Pal **nezapisuje vnitřní parametry Serum** (zeď Live API); Serum patche jsou binární stav → offline `.SerumPreset` nebo ruční klik.
- Upload nevydaných bounců do cizího cloudu (generátory hudby, stem separátory, sample služby).
- Oživení `neuroman/` orchestrátoru (legacy, v coding session horší než Producer Pal).
- Přenos placeného cizího obsahu (videa, přepisy, PDF kurzů) do repa nebo sdíleného exportu.
- Záznam bez zdroje v `knowledge/` (kap. 2.1).
- Nové adresáře nejvyšší úrovně bez souhlasu.

---

## 10. Pořadí implementace (v2)

**Hotovo:** kostra repa · build sheet a první analýza (*First Contact*) · `analyze_track.py` · český kánon (vault 00–05) · tento přepis repa (BLUEPRINT, knowledge, schémata, `check_repo.py`).

**Další kroky (nepřeskakovat):**
1. **Datová konverze:** převést už existující naměřené rozbory do `data/tracks/*/analysis.json` s poctivým `confidence` a `basis` (kandidáti: *Breach*, *Unleash The Beast*, *Restless*, *Hands Up*, *Been About This*, *Don't Play*, *Mechanism*, remix *Dirts*; každý musí mít záznam v `sources.jsonl`).
2. **Presety:** čtečka je hotová (`analyze_preset.py`). Zbývá převést ~15 rozborů presetů z próz do `data/presets/*.json` a doplnit ruční interpretaci (archetyp, funkce) k přečteným hodnotám; modulační matici a jednotky ověřit proti Serum UI.
3. **Korpus:** `rebuild_track_index.py` → `tracks.jsonl`, `query_tracks.py`.
5. **Dogfooding:** session log a build sheet na *každé* skutečné práci. Znalost se rozšiřuje, jen když se v praxi zasekneš.

### 10.1 Definition of Done (v2)
- [ ] Build sheet na každém novém tracku, session log na každé session.
- [ ] ≥ 10 analýz tracků, z nich ≥ 5 s basovým pásmem ze stemů nebo bass-mute (`basis: stems`).
- [ ] ≥ 15 analýz presetů s `function` a `archetype`.
- [ ] `tracks.jsonl` dotazovatelný podle typu, crestu a `usable_for`.
- [ ] `check_repo.py` bez chyb a **nula záznamů bez zdroje**.
- [ ] Nula UI komponent mimo `vault-app`, nula stem-separation pipeline, nula rozšíření rozsahu.

---

## 11. Správa změn

- **Architekt** (Domin) schvaluje změny kap. 4, 5, 6 a 9 (principy, slovníky, schémata, blocklist). Agent návrh změny jen navrhne s důkazem.
- Změna slovníku = změna schématu v `core/`, aktualizace `knowledge/README.md` a poznámka v changelogu.
- Kánon ve vaultu a v `knowledge/` se mění přes pipeline (`docs/KNOWLEDGE_PIPELINE.md`); degradované pravidlo se nemaže, dostane `status: deprecated` a odkaz na důkaz.

---

## 12. Changelog

**v2 (2026-10-15)** — úplný přepis.
- Jazyk: próza česky, kontrakt anglicky.
- Odstraněno: mandát „Scorched Earth" (nahrazen pravidlem pravdivosti a selektivním dědictvím vrstev), profily producentů bez zdroje, odkazy na neexistující tracky, ušmudlané ear-based poznámky *Stink* a *Midnight Runner*, schémata opsaná v dokumentu (jediný zdroj je `core/`).
- Změněno: principy 3, 7 a 4, slovníky (`layer function`, `texture`), blocklist (`vault-app` povolen jen ke čtení; druhý MCP most, cloudové uploady a oživení `neuroman/` zakázány).
- Přidáno: pravidlo pravdivosti, registr zdrojů, `check_repo.py`, schémata `source`, `track-analysis`, `preset-analysis`, protokol měření basového pásma, `basis` a `modulation source`, princip 9.
- Zastaralé v v1: „Current stage: Skateboard step 1" — kroky 2 a 3 byly dávno hotové.

**v2.3 (2026-10-16)** — vault-app (jen místní server) má stránku `/generator.html`, která spouští `preset_seed.py` nad malou sadou semínek (20 až 30 vlastních presetů) a ukládá výsledek na disk uživatele; Architekt to schválil v chatu; výstup se nenahrává a statický export stránku neobsahuje. kap. 7.1: povolený offline zápis `preset_seed.py` (reálný preset + pár zmutovaných parametrů, výstup jen lokálně). Kap. 9: výjimka z blocklistu pro výukový trenažér syntézy (schválil Architekt v chatu). Nové nástroje: `analyze_fxp_host.py`, `render_preset.py`, `preset_roles.py`, `preset_stats.py`, `check_presets.py`, `serum_preset_io.py`, `preset_seed.py`.

**v2.2 (2026-10-15)** — `knowledge/guides/` (návod na aranž z rozborů), `tools/sync_knowledge.py`, typ `guide` ve frontmatteru. Šablona Ableton: uživatel smazal poznámky o šabloně a označil ji za nedobrou; kap. 8 čeká na rozhodnutí (viz vault `06 Návod na aranž` a `02 Šablona`).

**v2.1 (2026-10-15)** — přidáno `preset_file` do `basis`, `preset_pack` do `source kind`, kap. 7.1 a `tools/analyze_preset.py`; schéma `preset-analysis` má `basis` a `reading`.

**v1 (2026-08-02)** — skeleton podle původního BLUEPRINTu (viz historie gitu).
