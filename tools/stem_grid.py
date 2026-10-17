"""Rytmus a stavba z odseparovaných stemů (Demucs, RipX, oficiální stemy): mřížka 1/16 po taktech.

Jen čtení. Z `drums.wav` se po taktech vyčte kick (pásmo 30-150 Hz) a snare (pásmo 1,5-6 kHz) na mřížce
1/16, z `bass.wav` nástupy basy, z každého stemu energie po taktech (kde stem hraje). Tempo a posun mřížky
se dohledají měřením (zadáš přibližné BPM). Je to měření ze zvuku: štítek `naměřeno` u energie po taktech,
`odhad` u mřížky (separace stemů není dokonalá, hi-haty prosakují do basy).

Použití:
  py -3.12 tools/stem_grid.py --dir "složka/se/stems" --bpm 174 [--json out.json]
Očekává soubory bass.wav, drums.wav (a volitelně other.wav, vocals.wav) ve složce.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt

ENV_HZ = 1000
BANDS = {"kick": (30.0, 150.0), "snare": (1500.0, 6000.0), "bass": (30.0, 300.0)}


def load_mono(path: Path) -> tuple[np.ndarray, int]:
    x, sr = sf.read(str(path), always_2d=True)
    return x.mean(axis=1).astype(np.float32), sr


def band_flux(x: np.ndarray, sr: int, lo: float, hi: float) -> tuple[np.ndarray, float]:
    """Nástupy v pásmu: pásmový filtr bez zpoždění, obálka, kladná derivace. Vrací (síla nástupu, krok v sekundách)."""
    hi = min(hi, sr / 2 * 0.95)
    band = sosfiltfilt(butter(4, [lo, hi], btype="band", fs=sr, output="sos"), x)
    env = sosfiltfilt(butter(2, 30.0, btype="low", fs=sr, output="sos"), np.abs(band))
    step = max(1, int(round(sr / ENV_HZ)))
    env = env[::step]
    flux = np.maximum(np.diff(env), 0)
    return flux.astype(np.float32), step / sr


def fit_grid(flux: np.ndarray, step_s: float, bpm: float, span: float = 0.6) -> tuple[float, float]:
    """Najde BPM (v okolí zadaného) a posun první doby tak, aby nástupy padaly na mřížku."""
    best = (-1.0, bpm, 0.0)
    n = len(flux)
    for b in np.arange(bpm - span, bpm + span + 1e-9, 0.02):
        beat = 60.0 / b
        # skóre pro posuny v rámci jedné doby; mřížka 1/4 doby
        sixteenth = beat / 4.0
        n_slots = int(n * step_s / sixteenth)
        idx0 = np.arange(n_slots) * sixteenth
        for ph in np.arange(0.0, beat, step_s * 2):
            pos = ((idx0 + ph) / step_s).astype(int)
            pos = pos[pos < n]
            s = flux[pos].sum()
            if s > best[0]:
                best = (s, b, ph)
    return best[1], best[2]


def slot_peak(flux: np.ndarray, step_s: float, t: float, bar_s: float) -> float:
    i0 = int((t - bar_s / 64) / step_s)
    i1 = int((t + bar_s / 48) / step_s) + 1
    seg = flux[max(i0, 0):max(i1, 1)]
    return float(seg.max()) if len(seg) else 0.0


def pick_downbeat(kick: np.ndarray, snare: np.ndarray, step_s: float, bpm: float, phase: float, n_bars: int) -> float:
    """Mřížka je z měření známa jen po šestnáctinách; který úder je první doba taktu, se pozná podle typického
    uspořádání: kick na šestnáctinách 0 a 10, snare na 4 a 12. Vybere se z 16 možných posunů ten nejlepší."""
    bar_s = 240.0 / bpm
    beat = bar_s / 4
    kmax = float(kick.max()) or 1.0
    smax = float(snare.max()) or 1.0
    best, best_ph = -1.0, phase
    for o in range(16):
        ph = phase + o * beat / 4
        score = 0.0
        for b in range(max(n_bars - 4, 1)):
            base = ph + b * bar_s
            score += slot_peak(kick, step_s, base, bar_s) / kmax + slot_peak(kick, step_s, base + 10 * bar_s / 16, bar_s) / kmax
            score += slot_peak(snare, step_s, base + 4 * bar_s / 16, bar_s) / smax + slot_peak(snare, step_s, base + 12 * bar_s / 16, bar_s) / smax
        if score > best:
            best, best_ph = score, ph
    return best_ph


def bar_grid(flux: np.ndarray, step_s: float, bpm: float, phase: float, n_bars: int, rel: float = 0.35) -> list[str]:
    """Pro každý takt řetězec 16 znaků: x = nástup, . = ticho. Práh je relativní k nejsilnějšímu nástupu v taktu."""
    bar_s = 240.0 / bpm
    floor = float(np.percentile(flux, 90)) * 0.5
    out = []
    for b in range(n_bars):
        cells = []
        peaks = []
        for k in range(16):
            t = phase + b * bar_s + k * bar_s / 16
            i0 = int((t - bar_s / 64) / step_s)
            i1 = int((t + bar_s / 48) / step_s) + 1
            seg = flux[max(i0, 0):max(i1, 1)]
            peaks.append(float(seg.max()) if len(seg) else 0.0)
        top = max(peaks) if peaks else 0.0
        for p in peaks:
            cells.append("x" if top > floor and p >= rel * top and p > floor else ".")
        out.append("".join(cells))
    return out


def bar_rms_db(x: np.ndarray, sr: int, bpm: float, phase: float, n_bars: int) -> np.ndarray:
    bar_s = 240.0 / bpm
    out = np.full(n_bars, -120.0)
    for b in range(n_bars):
        a = int((phase + b * bar_s) * sr)
        z = int((phase + (b + 1) * bar_s) * sr)
        seg = x[max(a, 0):z]
        if len(seg) > 0:
            out[b] = 20 * np.log10(float(np.sqrt(np.mean(seg ** 2))) + 1e-9)
    return out


def runs(active: list[bool]) -> list[tuple[int, int]]:
    out, start = [], None
    for i, a in enumerate(active + [False]):
        if a and start is None:
            start = i
        if not a and start is not None:
            out.append((start + 1, i))
            start = None
    return out


def gap_signature(cells: str) -> str:
    hits = [i for i, c in enumerate(cells) if c == "x"]
    if not hits:
        return ""
    if len(hits) == 1:
        return "16"
    gaps = [b - a for a, b in zip(hits, hits[1:])] + [16 - hits[-1] + hits[0]]
    return "-".join(str(g) for g in gaps)


def analyze(directory: Path, bpm: float, files: dict[str, Path] | None = None) -> dict:
    """`files` přepíše výchozí názvy (drums.wav ...), např. oficiální skupinové stemy s jinými jmény."""
    stems = {n: (files or {}).get(n, directory / f"{n}.wav") for n in ("drums", "bass", "other", "vocals")}
    audio = {n: load_mono(p) for n, p in stems.items() if p.exists()}
    if "drums" not in audio:
        raise FileNotFoundError("chybí drums.wav")
    dx, sr = audio["drums"]
    kick_flux, step = band_flux(dx, sr, *BANDS["kick"])
    snare_flux, _ = band_flux(dx, sr, *BANDS["snare"])
    tempo, phase = fit_grid(kick_flux, step, bpm)
    phase = pick_downbeat(kick_flux, snare_flux, step, tempo, phase, int((len(dx) / sr - phase) / (240.0 / tempo)))
    n_bars = int((len(dx) / sr - phase) / (240.0 / tempo))
    rms = {n: bar_rms_db(x, s, tempo, phase, n_bars) for n, (x, s) in audio.items()}
    active = {}
    for n, r in rms.items():
        ref = float(np.percentile(r[r > -100], 75)) if np.any(r > -100) else -60.0
        active[n] = [bool(v > ref - 18) for v in r]
    grids = {"kick": bar_grid(kick_flux, step, tempo, phase, n_bars), "snare": bar_grid(snare_flux, step, tempo, phase, n_bars)}
    if "bass" in audio:
        bx, bsr = audio["bass"]
        bass_flux, bstep = band_flux(bx, bsr, *BANDS["bass"])
        grids["bass"] = bar_grid(bass_flux, bstep, tempo, phase, n_bars)
    return {"bpm": round(float(tempo), 2), "phase_s": round(float(phase), 3), "bars": n_bars,
            "rms_db": {n: [round(float(v), 1) for v in r] for n, r in rms.items()},
            "active_runs": {n: runs(a) for n, a in active.items()}, "grids": grids}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True, type=Path)
    ap.add_argument("--bpm", required=True, type=float, help="přibližné tempo, přesné se dohledá v okolí ±0,6")
    for n in ("drums", "bass", "other", "vocals"):
        ap.add_argument(f"--{n}", type=Path, help=f"soubor pro stem {n}, pokud se nejmenuje {n}.wav")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    try:
        r = analyze(a.dir, a.bpm, {n: getattr(a, n) for n in ("drums", "bass", "other", "vocals") if getattr(a, n)})
    except (OSError, FileNotFoundError, RuntimeError) as e:
        print(f"chyba: {e}", file=sys.stderr)
        return 2
    if a.json:
        a.json.write_text(json.dumps(r, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"BPM {r['bpm']}, posun {r['phase_s']} s, {r['bars']} taktů")
    for n, rr in r["active_runs"].items():
        print(f"{n:7} hraje v taktech: {', '.join(f'{x}-{y}' if x != y else str(x) for x, y in rr)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
