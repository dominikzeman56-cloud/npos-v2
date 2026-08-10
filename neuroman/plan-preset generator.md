lán M1: Pravidlový generátor Serum presetů + feature-vector infrastruktura
Cíl a strategie
Postavit pravidlový generátor (generalizace build_skullstep_lead), který produkuje validní .SerumPreset soubory pro neurofunk archetypy (Growl/Reese/Hybrid/Tech/FM), přes offline souborovou cestu (žádná závislost na flaky OmniRoute/Producer-Pal/Ableton řetězci z failed-session logu). Každý generátor běžně produkuje dvojí výstup: preset bytes + feature vektor — tak M1 funguje i jako továrna na trénovací data pro M2/M3.

SPARC TDD aplikováno: foundation (feature vektor) je testována round-tripem, každý archetyp má contract test, stdio most má JSON contract test.

Milníky (sekvenčně, každý má testy)
M1.1 — Feature-vector infrastruktura (základ)
Soubor: neuroman/tools/feature_vector.py (nový)

Schema definice nad existujícím KNOWN_PARAMS (27) + FX_TYPES (16). Feature vektor = seřazená float/one-hot reprezentace modulů: Oscillátory (0-2), VoiceFilter0, LFO0-1, ModSlot0, FX chain (typ + klíčové parametry na 6 pozicích).
API: to_feature_vector(cbor_dict) -> np.ndarray, from_feature_vector(vec) -> {params, fx_chain} kompatibilní s build_preset.
Categorical handling: oscilátor typ, filter typ (LB12 atd.), warp mode, FX typ = one-hot; kontinuální = normalizované float; booleans = 0.0/1.0.
Tests (tests/test_feature_vector.py): round-trip (decode existující preset → vektor → reconstruct → shoda v mapovaných parametrech), determinismus, schema validace, známý preset → známý vektor.
Závislost: přidat numpy>=1.24 do neuroman/requirements.txt.
M1.2 — Pravidlový generátor + archetypy
Soubory: neuroman/tools/preset_archetypes.py + neuroman/tools/preset_generator.py (nové)

5 archetypů odvozených z references/bass-engineering.md, každý jako {name, params, fx_chain} šablona (struktura identická se build_skullstep_lead):
Growl — synced LFO + filter movement + controlled distortion
Reese — vysoký detune + unison, beating/fáze, distortion po filtru
Hybrid — reese body + growl artikulace
Tech/FM — FM (FM(B) warp mode) + comb/band-reject filter
Pad — dlouhé env, chorus+reverb, nízký rezonance
Variace = váhovaná náhoda v rámci "zní-dobře" rozsahů (seed-controlled pro reprodukovatelnost). Rozsahy z bass-engineering.md rozhodovacích stromů.
generate(archetype, seed=None, variation=0.5) → vrací (preset_bytes, feature_vector, meta) — používá existující build_preset (dědí warp sub-moduly ze šablony, takže ty fungují).
Vyhnutí se mod-matrix: místo ModSlot routing (klíče neznámé — TODO v skullstep) používá LFO-as-envelope + přímé parametry. Mod-matrix označen jako M2 stretch goal.
Tests (tests/test_preset_generator.py): každý archetyp → round-trip přes decode_preset (validní soubor), očekávané moduly přítomny, FX chain validní (každá make_fx_item má známý typ id), stejný seed = stejný výstup, feature vektor se shoduje s to_feature_vector(generated).
M1.3 — Stdio most + API endpoint
Soubory: rozšířit neuroman/tools/preset_generator.py (CLI --stdio), rozšířit server/api.js

Stdio CLI: python -m neuroman.tools.preset_generator --stdio čte JSON z stdin {archetype, seed, variation, output_path}, píše jednu JSON řádku na stdout {ok, path, feature_vector, meta}. Zrcadlí callAnalyzer pattern (api.js:443-510).
Endpointy v server/api.js:
POST /api/preset/generate — spawn Python generátor, zapíše .SerumPreset do paths.presets, persistuje meta přes data-layer.savePreset, broadcast přes WS ({channel:'npos', type:'preset-generated'}).
GET /api/preset/archetypes — vrátí seznam archetypů + jejich popisy.
Traversal guard (api.js:517-521) na output_path; try/catch + res.status(500).
Tests: stdio JSON contract (požadavek → tvar odpovědi), error handling (neznámý archetyp, špatný seed).
M1.4 — UI + extrakce korpusu
Soubory: web/src/pages/presets/generate.astro (nový), scripts/_extract_corpus.py (nový)

UI panel (generate.astro) — selektor archetypu (z /api/preset/archetypes), slider variace (0-1), seed input, tlačítko Generate → POST /api/preset/generate. Výsledná karta ukazuje jméno + feature vektor (heatmap) + download link. Styl .hud-panel jako audio-analysis panel (index.astro:60-74). Progress přes existující /ws.
_extract_corpus.py — batch: decode_preset přes každý .SerumPreset v external.serum2Presets, extrahuje feature vektor + category hint, zapíše data/preset_corpus.jsonl. Toto je trénovací set pro M2.
Bonus fix: web/src/pages/presets/index.astro filtruje .serum/.xsr ale Serum 2 soubory jsou .SerumPreset — opravit filtr, aby něco zobrazil.
M1.5 — Dependency hygiene + konfigurace
neuroman/requirements.txt: doplnit chybějící zstandard, cbor2 (latent breakage dnes) + numpy>=1.24, scikit-learn>=1.3 (pro M1.4 clustering ladění). Žádný torch v M1.
npos.config.json: naplnit external.serum2Presets: "D:/VST/Xfer/Serum 2 Presets/Presets", přidat blok ai.presetGenerator: { device: "cpu", modelDir: "./data/preset-models", maxVariation: 1.0 }.
web/src/lib/config.ts: zrcadlit nový blok.
pyproject.toml: přidat [project] deps tabulku (NPOS-Analysis-Findings.md:85 flags chybějící).
Otevřená rizika (honest)
Mod-matrix routing klíče neznámé — M1 je obchází (LFO-as-envelope). Objev přes diff_params je explicitní M2 úkol.
Float kalibrace (detune/freq) je odhadnuta — laděno uchem proti Skullstep referenci, dokumentováno v komentářích.
Oscillator type omezen na Wavetable v M1 (ostatní 4 enginy — Multisample/Sample/Granular/Spectral — vyžadují víc reverse-engineeringu).
Korpus presetů musí být lokálně dostupný na D:\VST\Xfer\Serum 2 Presets\Presets (scannery ho tam hardcodují); pokud chybí, _extract_corpus.py ohlásí a M2 bude potřebovat naplnit.
Akční kroky po schválení
M1.1 → M1.2 → M1.3 → M1.4 → M1.5 (každý s testy před implementací).
Začnu feature-vector modulem (nejtestovatelnější, závisí na něm vše).
Po M1.5 bude M1 hotový a zároveň připravený trénovací set pro M2 (statistický) / M3 (neural).
Implementační poznámka: všechny nové Python soubory dodrží pyproject.toml Ruff pravidla (py311, single quotes, 120 znaků). Node kód zrcadlí callAnalyzer stdio pattern. UI používá existující HUD design systém.