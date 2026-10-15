---
id: guide-arrangement
type: guide
title: Návod na aranž
status: canon
confidence: measured
source_type: track_analysis
source_ids: [dont-play-skeleton, prolix-been-about-this, sinister-souls-raido-restless, triamer-nagato-hands-up, tr-tactics-mechanism, dirts-remix-skeleton, breach-balron-audio, letsynthesize-noisia-course, abis-start-to-finish, abis-grains-of-sooner, pythius-fearless-remix, pythius-inquisition, pythius-template-workflow, mefjus-remix-another-life, audio-headroom-2013, ed-rush-killbox-valkyrie-podcast, redpill-manual]
vault_note: 30 Aranž
updated: 2026-10-15
---

# 30 Aranž

> **Jak poskládat neurofunk track od intra po outro tak, aby měl tah.** Nejde o encyklopedii, ale o postup: co má která sekce dělat, čím se staví napětí, jak se dělá druhý drop jiný a co když se zasekneš. Vše je vytěžené z rozborů v 60 Rozbory — přehled (workshopy, kurzy, projekty `.als`, analyzované tracky); u každého bodu je zdroj a štítek.
> **Štítky.** Jistota: `naměřeno` (spektrální analýza, stemy, `.als`) · `kurz` (řečeno nebo ukázáno v kurzu) · `odhad` (moje syntéza). Pravidlo: **[K]** konsenzus ≥ 3 zdroje · **[P]** podmíněné (platí v určitém kontextu) · **[Š]** metoda jednoho producenta nebo školy · **[D]** k ověření.
> **Co tu není.** Zvukový design a mix jednotlivých vrstev (viz 20 Basa, 21 Bicí, 40 Mix a master), vokální texty. **Meze:** formy z cizích tracků jsou měřené z plného mixu (hranice sekcí ±pár barů); bary jsou přepočet ze sekund.

---

## 1. Princip: aranž je řízení energie, ne řazení bloků

Neurofunk se skládá z **16-barových bloků**. V každém bloku se dá změnit jen pár věcí a každá změna má cenu. Všechny rozbory se shodují, že napětí se **neukládá přidáváním**, ale **odebíráním a odkládáním**:

| Páka | Co se mění | Příklad ze zdrojů |
|---|---|---|
| **Vrstvy** | přidat / ubrat | Breach: druhá vrstva muted do baru 48 = +5 dB v pásmu 20–60 Hz (`naměřeno`) |
| **Rytmus basy** | jiný rytmus stejného riffu | Ekwols: hustší stab v dropu než v buildupu `naměřeno`; Pythius Inquisition: drop 2 s malou změnou rytmu `kurz` |
| **Filtr** | držet zavřený, otevřít později | LS 23/26: basa v buildupu přes LP, nikdy plně otevřená; filtrovaný pad ~2,5 kHz v první půlce bridge, plně až ve druhé `kurz` |
| **Hlasitost** | tišší kick v buildupu, automace levelu basy | LS 23, LS 26 `kurz` |
| **Stereo** | mono dole, široko nahoře; šířka se buduje v dropu | LS 01 `kurz`; Prolix: 23 → 64 → 70 % po pásmech `naměřeno` |
| **Tónina / oktáva** | transpozice o semitón nebo oktávu | Restless: B-sekce +3 (Ab); Neonlight: druhá půlka o půltón; LS 27: outro o oktávu níž |
| **Ticho** | řez, dropout, hard stop | Restless: 1 bar dropoutu před každým řezem `naměřeno` |

**Zlaté pravidlo transientů** `[K]` (Redpill): když udeří kick nebo snare, nemá tam být nic jiného. Čím složitější aranž, tím míň kontroly na konci.

---

## 2. Formy: co se skutečně měřilo

Bary jsou kumulativní od začátku. Typ jistoty u všech: `naměřeno` z plného mixu nebo stemů (hranice přibližné, ověř sluchem).

