#!/usr/bin/env python3
"""stem_bass.py — basové pásmo z izolovaných stemů jedné složky (oficiální nebo separované). Jen čtení.

Protokol BLUEPRINT kap. 7: basovou modulaci, rozdělení sub/mid, mono a reese-vs-growl měřit na izolovaném
pásmu, ne z plného mixu. Nástroj vezme vybrané stemy basy (sub, mids), sečte je do basové sběrnice a změří
je v nejdelším souvislém úseku, kde basa hraje (okno jde zadat ručně `--window`). Poměr vůči celku se bere ze součtu všech
stemů (nebo z hotového master souboru).

Co měří (vše `measured`, na stemech):
  - sub 20–60 Hz a fundament 60–250 Hz vůči celku, side/mid v obou pásmech (stejné definice jako analyze_track.py)
  - horní hrana subu (99 % energie sub stemů pod ní) a dolní hrana mid basy (nejnižší třetinooktávové pásmo do −10 dB)
  - side/mid mid basy 300 Hz–1 kHz
  - čáry spektra obálky 60–300 Hz od 1 Hz, s počtem cyklů na takt (celé/půlené = vzor zamčený na takt, jinak volně běžící),
    na basové sběrnici i na mid basě zvlášť
  - reese vs. growl na držené notě mid basy (hi-res FFT 350–900 Hz)
  - sub vs. mids: kolik energie subu leží na jedné notě, nástupy mids na takt a jejich shoda s nástupy subu

Co NEMĚŘÍ a nehádá: crest a spektrální centroid celku (součet stemů nemá mastering řetězec, hodnoty by byly
jiné než u vydaného mixu), příčinu modulace (LFO, rytmus not, sidechain: to je výklad, ne měření), výšky not mid basy.

Pozor na výběr stemů: varianty „no sidechain“ a „with sidechain“ dávají jinou obálku. Nástroj vypíše, co sečetl;
varianty stejného stemu nikdy nesčítej dvakrát (`--exclude`). Stemy mastered „Master“ souborem: použij `--mix`.

Použití:
  py -3.12 tools/stem_bass.py --dir "D:/Ableton/30_Stems/Audio - dont play stems 172" --list
  py -3.12 tools/stem_bass.py --dir <složka> --bpm 172 --sub "sub no sc" --mids "mid bass no sc" --exclude "sub" --json <mimo repo>
  py -3.12 tools/stem_bass.py ... --analysis-out data/tracks/<id>/analysis.json --id <id> --title "..." --source-id <id>
Výstup do repa smí obsahovat jen čísla a názvy stemů, žádné audio (cizí stemy se nekopírují).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from scipy import signal as sig

sys.path.insert(0, str(Path(__file__).parent))
import analyze_track as at  # noqa: E402

SR = at.SR
ROOT = Path(__file__).resolve().parent.parent

ROLE_PATTERNS = [
    ("mix", r"\b(master|premaster|full mix|bounce)\b"),
    ("sub", r"\bsub\b|808"),
    ("bass", r"bass|reese|reece|growl|wobble|neuro|\bmids?\b|talky|bassline"),
    ("drums", r"kick|kik|snare|hat|hihat|clap|perc|drum|tom|cymbal|ride|crash|break"),
    ("vox", r"vox|vocal|voice|acap"),
    ("fx", r"fx|riser|rise|impact|noise|sweep|whoosh|down|rumble|atmos|ambi|texture"),
]


def role_guess(name: str) -> str:
    """Hrubý odhad role z názvu souboru. Jen nápověda pro výběr, rozhoduje člověk (nebo agent po kontrole)."""
    n = name.lower()
    for role, pat in ROLE_PATTERNS:
        if re.search(pat, n):
            return role
    return "other"


def norm(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\.wav$", "", name.strip(), flags=re.I)).strip().lower()


def find_wavs(directory: Path) -> list[Path]:
    return sorted(p for p in directory.rglob("*.wav") if "__MACOSX" not in p.parts and not p.name.startswith("._"))


def pick(wavs: list[Path], names: list[str]) -> list[Path]:
    """Najde soubory podle přesného názvu (bez .wav, bez ohledu na velikost písmen a mezery navíc)."""
    index: dict[str, list[Path]] = {}
    for p in wavs:
        index.setdefault(norm(p.name), []).append(p)
    out: list[Path] = []
    for n in names:
        hit = index.get(norm(n))
        if not hit:
            near = [k for k in index if norm(n) in k or k in norm(n)][:5]
            raise SystemExit(f"stem „{n}“ nenalezen. Podobné: {', '.join(near) or '—'}")
        if len(hit) > 1:
            raise SystemExit(f"stem „{n}“ je nejednoznačný ({len(hit)} souborů): {[str(h) for h in hit]}")
        out.append(hit[0])
    return out


def load(path: Path) -> np.ndarray:
    return at.decode_audio(str(path))


def sum_stems(paths: list[Path]) -> np.ndarray | None:
    """Součet stemů sample po samplu (stemy z Live mají společný začátek). Průběžný součet, ať nedrží všechny soubory."""
    acc = None
    for p in paths:
        x = load(p)
        if acc is None:
            acc = x.copy()
        elif len(x) > len(acc):
            x = x.copy()                    # decode_audio vrací jen pro čtení (frombuffer)
            x[:len(acc)] += acc
            acc = x
        else:
            acc[:len(x)] += x
    return acc


def pad_to(x: np.ndarray | None, n: int) -> np.ndarray | None:
    if x is None or len(x) == n:
        return x
    out = np.zeros((n, 2), dtype=np.float32)
    out[:min(n, len(x))] = x[:n]
    return out


def edge_hz(mono: np.ndarray, frac: float, lo: float = 20.0, hi: float = 2000.0) -> float | None:
    """Frekvence, pod kterou leží `frac` energie signálu v pásmu lo–hi (Welch PSD). None, když tam nic není."""
    if len(mono) < 8192:
        return None
    f, p = sig.welch(mono, fs=SR, nperseg=16384)
    sel = (f >= lo) & (f <= hi)
    f, p = f[sel], p[sel]
    total = p.sum()
    if total <= 1e-18:
        return None
    cum = np.cumsum(p) / total
    return float(f[int(np.searchsorted(cum, frac))])


def band_share(mono: np.ndarray, lo: float, hi: float, total_lo: float = 20.0, total_hi: float = 2000.0) -> float | None:
    """Podíl energie pásma lo–hi na energii pásma total_lo–total_hi (Welch PSD). None, když tam nic není."""
    if len(mono) < 8192:
        return None
    f, p = sig.welch(mono, fs=SR, nperseg=16384)
    total = p[(f >= total_lo) & (f <= total_hi)].sum()
    if total <= 1e-18:
        return None
    return float(p[(f >= lo) & (f < hi)].sum() / total)


def third_octave_floor_hz(mono: np.ndarray, thr_db: float = -10.0, lo: float = 20.0, hi: float = 2000.0) -> float | None:
    """Dolní hrana nejnižšího třetinooktávového pásma, jehož energie je do `thr_db` pod nejsilnějším pásmem.

    Odolnější než „1 % energie“: jedno tiché prosakování pod filtrem hranu neposune. None, když v pásmu nic není.
    """
    if len(mono) < 8192:
        return None
    f, p = sig.welch(mono, fs=SR, nperseg=16384)
    edges = []
    e = lo
    while e < hi:
        edges.append(e)
        e *= 2 ** (1 / 3)
    energy = np.array([p[(f >= a) & (f < a * 2 ** (1 / 3))].sum() for a in edges])
    if energy.max() <= 1e-18:
        return None
    ok = np.where(10 * np.log10(np.maximum(energy, 1e-30) / energy.max()) >= thr_db)[0]
    return float(edges[int(ok[0])])


def envelope_profile(x: np.ndarray, t0: float, t1: float, bpm: float, n_peaks: int = 5,
                     lo: float = 1.0, hi: float = 24.0) -> dict:
    """Obálka 60–300 Hz -> Hilbert -> FFT v okně t0–t1; nejsilnější čáry od `lo` Hz (pod tím je stavba frází, ne rytmus).

    Každá čára má i počet cyklů na takt (hz / (bpm/240)): celá nebo půlená čísla = vzor zamčený na takt
    (rytmus not, mřížka), neceločíselná = volně běžící (LFO bez synchronizace, detune). Příčinu to neříká.
    Pole primary_hz / grid_match / secondary_hz odpovídají schématu (primary = nejsilnější čára).
    """
    seg = x[int(t0 * SR):int(t1 * SR)].mean(axis=1)
    out = {"primary_hz": None, "grid_match": "unknown", "secondary_hz": [], "peaks": [], "on_bar_grid": None,
           "on_bar_grid_chance": None, "detection": f"bandpass 60-300 -> Hilbert -> FFT, čáry od {lo:g} Hz"}
    if len(seg) < SR // 2:
        return out
    sos = sig.butter(4, [60.0 / (SR / 2), 300.0 / (SR / 2)], btype="band", output="sos")
    env = np.abs(sig.hilbert(sig.sosfiltfilt(sos, seg)))
    env = (env - env.mean()) * np.hanning(len(env))
    f = np.fft.rfftfreq(len(env), 1.0 / SR)
    m = np.abs(np.fft.rfft(env))
    sel = (f >= lo) & (f <= hi)
    if not sel.any() or m[sel].max() <= 1e-12:
        return out
    ff, mm = f[sel], m[sel]
    pk = sig.find_peaks(mm, distance=max(1, int(0.15 / (f[1] - f[0]))))[0]
    top = sorted(pk, key=lambda i: -mm[i])[:n_peaks]
    if not top:                                     # hladká obálka (držený tón): žádné čáry
        return out
    bar_hz = bpm / 240.0
    peaks = [{"hz": round(float(ff[i]), 2), "per_bar": round(float(ff[i] / bar_hz), 2), "rel": round(float(mm[i] / mm[top[0]]), 2)}
             for i in top]
    out["peaks"] = peaks
    out["primary_hz"] = peaks[0]["hz"]
    out["grid_match"] = at.grid_label(peaks[0]["hz"], bpm)
    out["secondary_hz"] = [p["hz"] for p in peaks[1:]]
    # Tolerance podle rozlišení FFT (kratší okno = hrubší čáry), nejméně ±0,05 cyklu na takt. Náhodná shoda s celým nebo
    # půleným počtem cyklů na takt je pak 4 × tolerance (±0,05 -> 20 %), proto se vrací i ona; samotné „true“ nic nedokazuje.
    tol = max(0.05, 1.5 * (1.0 / (len(seg) / SR)) / bar_hz)
    out["on_bar_grid"] = abs(peaks[0]["per_bar"] * 2 - round(peaks[0]["per_bar"] * 2)) <= 2 * tol
    out["on_bar_grid_chance"] = round(min(1.0, 4 * tol), 2)
    return out


def grid_phrase(p: dict) -> str:
    """Věta o nejsilnější čáře: leží na celém/půleném počtu cyklů na takt, nebo ne (s pravděpodobností náhodné shody)."""
    if p.get("on_bar_grid") is None:
        return "bez čar"
    where = "na celém/půleném počtu cyklů na takt" if p["on_bar_grid"] else "mimo celé/půlené cykly na takt"
    return f"{where} (náhodná shoda ~{p['on_bar_grid_chance']:.0%})"


def active_window(bus: np.ndarray, bpm: float, drop_db: float = 12.0, min_len_s: float = 8.0) -> tuple[float, float] | None:
    """Nejdelší souvislý úsek, kde basová sběrnice hraje (RMS do `drop_db` pod 90. percentilem), mezery do jednoho taktu se zavírají.

    Součet všech stemů dropy hledá špatně (u části tracků vyšlo okno 12 s nebo celý soubor), basa sama je spolehlivější.
    """
    db, times = at.rms_curve(bus)
    if len(db) == 0:
        return None
    active = db > np.percentile(db, 90) - drop_db
    idx = np.flatnonzero(active)
    if len(idx) == 0:
        return None
    hop = float(times[1] - times[0]) if len(times) > 1 else at.HOP_S
    gap = max(1, int(round(240.0 / bpm / hop)))
    runs = np.split(idx, np.flatnonzero(np.diff(idx) > gap) + 1)
    best = max(runs, key=len)
    t0, t1 = float(times[best[0]]), float(times[best[-1]])
    return (t0, t1) if t1 - t0 >= min_len_s else None


def hold_start(mono: np.ndarray, t0: float, t1: float, win_s: float = 1.5, hop_s: float = 0.25) -> float | None:
    """Začátek nejhlasitější držené pasáže 1,5 s v okně t0–t1 (pásmo 60–900 Hz). None, když je okno příliš krátké."""
    seg = mono[int(t0 * SR):int(t1 * SR)]
    win, hop = int(win_s * SR), int(hop_s * SR)
    if len(seg) < win:
        return None
    sos = sig.butter(4, [60.0 / (SR / 2), 900.0 / (SR / 2)], btype="band", output="sos")
    y = sig.sosfiltfilt(sos, seg)
    sq = np.concatenate([[0.0], np.cumsum(y.astype(np.float64) ** 2)])
    starts = np.arange(0, len(y) - win + 1, hop)
    s = int(starts[int(np.argmax(sq[starts + win] - sq[starts]))])
    return t0 + s / SR


def _f(v, nd=2):
    return None if v is None else float(f"{float(v):.{nd}f}")

# --- sub vs. mid basa: drží sub jednu notu, zatímco mids hrají vlastní rytmus? ---------------------------------

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
ENV_FS = 240                      # vzorkování obálky pro nástupy (Hz)


def note_name(midi: float) -> str:
    """Název noty podle Live (C3 = MIDI 60, A3 = 440 Hz)."""
    p = int(round(midi))
    return f"{NOTE_NAMES[p % 12]}{p // 12 - 2}"


def _bandpass(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    sos = sig.butter(4, [lo / (SR / 2), min(hi, SR / 2 * 0.95) / (SR / 2)], btype="band", output="sos")
    return sig.sosfiltfilt(sos, x)


def band_envelope(x: np.ndarray, lo: float, hi: float, smooth_hz: float = 30.0) -> np.ndarray:
    """Obálka pásma lo–hi (Hilbert, dolní propust) decimovaná na ENV_FS."""
    e = np.abs(sig.hilbert(_bandpass(x, lo, hi)))
    e = sig.sosfiltfilt(sig.butter(2, smooth_hz / (SR / 2), btype="low", output="sos"), e)
    return np.maximum(e[:: SR // ENV_FS], 0.0)


def envelope_onsets(env: np.ndarray, bpm: float, rise_db: float = 4.0, floor_db: float = 35.0) -> np.ndarray:
    """Časy nástupů (s): obálka vyroste o `rise_db` během ~21 ms; minimální odstup 1/32 noty."""
    if len(env) < 20 or env.max() <= 1e-9:
        return np.array([])
    db = 20 * np.log10(np.maximum(env, 1e-9))
    k = 5
    rise = np.concatenate([np.zeros(k), db[k:] - db[:-k]])
    score = np.where(db >= np.percentile(db, 95) - floor_db, rise, 0.0)
    pk, _ = sig.find_peaks(score, height=rise_db, distance=max(1, int(round(60.0 / bpm / 8 * ENV_FS))))
    return pk / ENV_FS


def pitch_track(mono: np.ndarray, lo: float = 25.0, hi: float = 120.0, win: int = 9600, hop: int = 2400,
                nfft: int = 32768, voiced_db: float = 24.0, min_prom: float = 4.0) -> dict | None:
    """Výška subu po okénkách 200 ms: špička spektra v lo–hi s parabolickou interpolací. Noty kratší než ~1/8 se rozmažou."""
    n = (len(mono) - win) // hop + 1
    if n < 8:
        return None
    w = np.hanning(win)
    f = np.fft.rfftfreq(nfft, 1.0 / SR)
    sel = np.flatnonzero((f >= lo) & (f <= hi))
    fs_ = f[sel]
    rms, freq, prom = np.empty(n), np.empty(n), np.empty(n)
    ar = np.arange(win)
    for c0 in range(0, n, 64):
        idx = np.arange(c0, min(n, c0 + 64))
        fr = mono[idx[:, None] * hop + ar] * w
        rms[idx] = np.sqrt(np.mean(fr ** 2, axis=1) / np.mean(w ** 2))
        sp = np.abs(np.fft.rfft(fr, nfft, axis=1))[:, sel]
        i = sp.argmax(axis=1)
        ii = np.clip(i, 1, len(fs_) - 2)
        r = np.arange(len(idx))
        a, b, c = (np.log(np.maximum(sp[r, ii + d], 1e-12)) for d in (-1, 0, 1))
        den = a - 2 * b + c
        delta = np.clip(0.5 * (a - c) / np.where(np.abs(den) > 1e-12, den, 1.0), -1, 1)
        freq[idx] = fs_[ii] + delta * (fs_[1] - fs_[0])
        prom[idx] = sp[r, i] / np.maximum(np.median(sp, axis=1), 1e-12)
    rms_db = 20 * np.log10(np.maximum(rms, 1e-9))
    voiced = (rms_db >= np.percentile(rms_db, 95) - voiced_db) & (prom >= min_prom) & (rms > 1e-6)
    return {"midi": 69.0 + 12.0 * np.log2(np.maximum(freq, 1e-6) / 440.0), "rms_db": rms_db, "voiced": voiced}


def sub_note_profile(track: dict | None, bars: float, min_run: int = 4) -> dict:
    """Dominantní nota subu, podíl energie na ní (±0,5 půltónu), rozdělení not a počet změn noty (běhy od 200 ms)."""
    out = {"note": None, "hz": None, "static_share": None, "notes": [], "changes_per_8bars": None}
    if track is None or track["voiced"].sum() < 8:
        return out
    v = track["voiced"]
    m = track["midi"][v]
    wgt = 10 ** (track["rms_db"][v] / 10.0)
    cand = np.arange(m.min(), m.max() + 0.05, 0.05)
    c0 = float(cand[int(np.argmax([wgt[np.abs(m - c) <= 0.5].sum() for c in cand]))])
    near = np.abs(m - c0) <= 0.5
    c0 = float(np.average(m[near], weights=wgt[near]))
    tot = wgt.sum()
    k = np.round(m - c0).astype(int)
    ks = sig.medfilt(k.astype(float), 3).astype(int) if len(k) >= 3 else k
    uniq, inv = np.unique(ks, return_inverse=True)
    shares = np.bincount(inv, weights=wgt) / tot
    runs, start = [], 0
    for i in range(1, len(ks) + 1):
        if i == len(ks) or ks[i] != ks[start]:
            if i - start >= min_run and (not runs or runs[-1] != int(ks[start])):
                runs.append(int(ks[start]))
            start = i
    out.update({
        "note": note_name(c0), "hz": _f(440.0 * 2 ** ((c0 - 69) / 12), 1),
        "static_share": _f(wgt[np.abs(m - c0) <= 0.5].sum() / tot, 3),
        "notes": [{"note": note_name(c0 + int(u)), "share": _f(sh, 2)}
                  for u, sh in sorted(zip(uniq, shares), key=lambda z: -z[1]) if sh >= 0.05],
        "changes_per_8bars": _f(max(0, len(runs) - 1) / max(bars / 8.0, 1e-9), 1),
    })
    return out


def onset_coincidence(a: np.ndarray, b: np.ndarray, tol_s: float, dur_s: float) -> tuple[float | None, float | None]:
    """Podíl nástupů `a`, u kterých je do ±tol nástup `b`, a náhodná shoda při stejné hustotě `b` (Poisson)."""
    if len(a) == 0:
        return None, None
    if len(b) == 0:
        return 0.0, 0.0
    j = np.searchsorted(b, a)
    d = np.minimum(np.abs(a - b[np.clip(j, 0, len(b) - 1)]), np.abs(a - b[np.clip(j - 1, 0, len(b) - 1)]))
    return float((d <= tol_s).mean()), float(1 - np.exp(-2 * tol_s * len(b) / dur_s))


def measure_layering(sub: np.ndarray | None, mids: np.ndarray | None, bpm: float, t0: float, t1: float) -> dict | None:
    """Vztah subu a mid basy v okně t0–t1: výška subu (jedna nota, nebo linka) a rytmus mids proti subu.

    Bez sub stemu se sub bere z pásma 22–75 Hz stemu mids (slabší důkaz, je to v `sub_source`). `relation` je
    popisný štítek s pevnými prahy (static = 85 % energie na jedné notě; together = shoda nástupů 0,2 nad náhodou).
    """
    sl = lambda a: a[int(t0 * SR):int(t1 * SR)].mean(axis=1).astype(np.float64)  # noqa: E731
    dur = t1 - t0
    if dur < 8.0:
        return None
    bars = dur / (240.0 / bpm)
    if sub is not None:
        sub_x, src, hi = sl(sub), "sub stemy", 120.0
    elif mids is not None:
        sub_x, src, hi = sl(mids), "pásmo 22–75 Hz stemu mids (sub stem zvlášť není)", 75.0
    else:
        return None
    prof = sub_note_profile(pitch_track(_bandpass(sub_x, 22.0, hi + 10), hi=hi), bars)
    res = {"sub_source": src, "bars": _f(bars, 1), "sub_note": prof["note"], "sub_hz": prof["hz"],
           "sub_static_share": prof["static_share"], "sub_notes": prof["notes"],
           "sub_note_changes_per_8bars": prof["changes_per_8bars"],
           "mids_onsets_per_bar": None, "sub_onsets_per_bar": None, "onset_coincidence": None,
           "onset_coincidence_chance": None, "relation": "unknown"}
    so = envelope_onsets(band_envelope(sub_x, 22.0, hi), bpm)
    res["sub_onsets_per_bar"] = _f(len(so) / bars)
    together = None
    if mids is not None:
        mo = envelope_onsets(band_envelope(sl(mids), 100.0, 3000.0), bpm)
        res["mids_onsets_per_bar"] = _f(len(mo) / bars)
        frac, chance = onset_coincidence(mo, so, 60.0 / bpm / 8, dur)
        res["onset_coincidence"], res["onset_coincidence_chance"] = _f(frac), _f(chance)
        if frac is not None and len(mo) / bars >= 2:
            together = frac - chance >= 0.2
    if prof["static_share"] is None:
        return res
    if prof["static_share"] < 0.85:
        res["relation"] = "sub_moves"
    elif together is None:
        res["relation"] = "sub_static"
    else:
        res["relation"] = "sub_static_mids_together" if together else "sub_static_mids_independent"
    return res


def layering_phrase(lay: dict | None) -> str:
    if not lay or lay.get("sub_static_share") is None:
        return "Sub vs. mids: neměřeno."
    notes = ", ".join(f"{n['note']} {n['share']:.0%}" for n in lay["sub_notes"][:4])
    txt = (f"Sub ({lay['sub_source']}): {lay['sub_static_share']:.0%} energie na notě {lay['sub_note']} ({lay['sub_hz']} Hz, názvy podle Live); "
           f"noty: {notes}; změn noty na 8 taktů ~{lay['sub_note_changes_per_8bars']}.")
    if lay.get("onset_coincidence") is not None:
        txt += (f" Mids: {lay['mids_onsets_per_bar']} nástupu na takt; se subem se kryje {lay['onset_coincidence']:.0%} nástupů mids"
                f" (náhodná shoda {lay['onset_coincidence_chance']:.0%}).")
    return txt + " Okno 200 ms: noty kratší než osmina se rozmažou; sidechain umí vyrobit nástupy subu i při stálé výšce."


def _clean_caveat(text: str) -> str:
    return text.replace(" — full mix: not discriminative, confirm on stems",
                        " — izolovaná mid basa; heuristika, u vrstvené basy vychází „reese-like“ téměř vždy, neprůkazné")


def measure_stems(sub: np.ndarray | None, mids: np.ndarray | None, mix: np.ndarray, bpm: float,
                  window: tuple[float, float] | None = None) -> dict:
    """Měření basové sběrnice v hlavním dropu. sub/mids/mix jsou (N,2) při SR; mix určuje okno a poměr vůči celku."""
    if sub is None and mids is None:
        raise ValueError("žádné stemy basy")
    n = max(len(a) for a in (sub, mids, mix) if a is not None)
    sub, mids, mix = pad_to(sub, n), pad_to(mids, n), pad_to(mix, n)
    parts = [a for a in (sub, mids) if a is not None]
    bus = parts[0] if len(parts) == 1 else parts[0] + parts[1]

    db, times = at.rms_curve(mix)
    sections, drop_win = at.detect_sections(db, times)
    warnings: list[str] = []
    if window:
        t0, t1 = window
        win_src = "manual"
    elif (aw := active_window(bus, bpm)) is not None:
        (t0, t1), win_src = aw, "basa hraje"
    elif drop_win[1] > drop_win[0]:
        (t0, t1), win_src = drop_win, "drop ze součtu stemů"
        warnings.append("souvislý úsek basy se nenašel, okno z RMS součtu stemů")
    else:
        t0, t1, win_src = 0.0, n / SR, "celý soubor"
        warnings.append("okno dropu se nenašlo, měřeno přes celý soubor")
    sl = lambda a: a[int(t0 * SR):int(t1 * SR)]  # noqa: E731
    mix_d, bus_d = sl(mix), sl(bus)
    mix_mono, bus_mono = mix_d.mean(axis=1), bus_d.mean(axis=1)

    full_db = at.band_rms(mix_mono, 20, 10000)
    sub_db = at.band_rms(bus_mono, 20, 60)
    fund_db = at.band_rms(bus_mono, 60, 250)
    sub_rel, fund_rel = sub_db - full_db, fund_db - full_db
    profile = "sub_dominant" if sub_rel > fund_rel + 2 else "fundament_dominant" if fund_rel > sub_rel + 2 else "balanced"

    m_s, s_s = at.mid_side_db(bus_d, 20, 60)
    m_f, s_f = at.mid_side_db(bus_d, 60, 250)

    res: dict = {
        "window": {"start_sec": round(t0, 2), "end_sec": round(t1, 2), "source": win_src},
        "mix_drop_window": [round(drop_win[0], 2), round(drop_win[1], 2)],
        "sections": sections,
        "sub_rel_db": _f(sub_rel), "fundament_rel_db": _f(fund_rel), "profile": profile,
        "sub_side_db": _f(s_s - m_s), "fundament_side_db": _f(s_f - m_f),
        "modulation_bus": envelope_profile(bus, t0, t1, bpm),
        "warnings": warnings,
    }
    if sub is not None:
        res["sub_top_hz"] = _f(edge_hz(sl(sub).mean(axis=1), 0.99, 20, 400), 1)
        res["sub_p90_hz"] = _f(edge_hz(sl(sub).mean(axis=1), 0.90, 20, 400), 1)
    if mids is not None:
        md = sl(mids)
        sub_share = band_share(md.mean(axis=1), 20, 60, 20, 2000)
        res["mids_sub_share"] = _f(sub_share, 3)
        if sub_share is not None and sub_share > 0.15:
            res["mids_bottom_hz"] = None
            warnings.append(f"mids stemy nesou {sub_share:.0%} energie v 20–60 Hz (jsou plnorozsahové), spodní hrana mid basy se neměří")
        else:
            res["mids_bottom_hz"] = _f(third_octave_floor_hz(md.mean(axis=1)), 1)
        m_h, s_h = at.mid_side_db(md, 300, 1000)
        res["mids_side_300_1k_db"] = _f(s_h - m_h)
        res["modulation_mids"] = envelope_profile(mids, t0, t1, bpm)
        hs = hold_start(mids.mean(axis=1), t0, t1)
        if hs is not None:
            r = at.reese_vs_growl(mids, hs - 1.5, hs + 1.5, bpm)
            r["conclusion"] = _clean_caveat(r["conclusion"])
            r["hold_start_sec"] = round(hs, 2)
            res["reese_vs_growl"] = r
        else:
            res["reese_vs_growl"] = None
            warnings.append("okno dropu je kratší než 1,5 s, reese vs. growl se neměřilo")
    res["layering"] = measure_layering(sub, mids, bpm, t0, t1)
    return res


def build_analysis(id_: str, bpm: float, title: str, res: dict, sub_names: list[str], mids_names: list[str],
                   mix_desc: str, source_id: str = "") -> dict:
    """Návrh analysis.json (schéma track-analysis). Crest a centroid se nevyplňují (součet stemů není mastered mix)."""
    m = {
        "crest_factor_drop_db": None, "loudness_strategy": "", "sections": [],
        "sub_rel_db": res["sub_rel_db"], "fundament_rel_db": res["fundament_rel_db"], "profile": res["profile"],
        "spectral_centroid_hz": None, "sub_side_db": res["sub_side_db"], "fundament_side_db": res["fundament_side_db"],
        "modulation": {k: res["modulation_bus"][k] for k in ("primary_hz", "grid_match", "secondary_hz", "detection")},
        "reese_vs_growl": res.get("reese_vs_growl"),
    }
    a = at.build_analysis(id_, bpm, "", title, "deep", "", m)
    stems_txt = f"sub: {', '.join(sub_names) or '—'}; mids: {', '.join(mids_names) or '—'}"
    a["method"].update({
        "tooling": "tools/stem_bass.py (ffmpeg -> numpy/scipy; součet stemů basy, pásma, side/mid, obálka 60–300 Hz, hi-res FFT)",
        "stems": True, "basis": "stems",
        "notes": f"Basové pásmo změřeno na izolovaných stemech ({stems_txt}). Okno dropu a celek: {mix_desc}. "
                 "Crest a centroid celku se neměří (součet stemů nemá mastering řetězec).",
    })
    a["confidence_overall"] = "mixed"
    a["structure"].update({"sections": [], "confidence": "",
                           "notes": "Sekce se ze stemů neurčují: RMS součtu stemů dává nespolehlivé hranice. Měřené okno basy je v bass.energy.notes."})
    a["dynamics"].update({"crest_factor_drop_db": None, "loudness_strategy": "", "confidence": "",
                          "notes": "Neměřeno: stemy bez mastering řetězce (limiter, master EQ), crest by nebyl srovnatelný s vydaným mixem."})
    e = a["bass"]["energy"]
    e["notes"] = (f"Basová sběrnice na stemech vůči {mix_desc} (bas bez bicích, proto fundament vychází níž než z plného mixu). "
                  + (f"Sub stemy: 90 % energie pod {res.get('sub_p90_hz')} Hz, 99 % pod {res.get('sub_top_hz')} Hz. " if sub_names else "Sub stem zvlášť není. ")
                  + (f"Mid basa: nejnižší třetinooktávové pásmo do −10 dB od maxima začíná na {res['mids_bottom_hz']} Hz. "
                     if res.get("mids_bottom_hz") is not None else "Spodní hrana mid basy neměřena (mids stemy nesou sub). ")
                  + f"Měřené okno {res['window']['start_sec']}–{res['window']['end_sec']} s ({res['window']['source']}).")
    a["bass"]["stereo"]["notes"] = (f"Side/mid na basové sběrnici; mid basa nad 300 Hz–1 kHz: {res.get('mids_side_300_1k_db')} dB."
                                    if "mids_side_300_1k_db" in res else "Side/mid na basové sběrnici.")
    mod = a["bass"]["modulation"]

    def _pk(prof):
        return ", ".join(f"{p['hz']} Hz ({p['per_bar']}/takt, {p['rel']})" for p in prof["peaks"]) or "žádné čáry"

    bus_prof, mid_prof = res["modulation_bus"], res.get("modulation_mids")
    mod.update({"source": "unknown", "basis": "stems", "confidence": "measured",
                "detection": "obálka 60–300 Hz na stemech basy -> Hilbert -> FFT, čáry od 1 Hz (pod tím je stavba frází). "
                             f"Basová sběrnice: {_pk(bus_prof)}; nejsilnější čára {grid_phrase(bus_prof)}"
                             + (f". Jen mid basa: {_pk(mid_prof)}" if mid_prof else "")
                             + ". Příčina (LFO, rytmus not, sidechain) není změřena."})
    lay = res.get("layering")
    if lay and lay.get("sub_static_share") is not None:
        a["bass"]["layering"] = {
            "sub_note": lay["sub_note"], "sub_hz": lay["sub_hz"], "sub_static_share": lay["sub_static_share"],
            "sub_note_changes_per_8bars": lay["sub_note_changes_per_8bars"],
            "mids_onsets_per_bar": lay["mids_onsets_per_bar"], "sub_onsets_per_bar": lay["sub_onsets_per_bar"],
            "onset_coincidence": lay["onset_coincidence"], "onset_coincidence_chance": lay["onset_coincidence_chance"],
            "relation": lay["relation"], "basis": "stems", "confidence": "measured", "notes": layering_phrase(lay),
        }
    a["bass"]["timbre"] = {"spectral_centroid_hz": None, "notes": "Neměřeno (součet stemů není mastered mix)."}
    a["fields_confidence"]["dynamics"] = ""
    if source_id:
        a["source_id"] = source_id
    return a


def list_stems(wavs: list[Path]) -> list[dict]:
    rows = []
    for p in wavs:
        x = load(p)
        mono = x.mean(axis=1)
        rms = float(np.sqrt(np.mean(mono.astype(np.float64) ** 2)))
        rows.append({
            "name": re.sub(r"\.wav$", "", p.name, flags=re.I), "sec": round(len(x) / SR, 1),
            "peak_db": round(20 * np.log10(max(float(np.abs(x).max()), 1e-9)), 1),
            "rms_db": round(20 * np.log10(max(rms, 1e-9)), 1), "role": role_guess(p.name),
        })
    return rows


def _names(s: str) -> list[str]:
    return [t.strip() for t in s.split(",") if t.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description="Basové pásmo z izolovaných stemů (jen čtení).")
    ap.add_argument("--dir", required=True, type=Path)
    ap.add_argument("--bpm", type=float, default=174.0)
    ap.add_argument("--sub", default="", help="názvy sub stemů (bez .wav), oddělené čárkou")
    ap.add_argument("--mids", default="", help="názvy mid stemů (bez .wav), oddělené čárkou")
    ap.add_argument("--exclude", default="", help="stemy vynechané ze součtu celku (duplicity, varianty)")
    ap.add_argument("--mix", default="", help="hotový master soubor složky místo součtu stemů")
    ap.add_argument("--window", default="", help="t0,t1 v sekundách místo automatického dropu")
    ap.add_argument("--list", action="store_true", help="vypsat stemy (délka, hlasitost, odhad role) a skončit")
    ap.add_argument("--json", type=Path, help="uložit měření jako JSON (mimo repo nebo do _local)")
    ap.add_argument("--analysis-out", type=Path, help="zapsat návrh analysis.json")
    ap.add_argument("--id", default="")
    ap.add_argument("--title", default="")
    ap.add_argument("--source-id", default="")
    args = ap.parse_args()

    wavs = find_wavs(args.dir)
    if not wavs:
        raise SystemExit(f"ve složce nejsou žádné .wav: {args.dir}")
    if args.list:
        print(f"{'stem':<64}{'s':>7}{'peak':>7}{'rms':>7}  role")
        for r in list_stems(wavs):
            print(f"{r['name'][:62]:<64}{r['sec']:>7}{r['peak_db']:>7}{r['rms_db']:>7}  {r['role']}")
        return 0

    sub_names, mids_names = _names(args.sub), _names(args.mids)
    if not (sub_names or mids_names):
        raise SystemExit("zadej --sub a/nebo --mids (nejdřív --list)")
    sub_p, mids_p = pick(wavs, sub_names), pick(wavs, mids_names)
    excl = {p.resolve() for p in pick(wavs, _names(args.exclude))}
    if args.mix:
        mix_p = pick(wavs, [args.mix])[0]
        mix, mix_desc = load(mix_p), f"master soubor „{mix_p.stem}“"
    else:
        used = [p for p in wavs if p.resolve() not in excl]
        mix, mix_desc = sum_stems(used), f"součet {len(used)} stemů"
    window = None
    if args.window:
        a, b = (float(v) for v in args.window.split(","))
        window = (a, b)

    res = measure_stems(sum_stems(sub_p), sum_stems(mids_p), mix, args.bpm, window)
    res.update({"basis": "stems", "bpm": args.bpm, "sub_stems": sub_names, "mids_stems": mids_names, "mix_reference": mix_desc})

    def _prof(p):
        return ", ".join(f"{q['hz']} Hz = {q['per_bar']}/takt ({q['rel']})" for q in p["peaks"]) or "žádné čáry"

    print(f"Okno dropu: {res['window']['start_sec']}–{res['window']['end_sec']} s ({res['window']['source']}); celek: {mix_desc}")
    print(f"sub vůči celku {res['sub_rel_db']} dB, fundament {res['fundament_rel_db']} dB ({res['profile']}); bas bez bicích, fundament tedy níž než z plného mixu")
    print(f"side/mid: sub {res['sub_side_db']} dB, fundament {res['fundament_side_db']} dB"
          + (f", mid basa 300 Hz–1 kHz {res['mids_side_300_1k_db']} dB" if "mids_side_300_1k_db" in res else ""))
    print((f"sub: 90 % energie pod {res.get('sub_p90_hz')} Hz, 99 % pod {res.get('sub_top_hz')} Hz; " if sub_names else "sub stem zvlášť není; ") + f"mid basa: spodní hrana (−10 dB, třetinoktávy) {res.get('mids_bottom_hz') if res.get('mids_bottom_hz') is not None else 'neměřena'}")
    print(f"modulace basové sběrnice (čáry od 1 Hz): {_prof(res['modulation_bus'])}; nejsilnější "
          f"{grid_phrase(res['modulation_bus'])}")
    if res.get("modulation_mids"):
        print(f"modulace mid basy: {_prof(res['modulation_mids'])}")
    if res.get("reese_vs_growl"):
        r = res["reese_vs_growl"]
        print(f"reese vs. growl (držená nota od {r['hold_start_sec']} s): {r['hi_res_fft_350_900']}; {r['conclusion']}")
    print(layering_phrase(res.get("layering")) + (f" Štítek: {res['layering']['relation']}." if res.get("layering") else ""))
    for w in res["warnings"]:
        print(f"Pozor: {w}")

    for out in (args.json,):
        if out:
            out = out.resolve()
            if ROOT in out.parents and "_local" not in out.parts:
                raise SystemExit("výstup patří mimo repo nebo do složky _local")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    if args.analysis_out:
        if not args.id:
            raise SystemExit("--analysis-out vyžaduje --id")
        a = build_analysis(args.id, args.bpm, args.title or args.id, res, sub_names, mids_names, mix_desc, args.source_id)
        args.analysis_out.parent.mkdir(parents=True, exist_ok=True)
        args.analysis_out.write_text(json.dumps(a, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
