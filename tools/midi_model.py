"""Model pro generátor MIDI (Max for Live zařízení NPOS Skeleton): co se v referencích hraje, po rolích a po taktech.

Jen čtení zdrojů, výstup jedno JSON s čísly (žádné názvy packů, cest ani celé melodie):
- `slot_prob`: pravděpodobnost nástupu na každé z 16 šestnáctin taktu,
- `rhythms`: nejčastější rytmy jednoho taktu (16 znaků `x`/`.`) s počty, `rhythms2` totéž pro dvoutakty (32 znaků),
- `dur16`: rozložení délek not v šestnáctinách, `motion`: pohyb jednohlasé linky,
- `offsets`: výšky vůči tónice vzoru (0–11), `octave_up`: podíl not o oktávu a víc nad nejnižší,
- `vel`: průměrná velocity na době a mimo dobu, `density`: nástupy na takt (kvartily).

Role z názvů stop a souborů jsou `hypotéza` (stejná pravidla jako `midi_stats.py`). Bicí se dělí na kick, snare, hats
podle názvu nebo podle GM výšky. Role s méně než 10 vzory nebo 3 zdroji má `enough: false`; zařízení pak jede podle pravidel.

POZOR: rytmy pochází i z placených packů. Výstup je pro osobní použití, zařízení s vloženým modelem nesdílet veřejně.

Použití:
  py -3.12 tools/midi_model.py --als-roots _sources/projects --mid-roots D:/Ableton/20_Samples D:/Ableton/40_MIDI \\
      --exclude _MIDI_KOSTRY --out data/midi/_local/midi-model.json
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
from collections import Counter, defaultdict
from pathlib import Path

try:
    import als_stats as A
    import midi_stats as M
except ImportError:  # spuštěno z kořene repa
    sys.path.insert(0, str(Path(__file__).parent))
    import als_stats as A
    import midi_stats as M

TOP_RHYTHMS = 48
DUR_CLASSES = [1, 2, 3, 4, 6, 8, 12, 16]
DRUM_NAME = [
    ("kick", re.compile(r"kick|kik|\bbd\b", re.I)),
    ("snare", re.compile(r"snare|clap|\bsd\b|\bsn\b", re.I)),
    ("hats", re.compile(r"hat|\bhh\b|hihat|ride|shaker|cymb", re.I)),
]
REESE = re.compile(r"reese|reece|rees\b", re.I)  # reese podle názvu stopy / souboru (hypotéza jako ostatní role)
GM = {35: "kick", 36: "kick", 37: "snare", 38: "snare", 39: "snare", 40: "snare",
      42: "hats", 44: "hats", 46: "hats", 51: "hats", 53: "hats", 59: "hats"}

Note = tuple[float, float, int, int]


def split_roles(text: str, notes: list[Note]) -> dict[str, list[Note]]:
    """Role vzoru; bicí rozdělené na kick/snare/hats, reese oddělená od ostatní basy. Vrací role -> noty."""
    if REESE.search(text):
        return {"reese": notes}
    role = M.role_of(text)
    if role != "drums":
        return {role: notes}
    pitches = {n[2] for n in notes}
    for sub, rx in DRUM_NAME:
        if rx.search(text) and len(pitches) <= 2:
            return {sub: notes}
    out: dict[str, list[Note]] = defaultdict(list)
    for n in notes:
        sub = GM.get(n[2])
        if sub:
            out[sub].append(n)
    return dict(out)


def bars_of(notes: list[Note], length: float) -> list[list[Note]]:
    nb = max(1, math.ceil(length / 4 - 1e-6))
    out = [[] for _ in range(nb)]
    for n in notes:
        k = int(n[0] // 4)
        if 0 <= k < nb:
            out[k].append((n[0] - 4 * k, n[1], n[2], n[3]))
    return out


def rhythm(bar: list[Note]) -> str | None:
    """16 znaků, None když je v taktu nástup mimo mřížku 1/16 (triolky a swing se do banky nedávají)."""
    cells = ["."] * 16
    for s, *_ in bar:
        pos = s / 0.25
        if abs(pos - round(pos)) > 0.16:
            return None
        cells[int(round(pos)) % 16] = "x"
    return "".join(cells)


def line(notes: list[Note]) -> list[int]:
    """Jednohlasá linka: nejnižší tón v každém nástupu."""
    by: dict[float, int] = {}
    for s, _d, p, _v in notes:
        k = round(s, 4)
        by[k] = min(p, by.get(k, 999))
    return [by[k] for k in sorted(by)]


def tonic(notes: list[Note]) -> int:
    """Tónina vzoru = třída tónu s největší celkovou délkou mezi nejnižšími tóny."""
    w: Counter[int] = Counter()
    low = min(n[2] for n in notes)
    for s, d, p, _v in notes:
        if p < low + 12:
            w[p % 12] += d
    return w.most_common(1)[0][0]


class Acc:
    def __init__(self) -> None:
        self.sources: set[str] = set()
        self.patterns = 0
        self.bars = 0
        self.slot = [0] * 16
        self.rhythms: Counter[str] = Counter()
        self.rhythms2: Counter[str] = Counter()  # dvoutakty: DnB groove je dvoutaktový, druhý takt sám o sobě nedává smysl
        self.dens: list[int] = []
        self.dur: Counter[int] = Counter()
        self.motion: Counter[str] = Counter()
        self.offsets: Counter[int] = Counter()
        self.oct_up = [0, 0]
        self.vel_on: list[int] = []
        self.vel_off: list[int] = []

    def add(self, notes: list[Note], length: float, source: str, pitched: bool) -> None:
        if len(notes) < M.MIN_NOTES:
            return
        self.sources.add(source)
        self.patterns += 1
        bars = bars_of(notes, length)
        for k in range(0, len(bars) - 1, 2):
            a, b = rhythm(bars[k]), rhythm(bars[k + 1])
            if a and b and "x" in a + b:
                self.rhythms2[a + b] += 1
        for bar in bars:
            if not bar:
                continue
            self.bars += 1
            onsets = sorted({round(n[0], 4) for n in bar})
            self.dens.append(len(onsets))
            r = rhythm(bar)
            if r:
                self.rhythms[r] += 1
                for i, c in enumerate(r):
                    self.slot[i] += c == "x"
        for s, d, p, v in notes:
            k = min(DUR_CLASSES, key=lambda c: abs(c - d * 4))
            self.dur[k] += 1
            (self.vel_on if abs((s % 1.0)) < 0.04 else self.vel_off).append(v)
        if pitched:
            t = tonic(notes)
            ln = line(notes)
            low = min(ln)
            for p in ln:
                self.offsets[(p - t) % 12] += 1
                self.oct_up[0] += p >= low + 12
                self.oct_up[1] += 1
            for a, b in zip(ln, ln[1:]):
                d = abs(b - a)
                self.motion["repeat" if d == 0 else "step" if d <= 2 else "mid" if d <= 6 else "leap" if d <= 11 else "octave"] += 1

    def result(self) -> dict:
        enough = self.patterns >= M.MIN_PATTERNS and len(self.sources) >= M.MIN_SOURCES
        out: dict = {"n_patterns": self.patterns, "n_sources": len(self.sources), "n_bars": self.bars, "enough": enough}
        if not enough or not self.bars:
            return out
        grid_bars = sum(self.rhythms.values()) or 1
        tot = lambda c: sum(c.values()) or 1  # noqa: E731
        out.update({
            "slot_prob": [round(x / grid_bars, 3) for x in self.slot],
            "rhythms": [[r, c] for r, c in self.rhythms.most_common(TOP_RHYTHMS)],
            "rhythms2": [[r, c] for r, c in self.rhythms2.most_common(TOP_RHYTHMS)],
            "density": M.quant([float(x) for x in self.dens]),
            "dur16": {str(k): round(self.dur[k] / tot(self.dur), 3) for k in DUR_CLASSES},
            "vel": {"on": round(sum(self.vel_on) / len(self.vel_on)) if self.vel_on else 100,
                    "off": round(sum(self.vel_off) / len(self.vel_off)) if self.vel_off else 90},
        })
        if self.offsets:
            out["offsets"] = [round(self.offsets[i] / tot(self.offsets), 3) for i in range(12)]
            out["octave_up"] = round(self.oct_up[0] / max(1, self.oct_up[1]), 3)
            out["motion"] = {k: round(self.motion[k] / tot(self.motion), 3) for k in ("repeat", "step", "mid", "leap", "octave")}
        return out


PITCHED = {"sub", "bass", "reese", "stab", "lead", "harmony"}

# ---------- fráze a progrese (jen .mid s tóninou v názvu) ----------
# Linka a akordy se ukládají ve stupních proti tónině z názvu souboru, aby šly přenést do tóniny klipu.
# Bez tóniny v názvu (AC13 loopy apod.) se nic neukládá: odhad tóniny by do frází zanesl chyby.
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}
KEY_EXPLICIT = re.compile(r"(?:^|[ _\-(\[])([A-G](?:#|b)?)\s?(min|minor|m|maj|major)(?=$|[ _\-)\].])")
KEY_BARE = re.compile(r"(?:^|[ _\-])([A-G](?:#|b)?)(?=$|[ _\-])")
PHRASE_ROLES = {"sub", "bass", "reese", "lead"}
PHRASE_BARS = 4
MAX_PHRASES = 160
MAX_PROGS = 120


def key_of(rel: Path) -> tuple[int, bool] | None:
    """(tónika 0–11, dur?) z názvu souboru nebo složky. Nejdřív explicitní moll/dur, pak samotné písmeno (…_F_175)."""
    parts = [rel.stem] + list(reversed(rel.parent.parts))
    for part in parts:
        m = KEY_EXPLICIT.search(part)
        if m:
            return NOTE_NAMES.index(FLAT.get(m.group(1), m.group(1))), m.group(2).startswith("maj")
    for part in parts:
        m = KEY_BARE.search(part)
        if m:
            return NOTE_NAMES.index(FLAT.get(m.group(1), m.group(1))), False
    return None


def _tile(nb: int) -> list[int]:
    """Začátky čtyřtaktových oken; krátký vzor (1–2 takty) se zopakuje do čtyř."""
    return list(range(0, nb - PHRASE_BARS + 1, PHRASE_BARS)) if nb >= PHRASE_BARS else [0]


def phrase_windows(notes: list[Note], tonic: int, top: bool) -> tuple[list[list[list[int]]], str]:
    """Jednohlasá linka po čtyřtaktech: [slot 1/16, délka v 1/16, půltóny nad tónikou pod nejnižší notou].
    top = vrchní tón (lead), jinak spodní (basy). Vrací i formu prvních 8 taktů (A = stejný takt jako dřív)."""
    by: dict[float, tuple[int, float]] = {}
    for s, d, p, _v in notes:
        k = round(s * 4) / 4
        if k not in by or (p > by[k][0] if top else p < by[k][0]):
            by[k] = (p, d)
    line = sorted((s, p, d) for s, (p, d) in by.items())
    low = min(p for _s, p, _d in line)
    ref = tonic + 12 * math.floor((low - tonic) / 12)
    nb = max(1, math.ceil(max(s + d for s, _p, d in line) / 4 - 1e-6))
    bars = [tuple((round((s - 4 * b) * 4), p - ref) for s, p, _d in line if 4 * b <= s < 4 * b + 4) for b in range(nb)]
    labels, seen = [], {}
    for x in bars[:8]:
        seen.setdefault(x, "ABCDEFGH"[len(seen) % 8])
        labels.append(seen[x])
    out = []
    for w in _tile(nb):
        span = min(PHRASE_BARS, nb) * 4
        ph = [[round((s - 4 * w) * 4), max(1, min(64, round(d * 4))), p - ref] for s, p, d in line if 4 * w <= s < 4 * w + span]
        reps = PHRASE_BARS * 4 // span
        ph = [[sl + k * span * 4, du, pr] for k in range(reps) for sl, du, pr in ph]
        if len(ph) >= 3:
            out.append(ph)
    return out, "".join(labels)


def progression_windows(notes: list[Note], tonic: int) -> list[list]:
    """Akordy po čtyřtaktech: [start 1/16, délka 1/16, basový tón v půltónech od tóniky (0–11), voicing od basu]."""
    by: dict[float, list[tuple[int, float]]] = defaultdict(list)
    for s, d, p, _v in notes:
        by[round(s * 4) / 4].append((p, d))
    chords = []
    for s in sorted(by):
        ps = sorted({p for p, _d in by[s]})
        if len(ps) >= 3:
            chords.append((s, max(d for _p, d in by[s]), ps))
    if not chords:
        return []
    nb = max(1, math.ceil(max(s + d for s, d, _ps in chords) / 4 - 1e-6))
    out = []
    for w in _tile(nb):
        span = min(PHRASE_BARS, nb) * 4
        pr = [[round((s - 4 * w) * 4), max(1, min(64, round(d * 4))), (ps[0] - tonic) % 12, [p - ps[0] for p in ps]]
              for s, d, ps in chords if 4 * w <= s < 4 * w + span]
        reps = PHRASE_BARS * 4 // span
        pr = [[st + k * span * 4, du, ro, vo] for k in range(reps) for st, du, ro, vo in pr]
        if pr:
            out.append(pr)
    return out


def _cap(items: list, n: int) -> list:
    """Deterministický výběr n položek rozprostřených přes celý seznam (ne jen první pack)."""
    if len(items) <= n:
        return items
    step = len(items) / n
    return [items[int(i * step)] for i in range(n)]


def build(als_roots: list[Path], mid_roots: list[Path], exclude: list[str]) -> dict:
    acc: dict[str, Acc] = defaultdict(Acc)
    seen: set[str] = set()
    failed: Counter[str] = Counter()
    phrases: dict[str, list] = defaultdict(list)
    phrase_seen: set[str] = set()
    forms: dict[str, Counter[str]] = defaultdict(Counter)
    progs: list = []

    def feed_keyed(text: str, notes: list[Note], key: tuple[int, bool]) -> None:
        if key[1]:  # dur vynechán: banka je pro moll (DnB)
            return
        for role, ns in split_roles(text, notes).items():
            if role in PHRASE_ROLES and len(ns) >= 3:
                wins, form = phrase_windows(ns, key[0], top=role == "lead")
                forms[role][form] += 1
                for ph in wins:
                    fp = role + json.dumps(ph)
                    if fp not in phrase_seen:
                        phrase_seen.add(fp)
                        phrases[role].append(ph)
            elif role == "harmony":
                for pr in progression_windows(ns, key[0]):
                    if pr not in progs:
                        progs.append(pr)

    def feed(text: str, notes: list[Note], length: float, src: str) -> None:
        fp = M.fingerprint(notes)
        if fp in seen:
            return
        seen.add(fp)
        for role, ns in split_roles(text, notes).items():
            if role in ("other", "songstarter"):
                continue
            acc[role].add(sorted(ns), length, src, role in PITCHED)

    for group, root, p in A.find_sets(als_roots):
        if group != "reference":
            continue
        try:
            pats = M.als_patterns(A.read_set(p))
        except (OSError, EOFError, ET.ParseError, ValueError) as e:
            failed[type(e).__name__] += 1
            continue
        src = hashlib.sha1(str(p.relative_to(root)).encode()).hexdigest()[:8]
        for name, notes, length in pats:
            if math.ceil(length / 4 - 1e-6) <= M.MAX_BARS:
                feed(name, notes, length, src)

    for root in mid_roots:
        for p in sorted(root.rglob("*.mid")) + sorted(root.rglob("*.midi")):
            rel = p.relative_to(root)
            if any(x.lower() in str(rel).lower() for x in exclude) or "__MACOSX" in rel.parts:
                continue
            try:
                notes = M.read_smf(p.read_bytes())
            except (OSError, ValueError, IndexError, struct.error) as e:
                failed[type(e).__name__] += 1
                continue
            if not notes:
                continue
            length = max(4.0, math.ceil(max(n[0] + n[1] for n in notes) / 4 - 1e-6) * 4.0)
            if length / 4 <= M.MAX_BARS:
                src = hashlib.sha1(M._source_key(root, rel).encode()).hexdigest()[:8]
                feed(M.role_text(root, rel), notes, length, src)
                key = key_of(rel)
                if key:
                    feed_keyed(M.role_text(root, rel), notes, key)

    return {
        "basis": "midi_notes", "confidence": "naměřeno; role jsou hypotéza",
        "note": "Pro osobní použití: rytmy a fráze pochází i z placených packů.",
        "failed": dict(failed),
        "roles": {r: acc[r].result() for r in sorted(acc)},
        "phrases": {r: _cap(v, MAX_PHRASES) for r, v in sorted(phrases.items())},
        "forms": {r: [[f, c] for f, c in v.most_common(20) if len(f) >= 2] for r, v in sorted(forms.items())},
        "progressions": _cap(progs, MAX_PROGS),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--als-roots", nargs="*", type=Path, default=[])
    ap.add_argument("--mid-roots", nargs="*", type=Path, default=[])
    ap.add_argument("--exclude", nargs="*", default=["_MIDI_KOSTRY"])
    ap.add_argument("--out", type=Path, default=Path("data/midi/_local/midi-model.json"))
    a = ap.parse_args(argv)
    model = build(a.als_roots, a.mid_roots, a.exclude)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(model, ensure_ascii=False, indent=1), encoding="utf-8")
    for r, v in model["roles"].items():
        print(f"{r:<8} vzorů {v['n_patterns']:>4}  zdrojů {v['n_sources']:>3}  taktů {v['n_bars']:>5}  {'OK' if v['enough'] else 'málo dat'}")
    print("fráze:", {r: len(v) for r, v in model["phrases"].items()}, " progrese:", len(model["progressions"]))
    print(f"selhalo: {model['failed']}  ->  {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
