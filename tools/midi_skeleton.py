"""Generátor MIDI koster pro neurofunk / DnB. Pravidlový, deterministický (seed).

Vyrobí složku ve stejné konvenci jako `40_MIDI/_MIDI_KOSTRY/*` (Prolix, Sequence rebuild):
  01_sub_bass, 02_mid_reese, 03_bass_stab, 04_kick, 05_snare, 06_hihats, 07_sc_trigger, 08_lead,
  (volitelně 09_pad), `00_ALL_TRACKS.mid`, `skeleton.json` (parametry a seed, jde reprodukovat)
  a `PPAL_notes.md` (stejné noty v bar|beat notaci Producer Pal, jde vložit do `notes` u create-clip).

Co je naměřené a co je hypotéza:
- kick na 1. době a "and" 3. doby, snare na 2 a 4, basa nejčastěji jedna nota na 1. době:
  `naměřeno` (viz `data/midi/midi-stats.json`, vault `60 Rozbory/MIDI`).
- tvary rytmu reese, turnaround na konci čtyřtaktí, arp cely: `hypotéza`, je to kostra k přepsání, ne hotový riff.
  Generátor nenahrazuje ucho; dává 8 taktů, ze kterých si uděláš vlastní věc.

Použití:
  py -3.12 tools/midi_skeleton.py --name MOJE --key F --scale minor --bars 8 --seed 1
  py -3.12 tools/midi_skeleton.py --key C# --scale phrygian --bars 16 --density 3 --layers sub,reese,kick,snare,hats,sc
Výchozí cíl: D:/Ableton/40_MIDI/_MIDI_KOSTRY/GEN_<name>_<key><scale>_s<seed>
"""
from __future__ import annotations

import argparse
import json
import math
import random
import struct
import sys
from pathlib import Path

TPB = 960
BEATS_PER_BAR = 4
DEFAULT_OUT = Path("D:/Ableton/40_MIDI/_MIDI_KOSTRY")
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLATS = {"Db": 1, "Eb": 3, "Gb": 6, "Ab": 8, "Bb": 10}
SCALES = {
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "harmonic": [0, 2, 3, 5, 7, 8, 11],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
}
KICK, SNARE, HAT, OPEN_HAT = 36, 38, 42, 46

# (start, délka, výška, velocity) — vše v dobách (čtvrťové)
Note = tuple[float, float, int, int]

# Rytmy jednoho taktu pro reese (začátky not v dobách). Hypotéza, ne měření.
SPARSE = [[0, 2.5], [0, 1.5, 2.5], [0, 2.75], [0.5, 2.5]]
DENSE = [[0, 0.75, 2.5, 3.25], [0.5, 1.5, 2.5, 3.5], [0, 1.25, 2.5, 3], [0, 0.75, 1.5, 2.75]]

LAYERS = {
    "sub": "01_sub_bass",
    "reese": "02_mid_reese",
    "stab": "03_bass_stab",
    "kick": "04_kick",
    "snare": "05_snare",
    "hats": "06_hihats",
    "sc": "07_sc_trigger",
    "lead": "08_lead",
    "pad": "09_pad",
}
DEFAULT_LAYERS = ["sub", "reese", "stab", "kick", "snare", "hats", "sc", "lead"]


def parse_key(text: str) -> int:
    t = text.strip().capitalize()
    if t in FLATS:
        return FLATS[t]
    if t in NOTE_NAMES:
        return NOTE_NAMES.index(t)
    raise ValueError(f"neznámá tónina: {text}")


def deg(scale: list[int], degree: int, octave_base: int) -> int:
    """Stupeň stupnice (0 = tónika) na výšku. octave_base = MIDI výška tóniny v dané oktávě."""
    octs, idx = divmod(degree, len(scale))
    return octave_base + scale[idx] + 12 * octs


