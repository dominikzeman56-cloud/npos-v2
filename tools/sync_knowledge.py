#!/usr/bin/env python3
"""sync_knowledge.py - vygeneruje knowledge/ (krome sources.jsonl) z kanonu ve vaultu.

Vault (Obsidian) je zdroj pravdy pro lidsky kanon (10 Principy, 20 Basa, 50 Producenti,
30 Aranz); soubory v knowledge/ se z nej generuji a rucne se needituji.
Cesta k vaultu: env NPOS_VAULT, vychozi D:/ObsidianVault/Hudební produkce (viz DEFAULT_VAULT).
Registr zdroju knowledge/sources.jsonl se edituje rucne. Po generovani: python tools/check_repo.py
"""
import re, os, json
from pathlib import Path
DEFAULT_VAULT = r"D:\ObsidianVault\Hudební produkce"
V = os.environ.get("NPOS_VAULT", DEFAULT_VAULT)
K = str(Path(__file__).resolve().parent.parent / "knowledge")
DATE = "2026-10-15"

def rd(n):
    return open(os.path.join(V, n), encoding="utf-8").read()

def unlink(t):
    t = re.sub(r"\[\[([^\]|]*)\|([^\]]*)\]\]", r"\2", t)
    def plain(target):  # "40 Mix a master#2. Tři výstupy" -> "40 Mix a master, kap. 2. Tři výstupy"
        note, _, head = target.partition("#")
        note = note.split("/")[-1].replace("_", " ")
        return f"{note}, kap. {head}" if head else note
    t = re.sub(r"\[\[([^\]]*)\]\]", lambda m: plain(m.group(1)), t)
    return t

def fm(d):
    out = ["---"]
    for k, v in d.items():
        if isinstance(v, list):
            out.append(f"{k}: [{', '.join(v)}]")
        elif v is None:
            continue
        else:
            sv = str(v)
            if re.search(r"[:#\[\]{}]", sv) and not sv.startswith('"'):
                sv = json.dumps(sv, ensure_ascii=False)
            out.append(f"{k}: {sv}")
    out.append("---")
    return "\n".join(out) + "\n"

