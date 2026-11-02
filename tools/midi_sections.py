"""Části aranže z MIDI jednoho Live setu (`.als`): intro, build, drop, break, outro.

Jen čtení. Výstup jde na obrazovku (nebo do JSON přes `--json`), nic se nezapisuje do repa.
Postup:
- klipy se spojí do aranžního času (`midi_project.timeline`), po taktech se spočítá, které stopy a role hrají
  a jejich hustota (počet nástupů v taktu, mřížka 1/16),
- hranice = takt, kde se sada hrajících rolí výrazně změní (Jaccardova vzdálenost >= `--threshold`)
  nebo kde přijdou či odejdou bicí (kick/snare/drums) nebo basa (bass/sub), přichycená na nejbližší začátek fráze (`--phrase` 8 nebo 16 taktů),
- role části = role, které hrají aspoň v polovině jejích taktů; sousední části se stejnými rolemi se spojí,
- štítek z kicku, snaru, basy a subu: bicí (kick/snare/drums) + basa/sub = drop; bicí bez basy v řadě
  těsně před dropem = build; první část = intro, poslední = outro; ostatní = break.

Role z názvů stop (jako `midi_batch` a `midi_stats`) a štítky částí jsou `hypotéza`; počty nástupů `naměřeno`.

Použití:
  py -3.12 tools/midi_sections.py "cesta/k/setu.als" [--phrase 16] [--audio] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import als_stats as A
    import midi_batch as B
    import midi_project as P
    import midi_stats as M
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    import als_stats as A
    import midi_batch as B
    import midi_project as P
    import midi_stats as M

DRUMS = ("kick", "snare", "drums")
LOW = ("bass", "sub")


def track_role(name: str) -> str:
    """kick/snare/bass/sub jako v `midi_batch`, jinak role z `midi_stats` (drums, lead, pad …, other)."""
    return B.role_of_track(name) or M.role_of(name)


def bar_activity(cl: list[dict], include_muted: bool = False) -> tuple[dict[int, dict], int]:
    """Takt -> {"tracks": {stopa: nástupů}, "roles": {role: nástupů}} a poslední takt s notou."""
    bars: dict[int, dict] = {}
    for name in sorted({c["track"] for c in cl}):
        role = track_role(name)
        for bar, b in P.timeline(cl, name, include_muted).items():
            hits = sum(c != "." for c in b["cells"])
            if not hits:
                continue
            d = bars.setdefault(bar, {"tracks": {}, "roles": {}})
            d["tracks"][name] = d["tracks"].get(name, 0) + hits
            d["roles"][role] = d["roles"].get(role, 0) + hits
    return bars, max(bars, default=0)


def distance(a: set, b: set) -> float:
    """Jaccardova vzdálenost dvou sad rolí (0 = stejné, 1 = nic společného; dvě prázdné = 0)."""
    u = a | b
    return 1 - len(a & b) / len(u) if u else 0.0


def snap(bar: int, phrase: int) -> int:
    """Nejbližší začátek fráze (1, 1+phrase, …); v půlce se zaokrouhlí dopředu."""
    return 1 + int((bar - 1) / phrase + 0.5) * phrase


def groups(roles: set) -> tuple[bool, bool]:
    """(hrají bicí, hraje basa nebo sub)."""
    return any(r in roles for r in DRUMS), any(r in roles for r in LOW)


def boundaries(bars: dict[int, dict], last: int, phrase: int = 8, threshold: float = 0.5) -> list[int]:
    """Začátky částí: 1 a přichycené takty, kde se sada rolí změní aspoň o `threshold`
    nebo kde přijdou či odejdou bicí nebo basa."""
    out = {1}
    for bar in range(2, last + 1):
        prev = set(bars.get(bar - 1, {}).get("roles", {}))
        cur = set(bars.get(bar, {}).get("roles", {}))
        if distance(prev, cur) >= threshold or groups(prev) != groups(cur):
            s = snap(bar, phrase)
            if s <= last:
                out.add(s)
    return sorted(out)


def profile(bars: dict[int, dict], start: int, end: int) -> tuple[list[str], dict[str, float], dict[str, float]]:
    """Role hrající aspoň v polovině taktů části, průměrná hustota rolí a stop (nástupů na takt části)."""
    n = end - start + 1
    present: dict[str, int] = {}
    rhits: dict[str, int] = {}
    thits: dict[str, int] = {}
    for bar in range(start, end + 1):
        d = bars.get(bar)
        if not d:
            continue
        for r, h in d["roles"].items():
            present[r] = present.get(r, 0) + 1
            rhits[r] = rhits.get(r, 0) + h
        for t, h in d["tracks"].items():
            thits[t] = thits.get(t, 0) + h
    roles = sorted(r for r, k in present.items() if k * 2 >= n)
    return roles, {r: round(h / n, 2) for r, h in sorted(rhits.items())}, {t: round(h / n, 2) for t, h in sorted(thits.items())}


def label(sections: list[dict]) -> None:
    """Doplní štítek každé části podle přítomnosti bicích a basy (viz docstring modulu)."""
    def is_drop(s: dict) -> bool:
        return all(groups(set(s["roles"])))

    last = len(sections) - 1
    for i in range(last, -1, -1):  # odzadu, aby build mohl navazovat na další build před dropem
        s = sections[i]
        drums = groups(set(s["roles"]))[0]
        if is_drop(s):
            s["label"] = "drop"
        elif i == 0:
            s["label"] = "intro"
        elif i == last:
            s["label"] = "outro"
        elif drums and sections[i + 1]["label"] in ("drop", "build"):
            s["label"] = "build"
        else:
            s["label"] = "break"


def sections(cl: list[dict], phrase: int = 8, threshold: float = 0.5, include_muted: bool = False) -> dict:
    """Části aranže se štítky, rolemi a hustotou; `bars` = role a nástupy po taktech."""
    bars, last = bar_activity(cl, include_muted)
    out: list[dict] = []
    if last:
        starts = boundaries(bars, last, phrase, threshold)
        for s, nxt in zip(starts, starts[1:] + [last + 1]):
            roles, rd, td = profile(bars, s, nxt - 1)
            if out and out[-1]["roles"] == roles:  # stejné role = pokračování předchozí části
                s = out.pop()["start"]
                roles, rd, td = profile(bars, s, nxt - 1)
            out.append({"start": s, "end": nxt - 1, "roles": roles, "density": rd, "tracks": td})
        label(out)
    return {"phrase": phrase, "last_bar": last, "sections": out,
            "bars": {str(b): bars[b]["roles"] for b in sorted(bars)}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("als", type=Path)
    ap.add_argument("--phrase", type=int, choices=(8, 16), default=8, help="délka fráze v taktech pro přichycení hranic")
    ap.add_argument("--threshold", type=float, default=0.5, help="Jaccardova vzdálenost sad rolí mezi takty, od které je to hranice")
    ap.add_argument("--audio", action="store_true", help="přidá audio stopy (každý klip = jeden úder na začátku)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        rt = A.read_set(a.als)
    except (OSError, EOFError, ET.ParseError) as e:
        print(f"nelze přečíst: {type(e).__name__}", file=sys.stderr)
        return 2
    cl = P.clips(rt) + (P.audio_as_hits(P.audio_clips(rt)) if a.audio else [])
    rep = sections(cl, a.phrase, a.threshold)
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        return 0
    for s in rep["sections"]:
        dens = ", ".join(f"{r} {v:g}" for r, v in s["density"].items())
        print(f"takty {s['start']:>3}-{s['end']:<3} {s['label']:6} {' '.join(s['roles']) or '-':28} (nástupů/takt: {dens or '-'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
