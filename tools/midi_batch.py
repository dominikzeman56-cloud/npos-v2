"""Dávkový rozbor MIDI přes celou složku Live setů: rytmický otisk basy, kicku a snaru po projektech.

Jen čtení. Pro každý `.als` (bez záloh a bez kopií se stejným obsahem) spočítá podle názvů stop:
- nejčastější neprázdný takt každé role (mřížka 1/16) a z něj "podpis mezer" (vzdálenosti mezi nástupy, např. 3-3-2),
- tempo, počet tracků a skupin, poslední takt s MIDI.

Do repa jdou jen souhrnná čísla (kolik projektů má jaký podpis), bez názvů projektů a cest. Podrobnosti po
projektech jdou na obrazovku nebo do `--detail` souboru, který patří mimo git.

Role z názvů stop jsou `hypotéza`; čísla z not `naměřeno`. Skupina s méně než 10 projekty má jen počet.

Použití:
  py -3.12 tools/midi_batch.py --root "D:/Ableton/10_Projects/04_Learning/lets_syntetize_new" --label ls --out data/midi/batch-ls.json --detail scratch.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

try:
    import als_stats as A
    import midi_project as P
    import midi_stats as M
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    import als_stats as A
    import midi_project as P
    import midi_stats as M

MIN_PROJECTS = 10
ROLES = ("kick", "snare", "bass", "sub")


def role_of_track(name: str) -> str | None:
    n = name.lower()
    if "snare" in n:
        return "snare"
    if "kick" in n:
        return "kick"
    r = M.role_of(name)
    return r if r in ("bass", "sub") else None


def gap_signature(cells: str) -> str:
    """Vzdálenosti mezi nástupy v jednom taktu (v šestnáctinách), s návratem na začátek taktu: 'x...x..x' -> '4-3-1'."""
    hits = [i for i, c in enumerate(cells) if c in "x+"]
    if not hits:
        return ""
    if len(hits) == 1:
        return "16"
    gaps = [b - a for a, b in zip(hits, hits[1:])] + [16 - hits[-1] + hits[0]]
    return "-".join(str(g) for g in gaps)


def dominant_bar(tl: dict[int, dict]) -> tuple[str, int, int] | None:
    """Nejčastější neprázdný takt: (mřížka, kolikrát, počet neprázdných taktů)."""
    grids = Counter("".join(b["cells"]) for b in tl.values() if any(c != "." for c in b["cells"]))
    if not grids:
        return None
    g, n = grids.most_common(1)[0]
    return g, n, sum(grids.values())


def analyze_project(path: Path) -> dict:
    root = A.read_set(path)
    base = A.analyze(root)
    cl = P.clips(root)
    last = 0
    roles: dict[str, list[dict]] = {}
    for name in sorted({c["track"] for c in cl}):
        tl = P.timeline(cl, name)
        if not tl:
            continue
        last = max(last, max(tl))
        role = role_of_track(name)
        dom = dominant_bar(tl) if role else None
        if role and dom:
            roles.setdefault(role, []).append({"track": name, "grid": dom[0], "repeats": dom[1], "bars": dom[2],
                                               "signature": gap_signature(dom[0]),
                                               "pitches": sorted({pp for b in tl.values() for pp in b["pitches"]})})
    return {"tracks": base["tracks"], "groups": base["groups"], "tempo": base["tempo"], "last_midi_bar": last, "roles": roles}


def file_key(p: Path) -> str:
    h = hashlib.sha1()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_sets(root: Path) -> tuple[list[Path], int]:
    """Sety bez záloh a bez kopií se stejným obsahem; druhá hodnota = kolik souborů nešlo přečíst (zamčené)."""
    seen, out, unreadable = set(), [], 0
    for p in sorted(root.rglob("*.als")):
        if "Backup" in p.parts:
            continue
        try:
            k = file_key(p)
        except OSError:
            unreadable += 1
            continue
        if k in seen:
            continue
        seen.add(k)
        out.append(p)
    return out, unreadable


def aggregate(projects: list[dict]) -> dict:
    n = len(projects)
    out: dict = {"n_projects": n}
    if n < MIN_PROJECTS:
        out["note"] = "méně než 10 projektů: jen počet"
        return out
    for role in ROLES:
        have = [pr for pr in projects if role in pr["roles"]]
        entry: dict = {"projects_with_role": len(have)}
        if len(have) >= MIN_PROJECTS:
            sigs = Counter()
            for pr in have:
                best = max(pr["roles"][role], key=lambda r: r["repeats"])  # nejčastěji opakovaná stopa projektu
                if best["signature"]:
                    sigs[best["signature"]] += 1
            entry["signatures_by_projects"] = dict(sigs.most_common(8))
            entry["share_with_3_gap"] = round(sum(1 for pr in have if any("3-3" in r["signature"] for r in pr["roles"][role])) / len(have), 3)
        out[role] = entry
    tempos = Counter(round(pr["tempo"]) for pr in projects if pr["tempo"])
    out["tempo"] = dict(tempos.most_common(6))
    bars = sorted(pr["last_midi_bar"] for pr in projects if pr["last_midi_bar"])
    if len(bars) >= MIN_PROJECTS:
        out["last_midi_bar"] = M.quant([float(b) for b in bars])
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--label", default="batch")
    ap.add_argument("--out", type=Path, required=True, help="souhrn pro repo (bez názvů)")
    ap.add_argument("--detail", type=Path, help="podrobnosti po projektech, jen lokálně (mimo git)")
    ap.add_argument("--max-mb", type=float, default=60, help="větší soubory přeskočit")
    a = ap.parse_args(argv)
    if not a.root.is_dir():
        print(f"folder missing: {a.root}", file=sys.stderr)
        return 2
    rows, detail, failed, skipped = [], {}, Counter(), 0
    sets, unreadable = find_sets(a.root)
    if unreadable:
        failed["unreadable_locked"] = unreadable
    for p in sets:
        if p.stat().st_size > a.max_mb * 1e6:
            skipped += 1
            continue
        try:
            r = analyze_project(p)
        except (OSError, EOFError, ET.ParseError, ValueError, MemoryError) as e:
            failed[type(e).__name__] += 1
            continue
        rows.append(r)
        detail[p.name] = r
    result = {"basis": "midi_notes", "confidence": "naměřeno", "label": a.label,
              "note": "Role z názvů stop jsou hypotéza. Podpis = vzdálenosti mezi nástupy v nejčastějším taktu. Bez názvů projektů.",
              "failed": dict(failed), "skipped_large": skipped, "summary": aggregate(rows)}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if a.detail:
        a.detail.write_text(json.dumps(detail, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"projects {len(rows)}, failed {sum(failed.values())}, skipped large {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