| Track | BPM / tónina | Délka | Sled sekcí (bar) |
|---|---|---|---|
| Prolix & Figure — Been About This | 172,3 / A moll | 141 barů, 3:29 | intro 1 · build 13 · drop A 17 · breakdown 33 · build 2 45 · **drop B (main) 49** · switch-up 61 · drop B 65 · switch-up 77 · breakdown 2 81 · build 3 93 · **drop C 97** · switch-up 109 · drop C 113 · outro 129–141. **16 barů + 4-barový switch-up uprostřed**, každý další drop hlasitější |
| Audio — Don't Play | 172,3 / G# moll | 168 barů | intro 1–24 · build ≈ 25–33 · drop A ≈ 33–80 · tension 81–96 · breakdown 97–112 · drop B 113–144 · outro 145–160. **Drop 6+2**, breakdown nejde do ticha (−8 dB) |
| Balron & Audio — Breach | 174 / F moll | 192 barů | lokátory 0 / 24 / 32 / 48 / 112 / 128 / 176; **drop A 80 barů** s aditivními 8-bar vrstvami; bass mute posledních 2 barů z prvních 16 |
| Sinister Souls & RAIDO — Restless | 174 / F moll | 225 barů | intro A 1 · intro B 17 · build 33 · **drop 1A 49 · 1B 81** · reprise 113 · build 2 129 · **drop 2A/B 145** · outro 209. **AABB**, bez tichého breaku, 1 bar dropoutu před každým řezem |
| TriaMer & Nagato — Hands Up | 175 / A moll | 260 barů | intro A 1 · intro B 17 · falešný drop (HIT) 33 · dip/vox 49 · **drop 1A 65** · break + riser 97 · drop 1B 113 · breakdown 145 · **drop 2 161–240 (~80 barů)** · outro 241. Opravdová údolí |
| TR Tactics — Mechanism | 174 / chroma F | ≈ 168 barů, 240 s | intro/build ≈ 0–14 · **drop A ≈ 15–78** · **breakdown ≈ 79–96 (24 s, exponovaný pluck)** · **drop B ≈ 96–160** · outro ≈ 160–168 (přepočet ze sekund) |

### Vzory drop bloků `[Š]` (Redpill, A a B = bloky po 16 barech)
`ABA` (More Energy, Death Ray) · `AAB` (Into Black, Brokn) · `AABA` (Beat Down, Mosh Pit) · `AABB` (ENERGY remix; Restless) · `AA` nebo `AB` (The Siren). **Délka:** intro a drop buď 3×16 a víc (silné téma, hodně variací), nebo 2×16 (silný nápad, jít k věci); „potom už neexistují pravidla“ `kurz`.

> **Co z toho plyne.** Dnešní tracky jsou kratší než dřív (Redpill). Reálné délky 141–260 barů; střed je kolem 170–190 barů. Počet dropů je 2–3 a každý z nich má vnitřní vývoj, nikdy není čistá kopie (viz kap. 6).

---

## 3. Sekce po sekci

### 3.1 INTRO (≈ 16–32 barů)
**Úkol:** nastavit tóninu, náladu a očekávání; předznamenat drop; neutratit energii.

- **Foreshadowing** `[K]`: do intra propašovat prvek z dropu (basový riff, textura, riser), aby drop nepřišel „odnikud“; nejdřív placeholder zvuky, finální až později (Abis S2F `naměřeno`). V intru i **téma, které se vrátí** v dropu nebo breakdownu (Abis Grains, Dirts originál).
- **Intro nemá basu nebo má jen náznak:** Prolix intro = jen bicí a hi buildup; Hands Up intro = široký A drone s 1/16 gate, bez subu; Don't Play intro = beeps, intro kick, reece pickup v barech 15–16 `naměřeno`.
- **Intro je tišší a širší než drop.** LS: intro a build byly nadřazené dropu → srazit ~−6 dB a lehce komprimovat skupinu (MultibandDynamics), aby kontrast zůstal `kurz`; Hands Up: S/M intro −3,7 dB (široké) × drop −9 dB `naměřeno`.
- **„Neviditelný lead“** = silně filtrovaný pad nese melodii a vyplní prostor (LS 16 `kurz`). Pady nemají sub; low end patří basám (Pythius `kurz`).
- **Neopakuj materiál mezi intro A a B:** transponuj nebo přehlasuj (LS 18: oktávová posunutí screechy a subby padu) `kurz`; Restless: B-intro přidá bicí `naměřeno`.
- Vokál/dialogový sample (Noisia: staré filmové dialogy) je legitimní prostředek intra (LS 21 `kurz`).

