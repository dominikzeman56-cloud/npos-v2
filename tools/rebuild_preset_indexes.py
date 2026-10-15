#!/usr/bin/env python3
"""rebuild_preset_indexes.py — hromadně přeindexuje všechny packy presetů z `_sources/presets/<source_id>/`.

Zdrojová složka vzniká přes `tools/collect_local_sources.py`. Pro každý pack:
  - spočítá kompaktní index (`tools/index_presets.py`),
  - porovná ho s committed `data/presets/index/<source_id>.jsonl` (stejná id, stejné cues/funkce/archetyp),
  - s `--write` index přepíše a plné dumpy uloží do `data/presets/_local/` (mimo git).

Bez `--write` nic nezapisuje a vrací kód 1, pokud se nějaký index liší (hodí se jako kontrola po změně heuristik).

Použití:
  py -3.12 tools/rebuild_preset_indexes.py              # jen porovná
  py -3.12 tools/rebuild_preset_indexes.py --write      # přepíše indexy a dumpy
  py -3.12 tools/rebuild_preset_indexes.py --only letsynthesize-preset-files
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import index_presets as ip  # noqa: E402

# složky plných dumpů mimo git (zpětná kompatibilita s dřívějšími názvy)
DUMP_DIR = {"letsynthesize-preset-files": "letsynthesize"}
COMPARE = ("id", "name", "group", "function", "archetype", "confidence", "cues", "fx_chain")


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def diff(old: list[dict], new: list[dict]) -> list[str]:
    o = {r["id"]: r for r in old}
    n = {r["id"]: r for r in new}
    out = [f"chybí v novém: {i}" for i in o.keys() - n.keys()] + [f"nové: {i}" for i in n.keys() - o.keys()]
    for i in o.keys() & n.keys():
        bad = [k for k in COMPARE if o[i].get(k) != n[i].get(k)]
        if bad:
            out.append(f"{i}: liší se {', '.join(bad)}")
    return sorted(out)


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap_ = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap_.add_argument("--root", type=Path, default=REPO / "_sources" / "presets", help="složka s podsložkami <source_id>")
    ap_.add_argument("--write", action="store_true", help="přepsat indexy a dumpy")
    ap_.add_argument("--only", action="append", default=[], help="jen tyhle source_id (lze opakovat)")
    a = ap_.parse_args(argv)

    if not a.root.is_dir():
        print(f"složka {a.root} neexistuje (spusť tools/collect_local_sources.py)", file=sys.stderr)
        return 2
    packs = sorted(p for p in a.root.iterdir() if p.is_dir() and (not a.only or p.name in a.only))
    if not packs:
        print("žádné packy", file=sys.stderr)
        return 2

    changed = failed = 0
    for pack in packs:
        sid = pack.name
        out = REPO / "data" / "presets" / "index" / f"{sid}.jsonl"
        dump = REPO / "data" / "presets" / "_local" / DUMP_DIR.get(sid, sid) if a.write else None
        rows, bad = ip.index([pack], sid, dump)
        d = diff(load(out), rows)
        status = "beze změny" if not d else f"{len(d)} rozdílů"
        print(f"{sid:<32} {len(rows):>4} presetů  {status}" + (f"  ({len(bad)} chyb)" if bad else ""))
        for line in d[:5]:
            print("   ", line)
        for b in bad:
            print("    chyba:", b, file=sys.stderr)
        failed += bool(bad)
        changed += bool(d)
        if a.write:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="\n")
    return 1 if failed or (changed and not a.write) else 0


if __name__ == "__main__":
    sys.exit(main())
