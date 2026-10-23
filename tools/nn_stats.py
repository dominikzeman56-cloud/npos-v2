"""Statistika přepisů z NeuralNote (audio na MIDI): basa po taktech, třídy taktů, délky not, kořeny vůči tónice.

Vstup: složka se soubory `*_NNTranscription.mid` (jedno tempo, stopy Bass / Distorted Guitar / Strings / Synth Lead / Drums).
Výstup: jen čísla (`data/midi/nn-stats.json`), bez názvů skladeb, bez konkrétních výšek (kořeny jsou intervaly od tónice).
Podrobnosti po taktech jdou do lokálního `--local` souboru (gitignored).

Třídy taktu basy (podle počtu not a rozestupů v šestnáctinách):
  long       0-3 noty (dlouhé tóny)
  call       4-6 not, nestejné rozestupy (synkopa)
  eighths    7-9 not, rozestupy 2 šestnáctiny
  sixteenths 12 a více not
  mixed      ostatní
Délky not v klíčích `note_length_share` jsou v šestnáctinách (2 = osmina, 4 = čtvrťová).
Štítky jistoty: `naměřeno` z přepisu; přepis je automatický, oktávy a hustá místa mohou být nepřesné.

Použití:
  py -3.12 tools/nn_stats.py --dir D:/Ableton/40_MIDI/Neural_Note --out data/midi/nn-stats.json \\
      --local data/midi/_local/nn-bars.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import mido

BASS_TRACK = "Bass"
MIN_BASS_NOTES = 40


def read_tracks(path: Path) -> tuple[float, dict[str, list[tuple[float, float, int, int]]]]:
    """Tempo (BPM) a noty po stopách: (začátek v dobách, délka v dobách, výška, velocity)."""
    m = mido.MidiFile(str(path))
    ppq = m.ticks_per_beat
    tempos = [e.tempo for t in m.tracks for e in t if e.type == "set_tempo"]
    bpm = round(60e6 / tempos[0], 2) if tempos else 120.0
    out: dict[str, list[tuple[float, float, int, int]]] = {}
    for t in m.tracks:
        tick, on, notes = 0, {}, []
        for e in t:
            tick += e.time
            if e.type == "note_on" and e.velocity > 0:
                on[e.note] = (tick, e.velocity)
            elif e.type in ("note_off", "note_on") and e.note in on:
                a, v = on.pop(e.note)
                notes.append((a / ppq, (tick - a) / ppq, e.note, v))
        if notes:
            out[t.name or f"trk{len(out)}"] = sorted(notes)
    return bpm, out


def grid_phase(starts: list[float]) -> float:
    """Posun mřížky 1/16 (v dobách), který nejméně vzdaluje začátky not od šestnáctin."""
    best, phase = 9.0, 0.0
    for i in range(50):
        ph = i * 0.005
        err = sum(abs((s - ph) * 4 - round((s - ph) * 4)) for s in starts) / max(1, len(starts))
        if err < best:
            best, phase = err, ph
    return phase


def classify(notes: list[tuple[float, float, int, int]], bar_start: float) -> tuple[str, list[int], list[int]]:
    """Třída taktu, kroky (0-15) a délky v šestnáctinách."""
    steps = sorted({int(round((n[0] - bar_start) * 4)) for n in notes if 0 <= round((n[0] - bar_start) * 4) < 16})
    lens = [max(1, int(round(n[1] * 4))) for n in sorted(notes)]
    c = len(steps)
    if c <= 3:
        return "long", steps, lens
    gaps = [b - a for a, b in zip(steps, steps[1:])]
    if 7 <= c <= 9 and gaps and Counter(gaps).most_common(1)[0][0] == 2 and Counter(gaps).most_common(1)[0][1] >= c - 3:
        return "eighths", steps, lens
    if c >= 12:
        return "sixteenths", steps, lens
    if 4 <= c <= 6:
        return "call", steps, lens
    return "mixed", steps, lens


def bar_rows(notes: list[tuple[float, float, int, int]], origin: float) -> list[dict]:
    """Rozbor po taktech pro basu: třída, kořen (výška nejdelšího tónu), hustota."""
    n_bars = int((max(n[0] for n in notes) - origin) // 4) + 1
    rows = []
    for b in range(n_bars):
        s = origin + 4 * b
        sel = [n for n in notes if s - 0.1 <= n[0] < s + 4 - 0.1]
        if not sel:
            rows.append({"bar": b + 1, "n": 0})
            continue
        low = [n for n in sel if n[2] < 52] or sel
        w: Counter = Counter()
        for n in low:
            w[n[2]] += n[1]
        root = w.most_common(1)[0][0]
        cls, steps, lens = classify(low, s)
        rows.append({"bar": b + 1, "n": len(sel), "cls": cls, "root": root, "steps": steps, "lens": lens})
    return rows


def tonic_pc(rows: list[dict]) -> int:
    """Tónika = nejčastější pitch class kořenů v taktech."""
    c = Counter(r["root"] % 12 for r in rows if r.get("root") is not None)
    return c.most_common(1)[0][0] if c else 0


def analyse(path: Path) -> tuple[dict | None, list[dict]]:
    bpm, tracks = read_tracks(path)
    bass = tracks.get(BASS_TRACK) or []
    if len(bass) < MIN_BASS_NOTES:
        return None, []
    phase = grid_phase([n[0] for n in bass])
    rows = bar_rows(bass, phase)
    active = [r for r in rows if r["n"] > 0]
    tonic = tonic_pc(active)
    cls = Counter(r["cls"] for r in active)
    lens = Counter()
    for r in active:
        for ln in r["lens"]:
            lens["1" if ln <= 1 else "2" if ln == 2 else "3" if ln == 3 else "4" if ln == 4 else "5+"] += 1
    total_len = sum(lens.values()) or 1
    rel = Counter((r["root"] - tonic) % 12 for r in active)
    semi = sum(1 for a, b in zip(active, active[1:]) if abs(a["root"] - b["root"]) == 1)
    octave_drop = 0
    for a, b in zip(active, active[1:]):
        if a["cls"] == "call" and b["cls"] == "eighths" and a["root"] % 12 == b["root"] % 12 and a["root"] - b["root"] == 12:
            octave_drop += 1
    def med(xs):
        xs = sorted(xs)
        return xs[len(xs) // 2] if xs else None

    m_call, m_eig = med([r["root"] for r in active if r["cls"] == "call"]), med([r["root"] for r in active if r["cls"] == "eighths"])
    res = {
        "bpm": bpm,
        "bars": len(rows),
        "active_bars": len(active),
        "grid_phase_beats": round(phase, 3),
        "tracks": {k: len(v) for k, v in tracks.items()},
        "bar_classes": dict(cls),
        "note_length_share": {k: round(v / total_len, 3) for k, v in sorted(lens.items())},
        "roots_vs_tonic": {str(k): v for k, v in sorted(rel.items())},
        "semitone_root_steps": semi,
        "call_to_eighths_octave_drops": octave_drop,
        "median_root_eighths_minus_call_semitones": (m_eig - m_call) if m_call is not None and m_eig is not None else None,
    }
    return res, rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True, type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--local", type=Path, help="podrobnosti po taktech (lokálně, gitignored)")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    files = sorted(a.dir.glob("*_NNTranscription.mid"))
    results, local, skipped = [], {}, 0
    for f in files:
        try:
            r, rows = analyse(f)
        except (OSError, ValueError, EOFError) as e:
            print(f"přeskočeno ({e.__class__.__name__}): {f.name}", file=sys.stderr)
            skipped += 1
            continue
        if r is None:
            skipped += 1
            continue
        results.append(r)
        local[f.name] = rows
    summary = {
        "basis": "neuralnote_mid",
        "confidence": "naměřeno z automatického přepisu; počet skladeb malý, nejde o pravidla",
        "files": len(results),
        "skipped": skipped,
        "per_file": results,
    }
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if a.local:
        a.local.parent.mkdir(parents=True, exist_ok=True)
        a.local.write_text(json.dumps(local, ensure_ascii=False) + "\n", encoding="utf-8")
    for i, r in enumerate(results, 1):
        print(f"#{i} {r['bpm']} BPM, {r['bars']} taktů, aktivních {r['active_bars']}, třídy {r['bar_classes']}, "
              f"délky {r['note_length_share']}, kořeny {r['roots_vs_tonic']}, pád call→osminy o oktávu {r['call_to_eighths_octave_drops']}, medián výšky osmin minus call {r['median_root_eighths_minus_call_semitones']} půltónů")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
