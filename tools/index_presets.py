#!/usr/bin/env python3
"""index_presets.py — projde složku `.SerumPreset` a vyrobí kompaktní index pro repo.

Index (jeden JSON na řádek) nese jen metadata a přečtené „stopy“ (cues): počet aktivních oscilátorů, unison,
cross-osc warp, tiché modulátory, LFO → filtr, mono, délku FX řetězu. Žádný výpis parametrů — plný
`reading` jde volitelně do `--dump-dir`, který patří mimo git (`data/presets/_local/`), protože presety
z placených packů se nesdílejí.

Stopy jsou `preset_file` (přečtené ze souboru). Funkce a archetyp jsou **návrh** z heuristiky
(jméno presetu + stopy) a nesou `confidence: hypothesis`; potvrzuje je člověk poslechem nebo A/B v Serumu.

Použití:
  py -3.12 tools/index_presets.py ROOT --source-id letsynthesize-preset-files \\
      --out data/presets/index/letsynthesize-preset-files.jsonl --dump-dir data/presets/_local/letsynthesize
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
import analyze_preset as ap  # noqa: E402

# (funkce vrstvy, regex na jméno) — první shoda vyhrává
NAME_RULES = [
    ("other", r"kick|snare|clap|drums|perc|hat"),
    ("fx", r"riser|buildup|scream|drunk|breathfx|foley|sweep|impact"),
    ("pad", r"pad|atmos|drone|strings|soft|chord"),
    ("lead", r"lead|lazer|robot|idiot|funky|pulse|pluck|(^|[\s_])ld([\s_]|$)"),
    ("other", r"guitar"),
    ("sub", r"\bsub\b|compressed sine|distorted sine"),
    ("body", r"bass|reese|neuro|nruo|stab|annihilation|weird|screechy|metallic|noise|synth layer|thing|growl|wobble"
             r"|(^|[\s_])bs([\s_]|$)"),
]
# jemnější role (návrh z jména, první shoda vyhrává; `hypothesis` jako function/archetype)
# Prefixy balíků: BA_ = bass, SY_ = syntezátor, PD_ = pad, FX_ = fx, DR_ = bicí (Burr Oak); "BA ..." a "TKpatreon" u dalších.
ROLE_RULES = [
    ("perc", r"kick|\bkik\b|snare|clap|drums|perc|hats?\b|toms|cymbal|^dr[_ ]"),
    ("fx", r"riser|buildup|scream|drunk|breathfx|foley|sweep|impact|rattle|^fx[_ ]|^fx$|transition|reverse"),
    ("chords", r"chord"),
    ("pluck", r"pluck"),
    ("pad", r"pad|atmos|drone|strings|soft|^pd[_ ]"),
    ("guitar", r"guitar"),
    ("sub", r"\bsub\b|compressed sine|distorted sine|sinus"),
    ("reese", r"reese"),
    ("neuro", r"neuro|nruo|wobble|growl"),
    ("stab", r"stab"),
    ("seq", r"\barp\b|\bseq\b|\bmel\b|sequence"),
    ("lead", r"lead|lazer|robot|idiot|funky|pulse|(^|[\s_])ld([\s_]|$)"),
    ("bass", r"bass|(^|[\s_])bs([\s_]|$)|bassline|^ba([_ ]|$)|\b808\b|^serum preset ba\b|^patreon bass"),
    ("synth", r"^sy[_ ]"),
    ("layer", r"layer|synth|weird|screechy|metallic|thing|noise|annihilation"),
]


def role_of(name: str) -> str:
    n = name.lower()
    return next((r for r, pat in ROLE_RULES if re.search(pat, n)), "other")


CROSS_WARP = ("_OSC", "_OSC2", "_SUB", "_NOISE")


def cues(a: dict[str, Any]) -> dict[str, Any]:
    r = a["reading"]
    on = [o for o in r["oscillators"] if o["enabled"]]
    warps = {o.get("kind_params", {}).get(k) for o in on for k in ("kParamWarpMenu", "kParamWarpMenu2")}
    cross = sorted(w for w in warps if isinstance(w, str) and (w.endswith(CROSS_WARP) or w == "kSync"))
    mods = r["modulation"]
    # hlasitost 0 + modulace hlasitosti (LFO/obálka ji otevírá) = oscilátor hraje, není tichý
    vol_mod = {m["dest_module_id"] for m in mods if m["dest_module"] == "Oscillator" and m["dest_param"] == "kParamVolume"}
    silent = [o for o in on if o["slot"] <= 2 and o["params"].get("kParamVolume") == 0.0 and o["slot"] not in vol_mod]
    audible = [o for o in on if o["slot"] <= 2 and o not in silent]
    fine_mods = [m["amount"] for m in mods if m["dest_module"] == "Oscillator" and m["dest_param"] == "kParamFine"
                 and isinstance(m["amount"], (int, float))]
    fine_by_oct: dict[Any, set] = {}
    for o in audible:
        fine_by_oct.setdefault(o["params"].get("kParamOctave", 0.0), set()).add(o["params"].get("kParamFine", 0.0))
    return {
        "active_osc": sum(1 for o in on if o["slot"] <= 2),   # wavetable osc A–C; Noise (slot 3) and Sub (slot 4) separately
        "noise": any(o["slot"] == 3 for o in on),
        "sub": any(o["slot"] == 4 for o in on),
        "max_unison": max((o["unison_voices"] for o in on), default=1),
        "cross_warp": cross,
        # zapnutý hlavní oscilátor (slot 0–2) s hlasitostí 0 a bez modulace hlasitosti: nehraje, jen moduluje
        # (čtení ze souboru, neověřeno A/B v Serumu)
        "silent_mod_osc": len(silent),
        # reese ze dvou oscilátorů: protisměrná modulace Fine, nebo různé Fine u slyšitelných osc ve stejné oktávě
        "fine_spread": (any(a > 0 for a in fine_mods) and any(a < 0 for a in fine_mods))
                       or any(len(v) > 1 for v in fine_by_oct.values()),
        "lfo_to_filter": any(m["source"].startswith("LFO") and m["dest_module"] == "VoiceFilter" for m in r["modulation"]),
        "mod_slots": len(r["modulation"]),
        "mono": r["voice"].get("kParamMonoToggle") == 1.0,
        "fx_count": len(r["fx"]),
    }


def propose(name: str, c: dict[str, Any]) -> tuple[str, str, list[str]]:
    """Návrh (function, archetype, why). Archetyp jen ze slovníku seed + kandidát osc-warp-body."""
    n = name.lower()
    func = next((f for f, pat in NAME_RULES if re.search(pat, n)), "other")
    why = [f"jméno → {func}"]
    if func == "body" and "sub" in n:
        func = "sub"
    arch = "unclassified"
    if func == "sub":
        arch = "clean-sub-sine"
    elif func == "body":
        if any("FM" in w for w in c["cross_warp"]):
            arch = "fm-distorted-body"; why.append("FM z jiného oscilátoru")
        elif c["silent_mod_osc"] and any(w.startswith(("kPD", "kAM", "kRM")) or w == "kSync" for w in c["cross_warp"]):
            arch = "osc-warp-body"; why.append("tichý modulátor → " + ",".join(c["cross_warp"]))
        elif c["fine_spread"]:
            arch = "detuned-unison-reese"; why.append("rozladění Fine mezi oscilátory")
        elif c["max_unison"] >= 3 and not c["lfo_to_filter"]:
            arch = "detuned-unison-reese"; why.append(f"unison {c['max_unison']}")
        if c["lfo_to_filter"]:
            why.append("LFO → filtr (mřížka ze souboru neověřitelná)")
    return func, arch, why


def collect(paths: list[Path]) -> list[tuple[Path, str]]:
    """Složka → všechny presety (skupina = první podsložka); soubor → sám (skupina = jeho složka)."""
    out = []
    for p in paths:
        if p.is_dir():
            for f in sorted(x for x in p.rglob("*.SerumPreset") if not x.name.startswith("._")):
                rel = f.relative_to(p)
                out.append((f, rel.parts[0] if len(rel.parts) > 1 else ""))
        else:
            out.append((p, p.parent.name))
    return out


def index(root: Path | list[Path], source_id: str, dump_dir: Path | None) -> tuple[list[dict[str, Any]], list[str]]:
    rows, full, bad = [], [], []
    for f, group in collect(root if isinstance(root, list) else [root]):
        try:
            a = ap.analyze(f, source_id=source_id)
        except (ValueError, OSError) as e:
            bad.append(f"{f.name}: {e}")
            continue
        pid = ap.slugify(f"{source_id}-{group[:32]}-{a['name']}")
        c = cues(a)
        func, arch, why = propose(a["name"], c)
        rows.append({"id": pid, "source_id": source_id, "name": a["name"], "group": group, "file": f.name,
                     "synth": a["synth"], "tags": a["tags"], "function": func, "role": role_of(a["name"]), "archetype": arch,
                     "confidence": "hypothesis", "cues_basis": "preset_file", "cues": c, "why": why,
                     "fx_chain": a["fx_chain"]})
        full.append(a)
    ids = collections.Counter(r["id"] for r in rows)
    for r in rows:  # duplicitní jména ve stejné skupině
        if ids[r["id"]] > 1:
            r["id"] = ap.slugify(f"{r['id']}-{Path(r['file']).stem}")
    if dump_dir:
        dump_dir.mkdir(parents=True, exist_ok=True)
        for r, a in zip(rows, full):
            a.update(id=r["id"], function=r["function"], role=r["role"], archetype=r["archetype"])
            (dump_dir / f"{r['id']}.json").write_text(json.dumps(a, ensure_ascii=False, indent=2) + "\n",
                                                      encoding="utf-8", newline="\n")
    return rows, bad


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description="Kompaktní index složky .SerumPreset (návrhy = hypothesis).")
    p.add_argument("paths", type=Path, nargs="+", help="složka packu nebo jednotlivé .SerumPreset soubory")
    p.add_argument("--source-id", required=True)
    p.add_argument("--out", type=Path, required=True, help="JSONL index (do repa)")
    p.add_argument("--dump-dir", type=Path, default=None, help="plné analýzy (mimo git)")
    args = p.parse_args(argv)
    rows, bad = index(args.paths, args.source_id, args.dump_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="\n")
    print(f"{len(rows)} presetů → {args.out}" + (f", dumpy → {args.dump_dir}" if args.dump_dir else ""))
    print("návrhy:", collections.Counter((r["function"], r["archetype"]) for r in rows).most_common())
    for b in bad:
        print("chyba:", b, file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