### 3.2 BUILD (≈ 8–16 barů)
**Úkol:** napnout a vybít do dropu. Cílem je **kontrast**, ne maximum hlasitosti.

1. **Tišší kick v buildupu** `[K]` (LS 23 `kurz`): v breakdownu a buildupu nenechávej kick na hlasitosti dropu; drop pak zasáhne. Trik: hustý kick pattern, přes něj fade-in, pak zkopíruj původní kicky navrch.
2. **Rytmus bicích houstne:** kick 4/4 → osminy → šestnáctiny (Don't Play, bary 29–31) `naměřeno`; „standardní rocky daku-daku“ tom fill je OK, protože dělá hype (Pythius) `kurz`.
3. **Basa se předvede, ale zavřená:** hlavní basa v buildupu na každou první čtvrtku, přes LP začínající velmi nízko; neotvírej plně — plný zvuk až v dropu (LS 23 `kurz`). Audio: low-cut mid bass s hodně wet reverbem, **automatizuj reverb sušší** k dropu → mid se „zformuje“ a drop „nasaje“ (Audio 2013 `kurz`). Audio: bass-bus automace low/high-cut (vynést váhu a vrátit ji).
4. **Riser je stack 5–8 vrstev**, z toho jen jedna ze Seru (Pythius Fearless `kurz`); vždy něco ve pozadí stoupá (Shepard-tone, Pythius). **Rozsah pitch bendu 2 oktávy**, začít dole a v půlce přepnout na opačný extrém → 4 oktávy pohybu (LS 22 `kurz`); všechny vrstvené risery nastav na stejný rozsah, jinak se nebudou sledovat. Šumový riser: tonalita nehraje roli, rozhoduje filtr; začínat velmi nízko a stažený (LS 21).
5. **Vokál do buildupu:** reverb dry/wet automatizuj od nuly nahoru; pitch-drop na vokálu těsně před dropem (LS 21 `kurz`).
6. **Reverse crash** pro „suck into the drop“ (Audio `kurz`); Mefjus: risery z materiálu originální basy (loop + pitch) `kurz`.
7. **Řez před sekcí:** vystřihni bicí těsně před změnou sekce (LS 26), nebo **1 bar dropoutu** (Restless `naměřeno`) — řezat, ne fade-ovat `[Š]`.
8. **Chromatický walk v buildupu** (Restless build 2: E–F–F#; build 1 chromatika + 1/4 growl lock) `naměřeno`.

### 3.3 DROP (16 nebo 2×16 barů)
**Úkol:** předvést basu a groove; dopad musí být okamžitý a čitelný.

- **Stavba po 8 barech.** Breach: drop A má 80 barů, aditivní 8-bar vrstvy (půlka na baru 32, „wall“ na 48) `naměřeno`. Vrstvu zapni až když předchozí „dosloužila“.
- **Drop 6+2** `[K]` (Don't Play, Prolix): 6 barů riffu + 2 bary **switch-up** místo osmi identických. Switch-up v Don't Play (bary 7–8): sub OFF nebo oktáva nahoru, reese edit, pickupy chromaticky F/E/C#/C; druhá půlka dropu (57–62) má kick na 1 a 3 místo 3& (groove switch) `naměřeno`. Prolix: **4-barový switch-up uprostřed 16-barového dropu** (sub dip + hi-end akcent) `naměřeno`.
- **Riff, ne řada nepovázaných not.** Don't Play: `G1 G1 G#1~` (16+16+8), liché bary držená G1, sudé `A#1 A#1 A1~`; sub jede nepřetržitě, pohyb dělá chromatický skluz `naměřeno`. Prolix: sub nese melodii (chromatický riff), mid reese dělá groove `naměřeno`.
- **Sub: dva přístupy** — (a) souvislý sub s portamentem (Don't Play, Prolix; glide ~120 ms) a (b) **sub ručně do mezer v resamplu dropu** (LS 28 `kurz`; nejcennější lekce kurzu: resample drop → nakresli sub do každé mezery → fázově čisté, bezpečné pro transienty; ocasy basy ustřihni od kicku/snaru). Vyber jedno podle hustoty aranže.
- **Stereo se buduje v dropu:** drop začíná téměř mono (stereo nese jen hi-hat), pak basa s krátkým room reverbem, až na konci široký „weird percussion“ synt (LS 01 `kurz`). Pod ~150 Hz nic stereo `[K]`.
- **Rytmický kontrakt** drží žánr: kick na každou dobu = industrial/crossbreed (Restless), broken kick 1+2+4 / snare 2+4 + 1/16 pickup = Hands Up, 2-step = Don't Play. Neměň ho uprostřed dropu bez důvodu.
- **Call a response** `[Š]`: call = dlouhá pohyblivá reese fráze („mluví“), response = rytmická gatovaná groove („valí“); Abis Grains: 4 dropy Reese A / 4 dropy Reese B `kurz`.

### 3.4 BREAKDOWN (≈ 16–29 barů)
**Úkol:** obnovit napětí a dát poslechu vzduch. Zvol jednu ze tří cest a **nedělej víc než jednu v jednom tracku** `[Š]`:

| Typ | Co se děje | Zdroj |
|---|---|---|
| **A. Hard stop do ticha** | digitální ticho a návrat | zatím bez profi reference v datech (dřívější doklad byl vlastní track) `[Š]` |
| **B. Stripped, ale hlasitý** | hats OFF, pad z intra se vrací, sub jede dál; žádné ticho | Restless (reprise 113–128); Don't Play (−8 dB, nejde do ticha) `naměřeno` |
| **C. Exponovaný hlas** | jedna řídká figura nese sekci (pluck: rozložený mollový kvintakord, 1 nota na dobu, mezery) a pak re-entry do dropu | Mechanism (24 s) `naměřeno` |

- **Reprise intra v breakdownu je feature** `[K]`: pady z intra se vrací (Dirts, originál Tao Maffa 2:15–2:47; Restless reprise) — posluchač dostane tvar.
- **Bridge en bloc** (LS 26): zkopíruj breakdown + build + drop → „mimořádný breakdown uprostřed“; vrstvené přechodové efekty (impact → zadušený impact → dlouhý šumový sweep) `kurz`.
- **Filtrové napětí:** v bridgi neotevírej spektrum plně; filtrovaný pad ~2,5 kHz v první polovině, plně až ve druhé (LS 26 `kurz`). Vokál/lead v breakdownu nese prostor → `Utility` před limiterem, aby šlo zvednout level tam, kde ostatní odpadne (LS 21 `kurz`).
- **Falešný drop** (Hands Up bar 33, na G místo A) a **údolí** s dipem — nechává druhý, pravý drop zasáhnout víc `naměřeno`.
- **Údržba napětí v prázdnu:** Restless nechává dropout 1 bar před každým řezem; Mechanism drží breakdown s `delay` a `room reverb`, bez bicích.

### 3.5 BUILD 2 → DROP 2/C
Stejné nástroje jako build 1, ale **jiný materiál**: Dirts — vox tag originálu na přechodu (~2:47–2:56); Mefjus — risery z materiálu originální basy. Pythius: riser z jiných zdrojů než v prvním buildupu. Cíl: druhý příchod dropu je očekávaný, ale ne identický.

### 3.6 DROP 2 — jak ho dělat jiný, nikoli nový `[K]`
Čtyři osvědčené cesty (ze zdrojů, seřazeno od nejlevnější):

1. **Automace levelu / transpozice místo nového materiálu** (LS 26: fade křivka přes druhý drop; rozdíl −5/−10 dB není dramatický, neřeš hloubku) `kurz`.
2. **Jiný rytmus a variace na stejném riffu** (Pythius Fearless: odpověď = stejné reese jako otázka, riff 2× natažený, rychlejší bicí, ShaperBox stutter; každý zásah jiná varianta makra/wavetable/EQ; dřívější tvrzení o „Shade + Corrosion“ pro druhý drop v řeči není) `kurz`.
3. **Změna rytmu basy** (Inquisition: malá změna rytmu stačí, původně úplně jiný drop stáhnul zpět kvůli DNA) `kurz`.
4. **Vokálně prázdný drop 2** (Dirts, originál Tao Maffa: čistě instrumentální 3:03–3:51) = prostor pro vlastní podpis `naměřeno`.

Ještě: **Neonlight** hraje druhou půlku o půltón výš; **Restless** má B-sekci o +3 (Ab); **Hands Up** drop 2 je dlouhý (~80 barů) s vlastním vývojem.

### 3.7 OUTRO (≈ 6–20 barů)
**Úkol:** rozloučit se známým materiálem, ne dobít poslední energii.

- **Odečítání** `[K]` (LS 27 `kurz`): smaž bicí na hranici, vlož impact a později zadušený druhý; prvky z intra se vrací **o oktávu níž** (nový rejstřík); nový prvek až ve druhé půlce outra; filtrovaný pad jako **fade-out zařízení**; prodloužený tom fill kopií předdropového.
- **Bookend:** Restless outro: fade, Fm + kvinta C; Don't Play outro = riff a clap `naměřeno`.
- **Neřeš fade pomocí master faderu**; řez nebo automace skupin (Restless: „řež, nefadeuj“) `[Š]`.

---

## 4. Rozhodovací pomůcka: „zasekl jsem se"

| Situace | Další krok | Zdroj |
|---|---|---|
| Drop nezní jako drop | zkontroluj kontrast: je build tišší a užší? | LS 23, LS 01 |
| Drop 2 je nuda (kopie) | automace levelu → jiná distorze → změna rytmu basy (kap. 3.6) | LS 26, Fearless, Inquisition |
| Breakdown se vleče | vyber typ A/B/C a drž ho; 16–24 barů, ne víc; re-entry element před dropem | Mechanism, Restless |
| Nevím, co dál po 16 barech dropu | switch-up (6+2) nebo +1 vrstva po 8 barech | Don't Play, Breach |
| Drop je tlustý a plochý | sub ručně do mezer + ustřihnout ocasy basy od kicku/snaru | LS 28 |
| Intro mi nic neříká | foreshadowing + filtrovaný pad jako „neviditelný lead“ | Abis, LS 16 |
| Buildup se nezvedá | tišší kick, riser stack s 4 oktávami, reverb dry→0, řez bicích | LS 22/23, Audio |
| Remix: jak ho odlišit | OG stemy ve vlastní skupině; question/answer riff; jedna barva reese na A i B | kap. 5 |
| Kolik barů? | 2×16 pro silný nápad, 3×16 pro silné téma; celek 140–260 barů | Redpill; kap. 2 |

---

## 5. Remix: aranžérské zvláštnosti

- **Pročesat originál**, hledat cool parts (Pythius Fearless), ne „jak nahradím drop“. **Over-exaggerate, ne nahradit** (Mefjus) `kurz`.
- **Zachovat DNA:** originální kick pod vlastním, vokál a MC zůstávají, drum fill originálu jako textura pod vlastním kickem, risery z materiálu originálu.
- **Question / answer riff:** question = jiný riff z originálních stemů, answer = stejný, ale roztažený 2×, rychlejší drum a ShaperBox stutter. **Jedna barva reese na A i B**, malé EQ/pitch variace (Pythius) `kurz`.
- **Reprise intra v breakdownu a vokální mapa originálu** určují, kde je „díra“ pro tvůj materiál (Dirts: drop 2 originálu je instrumentální) `naměřeno`.
- **Kolaborace přes stemy** (Ed Rush & Killbox): jeden postaví intro + ~32 barů dropu, druhý dokončí; funguje díky cross-kompatibilní referenci `kurz`.

---

## 6. Výchozí kostry (návrh, `odhad`)

Syntéza z naměřených forem — **nejde o naměřený standard**, ale o startovní mapu k doladění sluchem.

**Kostra A — standard (~176 barů).** `INTRO 1–24 · BUILD 25–32 · DROP A 33–64 (16 + 16, switch-up v barech 7–8 každé osmičky) · BREAKDOWN 65–88 · BUILD 2 89–96 · DROP B 97–144 (3 × 16, třetí blok nejhustší) · OUTRO 145–176.`

**Kostra B — krátká (~128 barů, 2×16).** `INTRO 1–16 · BUILD 17–24 · DROP A 25–56 · BREAKDOWN 57–72 · BUILD 2 73–80 · DROP B 81–112 · OUTRO 113–128.`

**Kostra C — AABB, bez ticha (~225 barů, vzor Restless).** `INTRO A 1–16 · INTRO B 17–32 · BUILD 33–48 · DROP 1A 49–80 · 1B 81–112 (B o +3 semitóny) · REPRISE 113–128 · BUILD 2 129–144 · DROP 2A/B 145–208 · OUTRO 209–225.`

Pro každou kostru nastav lokátory v projektu a **ověř A/B proti referenci na vlastní stopě** (BUS, ne master).

---

## 7. Kontrolní seznam před exportem aranže

- [ ] Jde napětí z kontrastu (build tišší a užší než drop), ne z hlasitosti?
- [ ] Je v každém dropu aspoň jeden důvod, proč nezní jako předchozí? (kap. 3.6)
- [ ] Je před každým řezem 1 bar dropoutu nebo jasný přechodový prvek?
- [ ] Breakdown: jeden typ (A/B/C), ne dva.
- [ ] Prvek z dropu v intru (foreshadowing), prvek z intra v breakdownu nebo outru (reprise)?
- [ ] Sub mono, nic stereo pod ~150 Hz; stereo roste v dropu, ne od začátku.
- [ ] Transient kicku/snaru je čistý (zlaté pravidlo).
- [ ] Délka odpovídá nápadu (2×16 × 3×16).
- [ ] Resample a pohled na waveform: překomprimovaný master nebo moc hlasité intro vůči dropu? (LS 29)

---

## 8. Rozpory a co je nejisté

- **Souvislý sub × sub v mezerách.** Don't Play a Prolix mají sub jedoucí nepřetržitě; Letsynthesize ho zásadně kreslí do mezer resamplu. Obojí funguje; závisí na hustotě aranže a na tom, jestli sub nese melodii. `[P]`
- **Breakdown do ticha × bez ticha.** Zdroje jdou oběma směry (kap. 3.4). Vyber podle tracku.
- **AM gate 1/16 jako „standard“ není pravidlo aranže.** Původní měření z plného mixu bylo artefakt hi-hatů; stemy Don't Play modulaci neukazují. Rytmus basy v aranži je **rytmus not**, ne LFO.
- **Délky vs. DJ použitelnost.** Redpill: dnes se hraje kratší, ale Hands Up (260 barů) nebo Restless (225) ukazují, že délka je závislá na žánru (crossbreed/industrial).
- **Cizí formy jsou z plného mixu.** Hranice sekcí jsou přesné na několik barů; kdo chce víc, měří stemy (`basis: stems`).

---


> Strojově čitelná kopie z vaultu (`Hudební produkce`). Zdroje: `knowledge/sources.jsonl`. Neupravuj ručně — změny se dělají ve vaultu a regenerují.
