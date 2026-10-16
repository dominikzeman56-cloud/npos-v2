#!/usr/bin/env python3
"""check_presets.py — kontrola konzistence dat presetů v `data/presets/` (to, co check_repo.py nehlídá).

Kontroluje:
  - id jsou unikátní napříč `index/` a `fxp/` (dřív tu bylo 15 duplicitních dvojic bez povšimnutí),
  - `features/`, `audio*/` a `roles/` odkazují jen na existující id, každé id nanejvýš jednou na soubor,
  - hodnoty features a deskriptorů jsou čísla (nebo null/bool a pár známých textových polí),
  - v `fxp/` není stejný `container.sha256` dvakrát (jeden soubor = jeden řádek napříč složkami),
  - řádky čtené `serum1_host` mají modulaci (zdroj, cíl, mono LFO/obálek, křivky) `null`, ne nulu: ta se z S1 nečte,
  - v commitovaných souborech nejsou lokální cesty ani jména `.wav` (placené packy, soukromé cesty).
Použití: py -3.12 tools/check_presets.py [--root data/presets]   (nenulový kód = chyba)
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEXT_OK = {"am_grid", "window"}
# co z Serum 1 přes hostovaný plugin neznáme: musí být null (0 by tvrdilo, že preset nic nemoduluje)
S1_UNKNOWN_FEATURES = ("mod_lfo", "mod_env", "mod_macro", "mod_to_osc", "mod_to_filter", "lfo_curves", "lfo_points", "env_count", "macro_count")
S1_UNKNOWN_CUES = ("lfo_to_filter", "silent_mod_osc")
LEAK = re.compile(r"[A-Za-z]:[\\/]{1,2}(?:Users|samples|Dev|VST|Ableton)|\.wav\b", re.I)


def load(p: Path) -> list[dict]:
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def check(root: Path) -> list[str]:
    errs: list[str] = []
    ids: dict[str, str] = {}
    for d in ("index", "fxp"):
        for f in sorted((root / d).glob("*.jsonl")):
            for r in load(f):
                if r["id"] in ids:
                    errs.append(f"{d}/{f.name}: duplicitní id {r['id']} (už v {ids[r['id']]})")
                ids[r["id"]] = f"{d}/{f.name}"
    sha: dict[str, str] = {}
    for f in sorted((root / "fxp").glob("*.jsonl")):
        for r in load(f):
            h = (r.get("container") or {}).get("sha256")
            if h and h in sha and sha[h] != r["id"]:
                errs.append(f"fxp/{f.name}: {r['id']} má stejný sha256 jako {sha[h]}")
            elif h:
                sha[h] = r["id"]
            if r.get("reader") == "serum1_host":
                errs += [f"fxp/{f.name}: {r['id']}.cues.{k} má být null u serum1_host ({r['cues'][k]!r})"
                         for k in S1_UNKNOWN_CUES if (r.get("cues") or {}).get(k) is not None]
    for d, field in (("features", "features"), ("roles", None)):
        for f in sorted((root / d).glob("*.jsonl")):
            seen = collections.Counter()
            for r in load(f):
                seen[r["id"]] += 1
                if r["id"] not in ids:
                    errs.append(f"{d}/{f.name}: neznámé id {r['id']}")
                if field and r.get("reader") == "serum1_host":
                    errs += [f"{d}/{f.name}: {r['id']}.{k} má být null u serum1_host ({r[field][k]!r})"
                             for k in S1_UNKNOWN_FEATURES if r.get(field, {}).get(k) is not None]
                if field:
                    for k, v in r.get(field, {}).items():
                        if v is not None and not isinstance(v, (int, float)):
                            errs.append(f"{d}/{f.name}: {r['id']}.{k} není číslo ({v!r})")
            errs += [f"{d}/{f.name}: id {i} {n}×" for i, n in seen.items() if n > 1]
    for adir in sorted(p for p in root.glob("audio*") if p.is_dir()):
        for f in sorted(adir.glob("*.jsonl")):
            seen = collections.Counter()
            for r in load(f):
                seen[r["id"]] += 1
                if r["id"] not in ids:
                    errs.append(f"{adir.name}/{f.name}: neznámé id {r['id']}")
                if not isinstance(r.get("protocol"), dict) or "note" not in r["protocol"]:
                    errs.append(f"{adir.name}/{f.name}: {r['id']} bez protokolu renderu")
                for k, v in r.get("audio", {}).items():
                    if v is None or isinstance(v, (bool, int, float)) or (k in TEXT_OK and isinstance(v, str)):
                        continue
                    errs.append(f"{adir.name}/{f.name}: {r['id']}.{k} nečekaný typ ({v!r})")
            errs += [f"{adir.name}/{f.name}: id {i} {n}×" for i, n in seen.items() if n > 1]
    for f in sorted(root.rglob("*.jsonl")):
        if "_local" in f.parts or "analyzed" in f.parts:
            continue
        m = LEAK.search(f.read_text(encoding="utf-8"))
        if m:
            errs.append(f"{f.relative_to(root)}: lokální cesta nebo .wav v commitovaném souboru ({m.group(0)!r})")
    return errs


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", type=Path, default=REPO / "data" / "presets")
    a = p.parse_args(argv)
    errs = check(a.root)
    for e in errs[:50]:
        print("ERROR:", e)
    print(f"presety: {len(errs)} chyb")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
