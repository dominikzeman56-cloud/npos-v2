#!/usr/bin/env python3
"""stem_to_live.py — z tracku (stemy, nebo plný mix) udělá MIDI kostru pro Ableton: mřížka, sekce a noty. Jen čtení.

Výstup je plán (`plan.json`) a noty v zápisu Producer Pal (`notes_<role>_<od>-<do>.txt`), které se do Live zapíšou
nástrojem ppal-create-clip. Sám do Live nic nezapisuje a žádné audio nekopíruje.

Co měří:
  - tempo (autokorelace nástupů, když není zadané) a fázi mřížky: kde leží šestnáctiny a kde začíná takt 1
  - kick a snare na 1/16 (nástupy v pásmu), linku subu po 1/16 (výška ze špičky spektra 25–120 Hz, okno 200 ms)
  - rytmus mid basy (nástupy v pásmu 100–3000 Hz); výšky mids se NEMĚŘÍ, noty jsou zástupné (oktáva nad subem)
  - úseky, kde hraje sub (z nich jsou klipy)

Dva režimy:
  stemy:    --dir <složka> --kick "kik" --snare "snare" --sub "sub" --mids "main mids"      (štítek `measured`)
  plný mix: --mix <soubor>   kick, snare, sub i mids se berou z pásem jednoho souboru       (štítek `estimated`:
            sub přesahuje do pásma kicku, bicí do pásma mids; rytmus mids z plného mixu je nejvýš hypotéza)

Použití:
  py -3.12 tools/stem_to_live.py --dir "D:/Ableton/30_Stems/<track>" --bpm 172 --kick kik --snare snare --sub sub --mids "main mids" --out <mimo repo>
  py -3.12 tools/stem_to_live.py --mix "D:/Downloads/track.mp3" --out <mimo repo>
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import signal as sig

sys.path.insert(0, str(Path(__file__).parent))
import analyze_track as at  # noqa: E402
import stem_bass as sb  # noqa: E402

SR = at.SR
ROOT = Path(__file__).resolve().parent.parent
BANDS = {"kick": (30.0, 150.0), "snare": (150.0, 6000.0), "sub": (22.0, 120.0), "mids": (100.0, 3000.0)}
MIX_BANDS = {"kick": (35.0, 110.0), "snare": (1500.0, 6000.0), "sub": (22.0, 75.0), "mids": (150.0, 1200.0)}


def estimate_bpm(mono: np.ndarray, lo: float = 120.0, hi: float = 200.0) -> float:
    """Tempo z autokorelace nástupů v pásmu kicku a snare (součet přes 64 dob). Hrubě po 0,5, pak jemně po 0,01.

    Rozsah 120–200: poloviční tempo dává stejné skóre, takže se bez omezení plete 86 a 172. Pomalejší track: zadej --bpm.
    """
    acs = []
    for a, b in ((30.0, 150.0), (1500.0, 6000.0)):
        e = sb.band_envelope(mono, a, b)
        fl = np.maximum(np.diff(e), 0)
        fl = fl - fl.mean()
        n = 1 << int(np.ceil(np.log2(2 * len(fl))))
        ac = np.fft.irfft(np.abs(np.fft.rfft(fl, n)) ** 2)[: len(fl) // 2]
        acs.append(ac / max(ac[0], 1e-12))
    ac = acs[0] + acs[1]

    def score(bpm: float) -> float:
        lags = np.round(np.arange(1, 65) * 60.0 / bpm * sb.ENV_FS).astype(int)
        lags = lags[lags < len(ac)]
        return float(ac[lags].mean()) if len(lags) else -1.0

    coarse = max(np.arange(lo, hi + 0.01, 0.5), key=score)
    return float(round(max(np.arange(coarse - 0.6, coarse + 0.6, 0.01), key=score), 2))


def grid_phase(onsets: np.ndarray, s16: float) -> tuple[float, float]:
    """Posun šestnáctinové mřížky (s) a medián odchylky nástupů od ní (v krocích)."""
    if len(onsets) == 0:
        return 0.0, 0.5
    cands = np.arange(0.0, s16, 0.0005)
    err = [float(np.median(np.abs((onsets - c) / s16 - np.round((onsets - c) / s16)))) for c in cands]
    i = int(np.argmin(err))
    return float(cands[i]), err[i]


def to_steps(onsets: np.ndarray, phase: float, s16: float) -> list[int]:
    return sorted({int(v) for v in np.round((np.asarray(onsets) - phase) / s16).astype(int)})


def bar_offset(kick_steps: list[int], snare_steps: list[int]) -> int:
    """Který krok (0–15) je jednička taktu: kick na 1. době, snare na 2. a 4. (kroky +4 a +12)."""
    k, s = Counter(v % 16 for v in kick_steps), Counter(v % 16 for v in snare_steps)
    hit = lambda o: sum(s[(o + d) % 16] for d in (3, 4, 11, 12))  # noqa: E731  (snare se detekuje i krok před dobou)
    return max(range(16), key=lambda o: k[o] + hit(o))


def snare_fix(steps: list[int]) -> list[int]:
    """Nástup snare se detekuje krok před dobou (náběh obálky): kroky 3, 7, 11, 15 se posunou na dobu."""
    return sorted({s + 1 if s % 4 == 3 else s for s in steps})


def fmt_beat(step_in_bar: int) -> str:
    return f"{1 + step_in_bar / 4:g}"


def hits_text(steps: list[int], b0: int, b1: int, pitch: str, vel: int = 100) -> str:
    """Úderové noty (1/16) v zápisu Producer Pal; takty jsou číslované od začátku klipu (b0 = takt 1)."""
    by: dict[int, list[int]] = {}
    for s in steps:
        b = s // 16 + 1
        if s >= 0 and b0 <= b <= b1:
            by.setdefault(b - b0 + 1, []).append(s % 16)
    if not by:
        return ""
    return f"v{vel} n1/16 {pitch} " + " ".join(f"{b}|{','.join(fmt_beat(x) for x in sorted(set(v)))}" for b, v in sorted(by.items()))


def smooth_steps(steps: list[int | None]) -> list[int | None]:
    """Výšky po krocích: osamělý krok jiné výšky přebije většina z okolí ±2, díra jednoho kroku se zalepí."""
    sm = list(steps)
    for i, v in enumerate(steps):
        if v is not None:
            sm[i] = Counter(x for x in steps[max(0, i - 2):i + 3] if x is not None).most_common(1)[0][0]
    for i in range(1, len(sm) - 1):
        if sm[i] is None and sm[i - 1] is not None and sm[i - 1] == sm[i + 1]:
            sm[i] = sm[i - 1]
    return sm


def held_notes(steps: list[int | None], b0: int, b1: int, min_len: int = 2) -> list[tuple[int, int, int]]:
    """Držené noty (krok, délka v krocích, MIDI) z výšek po krocích; nota končí na hraně taktu."""
    sm = smooth_steps(steps)
    out, i, end = [], (b0 - 1) * 16, min(b1 * 16, len(sm))
    while i < end:
        if sm[i] is None:
            i += 1
            continue
        j = i + 1
        while j < end and sm[j] == sm[i] and j % 16 != 0:
            j += 1
        if j - i >= min_len:
            out.append((i, j - i, int(sm[i])))
        i = j
    return out


def rhythm_notes(onsets: list[int], active: list[bool], b0: int, b1: int, pitch: int) -> list[tuple[int, int, int]]:
    """Noty z nástupů: dvojitý nástup (sousední kroky) je jeden; nota trvá, dokud pásmo zní, nejdéle do dalšího nástupu."""
    on = sorted(s for s in onsets if (b0 - 1) * 16 <= s < b1 * 16)
    on = [s for k, s in enumerate(on) if k == 0 or s - on[k - 1] > 1]
    out = []
    for k, s in enumerate(on):
        nxt = on[k + 1] if k + 1 < len(on) else b1 * 16
        j = s + 1
        while j < nxt and j < len(active) and active[j]:
            j += 1
        out.append((s, max(1, j - s), pitch))
    return out


def notes_text(notes: list[tuple[int, int, int]], b0: int, vel: int = 100) -> str:
    if not notes:
        return ""
    parts, last = [], None
    for s, ln, p in notes:
        if (ln, p) != last:
            parts.append(f"n{ln}/16 {sb.note_name(p)}")
            last = (ln, p)
        parts.append(f"{s // 16 - (b0 - 1) + 1}|{fmt_beat(s % 16)}")
    return f"v{vel} " + " ".join(parts)


def active_ranges(active_bars: list[int], max_gap: int = 1, min_len: int = 4) -> list[tuple[int, int]]:
    """Souvislé úseky taktů (díry do `max_gap` taktů se zavřou), jen od `min_len` taktů."""
    out: list[list[int]] = []
    for b in sorted(active_bars):
        if out and b - out[-1][1] <= max_gap + 1:
            out[-1][1] = b
        else:
            out.append([b, b])
    return [(a, b) for a, b in out if b - a + 1 >= min_len]


def bar_activity(mono: np.ndarray, lo: float, hi: float, t_bar1: float, bar_s: float, drop_db: float = 18.0) -> list[int]:
    env = sb.band_envelope(mono, lo, hi)
    nb = int((len(mono) / SR - t_bar1) // bar_s)
    lv = []
    for i in range(nb):
        seg = env[int((t_bar1 + i * bar_s) * sb.ENV_FS):int((t_bar1 + (i + 1) * bar_s) * sb.ENV_FS)]
        lv.append(float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0)
    db = 20 * np.log10(np.maximum(np.array(lv), 1e-9))
    return [int(i) + 1 for i in np.flatnonzero((db > db.max() - drop_db) & (db > -70))] if len(db) else []


def step_pitches(mono: np.ndarray, lo: float, hi: float, t_bar1: float, s16: float, n_steps: int) -> list[int | None]:
    """Výška subu po 1/16: znělý krok = obálka pásma nad prahem; výška = medián pitch tracku kolem kroku."""
    pt = sb.pitch_track(sb._bandpass(mono, lo, hi + 10), hi=hi)
    env = sb.band_envelope(mono, lo, hi)
    edb = 20 * np.log10(np.maximum(env, 1e-9))
    thr = np.percentile(edb, 95) - 18
    if pt is None:
        return [None] * n_steps
    tt = (np.arange(len(pt["midi"])) * 2400 + 4800) / SR
    out: list[int | None] = []
    for i in range(n_steps):
        t0 = t_bar1 + i * s16
        seg = edb[max(0, int(t0 * sb.ENV_FS)):int((t0 + s16) * sb.ENV_FS)]
        m = (tt >= t0 - 0.05) & (tt < t0 + s16 + 0.05) & pt["voiced"]
        ok = len(seg) and np.mean(seg > thr) >= 0.5 and m.sum()
        out.append(int(round(float(np.median(pt["midi"][m])))) if ok else None)
    return out


def step_active(mono: np.ndarray, lo: float, hi: float, t_bar1: float, s16: float, n_steps: int) -> list[bool]:
    env = sb.band_envelope(mono, lo, hi)
    edb = 20 * np.log10(np.maximum(env, 1e-9))
    thr = np.percentile(edb, 95) - 18
    return [bool(np.mean(edb[max(0, int((t_bar1 + i * s16) * sb.ENV_FS)):int((t_bar1 + (i + 1) * s16) * sb.ENV_FS)] > thr) >= 0.5)
            if int((t_bar1 + (i + 1) * s16) * sb.ENV_FS) <= len(edb) else False for i in range(n_steps)]


def build_plan(src: dict[str, np.ndarray], bands: dict[str, tuple[float, float]], bpm: float | None, basis: str,
               kick_pitch: str = "C1", snare_pitch: str = "D1") -> dict:
    """src: role -> mono signál (kick, snare, sub, mids; chybějící role se vynechá). Vrací plán s notami v textu."""
    ref = src.get("kick", next(iter(src.values())))
    if bpm is None:
        bpm = estimate_bpm(ref)
    bar_s, s16 = 240.0 / bpm, 15.0 / bpm
    on = {r: sb.envelope_onsets(sb.band_envelope(src[r], *bands[r]), bpm) for r in ("kick", "snare", "mids") if r in src}
    grid_src = "kick" if "kick" in on and len(on["kick"]) >= 8 else next(iter(on))
    phase, err = grid_phase(on[grid_src], s16)
    steps = {r: to_steps(v, phase, s16) for r, v in on.items()}
    off = bar_offset(steps.get("kick", []), steps.get("snare", []))
    t_bar1 = phase + off * s16
    while t_bar1 - bar_s >= -s16 / 2:           # takt 1 = první celý takt v souboru
        t_bar1 -= bar_s
    shift = int(round((t_bar1 - phase) / s16))  # o kolik kroků se posunula nula mřížky
    steps = {r: [s - shift for s in v] for r, v in steps.items()}
    if "snare" in steps:
        steps["snare"] = snare_fix(steps["snare"])
    dur = len(ref) / SR
    n_bars = int((dur - t_bar1) // bar_s)
    n_steps = n_bars * 16
    plan: dict = {"basis": basis, "bpm": bpm, "grid_source": grid_src, "grid_error_steps": round(err, 3),
                  "bar1_sec": round(t_bar1, 3), "bars": n_bars, "clips": [], "warnings": []}
    if err > 0.15:
        plan["warnings"].append(f"nástupy sedí na 1/16 špatně (medián {err:.2f} kroku): tempo nebo zdroj mřížky jsou podezřelé")
    sub_steps = step_pitches(src["sub"], *bands["sub"], t_bar1, s16, n_steps) if "sub" in src else []
    mids_act = step_active(src["mids"], *bands["mids"], t_bar1, s16, n_steps) if "mids" in src else []
    act_role = "sub" if "sub" in src else "kick"
    ranges = active_ranges(bar_activity(src[act_role], *bands[act_role], t_bar1, bar_s)) or [(1, n_bars)]
    plan["ranges_from"], plan["ranges"] = act_role, [list(r) for r in ranges]
    kick_bars = sorted({s // 16 + 1 for s in steps.get("kick", []) if s >= 0})
    drum_ranges = active_ranges(kick_bars, max_gap=2) or ranges
    plan["drum_ranges"] = [list(r) for r in drum_ranges]
    for b0, b1 in drum_ranges:
        for role, pitch in (("kick", kick_pitch), ("snare", snare_pitch)):
            txt = hits_text(steps.get(role, []), b0, b1, pitch)
            if txt:
                plan["clips"].append({"role": role, "start_bar": b0, "end_bar": b1, "notes": txt})
    for b0, b1 in ranges:
        if sub_steps:
            notes = held_notes(sub_steps, b0, b1)
            if notes:
                plan["clips"].append({"role": "sub", "start_bar": b0, "end_bar": b1, "notes": notes_text(notes, b0)})
        if mids_act:
            root = Counter(v for v in sub_steps[(b0 - 1) * 16:b1 * 16] if v is not None).most_common(1)
            notes = rhythm_notes(steps.get("mids", []), mids_act, b0, b1, (root[0][0] if root else 29) + 12)
            if notes:
                plan["clips"].append({"role": "mids", "start_bar": b0, "end_bar": b1, "notes": notes_text(notes, b0, 90),
                                      "pitch_note": "zástupná výška (oktáva nad nejčastější notou subu), měřený je jen rytmus"})
    if sub_steps:
        c = Counter(v for v in sub_steps if v is not None)
        tot = sum(c.values())
        plan["sub_notes"] = [{"note": sb.note_name(p), "share": round(n / tot, 2)} for p, n in c.most_common(5)]
    return plan


def main() -> int:
    ap = argparse.ArgumentParser(description="Track (stemy nebo plný mix) -> MIDI kostra pro Ableton (jen čtení).")
    ap.add_argument("--dir", type=Path, help="složka stemů")
    ap.add_argument("--mix", type=Path, help="plný mix místo stemů (slabší důkaz)")
    ap.add_argument("--bpm", type=float, help="tempo; bez něj se změří")
    for r in ("kick", "snare", "sub", "mids"):
        ap.add_argument(f"--{r}", default="", help=f"názvy stemů role {r} (bez .wav), oddělené čárkou")
    ap.add_argument("--kick-pitch", default="C1", help="pad kicku v cílovém Drum Racku")
    ap.add_argument("--snare-pitch", default="D1", help="pad snare v cílovém Drum Racku")
    ap.add_argument("--out", type=Path, required=True, help="složka pro plan.json a noty (mimo repo nebo _local)")
    args = ap.parse_args()
    if bool(args.dir) == bool(args.mix):
        raise SystemExit("zadej právě jedno: --dir (stemy), nebo --mix (plný mix)")
    out = args.out.resolve()
    if ROOT in out.parents and "_local" not in out.parts:
        raise SystemExit("výstup patří mimo repo nebo do složky _local")
    if args.mix:
        mono = sb.load(args.mix).mean(axis=1).astype(np.float64)
        src, bands, basis = {r: mono for r in MIX_BANDS}, MIX_BANDS, "full_mix"
    else:
        wavs = sb.find_wavs(args.dir)
        src = {}
        for r in ("kick", "snare", "sub", "mids"):
            names = sb._names(getattr(args, r))
            if names:
                src[r] = sb.sum_stems(sb.pick(wavs, names)).mean(axis=1).astype(np.float64)
        if not src:
            raise SystemExit("zadej aspoň jednu roli (--kick, --snare, --sub, --mids); názvy stemů vypíše stem_bass.py --list")
        n = max(len(v) for v in src.values())
        src = {r: np.pad(v, (0, n - len(v))) for r, v in src.items()}
        bands, basis = BANDS, "stems"
    plan = build_plan(src, bands, args.bpm, basis, args.kick_pitch, args.snare_pitch)
    plan["source"] = str(args.mix or args.dir)
    out.mkdir(parents=True, exist_ok=True)
    for c in plan["clips"]:
        c["file"] = f"notes_{c['role']}_{c['start_bar']}-{c['end_bar']}.txt"
        (out / c["file"]).write_text(c["notes"] + "\n", encoding="utf-8", newline="\n")
    (out / "plan.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    lbl = "measured (stemy)" if basis == "stems" else "estimated (plný mix: pásma se překrývají, rytmus mids je nejvýš hypotéza)"
    print(f"{lbl}; tempo {plan['bpm']:g} BPM, takt 1 v {plan['bar1_sec']} s, {plan['bars']} taktů, "
          f"mřížka z {plan['grid_source']} (odchylka {plan['grid_error_steps']} kroku)")
    print(f"úseky basy ({plan['ranges_from']}): " + ", ".join(f"{a}-{b}" for a, b in plan["ranges"])
          + "; bicí: " + ", ".join(f"{a}-{b}" for a, b in plan["drum_ranges"]))
    if plan.get("sub_notes"):
        print("sub: " + ", ".join(f"{n['note']} {n['share']:.0%}" for n in plan["sub_notes"]) + " (názvy podle Live)")
    for c in plan["clips"]:
        print(f"  {c['role']:<5} takty {c['start_bar']}-{c['end_bar']}: {c['file']} ({len(c['notes'])} znaků)")
    for w in plan["warnings"]:
        print(f"Pozor: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
