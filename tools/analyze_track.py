#!/usr/bin/env python3
"""analyze_track.py — measure a full-mix audio file and fill an NPOS track analysis.

Implements the measurement pipeline from docs/BLUEPRINT.md §5 and fills the
analysis.json schema from §4.2 (see core/ docs). Full-mix only, no stems.

Pipeline:
  1. ffmpeg decode -> 48 kHz stereo float32 PCM
  2. RMS energy curve (20 ms windows) -> section detection
  3. crest factor in the main drop window -> loudness strategy
  4. band energy (sub/fundament/upper) -> bass.energy
  5. spectral centroid -> bass.timbre
  6. mid/side ratio per band -> bass.stereo / stereo_global
  7. bass modulation: bandpass 60-300 Hz -> Hilbert envelope -> FFT vs tempo grid
  8. reese-vs-growl test (--mode deep) on a stable drop hold

Fields that require listening (lead, midi_intent, drums, call_and_response) are
left empty with confidence marked — this tool only measures.

Usage:
  python tools/analyze_track.py --audio <file> --id <track-id> \
      --bpm 174 --key Em [--title "Title"] [--mode deep] [--out path.json]
"""

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import numpy as np
from scipy import signal as sig

SR = 48000          # decode sample rate (Hz)
HOP_S = 0.010       # RMS curve hop (s)
WIN_S = 0.020       # RMS window (s)
GRID_LABELS = {4: "1/4", 8: "1/8", 16: "1/16", 32: "1/32"}


def decode_audio(path: str) -> np.ndarray:
    """Decode any audio ffmpeg can read to (N,2) float32 at SR."""
    cmd = [
        "ffmpeg", "-v", "error", "-i", str(path),
        "-f", "f32le", "-acodec", "pcm_f32le",
        "-ar", str(SR), "-ac", "2", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=True)
    x = np.frombuffer(proc.stdout, dtype=np.float32).reshape(-1, 2)
    if x.size == 0:
        raise ValueError(f"no audio decoded from {path}")
    return x