def write(rel, meta, body):
    p = os.path.join(K, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(fm(meta) + "\n" + body.strip() + "\n")

def sections(text, level):
    pat = re.compile(r"^" + "#" * level + r" (.+)$", re.M)
    ms = list(pat.finditer(text))
    out = []
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        # stop at next higher-level heading or hr
        body = text[m.end():end]
        body = re.split(r"\n---\n|\n## ", body)[0]
        out.append((m.group(1).strip(), body.strip()))
    return out

NOTE = "\n\n> Strojově čitelná kopie z vaultu (`Hudební produkce`). Zdroje: `knowledge/sources.jsonl`. Neupravuj ručně — změny se dělají ve vaultu a regenerují.\n"

# ---------- principles ----------
pr = rd("10 Principy.md")
P = [
    ("p1-decision-system", "P1", "canon", "estimated", "consensus", "personal_observation", ["ed-rush-killbox-valkyrie-podcast", "ableton-template-final"]),
    ("p2-mixdown-from-first-second", "P2", "canon", "measured", "consensus", "producer_course", ["redpill-manual", "audio-headroom-2013", "letsynthesize-noisia-course", "pythius-template-workflow", "abis-start-to-finish"]),
    ("p3-midi-then-resample-deliberately", "P3", "canon", "measured", "conditional", "producer_course", ["redpill-manual", "audio-headroom-2013", "joe-ford-bassgorilla-course", "pythius-inquisition", "abis-start-to-finish", "letsynthesize-noisia-course"]),
    ("p4-one-layer-one-function", "P4", "canon", "measured", "consensus", "producer_course", ["letsynthesize-noisia-course", "pythius-template-workflow", "ekwols-reese-layering", "phenom-layering", "dont-play-skeleton"]),
    ("p5-producers-are-philosophy", "P5", "canon", "measured", "school", "producer_course", ["mefjus-remix-another-life", "letsynthesize-noisia-course", "ed-rush-killbox-valkyrie-podcast"]),
    ("p6-every-claim-carries-confidence", "P6", "canon", "measured", "consensus", "track_analysis", ["dont-play-skeleton", "grok-memory-dogma-critique"]),
    ("p7-measure-where-measurement-holds", "P7", "canon", "measured", "consensus", "track_analysis", ["dont-play-skeleton", "breach-balron-audio", "sinister-souls-raido-restless"]),
    ("p8-intent-over-transcription", "P8", "canon", "measured", "consensus", "track_analysis", ["dont-play-skeleton", "sinister-souls-raido-restless", "triamer-nagato-hands-up", "prolix-been-about-this"]),
    ("p9-values-are-starting-points", "P9", "canon", "measured", "consensus", "producer_course", ["audio-headroom-2013", "ableton-template-final", "grok-memory-dogma-critique"]),
]
secs = {t.split(" · ")[0]: (t, b) for t, b in sections(pr, 3) if re.match(r"P\d ·", t)}
for slug, pid, status, conf, label, stype, srcs in P:
    t, b = secs[pid]
    meta = {"id": slug, "type": "principle", "title": t, "status": status, "rule_label": label,
            "confidence": conf, "source_type": stype, "source_ids": srcs,
            "vault_note": "10 Principy", "updated": DATE}
    write(f"principles/{slug}.md", meta, f"# {t}\n\n" + unlink(b) + NOTE)

M = [
    ("decision-heuristics", "2.1", "conditional", "estimated", "personal_observation", []),
    ("layer-separation-bass", "2.2", "canon", "estimated", "producer_course", ["letsynthesize-noisia-course", "pythius-template-workflow", "dont-play-skeleton", "breach-balron-audio"]),
    ("reese-detuning-and-body-design", "2.3", "canon", "measured", "producer_course", ["abis-reese-fm-masterclass", "pythius-reese-tutorial", "phenom-roar"]),
    ("sidechain-trigger-template", "2.4", "canon", "measured", "producer_course", ["abis-start-to-finish", "joe-ford-bassgorilla-course", "pythius-template-workflow"]),
    ("preset-analysis-method", "2.5", "conditional", "estimated", "personal_observation", []),
    ("vocal-texture-and-foreshadowing", "2.6", "canon", "measured", "producer_course", ["abis-intro-vocal", "abis-start-to-finish", "pythius-template-workflow"]),
]
msecs = {t.split(" ")[0]: (t, b) for t, b in sections(pr, 3) if re.match(r"2\.\d ", t)}
for slug, num, status, conf, stype, srcs in M:
    t, b = msecs[num]
    t = t[len(num):].strip()
    meta = {"id": slug, "type": "method", "title": t, "status": status, "confidence": conf,
            "source_type": stype, "source_ids": srcs, "vault_note": "10 Principy", "updated": DATE}
    write(f"principles/{slug}.md", meta, f"# {t}\n\n" + unlink(b) + NOTE)

# candidates
cand = pr[pr.index("## 3. Kandidáti"):pr.index("## 4. Povyšování")]
cand = cand.split("\n---\n")[0]  # oddělovač sekce, ne |---| v tabulce
write("principles/candidates.md",
      {"id": "candidates", "type": "candidate", "title": "Kandidáti na nové principy", "status": "candidate",
       "confidence": "estimated", "source_type": "producer_course",
       "source_ids": ["pythius-inquisition", "joe-ford-bassgorilla-course", "letsynthesize-noisia-course", "abis-start-to-finish",
                      "audio-headroom-2013", "phenom-layering", "dont-play-skeleton", "prolix-been-about-this", "breach-balron-audio",
                      "redpill-manual", "ed-rush-killbox-valkyrie-podcast", "ekwols-reese-layering",
                      "letsynthesize-preset-files", "pythius-patreon-presets", "enta-serum-presets", "notequal-serum-presets"],
       "vault_note": "10 Principy", "updated": DATE},
      "# Kandidáti na nové principy\n\n" + unlink(cand.replace("## 3. Kandidáti na nové principy", "").strip()) + NOTE)

write("principles/README.md",
      {"id": "principles-index", "type": "index", "title": "Principy — rozcestník", "status": "canon",
       "confidence": "measured", "source_type": "other", "source_ids": [], "updated": DATE},
      """# Principy — rozcestník

Devět principů NPOS (P1–P9; závazné znění v `docs/BLUEPRINT.md`, kap. 4), šest metod z vrstvy 1 a kandidáti.

| Soubor | Co |
|---|---|
| `p1` … `p9` | principy NPOS s důkazy, mezemi a použitím v session |
| `decision-heuristics` | nejdřív odečíst, pak přidat |
| `layer-separation-bass` | pořadí sub → body → movement → noise/texture |
| `reese-detuning-and-body-design` | fázová fyzika reese, pořadí distorze |
| `sidechain-trigger-template` | dva tiché MIDI spouštěče |
| `preset-analysis-method` | analýza presetu = strategie, ne parametry |
| `vocal-texture-and-foreshadowing` | předznamenání dropu |
| `candidates` | kandidáti, kteří čekají na ověření v datech |

Povyšování a degradace: `docs/KNOWLEDGE_PIPELINE.md`. Lidská podoba: vault `10 Principy`.""")

# ---------- producers ----------
pd = rd("50 Producenti.md")
prof = {t: b for t, b in sections(pd, 3)}
# skip the blockquote note, studijní tracky
PRODS = [
    ("Abis", "abis", "measured", "producer_course", ["abis-reese-fm-masterclass", "abis-start-to-finish", "abis-grains-of-sooner", "abis-dnb-academy-tune"]),
    ("Pythius", "pythius", "measured", "producer_course", ["pythius-template-workflow", "pythius-inquisition", "pythius-fearless-remix", "pythius-reese-tutorial"]),
    ("Mefjus", "mefjus", "measured", "producer_course", ["mefjus-remix-another-life", "mefjus-zenith-track-insights"]),
    ("Noisia (a styl podle kurzu Letsynthesize)", "noisia", "estimated", "producer_course", ["letsynthesize-noisia-course", "letsynthesize-noisia-projects"]),
    ("Audio (Gareth)", "audio-gareth", "measured", "producer_course", ["audio-headroom-2013", "dont-play-skeleton"]),
    ("Ed Rush & Killbox", "ed-rush-killbox", "measured", "interview", ["ed-rush-killbox-valkyrie-podcast"]),
    ("Redpill", "redpill", "measured", "producer_course", ["redpill-manual"]),
    ("Joe Ford", "joe-ford", "estimated", "ableton_project", ["joe-ford-bassgorilla-course"]),
    ("Magnetude", "magnetude", "estimated", "producer_course", ["magnetude-neuro-basses"]),
    ("Ekwols", "ekwols", "measured", "track_analysis", ["ekwols-reese-layering", "ekwols-stab-accent", "ekwols-harmonic-chord"]),
    ("Burr Oak", "burr-oak", "measured", "track_analysis", ["burr-oak-harmonic-growl"]),
    ("Prolix & Figure", "prolix-figure", "measured", "track_analysis", ["prolix-been-about-this"]),
    ("Neonlight", "neonlight", "measured", "producer_course", ["neonlight-bass-filth"]),
    ("Phenom", "phenom", "measured", "producer_course", ["phenom-roar", "phenom-layering"]),
    ("Skullstep", "skullstep", "estimated", "producer_course", ["skullstep-rave-lead"]),
]
for name, slug, conf, stype, srcs in PRODS:
    body = prof[name].split("\n> **Black Sun")[0].strip()
    meta = {"id": f"producer-{slug}", "type": "producer", "title": name, "status": "canon",
            "confidence": conf, "source_type": stype, "source_ids": srcs,
            "vault_note": "50 Producenti", "updated": DATE}
    write(f"producers/{slug}.md", meta, f"# {name}\n\n" + unlink(body) + NOTE)

write("producers/README.md",
      {"id": "producers-index", "type": "index", "title": "Producenti — rozcestník", "status": "canon",
       "confidence": "measured", "source_type": "other", "source_ids": [], "updated": DATE},
      """# Producenti — rozcestník

Filozofie, ne životopisy. Každý profil: co rozhoduje a proč · rozhodnutí s jistotou · co nekopírovat · ověřené reference · zdroje.

**Pravidlo pravdivosti:** profil nese jen to, co je doložené v `sources.jsonl`. Producent bez zdroje profil nemá (původní generické profily Black Sun Empire, Aggressor Bunx a další byly odstraněny).

| Profil | Jistota | Typ zdroje |
""" + "\n".join(f"| [{n}]({s}.md) | `{c}` | `{t}` |" for n, s, c, t, _ in PRODS))

# ---------- archetypes ----------
zm = rd("20 Basa.md")
a = zm[zm.index("## 3. Archetypy basů"):zm.index("## 4. Pohyb")].split("\n---\n")[0]
a = a.replace("## 3. Archetypy basů", "").strip()
write("archetypes/bass.md",
      {"id": "archetypes-bass", "type": "archetype", "title": "Archetypy basů", "status": "canon",
       "confidence": "measured", "source_type": "track_analysis",
       "source_ids": ["abis-reese-fm-masterclass", "pythius-reese-tutorial", "pythius-fearless-remix", "phenom-roar", "letsynthesize-noisia-course",
                      "magnetude-neuro-basses", "burr-oak-harmonic-growl", "ekwols-reese-layering", "prolix-been-about-this",
                      "letsynthesize-preset-files", "pythius-patreon-presets", "enta-serum-presets", "notequal-serum-presets"],
       "vault_note": "20 Basa", "updated": DATE},
      "# Archetypy basů\n\nSeed (řádky 1–5) je v kontraktu BLUEPRINT kap. 5; řádky 6–16 jsou **kandidáti** — do slovníku se povyšují až po opakování v datech.\n\n" + unlink(a) + NOTE)

write("archetypes/README.md",
      {"id": "archetypes-index", "type": "index", "title": "Archetypy — rozcestník", "status": "canon",
       "confidence": "measured", "source_type": "other", "source_ids": [], "updated": DATE},
      """# Archetypy

Slovník archetypů se rozšiřuje **jen tím, co se opakuje v datech** (`data/tracks`, `data/presets`). Seed: `grid-locked-filter-growl` · `slow-grid-growl` · `detuned-unison-reese` · `fm-distorted-body` · `clean-sub-sine` · `serum-overlay-chords`.

Aktuálně: [`bass.md`](bass.md) — 16 archetypů basy s receptem, zdrojem a jistotou (5 seed, 11 kandidátů).

Návrhy archetypů pro presety z packů jsou v `data/presets/index/*.jsonl` (`tools/index_presets.py`, vždy `hypothesis`).""")

# ---------- guides ----------
def strip_frontmatter(t):
    if t.startswith("---"):
        e = t.find("\n---", 3)
        if e > 0:
            return t[e + 4:].lstrip("\n")
    return t


ga = strip_frontmatter(rd("30 Aranž.md"))
ga = re.split(r"\n## Zdroje\b", ga)[0]  # seznam wikilinků zdrojů je v source_ids
write("guides/arrangement.md",
      {"id": "guide-arrangement", "type": "guide", "title": "Návod na aranž", "status": "canon",
       "confidence": "measured", "source_type": "track_analysis",
       "source_ids": ["dont-play-skeleton", "prolix-been-about-this", "sinister-souls-raido-restless",
                      "triamer-nagato-hands-up", "tr-tactics-mechanism", "dirts-remix-skeleton", "breach-balron-audio",
                      "letsynthesize-noisia-course", "abis-start-to-finish", "abis-grains-of-sooner",
                      "pythius-fearless-remix", "pythius-inquisition", "pythius-template-workflow",
                      "mefjus-remix-another-life", "audio-headroom-2013",
                      "ed-rush-killbox-valkyrie-podcast", "redpill-manual"],
       "vault_note": "30 Aranž", "updated": DATE},
      unlink(ga) + NOTE)
write("guides/README.md",
      {"id": "guides-index", "type": "index", "title": "Návody — rozcestník", "status": "canon",
       "confidence": "measured", "source_type": "other", "source_ids": [], "updated": DATE},
      """# Návody

Postupy vytěžené ze všech rozborů (vrstva 1) do jedné použitelné podoby. Každý bod nese zdroj a štítek jistoty.

| Soubor | Co |
|---|---|
| [`arrangement.md`](arrangement.md) | aranž: energie, formy, sekce po sekci, druhý drop, breakdown, outro, remix, kostry, kontrolní seznam |
""")

print("generated")