class Plan:
    """Společný harmonický plán: kořen každého taktu (stupeň) a případný turnaround v druhé půlce taktu."""

    def __init__(self, bars: int, rng: random.Random):
        self.bars = bars
        self.root = [0] * bars  # stupeň, na kterém bar začíná
        self.turn: dict[int, int] = {}  # takt -> stupeň od 3. doby
        for b in range(bars):
            if b % 4 == 3:  # konec čtyřtaktí
                self.turn[b] = rng.choice([5, 6, 4, 6])  # b6, b7, kvinta (b7 dvojnásobně častější)
        if bars >= 8:  # druhá půlka je trochu jinde: jeden takt na jiném stupni
            self.root[bars // 2 + 1 if bars > 8 else 5] = rng.choice([5, 6])

    def segments(self, b: int) -> list[tuple[float, int]]:
        segs = [(0.0, self.root[b])]
        if b in self.turn:
            segs.append((2.0, self.turn[b]))
        return segs


def gen_kick(bars: int, rng: random.Random) -> list[Note]:
    out: list[Note] = []
    for b in range(bars):
        o = b * BEATS_PER_BAR
        hits = [0.0, 2.5] if b % 2 == 0 else [0.0, rng.choice([2.5, 2.5, 2.75, 3.5])]
        if b % 4 == 3:
            hits = [0.0, 2.5]
        for h in hits:
            out.append((o + h, 0.25, KICK, 127))
    return out


def gen_snare(bars: int, rng: random.Random) -> list[Note]:
    out: list[Note] = []
    for b in range(bars):
        o = b * BEATS_PER_BAR
        out += [(o + 1.0, 0.25, SNARE, 110), (o + 3.0, 0.25, SNARE, 110)]
        if b % 8 == 7:  # fill: šestnáctiny s rostoucí velocity na posledních dvou dobách
            out = [n for n in out if not (n[0] == o + 3.0)]
            for i in range(8):
                out.append((o + 2.0 + i * 0.25, 0.25, SNARE, 70 + i * 8))
        elif b % 4 == 3 and rng.random() < 0.6:
            out.append((o + 3.75, 0.25, SNARE, 80))  # ghost před čtyřtaktím
    return sorted(out)


def gen_hats(bars: int, rng: random.Random) -> list[Note]:
    out: list[Note] = []
    for b in range(bars):
        o = b * BEATS_PER_BAR
        for i in range(8):
            t = o + i * 0.5
            vel = 90 if i % 2 == 0 else 60
            out.append((t, 0.25, HAT, vel + rng.randint(-6, 6)))
        if rng.random() < 0.7:  # otevřený hat na "and" 2. doby
            out.append((o + 1.5, 0.25, OPEN_HAT, 85))
    return sorted(out)


def gen_sc(kick: list[Note]) -> list[Note]:
    return [(t, 0.25, KICK, 127) for t, _d, _p, _v in kick]


def _fill_durations(starts: list[float], end: float, allowed: list[float]) -> list[float]:
    """Délka každé noty = mezera do další, sražená dolů na povolenou hodnotu."""
    durs = []
    for i, s in enumerate(starts):
        nxt = starts[i + 1] if i + 1 < len(starts) else end
        gap = nxt - s
        durs.append(max(d for d in allowed if d <= gap + 1e-9) if gap >= allowed[0] else allowed[0])
    return durs


def gen_sub(plan: Plan, scale: list[int], key: int) -> list[Note]:
    base = 24 + key  # C1 = 24, F1 = 29 (43 Hz)
    out: list[Note] = []
    for b in range(plan.bars):
        o = b * BEATS_PER_BAR
        segs = plan.segments(b)
        for i, (off, d) in enumerate(segs):
            end = segs[i + 1][0] if i + 1 < len(segs) else BEATS_PER_BAR
            out.append((o + off, end - off, deg(scale, d, base), 100))
    return out


def gen_reese(plan: Plan, scale: list[int], key: int, rng: random.Random, density: int) -> list[Note]:
    base = 36 + key  # C2
    pool = {1: SPARSE, 2: SPARSE + DENSE, 3: DENSE}[density]
    tmpl_a, tmpl_b = rng.choice(pool), rng.choice(pool)
    out: list[Note] = []
    for b in range(plan.bars):
        tmpl = tmpl_a if (b // 2) % 2 == 0 else tmpl_b
        if b % 4 == 3:
            tmpl = [0, 1.5, 2.5, 3.25] if density > 1 else [0, 2.5]  # turnaround takt je živější
        durs = _fill_durations(tmpl, BEATS_PER_BAR, [0.25, 0.5, 1.0, 2.0])
        segs = plan.segments(b)
        for s, d in zip(tmpl, durs):
            degree = [dd for off, dd in segs if off <= s][-1]
            pitch = deg(scale, degree, base)
            r = rng.random()
            if r < 0.22:
                pitch += 12
            elif r < 0.30:
                pitch = deg(scale, degree + 4, base)  # kvinta nad stupněm
            out.append((b * BEATS_PER_BAR + s, d, pitch, 100 + rng.randint(-8, 8)))
    return out


def gen_stab(plan: Plan, scale: list[int], key: int, rng: random.Random) -> list[Note]:
    base = 48 + key  # C3
    out: list[Note] = []
    for b in range(plan.bars):
        if b % 8 == 7:
            continue  # fill takt bez stabů
        o = b * BEATS_PER_BAR
        spots = rng.choice([[1.5], [1.5, 3.5], [0.75, 2.5], [3.5]])
        for s in spots:
            degree = [dd for off, dd in plan.segments(b) if off <= s][-1]
            for iv in (0, 4):  # tónika + kvinta stupně
                out.append((o + s, 0.25, deg(scale, degree + iv, base), 112))
    return out


def gen_lead(plan: Plan, scale: list[int], key: int, rng: random.Random) -> list[Note]:
    base = 60 + key  # C3 v Live
    cell_tones = [0, 2, 4, 6, 7]  # tóny akordu (stupně: 1, b3, 5, b7, oktáva)
    cell = [rng.choice(cell_tones) for _ in range(4)]
    cell[0] = 0
    out: list[Note] = []
    for b in range(plan.bars):
        o = b * BEATS_PER_BAR
        shift = [dd for off, dd in plan.segments(b)][0]
        length = 12 if b % 4 == 3 else 16  # na konci čtyřtaktí dej poslední dobu ticho
        for i in range(length):
            if i % 4 == 3 and rng.random() < 0.35:
                continue  # mezera, aby arp dýchal
            degree = cell[i % 4] + (shift if b % 2 == 0 else 0)
            out.append((o + i * 0.25, 0.25, deg(scale, degree, base), 90 + (10 if i % 4 == 0 else 0)))
    return out


def gen_pad(plan: Plan, scale: list[int], key: int) -> list[Note]:
    base = 48 + key
    prog = [0, 5, 6, 4]  # i - VI - VII - v
    out: list[Note] = []
    for b in range(plan.bars):
        root = prog[b % 4]
        for iv in (0, 2, 4):
            out.append((b * BEATS_PER_BAR, float(BEATS_PER_BAR), deg(scale, root + iv, base), 85))
    return out


def generate(key: int, scale_name: str, bars: int, seed: int, density: int, layers: list[str]) -> dict[str, list[Note]]:
    rng = random.Random(seed)
    scale = SCALES[scale_name]
    plan = Plan(bars, rng)
    kick = gen_kick(bars, rng)
    made: dict[str, list[Note]] = {
        "sub": gen_sub(plan, scale, key),
        "reese": gen_reese(plan, scale, key, rng, density),
        "stab": gen_stab(plan, scale, key, rng),
        "kick": kick,
        "snare": gen_snare(bars, rng),
        "hats": gen_hats(bars, rng),
        "sc": gen_sc(kick),
        "lead": gen_lead(plan, scale, key, rng),
        "pad": gen_pad(plan, scale, key),
    }
    return {name: made[name] for name in layers}


# ---------- zápis SMF ----------

def _vlq(v: int) -> bytes:
    out = [v & 0x7F]
    v >>= 7
    while v:
        out.append((v & 0x7F) | 0x80)
        v >>= 7
    return bytes(reversed(out))


def _track(events: list[tuple[int, int, bytes]]) -> bytes:
    """events = (tick, pořadí, data); pořadí 0 = note_off/meta před note_on ve stejném ticku."""
    body = bytearray()
    last = 0
    for tick, _o, data in sorted(events, key=lambda e: (e[0], e[1])):
        body += _vlq(tick - last) + data
        last = tick
    body += _vlq(0) + b"\xff\x2f\x00"
    return b"MTrk" + struct.pack(">I", len(body)) + bytes(body)


def _meta_text(kind: int, text: str) -> bytes:
    raw = text.encode("ascii", "replace")
    return bytes([0xFF, kind]) + _vlq(len(raw)) + raw


def _note_events(notes: list[Note], channel: int = 0) -> list[tuple[int, int, bytes]]:
    ev = []
    for start, dur, pitch, vel in notes:
        on = round(start * TPB)
        off = round((start + dur) * TPB)
        ev.append((on, 1, bytes([0x90 | channel, pitch, max(1, min(127, vel))])))
        ev.append((off, 0, bytes([0x80 | channel, pitch, 0])))
    return ev


def write_midi(path: Path, tracks: dict[str, list[Note]], bpm: float) -> None:
    tempo = round(60_000_000 / bpm)
    head_ev = [
        (0, 0, _meta_text(0x03, "tempo")),
        (0, 0, b"\xff\x51\x03" + tempo.to_bytes(3, "big")),
        (0, 0, b"\xff\x58\x04\x04\x02\x18\x08"),
    ]
    chunks = [_track(head_ev)]
    for i, (name, notes) in enumerate(tracks.items()):
        ev = [(0, 0, _meta_text(0x03, name))] + _note_events(notes, 9 if name in ("kick", "snare", "hats", "sc") else 0)
        chunks.append(_track(ev))
    hdr = b"MThd" + struct.pack(">IHHH", 6, 1, len(chunks), TPB)
    path.write_bytes(hdr + b"".join(chunks))


# ---------- Producer Pal bar|beat ----------

def note_name(pitch: int) -> str:
    return f"{NOTE_NAMES[pitch % 12]}{pitch // 12 - 2}"  # Live: C3 = 60


def dur_token(d: float) -> str:
    sixteenths = max(1, round(d * 4))
    if sixteenths % 16 == 0:
        return f"{sixteenths // 16}bar"
    g = math.gcd(sixteenths, 16)
    num, den = sixteenths // g, 16 // g
    return f"n/{den}" if num == 1 else f"n{num}/{den}"


def to_barbeat(notes: list[Note]) -> str:
    """Jedna řádka na notu: `v100 n/4 C1 1|1`. Stavové prefixy se opakují, takže řádky jdou míchat."""
    lines = []
    for start, dur, pitch, vel in sorted(notes):
        bar, beat = divmod(start, BEATS_PER_BAR)
        beat_txt = f"{beat + 1:g}"
        lines.append(f"v{vel} {dur_token(dur)} {note_name(pitch)} {int(bar) + 1}|{beat_txt}")
    return "\n".join(lines)


# ---------- CLI ----------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", default="KOSTRA")
    ap.add_argument("--key", default="F", help="C, C#, Db, F ...")
    ap.add_argument("--scale", default="minor", choices=sorted(SCALES))
    ap.add_argument("--bpm", type=float, default=174.0)
    ap.add_argument("--bars", type=int, default=8)
    ap.add_argument("--seed", type=int, default=None, help="bez seedu se vylosuje a zapíše do skeleton.json")
    ap.add_argument("--density", type=int, default=2, choices=[1, 2, 3], help="1 řídké, 3 hustý reese rytmus")
    ap.add_argument("--layers", default=",".join(DEFAULT_LAYERS), help=f"z: {','.join(LAYERS)}")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    layers = [x.strip() for x in args.layers.split(",") if x.strip()]
    bad = [x for x in layers if x not in LAYERS]
    if bad:
        ap.error(f"neznámé vrstvy: {bad}")
    key = parse_key(args.key)
    seed = args.seed if args.seed is not None else random.SystemRandom().randint(1, 9999)

    made = generate(key, args.scale, args.bars, seed, args.density, layers)
    out = args.out or DEFAULT_OUT / f"GEN_{args.name}_{NOTE_NAMES[key].replace('#', 's')}{args.scale}_s{seed}"
    out.mkdir(parents=True, exist_ok=True)

    for name, notes in made.items():
        write_midi(out / f"{LAYERS[name]}_{args.bars}bar.mid", {name: notes}, args.bpm)
    write_midi(out / "00_ALL_TRACKS.mid", made, args.bpm)
    (out / "skeleton.json").write_text(
        json.dumps(
            {"name": args.name, "key": NOTE_NAMES[key], "scale": args.scale, "bpm": args.bpm, "bars": args.bars,
             "seed": seed, "density": args.density, "layers": layers,
             "notes": {n: len(v) for n, v in made.items()}},
            indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    md = [f"# {args.name} — bar|beat pro Producer Pal ({NOTE_NAMES[key]} {args.scale}, {args.bpm:g} BPM, {args.bars} taktů, seed {seed})", ""]
    for name, notes in made.items():
        md += [f"## {LAYERS[name]}", "```", to_barbeat(notes), "```", ""]
    (out / "PPAL_notes.md").write_text("\n".join(md), encoding="utf-8")

    print(f"{out}")
    for name, notes in made.items():
        print(f"  {LAYERS[name]:<16} {len(notes):>3} not")
    return 0


if __name__ == "__main__":
    sys.exit(main())