def rms_curve(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """RMS envelope in dB over WIN_S windows. Returns (db, times_s)."""
    mono = x.mean(axis=1)
    win = int(SR * WIN_S)
    hop = int(SR * HOP_S)
    n = (len(mono) - win) // hop
    if n < 1:
        raise ValueError("audio too short for RMS curve")
    idx = np.arange(n) * hop
    # vectorized windowed RMS
    rng = np.arange(win)
    windows = mono[idx[:, None] + rng]
    rms = np.sqrt(np.mean(windows ** 2, axis=1))
    rms = np.maximum(rms, 1e-9)
    db = 20.0 * np.log10(rms)
    times = (idx + win / 2) / SR
    return db, times


def detect_sections(db: np.ndarray, times: np.ndarray, drop_gap_s: float = 10.0) -> tuple[list[dict], tuple[float, float]]:
    """Coarse section detection from the RMS curve.

    Long smoothing + binary loud/quiet + gap merging. Outputs a handful of real
    sections (intro/build/drop/breakdown/outro), not per-window flicker. Returns
    (sections, main_drop); main_drop is the longest loud region.
    """
    if db.size == 0:
        return [], (0.0, 0.0)
    max_db = db.max()
    if max_db == -np.inf:
        return [], (0.0, 0.0)

    # Heavy smoothing (~2 s) so only real energy drops change the level.
    win_sm = max(1, int(2.0 / HOP_S))
    kernel = np.ones(win_sm) / win_sm
    smooth = np.convolve(db, kernel, mode="same")

    # Binary loud vs quiet, 8 dB below the loudest point.
    loud = (max_db - smooth) < 8.0

    # Contiguous loud runs.
    loud_runs: list[tuple[int, int]] = []
    i = 0
    n = len(loud)
    while i < n:
        if loud[i]:
            j = i
            while j < n and loud[j]:
                j += 1
            loud_runs.append((i, j))
            i = j
        else:
            i += 1
    if not loud_runs:
        return [], (0.0, 0.0)

    # Merge loud runs separated by < drop_gap_s (a brief dip is still one drop).
    merged = [list(loud_runs[0])]
    for s, e in loud_runs[1:]:
        gap = times[s] - times[merged[-1][1] - 1]
        if gap < drop_gap_s:
            merged[-1][1] = e
        else:
            merged.append([s, e])
    loud_runs = [(s, e) for s, e in merged]

    # Drop the first loud run if it's a short transient (e.g. a single kick at
    # the very start) — not a real drop. Re-label the pre-drop region instead.
    if len(loud_runs) > 1:
        first_dur = times[loud_runs[0][1] - 1] - times[loud_runs[0][0]]
        if first_dur < 4.0 and loud_runs[0][0] < int(2.0 / HOP_S):
            loud_runs = loud_runs[1:]

    if not loud_runs:
        return [], (0.0, 0.0)

    # Build the section list over the whole timeline.
    sections = []
    loud_count = 0
    prev_end = 0  # index boundary of the previous emitted section
    for k, (s, e) in enumerate(loud_runs):
        start_s = times[s]
        end_s = times[min(e, len(times) - 1)]
        # The region before this drop: intro (first, clearly quieter) or build.
        if k == 0 and s > 0:
            pre = smooth[:s]
            pre_max = pre.max() if len(pre) else max_db
            pre_name = "intro" if (max_db - pre_max) > 20.0 else "build"
            if start_s > 2.0:
                sections.append({"name": pre_name, "start_sec": 0.0, "end_sec": round(start_s, 2)})
        loud_count += 1
        name = "drop_a" if loud_count == 1 else f"drop_{chr(ord('a') + loud_count)}"
        sections.append({"name": name, "start_sec": round(start_s, 2), "end_sec": round(end_s, 2)})
        # Gap between this drop and the next is a breakdown (if long enough).
        if k < len(loud_runs) - 1:
            nxt_s = times[loud_runs[k + 1][0]]
            gap = nxt_s - end_s
            if gap > 3.0:
                gap_name = "breakdown" if gap > 8.0 else "build"
                sections.append({"name": gap_name, "start_sec": round(end_s, 2), "end_sec": round(nxt_s, 2)})
        prev_end = e
    # Tail after the last drop.
    if prev_end < len(smooth) - 1:
        tail_s = times[min(prev_end, len(times) - 1)]
        if times[-1] - tail_s > 3.0:
            sections.append({"name": "outro", "start_sec": round(tail_s, 2), "end_sec": round(times[-1], 2)})

    # Main drop = longest loud run
    longest = 0.0
    main_drop = (0.0, 0.0)
    for s, e in loud_runs:
        dur = times[min(e, len(times) - 1)] - times[s]
        if dur > longest:
            longest = dur
            main_drop = (times[s], times[min(e, len(times) - 1)])
    return sections, main_drop


def slice_range(x: np.ndarray, t0: float, t1: float) -> np.ndarray:
    a = int(t0 * SR)
    b = int(t1 * SR)
    return x[max(0, a):min(len(x), b)]


def band_rms(x: np.ndarray, lo: float, hi: float, fs: int = SR) -> float:
    """RMS level (dB) of a band-limited version of mono signal x."""
    if len(x) == 0:
        return -np.inf
    sos = sig.butter(4, [lo / (fs / 2), hi / (fs / 2)], btype="band", output="sos")
    y = sig.sosfiltfilt(sos, x)
    r = np.sqrt(np.mean(y ** 2))
    return 20.0 * np.log10(max(r, 1e-9))


def spectral_centroid(x: np.ndarray, fs: int = SR) -> float:
    f, t, z = sig.stft(x, fs=fs, nperseg=2048, noverlap=1024)
    mag = np.abs(z)
    total = mag.sum(axis=0) + 1e-12
    cent = (f[:, None] * mag).sum(axis=0) / total
    return float(cent.mean())


def mid_side_db(x: np.ndarray, lo: float, hi: float, fs: int = SR) -> tuple[float, float]:
    mid = (x[:, 0] + x[:, 1]) / 2.0
    side = (x[:, 0] - x[:, 1]) / 2.0
    sos = sig.butter(4, [lo / (fs / 2), hi / (fs / 2)], btype="band", output="sos")
    m = sig.sosfiltfilt(sos, mid)
    s = sig.sosfiltfilt(sos, side)
    m_db = 20.0 * np.log10(max(np.sqrt(np.mean(m ** 2)), 1e-9))
    s_db = 20.0 * np.log10(max(np.sqrt(np.mean(s ** 2)), 1e-9))
    return m_db, s_db  # return mid level and side level


def bass_modulation(x: np.ndarray, t0: float, t1: float, bpm: float) -> dict:
    """Bandpass 60-300 Hz -> Hilbert envelope -> FFT -> primary modulation Hz."""
    seg = slice_range(x, t0, t1)
    if len(seg) < SR // 4:
        return {"primary_hz": None, "grid_match": "unknown", "secondary_hz": [], "detection": "bandpass 60-300 -> Hilbert envelope -> FFT"}
    mono = seg.mean(axis=1)
    sos = sig.butter(4, [60.0 / (SR / 2), 300.0 / (SR / 2)], btype="band", output="sos")
    bp = sig.sosfiltfilt(sos, mono)
    env = np.abs(sig.hilbert(bp))
    env -= env.mean()
    freqs = np.fft.rfftfreq(len(env), 1.0 / SR)
    mag = np.abs(np.fft.rfft(env))
    # look at 0.5-30 Hz (below typical LFO area is irrelevant)
    band = (freqs >= 0.5) & (freqs <= 30.0)
    if not band.any():
        return {"primary_hz": None, "grid_match": "unknown", "secondary_hz": [], "detection": "bandpass 60-300 -> Hilbert envelope -> FFT"}
    peak_i = int(np.argmax(mag[band])) + int(np.where(band)[0][0])
    primary = float(freqs[peak_i])

    # secondary peaks > 50% of primary
    sec = []
    for i in range(int(np.where(band)[0][0]), len(freqs)):
        if freqs[i] > 30.0:
            break
        if i != peak_i and mag[i] > 0.5 * mag[peak_i] and freqs[i] > 0.5:
            sec.append(float(freqs[i]))
    sec = sec[:5]

    # grid match: modulation rate vs tempo grid (1/4..1/32)
    beat_hz = bpm / 60.0
    grid_match = "off_grid"
    best_d = 1e9
    for div, label in GRID_LABELS.items():
        gf = beat_hz * div  # 1/4=beat, 1/8=2x, 1/16=4x, 1/32=8x
        d = abs(primary - gf) / max(gf, 1e-9)
        if d < best_d:
            best_d = d
            grid_match = label
    if best_d > 0.15:
        grid_match = "off_grid"

    return {"primary_hz": round(primary, 2), "grid_match": grid_match, "secondary_hz": [round(v, 2) for v in sec], "detection": "bandpass 60-300 -> Hilbert envelope -> FFT"}


def reese_vs_growl(x: np.ndarray, t0: float, t1: float, bpm: float) -> dict:
    """Deep-mode test: envelope-vs-grid + hi-res FFT 350-900 Hz peak spacing."""
    seg = slice_range(x, t0, t1)
    result = {"envelope_vs_grid": "", "hi_res_fft_350_900": "", "conclusion": ""}
    if len(seg) < SR:
        result["conclusion"] = "insufficient audio"
        return result

    mono = seg.mean(axis=1)
    # stable hold window: middle 1.5 s
    mid = len(mono) // 2
    hold = mono[mid:int(mid + 1.5 * SR)]
    if len(hold) < SR // 2:
        hold = mono

    # envelope FFT -> modulation rate vs grid
    sos = sig.butter(4, [60.0 / (SR / 2), 300.0 / (SR / 2)], btype="band", output="sos")
    bp = sig.sosfiltfilt(sos, hold)
    env = np.abs(sig.hilbert(bp))
    env -= env.mean()
    freqs = np.fft.rfftfreq(len(env), 1.0 / SR)
    mag = np.abs(np.fft.rfft(env))
    band = (freqs >= 0.5) & (freqs <= 30.0)
    beat_hz = bpm / 60.0
    if band.any():
        peak_i = int(np.argmax(mag[band])) + int(np.where(band)[0][0])
        fpeak = freqs[peak_i]
        gf = beat_hz * 8  # 1/8 grid, typical growl
        on_grid = abs(fpeak - gf) / max(gf, 1e-9) < 0.15
        result["envelope_vs_grid"] = (
            f"peak {fpeak:.2f} Hz vs 1/8 grid {gf:.2f} Hz -> {'on-grid (growl path)' if on_grid else 'off-grid (reese/detune path)'}"
        )
    else:
        result["envelope_vs_grid"] = "no envelope peak in 0.5-30 Hz"

    # hi-res FFT 350-900 Hz: count spectral peaks and their spacing
    sos_h = sig.butter(4, [350.0 / (SR / 2), 900.0 / (SR / 2)], btype="band", output="sos")
    h = sig.sosfiltfilt(sos_h, hold)
    h_freqs = np.fft.rfftfreq(len(h), 1.0 / SR)
    h_mag = np.abs(np.fft.rfft(h))
    sel = (h_freqs >= 350.0) & (h_freqs <= 900.0)
    mags = h_mag[sel]
    freqs_sel = h_freqs[sel]
    if len(mags):
        thr = 0.3 * mags.max()
        pk_idx = sig.find_peaks(mags, height=thr)[0]
        n_peaks = len(pk_idx)
        if n_peaks >= 2:
            spacing = np.median(np.diff(freqs_sel[pk_idx]))
        else:
            spacing = float("nan")
        desc = (
            f"{n_peaks} peaks, median spacing {spacing:.1f} Hz"
            if n_peaks >= 2
            else f"{n_peaks} peaks (single dominant) — clean harmonic spikes"
        )
        result["hi_res_fft_350_900"] = desc
        if n_peaks >= 8 and spacing < 12.0:
            result["conclusion"] = "reese (dense peak forest, close spacing)"
        elif n_peaks <= 4:
            result["conclusion"] = "growl/modulated (few oscillators, clean harmonics)"
        else:
            result["conclusion"] = "hybrid (some layer density, not pure reese)"
    else:
        result["hi_res_fft_350_900"] = "no content in 350-900 Hz"
        result["conclusion"] = "unknown"
    return result


def measure(x: np.ndarray, bpm: float, mode: str) -> dict:
    db, times = rms_curve(x)
    sections, main_drop = detect_sections(db, times)
    drop = slice_range(x, main_drop[0], main_drop[1]) if main_drop[1] > main_drop[0] else x

    # Dynamics: crest factor in main drop
    mono_drop = drop.mean(axis=1)
    peak = np.abs(mono_drop).max()
    rms_drop = np.sqrt(np.mean(mono_drop ** 2))
    crest_lin = peak / max(rms_drop, 1e-9)
    crest_db = 20.0 * np.log10(max(crest_lin, 1e-9))
    if crest_db <= 4.5:
        strategy = "crushed"
    elif crest_db <= 6.5:
        strategy = "controlled"
    else:
        strategy = "open"

    # Band energy on drop window
    sub_db = band_rms(mono_drop, 20, 60)
    fund_db = band_rms(mono_drop, 60, 250)
    full_db = band_rms(mono_drop, 20, 10000)
    sub_rel = sub_db - full_db
    fund_rel = fund_db - full_db
    if sub_rel > fund_rel + 2.0:
        profile = "sub_dominant"
    elif fund_rel > sub_rel + 2.0:
        profile = "fundament_dominant"
    else:
        profile = "balanced"

    centroid = spectral_centroid(mono_drop)

    m_sub, s_sub = mid_side_db(drop, 20, 60)
    m_fund, s_fund = mid_side_db(drop, 60, 250)
    sub_side = s_sub - m_sub
    fund_side = s_fund - m_fund

    mod = bass_modulation(x, main_drop[0], main_drop[1], bpm)
    rvg = reese_vs_growl(x, main_drop[0], main_drop[1], bpm) if mode == "deep" else None

    def _f(x, nd=2):
        return float(f"{float(x):.{nd}f}")

    return {
        "crest_factor_drop_db": _f(crest_db),
        "loudness_strategy": strategy,
        "sections": sections,
        "sub_rel_db": _f(sub_rel),
        "fundament_rel_db": _f(fund_rel),
        "profile": profile,
        "spectral_centroid_hz": _f(centroid, 1),
        "sub_side_db": _f(sub_side),
        "fundament_side_db": _f(fund_side),
        "modulation": mod,
        "reese_vs_growl": rvg,
    }


def build_analysis(id_: str, bpm: float, key: str, title: str, mode: str, audio_path: str, m: dict) -> dict:
    analysis = {
        "id": id_,
        "mode": mode,
        "analyzed": date.today().isoformat(),
        "method": {
            "tooling": "ffmpeg -> numpy/scipy (RMS, STFT, band energy, crest, mid/side, envelope FFT, YIN optional)",
            "stems": False,
            "basis": "full_mix",
            "notes": "Full-mix only. Energy/spectral = high confidence. Pitch in dense polyphony = low. Bass modulation from a full mix is at most a hypothesis (hi-hats contaminate the envelope; see docs/BLUEPRINT.md section 7).",
        },
        "confidence_overall": "measured" if mode == "quick" else "mixed",
        "structure": {
            "sections": m["sections"],
            "notes": f"Auto-detected from RMS energy curve ({title}). Section boundaries approximate; verify by ear.",
            "confidence": "estimated",
        },
        "dynamics": {
            "crest_factor_drop_db": m["crest_factor_drop_db"],
            "loudness_strategy": m["loudness_strategy"],
            "notes": "",
            "confidence": "measured",
        },
        "bass": {
            "type": "",
            "type_confidence": "hypothesis",
            "archetype": "",
            "layers": [],
            "energy": {
                "sub_rel_db": m["sub_rel_db"],
                "fundament_rel_db": m["fundament_rel_db"],
                "profile": m["profile"],
                "notes": "",
            },
            "modulation": {**m["modulation"], "source": "unknown", "basis": "full_mix", "confidence": "hypothesis"},
            "timbre": {"spectral_centroid_hz": m["spectral_centroid_hz"], "notes": ""},
            "stereo": {"sub_side_db": m["sub_side_db"], "fundament_side_db": m["fundament_side_db"], "notes": ""},
            "reese_vs_growl_test": m["reese_vs_growl"] or {"envelope_vs_grid": "", "hi_res_fft_350_900": "", "conclusion": "not run (quick mode)"},
            "body_design": {"primary": "", "post": [], "confidence": "estimated"},
            "confidence": "measured",
        },
        "lead": {
            "present": None,
            "roles": [],
            "register": "",
            "playing_style": "",
            "density": "",
            "melodic_motion": "",
            "rhythm_vs_drums": "unknown",
            "rhythm_vs_bass": "unknown",
            "call_and_response": {"active": None, "call": "", "response": "", "period_bars": None, "overlap": None, "notes": ""},
            "timbre_family": "",
            "confidence": "hypothesis",
        },
        "midi_intent": {
            "bass": {"playing_style": "unknown", "rhythm": "unknown", "note_area": "", "grid_lock": "none", "silence_on_kick": None},
            "lead": {"playing_style": "", "phrase_length_beats": None, "enters_on": "", "avoids": [], "register": ""},
            "buildup": {"type": ""},
            "breakdown": {"type": "", "bass_present": None},
            "confidence": "hypothesis",
        },
        "drums": {"kick": "", "snare": "", "groove": "", "notes": "", "confidence": "hypothesis"},
        "stereo_global": {
            "low_mono_below_hz": 250,
            "rule": "mono low-end, open higher",
            "confidence": "measured",
        },
        "production_decisions": [],
        "recreate_workflow": [],
        "lessons": [],
        "related_archetypes": [],
        "usable_for": [],
        "fields_confidence": {
            "structure": "estimated",
            "dynamics": "measured",
            "bass": "measured",
            "lead": "hypothesis",
            "drums": "hypothesis",
        },
    }
    return analysis


def main() -> None:
    ap = argparse.ArgumentParser(description="Measure a full-mix audio file into an NPOS track analysis.json")
    ap.add_argument("--audio", required=True, help="full-mix audio file (wav/mp3/flac/...)")
    ap.add_argument("--id", required=True, help="track id, e.g. first-contact")
    ap.add_argument("--bpm", required=True, type=float, help="tempo for grid matching")
    ap.add_argument("--key", default="", help="musical key, e.g. Em")
    ap.add_argument("--title", default="", help="track title (optional)")
    ap.add_argument("--mode", default="quick", choices=["quick", "deep"], help="quick skips reese-vs-growl")
    ap.add_argument("--out", default=None, help="output path (default data/tracks/<id>/analysis.json)")
    args = ap.parse_args()

    audio_path = Path(args.audio)
    if not audio_path.exists():
        sys.exit(f"audio not found: {audio_path}")
    out = Path(args.out) if args.out else Path("data") / "tracks" / args.id / "analysis.json"
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"[1/3] decoding {audio_path}")
    x = decode_audio(str(audio_path))
    dur = len(x) / SR
    print(f"      {dur:.1f}s, {x.shape[1]}ch @ {SR}Hz")

    print(f"[2/3] measuring ({args.mode})")
    m = measure(x, args.bpm, args.mode)

    analysis = build_analysis(args.id, args.bpm, args.key, args.title or args.id, args.mode, str(audio_path), m)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"[3/3] wrote {out}")
    print(f"      sections: {len(m['sections'])}  drop crest: {m['crest_factor_drop_db']} dB ({m['loudness_strategy']})")
    print(f"      bass profile: {m['profile']}  mod: {m['modulation']['primary_hz']} Hz ({m['modulation']['grid_match']})")
    print(f"      centroid: {m['spectral_centroid_hz']} Hz  reese/growl: {(m['reese_vs_growl'] or {}).get('conclusion', 'n/a')}")


if __name__ == "__main__":
    main()
