#!/usr/bin/env python3
"""import_sessions.py — uloží session z Dashboardu (export `sessions.json`) do `data/sessions/`.

Dashboard exportuje pole objektů podle `core/session.schema.json` (date, track_id, goal + volitelně
done, blocked, learned, next). Skript je zvaliduje a zapíše jeden soubor na session:
`data/sessions/<date>-<track_id>[-n].json`. Nic nepřepisuje (existující soubor dostane číslo).

Použití:
  py -3.12 tools/import_sessions.py ~/Downloads/sessions.json [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REQUIRED = ("date", "track_id", "goal")
OPTIONAL_STR = ("blocked", "learned", "next")


def validate(s: object) -> list[str]:
    if not isinstance(s, dict):
        return ["není objekt"]
    errs = [f"chybí {k}" for k in REQUIRED if not isinstance(s.get(k), str) or not s[k].strip()]
    if isinstance(s.get("date"), str) and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s["date"]):
        errs.append("date není YYYY-MM-DD")
    if "done" in s and not (isinstance(s["done"], list) and all(isinstance(x, str) for x in s["done"])):
        errs.append("done není pole řetězců")
    errs += [f"{k} není řetězec" for k in OPTIONAL_STR if k in s and not isinstance(s[k], str)]
    return errs


def target(out_dir: Path, s: dict) -> Path:
    base = re.sub(r"[^a-z0-9-]+", "-", f"{s['date']}-{s['track_id']}".lower()).strip("-")
    p = out_dir / f"{base}.json"
    n = 2
    while p.exists():
        p = out_dir / f"{base}-{n}.json"
        n += 1
    return p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", type=Path)
    ap.add_argument("--out", type=Path, default=REPO / "data" / "sessions")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    data = json.loads(a.file.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        print("očekávám pole session", file=sys.stderr)
        return 2
    bad = 0
    for i, s in enumerate(data):
        errs = validate(s)
        if errs:
            print(f"#{i}: {'; '.join(errs)}", file=sys.stderr)
            bad += 1
            continue
        p = target(a.out, s)
        print(("[dry-run] " if a.dry_run else "") + f"{p.relative_to(REPO) if p.is_relative_to(REPO) else p}")
        if not a.dry_run:
            a.out.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({k: s[k] for k in (*REQUIRED, "done", *OPTIONAL_STR) if k in s}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
