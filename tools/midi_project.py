"""Rozbor MIDI jednoho Live setu (`.als`): vzory po stopách v mřížce 1/16 a kde se v aranži použijí.

Jen čtení. Výstup jde na obrazovku (nebo do JSON přes `--json`), nic se nezapisuje do repa.
Vzor = posloupnost not v klipu (po okně smyčky). Stejné vzory jednoho tracku dostanou stejné číslo.
Mřížka: jeden znak = šestnáctina, `x` = nástup, `.` = ticho, `+` = nástup mimo mřížku 1/16.

Použití:
  py -3.12 tools/midi_project.py "cesta/k/setu.als" [--track Bass] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import als_stats as A
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    import als_stats as A

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def pitch_name(p: int) -> str:
    return f"{NAMES[p % 12]}{p // 12 - 2}"  # C3 = MIDI 60, stejně jako Live a Producer Pal


def grid(notes: list[tuple[float, float, int, int]], length: float) -> str:
    n = max(1, round(length * 4))
    cells = ["."] * n
    for s, _d, _p, _v in notes:
        i = round(s * 4)
        if abs(s * 4 - i) < 0.12 and 0 <= i < n:
            cells[i] = "x"
        elif 0 <= int(s * 4) < n:
            cells[int(s * 4)] = "+"
    return "".join(cells)


def clips(root: ET.Element) -> list[dict]:
    out = []
    ls = root.find("LiveSet")
    tn = ls.find("Tracks") if ls is not None else None
    for t in (list(tn) if tn is not None else []):
        if t.tag != "MidiTrack":
            continue
        for clip in t.iter("MidiClip"):
            start = A.val(clip, "CurrentStart")
            end = A.val(clip, "CurrentEnd")
            a = float(A.val(clip, "Loop/LoopStart") or 0)
            b = float(A.val(clip, "Loop/LoopEnd") or 0)
            if start is None or b <= a:
                continue
            notes = []
            for kt in clip.findall("Notes/KeyTracks/KeyTrack"):
                key = A.val(kt, "MidiKey")
                for ev in kt.findall("Notes/MidiNoteEvent"):
                    s = float(ev.get("Time", "0"))
                    if key is not None and ev.get("IsEnabled") != "false" and a <= s < b:
                        notes.append((s - a, float(ev.get("Duration", "0")), int(key), int(float(ev.get("Velocity", "100")))))
            out.append({"track": A.track_name(t), "start": float(start), "length": float(end) - float(start) if end else b - a,
                        "loop": b - a, "notes": sorted(notes), "muted": A.val(clip, "Disabled") == "true",
                        "loop_on": A.val(clip, "Loop/LoopOn") != "false", "start_rel": float(A.val(clip, "Loop/StartRelative") or 0)})
    return out


def timeline(cl: list[dict], track: str, include_muted: bool = False) -> dict[int, dict]:
    """Spojí klipy jedné stopy do aranžního času: takt -> mřížka 1/16 a výšky. Opakuje smyčky do konce klipu."""
    bars: dict[int, dict] = {}
    for c in cl:
        if c["track"] != track or (c["muted"] and not include_muted):
            continue
        loop = c["loop"]
        for t, _d, pitch, _v in c["notes"]:
            first = t - c["start_rel"]
            if first < 0:
                first += loop
            k = 0
            while True:
                off = first + k * loop
                if off >= c["length"] - 1e-6 or (k > 0 and not c["loop_on"]):
                    break
                pos = c["start"] + off
                b = bars.setdefault(int(pos // 4) + 1, {"cells": ["."] * 16, "pitches": set()})
                step = (pos % 4) * 4
                i = round(step)
                if abs(step - i) < 0.12 and i < 16:
                    b["cells"][i] = "x"
                else:
                    b["cells"][min(15, int(step))] = "+"
                b["pitches"].add(pitch)
                k += 1
                if loop <= 0:
                    break
    return bars


def runs(tl: dict[int, dict], first: int, last: int) -> list[tuple[int, int, str, str]]:
    """Souvislé takty se stejnou mřížkou a stejnými výškami se spojí do jednoho řádku."""
    out: list[tuple[int, int, str, str]] = []
    for bar in range(first, last + 1):
        b = tl.get(bar)
        grid_s = "".join(b["cells"]) if b else "." * 16
        pit = " ".join(pitch_name(p) for p in sorted(b["pitches"])) if b else ""
        if out and out[-1][2] == grid_s and out[-1][3] == pit and out[-1][1] == bar - 1:
            out[-1] = (out[-1][0], bar, grid_s, pit)
        else:
            out.append((bar, bar, grid_s, pit))
    return out


def bar_beat(pos: float) -> str:
    bar, beat = int(pos // 4) + 1, pos % 4 + 1
    return f"{bar}|{beat:g}"


def report(cl: list[dict], only: str | None = None) -> dict:
    tracks: dict[str, list[dict]] = {}
    for c in cl:
        if only and only.lower() not in c["track"].lower():
            continue
        tracks.setdefault(c["track"], []).append(c)
    result = {}
    for name, items in tracks.items():
        items.sort(key=lambda c: c["start"])
        pats: dict[tuple, dict] = {}
        for c in items:
            sig = tuple((round(n[0], 3), n[2]) for n in c["notes"])
            p = pats.setdefault(sig, {"id": len(pats) + 1, "grid": grid(c["notes"], c["loop"]), "loop_beats": c["loop"],
                                      "pitches": [pitch_name(n[2]) for n in c["notes"]], "durations": [round(n[1], 3) for n in c["notes"]],
                                      "uses": []})
            p["uses"].append({"at": bar_beat(c["start"]), "length_beats": round(c["length"], 3), "muted": c["muted"]})
        result[name] = {"clips": len(items), "patterns": list(pats.values())}
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("als", type=Path)
    ap.add_argument("--track", help="jen stopy, jejichž název obsahuje tento text")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--bars", help="rozsah taktů, např. 33-64: vypíše aranžní mřížku po taktech (klipy spojené a smyčky rozbalené)")
    a = ap.parse_args(argv)
    if a.bars:
        lo, _, hi = a.bars.partition("-")
        cl = clips(A.read_set(a.als))
        for name in sorted({c["track"] for c in cl if not a.track or a.track.lower() in c["track"].lower()}):
            tl = timeline(cl, name)
            if not tl:
                continue
            print(f"\n== {name}")
            for f, l, g, pit in runs(tl, int(lo), int(hi or lo)):
                print(f"  takty {f}" + (f"-{l}" if l != f else "") + f": {g}  {pit}")
        return 0
    try:
        rep = report(clips(A.read_set(a.als)), a.track)
    except (OSError, EOFError, ET.ParseError) as e:
        print(f"nelze přečíst: {type(e).__name__}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        return 0
    for name, r in rep.items():
        print(f"\n== {name}: {r['clips']} klipů, {len(r['patterns'])} různých vzorů")
        for p in r["patterns"]:
            uses = ", ".join(u["at"] + ("*" if u["muted"] else "") for u in p["uses"][:10]) + (" …" if len(p["uses"]) > 10 else "")
            print(f"  #{p['id']} {p['grid']}  {' '.join(p['pitches'][:12])}  ({len(p['uses'])}×: {uses})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
