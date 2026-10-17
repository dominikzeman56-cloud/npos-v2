"""Statistiky MIDI vzorů: rytmus, hustota, pohyb tónů. Jen čtení, jen čísla.

Zdroje:
- MIDI klipy uvnitř Live setů (`.als`, reference = kurzy a cizí projekty; složka `own` se nepočítá),
- soubory `.mid` z balíčků (placené packy, jen čísla; názvy packů ani cesty se nepublikují).

Vzor = jeden klip nebo jeden soubor. Stejné vzory (shodná posloupnost not) se počítají jednou.
Měří se jen popisné veličiny (hustota, pozice na mřížce, mezery, kroky mezi tóny, opakování).
Pojmy jako "call a response" se neměří: zatím jen hypotéza.

Skupina s méně než 10 vzory nebo méně než 3 zdroji dostane jen počet.
Štítky jistoty: čísla `naměřeno`; role z názvů stop a souborů `hypotéza`.

Použití:
  py -3.12 tools/midi_stats.py --als-roots _sources/projects --mid-roots D:/Ableton/20_Samples D:/Ableton/40_MIDI \\
      --exclude _MIDI_KOSTRY --out data/midi/midi-stats.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

try:
    import als_stats as A
except ImportError:  # spuštěno z kořene repa
    sys.path.insert(0, str(Path(__file__).parent))
    import als_stats as A

MIN_PATTERNS = 10
MIN_SOURCES = 3
MIN_NOTES = 4
MAX_BARS = 32
ROLE_RULES = [
    ("drums", re.compile(r"kick|snare|hat|clap|perc|drum|break|beat|\btom|ride|cymb|shaker|fill", re.I)),
    ("sub", re.compile(r"(?<![a-z])sub(?![a-z])", re.I)),
    ("bass", re.compile(r"bass|reese|neuro|growl|wobble|talk|riff|\bmid\b", re.I)),
    ("stab", re.compile(r"stab|hit", re.I)),
    ("lead", re.compile(r"lead|melod|hook|arp|pluck|synth|vocal", re.I)),
    ("harmony", re.compile(r"chord|pad|string|key|piano|organ|harm", re.I)),
]


GENRE_WORDS = re.compile(r"drum\s*(?:&|and|n|'n')\s*bass|d\s*&\s*b|dnb", re.I)


def role_of(text: str) -> str:
    text = GENRE_WORDS.sub(" ", text)
    for role, rx in ROLE_RULES:
        if rx.search(text):
            return role
    return "other"


# ---------- čtení MIDI souborů (SMF) ----------

def _vlq(data: bytes, i: int) -> tuple[int, int]:
    v = 0
    while True:
        b = data[i]
        i += 1
        v = (v << 7) | (b & 0x7F)
        if not b & 0x80:
            return v, i


def read_smf(data: bytes) -> list[tuple[float, float, int, int]]:
    """Vrátí noty (začátek v dobách, délka v dobách, výška, velocity)."""
    if data[:4] != b"MThd":
        raise ValueError("není MIDI soubor")
    _fmt, ntrk, div = struct.unpack(">HHH", data[8:14])
    if div & 0x8000:
        raise ValueError("SMPTE čas se nepodporuje")
    i = 14
    notes: list[tuple[float, float, int, int]] = []
    for _ in range(ntrk):
        if data[i:i + 4] != b"MTrk":
            raise ValueError("chybí MTrk")
        ln = struct.unpack(">I", data[i + 4:i + 8])[0]
        j, end, t, status = i + 8, i + 8 + ln, 0, 0
        open_: dict[tuple[int, int], list[tuple[int, int]]] = {}
        while j < end:
            dt, j = _vlq(data, j)
            t += dt
            b = data[j]
            if b == 0xFF:
                ml, j2 = _vlq(data, j + 2)
                j = j2 + ml
                continue
            if b in (0xF0, 0xF7):
                ml, j2 = _vlq(data, j + 1)
                j = j2 + ml
                continue
            if b & 0x80:
                status = b
                j += 1
            kind, ch = status & 0xF0, status & 0x0F
            n = 1 if kind in (0xC0, 0xD0) else 2
            args = data[j:j + n]
            j += n
            if kind == 0x90 and args[1] > 0:
                open_.setdefault((ch, args[0]), []).append((t, args[1]))
            elif kind == 0x80 or (kind == 0x90 and args[1] == 0):
                q = open_.get((ch, args[0]))
                if q:
                    t0, vel = q.pop(0)
                    notes.append((t0 / div, max((t - t0) / div, 0.0), args[0], vel))
        i = end
    return sorted(notes)


# ---------- čtení klipů z .als ----------

def als_patterns(root: ET.Element) -> list[tuple[str, list[tuple[float, float, int, int]], float]]:
    out = []
    ls = root.find("LiveSet")
    tn = ls.find("Tracks") if ls is not None else None
    for t in (list(tn) if tn is not None else []):
        if t.tag != "MidiTrack":
            continue
        name = A.track_name(t)
        for clip in t.iter("MidiClip"):
            a = float(A.val(clip, "Loop/LoopStart") or 0)
            b = float(A.val(clip, "Loop/LoopEnd") or 0)
            if b <= a:
                continue
            notes = []
            for kt in clip.findall("Notes/KeyTracks/KeyTrack"):
                key = A.val(kt, "MidiKey")
                if key is None:
                    continue
                for ev in kt.findall("Notes/MidiNoteEvent"):
                    if ev.get("IsEnabled") == "false":
                        continue
                    s = float(ev.get("Time", "0"))
                    if a <= s < b:
                        notes.append((s - a, float(ev.get("Duration", "0")), int(key), int(float(ev.get("Velocity", "100")))))
            out.append((name, sorted(notes), b - a))
    return out


# ---------- popisné veličiny ----------

def _frac_class(f: float) -> str:
    for target, label in ((0.0, "beat"), (0.5, "eighth"), (0.25, "sixteenth"), (0.75, "sixteenth")):
        if abs(f - target) < 0.04:
            return label
    for target in (1 / 3, 2 / 3, 1 / 6, 5 / 6):
        if abs(f - target) < 0.04:
            return "triplet"
    return "off_grid"


def describe(notes: list[tuple[float, float, int, int]], length: float) -> dict | None:
    bars = max(1, math.ceil(length / 4 - 1e-6))
    if len(notes) < MIN_NOTES or bars > MAX_BARS:
        return None
    onsets = sorted({round(n[0], 4) for n in notes})
    cls = Counter(_frac_class(o % 1.0) for o in onsets)
    total = sum(cls.values())
    slots = [0] * 16
    for o in onsets:
        pos = (o % 4.0) / 0.25
        if abs(pos - round(pos)) < 0.16:
            slots[int(round(pos)) % 16] += 1
    # jednohlasá linka: nejnižší tón v každém okamžiku
    line = []
    for o in onsets:
        line.append(min(n[2] for n in notes if abs(n[0] - o) < 1e-4))
    steps = Counter()
    for p, q in zip(line, line[1:]):
        d = abs(q - p)
        steps["repeat" if d == 0 else "step" if d <= 2 else "mid" if d <= 6 else "leap" if d <= 11 else "octave_plus"] += 1
    nst = sum(steps.values())
    gaps = [b - a for a, b in zip(onsets, onsets[1:])]
    nxt = {a: b for a, b in zip(onsets, onsets[1:])}
    sounding = [n for n in notes if round(n[0], 4) in nxt]
    legato = (sum(1 for n in sounding if n[1] >= 0.9 * (nxt[round(n[0], 4)] - n[0])) / len(sounding)) if sounding else None
    bar_sets = []
    for k in range(bars):
        bar_sets.append(frozenset((round(n[0] - 4 * k, 3), n[2]) for n in notes if 4 * k <= n[0] < 4 * k + 4))
    rep = sum(1 for x, y in zip(bar_sets, bar_sets[1:]) if x == y) / (bars - 1) if bars > 1 else None
    empty = sum(1 for s in bar_sets if not s) / bars
    longest_rest = max([onsets[0]] + gaps + [length - (onsets[-1])]) if onsets else length
    return {
        "bars": bars,
        "density": len(notes) / bars,
        "onbeat": cls["beat"] / total,
        "eighth": cls["eighth"] / total,
        "sixteenth": cls["sixteenth"] / total,
        "triplet": cls["triplet"] / total,
        "off_grid": cls["off_grid"] / total,
        "slots": slots,
        "median_dur": sorted(n[1] for n in notes)[len(notes) // 2],
        "pitch_range": max(n[2] for n in notes) - min(n[2] for n in notes),
        "distinct_pitches": len({n[2] for n in notes}),
        "repeat": steps["repeat"] / nst if nst else None,
        "step": steps["step"] / nst if nst else None,
        "leap": (steps["leap"] + steps["octave_plus"]) / nst if nst else None,
        "legato": legato,
        "bar_repeat": rep,
        "empty_bars": empty,
        "longest_rest_beats": longest_rest,
    }


PITCHED_KEYS = ("pitch_range", "distinct_pitches", "repeat", "step", "leap")


def strip_pitch(d: dict) -> dict:
    """U bicích určuje výška not nástroj v racku, ne melodii: veličiny o výšce se nepočítají."""
    return {**d, **{k: None for k in PITCHED_KEYS}}


def fingerprint(notes: list[tuple[float, float, int, int]]) -> str:
    s = ";".join(f"{round(n[0], 3)},{round(n[1], 3)},{n[2]}" for n in notes)
    return hashlib.sha1(s.encode()).hexdigest()


# ---------- agregace ----------

def quant(xs: list[float]) -> dict:
    s = sorted(xs)
    n = len(s)

    def q(p: float) -> float:
        i = (n - 1) * p
        lo, hi = int(math.floor(i)), int(math.ceil(i))
        return round(s[lo] + (s[hi] - s[lo]) * (i - lo), 3)

    return {"n": n, "q1": q(0.25), "median": q(0.5), "q3": q(0.75)}


def summarize(rows: list[dict]) -> dict:
    n_src = len({r["source"] for r in rows})
    out: dict = {"n_patterns": len(rows), "n_sources": n_src}
    if len(rows) < MIN_PATTERNS or n_src < MIN_SOURCES:
        out["note"] = "méně než 10 vzorů nebo 3 zdroje: jen počet"
        return out
    for k in ("bars", "density", "onbeat", "eighth", "sixteenth", "triplet", "off_grid", "median_dur", "pitch_range",
              "distinct_pitches", "repeat", "step", "leap", "legato", "bar_repeat", "empty_bars", "longest_rest_beats"):
        xs = [r[k] for r in rows if r[k] is not None]
        if len(xs) >= MIN_PATTERNS:
            out[k] = quant(xs)
    out["share_with_any_sixteenth"] = round(sum(r["sixteenth"] > 0 for r in rows) / len(rows), 3)
    out["share_with_any_triplet"] = round(sum(r["triplet"] > 0 for r in rows) / len(rows), 3)
    out["share_with_any_off_grid"] = round(sum(r["off_grid"] > 0 for r in rows) / len(rows), 3)
    tot = [sum(r["slots"][i] for r in rows) for i in range(16)]
    s = sum(tot) or 1
    out["slots16_share"] = [round(x / s, 3) for x in tot]
    return out


def _finish(d: dict, role: str) -> dict:
    return strip_pitch(d) if role == "drums" else d


def collect_als(roots: list[Path]) -> tuple[list[dict], Counter]:
    rows, failed = [], Counter()
    for group, root, p in A.find_sets(roots):
        if group != "reference":
            continue
        try:
            pats = als_patterns(A.read_set(p))
        except (OSError, EOFError, ET.ParseError, ValueError) as e:
            failed[type(e).__name__] += 1
            continue
        src = hashlib.sha1(str(p.relative_to(root)).encode()).hexdigest()[:8]
        for name, notes, length in pats:
            d = describe(notes, length)
            if d:
                rows.append({**_finish(d, role_of(name)), "role": role_of(name), "source": src, "fp": fingerprint(notes), "kind": "als"})
    return rows, failed


GENERIC_DIRS = {"01_new", "new", "packs", "_standalone", "midi"}


def role_text(root: Path, rel: Path) -> str:
    """Text pro určení role: soubor a složky pod balíčkem (název balíčku se nepočítá)."""
    key = _source_key(root, rel).split("/", 1)
    pack = key[1] if len(key) > 1 else None
    parts = [x for x in rel.with_suffix("").parts if x != pack and x.lower() not in GENERIC_DIRS]
    return " / ".join(parts)


def _source_key(root: Path, rel: Path) -> str:
    """Zdroj = první složka, která není obecný kontejner (balíček), jinak kořen."""
    for part in rel.parts[:-1]:
        if part.lower() not in GENERIC_DIRS:
            return f"{root.name}/{part}"
    return root.name


def collect_mid(roots: list[Path], exclude: list[str]) -> tuple[list[dict], Counter]:
    rows, failed = [], Counter()
    for root in roots:
        for p in sorted(root.rglob("*.mid")) + sorted(root.rglob("*.midi")):
            rel = p.relative_to(root)
            if any(x.lower() in str(rel).lower() for x in exclude):
                continue
            try:
                notes = read_smf(p.read_bytes())
            except (OSError, ValueError, IndexError, struct.error) as e:
                failed[type(e).__name__] += 1
                continue
            if not notes:
                continue
            length = max(n[0] + n[1] for n in notes)
            length = max(4.0, math.ceil(length / 4 - 1e-6) * 4.0)
            d = describe(notes, length)
            if d:
                src = hashlib.sha1(_source_key(root, rel).encode()).hexdigest()[:8]
                rows.append({**_finish(d, role_of(role_text(root, rel))), "role": role_of(role_text(root, rel)), "source": src, "fp": fingerprint(notes), "kind": "mid"})
    return rows, failed


def dedupe(rows: list[dict]) -> list[dict]:
    seen, out = set(), []
    for r in rows:
        if r["fp"] in seen:
            continue
        seen.add(r["fp"])
        out.append(r)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--als-roots", nargs="*", default=[], type=Path)
    ap.add_argument("--mid-roots", nargs="*", default=[], type=Path)
    ap.add_argument("--exclude", nargs="*", default=[], help="podřetězce cest, které se přeskočí (např. vlastní kostry)")
    ap.add_argument("--out", type=Path, default=Path("data/midi/midi-stats.json"))
    a = ap.parse_args(argv)
    for r in a.als_roots + a.mid_roots:
        if not r.is_dir():
            print(f"folder missing: {r}", file=sys.stderr)
            return 2
    als_rows, f1 = collect_als(a.als_roots)
    mid_rows, f2 = collect_mid(a.mid_roots, a.exclude)
    result = {
        "basis": "midi_notes",
        "confidence": "naměřeno",
        "note": "Popisné veličiny vzorů. Role z názvů stop a souborů jsou hypotéza. Call/response se neměří. Vlastní tvorba je vyloučena.",
        "failed": {"als": dict(f1), "mid": dict(f2)},
        "sources": {},
    }
    for label, rows in (("als_reference", dedupe(als_rows)), ("mid_packs", dedupe(mid_rows))):
        by_role: dict[str, list[dict]] = {}
        for r in rows:
            by_role.setdefault(r["role"], []).append(r)
        result["sources"][label] = {"all": summarize(rows), "by_role": {k: summarize(v) for k, v in sorted(by_role.items())}}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"patterns: als {len(dedupe(als_rows))}/{len(als_rows)}, mid {len(dedupe(mid_rows))}/{len(mid_rows)}; failed {sum(f1.values()) + sum(f2.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
