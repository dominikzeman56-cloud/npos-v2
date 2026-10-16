#!/usr/bin/env python3
"""preset_roles.py — role presetu ze ZVUKU (render), ne z názvu.

Vstup: `data/presets/audio/*.jsonl` (deskriptory z `render_preset.py`) + role z názvu z `data/presets/index` a `fxp`.
Postup: kNN (k sousedů, z-skóre deskriptorů) natrénované na presetech, jejichž název roli nese; pro každý preset
navrhne rodinu (bass / tonal / perc / fx) a u basů podtyp, **jen pokud ho křížová validace odliší líp než náhoda**.

Pravdivost: deskriptory jsou `measured` (jen pro protokol renderu: nota E1, volitelně i C4 z `audio-c4/`), role ze zvuku je `estimated`
(statistický odhad z kotev, které samy pocházejí z názvu = hypothesis). Potvrzuje člověk poslechem.

Výstup: `data/presets/roles/audio-roles.jsonl` (řádek na preset) a `data/presets/roles/eval.json` (přesnost, záměny).
Použití: py -3.12 tools/preset_roles.py [--k 7] [--write]
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parent.parent
PRESETS = REPO / "data" / "presets"

FAMILY = {"bass": "bass", "reese": "bass", "neuro": "bass", "sub": "bass", "stab": "bass",
          "lead": "tonal", "pad": "tonal", "synth": "tonal", "seq": "tonal", "pluck": "tonal", "chords": "tonal",
          "layer": "tonal", "guitar": "tonal", "perc": "perc", "fx": "fx"}
BASS_SUB = ("bass", "reese", "neuro", "sub", "stab")
# (klíč, transformace): Hz a dB na log/lineární škálu, aby vzdálenost nedominovala jedna veličina
FEATURES = [("rms_db", None), ("crest_db", None), ("band_sub_pct", None), ("band_low_pct", None), ("band_mid_pct", None),
            ("band_high_pct", None), ("band_air_pct", None), ("centroid_hz", "log"), ("rolloff85_hz", "log"),
            ("harmonic_pct", None), ("am_depth", "log1p"), ("side_minus_mid_db", "clip"), ("upper_db", None),
            ("upper_centroid_hz", "log"), ("upper_flatness", None), ("upper_motion", "log1p"),
            ("upper_flux", "log1p"), ("attack", None)]
# z renderu na C4 (audio-c4/): leady a pady se posuzují ve své poloze, ne na E1
FEATURES_C4 = [("rms_db", None), ("band_low_pct", None), ("band_mid_pct", None), ("band_high_pct", None),
               ("centroid_hz", "log"), ("harmonic_pct", None), ("upper_flatness", None), ("upper_motion", "log1p"),
               ("side_minus_mid_db", "clip")]


def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def load(root: Path = PRESETS) -> tuple[list[dict], dict[str, dict]]:
    audio = [r for f in sorted((root / "audio").glob("*.jsonl")) for r in load_jsonl(f)]
    c4 = {r["id"]: r["audio"] for f in sorted((root / "audio-c4").glob("*.jsonl")) for r in load_jsonl(f)}
    for r in audio:
        r["audio_c4"] = c4.get(r["id"])
    meta: dict[str, dict] = {}
    for d in ("index", "fxp"):
        for f in sorted((root / d).glob("*.jsonl")):
            for r in load_jsonl(f):
                meta[r["id"]] = r
    return audio, meta


def vector(a: dict[str, Any], c4: dict[str, Any] | None = None, use_c4: bool = False) -> list[float | None]:
    out = _vec(a, FEATURES)
    if use_c4:
        out += _vec(c4 or {}, FEATURES_C4) if c4 and not c4.get("silent") else [None] * len(FEATURES_C4)
    return out


def _vec(a: dict[str, Any], spec: list[tuple[str, str | None]]) -> list[float | None]:
    out: list[float | None] = []
    for k, tr in spec:
        if k == "attack":
            out.append(1.0 if a.get("window") == "attack" else 0.0)
            continue
        v = a.get(k)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            out.append(None)
            continue
        v = float(v)
        if tr == "log":
            v = math.log10(max(v, 1.0))
        elif tr == "log1p":
            v = math.log1p(max(v, 0.0))
        elif tr == "clip":
            v = max(v, -40.0)   # dokonale mono (−138 dB) by jinak táhlo vzdálenost
        out.append(v)
    return out


def matrix(rows: list[list[float | None]]) -> np.ndarray:
    """Doplní chybějící mediánem sloupce a z-skóruje."""
    X = np.array([[np.nan if v is None else v for v in r] for r in rows], dtype=float)
    med = np.nanmedian(X, axis=0)
    med = np.where(np.isnan(med), 0.0, med)
    X = np.where(np.isnan(X), med, X)
    sd = X.std(axis=0)
    return (X - X.mean(axis=0)) / np.where(sd > 0, sd, 1.0)


def knn(X: np.ndarray, labels: list[str | None], k: int, exclude_self: bool = True,
        balance: bool = False) -> list[tuple[str | None, float]]:
    """Pro každý řádek většinová kotva mezi k nejbližšími označenými (vážené 1/d). Shodné vektory (duplikáty) se
    při validaci vynechávají, aby si preset neodpověděl sám sobě přes kopii."""
    lab_idx = np.array([i for i, l in enumerate(labels) if l is not None])
    out: list[tuple[str | None, float]] = []
    if not len(lab_idx):
        return [(None, 0.0)] * len(X)
    L = X[lab_idx]
    prior = collections.Counter(labels[i] for i in lab_idx)
    # vyvážení: hlas třídy dělený její četností, jinak by převaha basů (2/3 kotev) přehlasovala vše ostatní
    wcls = {c: (len(lab_idx) / (len(prior) * n)) if balance else 1.0 for c, n in prior.items()}
    for i in range(len(X)):
        d = np.sqrt(((L - X[i]) ** 2).sum(axis=1))
        if exclude_self:
            d = np.where(d < 1e-9, np.inf, d)
        order = np.argsort(d)[:k]
        votes: dict[str, float] = collections.defaultdict(float)
        for j in order:
            if np.isfinite(d[j]):
                votes[labels[lab_idx[j]]] += wcls[labels[lab_idx[j]]] / (d[j] + 1e-6)
        if not votes:
            out.append((None, 0.0))
            continue
        best = max(votes, key=votes.get)
        out.append((best, round(votes[best] / sum(votes.values()), 3)))
    return out


def evaluate(pred: list[tuple[str | None, float]], labels: list[str | None]) -> dict[str, Any]:
    pairs = [(t, p) for (p, _), t in zip(pred, labels) if t is not None and p is not None]
    classes = sorted({t for t, _ in pairs})
    conf = {t: dict(collections.Counter(p for tt, p in pairs if tt == t)) for t in classes}
    recall = {t: round(conf[t].get(t, 0) / max(sum(conf[t].values()), 1), 3) for t in classes}
    predicted = collections.Counter(p for _, p in pairs)
    precision = {t: round(conf[t].get(t, 0) / predicted[t], 3) for t in classes if predicted[t]}
    counts = collections.Counter(t for t, _ in pairs)
    chance = max(counts.values()) / len(pairs) if pairs else 0.0
    acc = sum(1 for t, p in pairs if t == p) / len(pairs) if pairs else 0.0
    return {"n": len(pairs), "accuracy": round(acc, 3), "majority_baseline": round(chance, 3),
            "balanced_accuracy": round(float(np.mean(list(recall.values()))) if recall else 0.0, 3),
            "recall": recall, "precision": precision, "confusion": conf, "counts": dict(counts)}


def run(k: int = 7, root: Path = PRESETS) -> tuple[list[dict], dict[str, Any]]:
    audio, meta = load(root)
    rows = [r for r in audio if not r["audio"].get("silent") and r["id"] in meta]
    use_c4 = any(r.get("audio_c4") for r in rows)
    X = matrix([vector(r["audio"], r.get("audio_c4"), use_c4) for r in rows])
    name_role = [meta[r["id"]].get("role", "other") for r in rows]
    fam = [FAMILY.get(x) for x in name_role]
    fam_pred = knn(X, fam, k)
    ev_fam = evaluate(fam_pred, fam)
    # podtypy basů: jen mezi presety, které zvuk zařadil do rodiny bass
    in_bass = [i for i, (p, _) in enumerate(fam_pred) if p == "bass"]
    sub_lab = [name_role[i] if name_role[i] in BASS_SUB else None for i in in_bass]
    sub_pred = knn(X[in_bass], sub_lab, k) if in_bass else []
    ev_sub = evaluate(sub_pred, sub_lab)
    # podtyp se publikuje jen pro třídy, které validace opravdu pozná: n >= 10, recall >= 0,5 a přesnost >= 0,5
    trusted = sorted(c for c in ev_sub["recall"] if ev_sub["counts"][c] >= 10 and ev_sub["recall"][c] >= 0.5
                     and ev_sub["precision"].get(c, 0.0) >= 0.5 and c != "bass")
    sub_map = {in_bass[j]: sub_pred[j] for j in range(len(in_bass))}
    out = []
    for i, r in enumerate(rows):
        fp, fs = fam_pred[i]
        sp, ss = sub_map.get(i, (None, 0.0))
        out.append({"id": r["id"], "source_id": r["source_id"], "name_role": name_role[i], "family_name": fam[i],
                    "family_audio": fp, "family_score": fs,
                    "bass_role_audio": sp if sp in trusted else None, "bass_role_score": ss if sp in trusted else None,
                    "agree": None if fam[i] is None else fam[i] == fp,
                    "confidence": "estimated", "basis": f"render_E1{'+C4' if use_c4 else ''}+knn{k}"})
    ev = {"k": k, "features": [f for f, _ in FEATURES] + ([f"c4_{f}" for f, _ in FEATURES_C4] if use_c4 else []), "family": ev_fam, "bass_subtype": ev_sub,
          "bass_subtype_trusted": trusted, "rows": len(out),
          "unlabeled_name": sum(1 for x in fam if x is None),
          "note": "Validace = leave-one-out nad kotvami z názvu (hypothesis); duplikáty se nepočítají jako sousedé."}
    return out, ev


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--k", type=int, default=7)
    p.add_argument("--write", action="store_true")
    a = p.parse_args(argv)
    rows, ev = run(a.k)
    f, b = ev["family"], ev["bass_subtype"]
    print(f"rodina: n={f['n']} přesnost {f['accuracy']} (vyvážená {f['balanced_accuracy']}, většinová {f['majority_baseline']})")
    print("  recall", f["recall"])
    print(f"podtyp basu: n={b['n']} přesnost {b['accuracy']} (vyvážená {b['balanced_accuracy']}, většinová {b['majority_baseline']})")
    print("  recall", b["recall"], "důvěryhodné:", ev["bass_subtype_trusted"])
    unl = collections.Counter(r["family_audio"] for r in rows if r["family_name"] is None)
    print("presety bez role z názvu → rodina ze zvuku:", dict(unl))
    dis = [r for r in rows if r["agree"] is False]
    print(f"rozpor název vs. zvuk: {len(dis)}")
    if a.write:
        out = PRESETS / "roles"
        out.mkdir(parents=True, exist_ok=True)
        (out / "audio-roles.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                                               encoding="utf-8", newline="\n")
        (out / "eval.json").write_text(json.dumps(ev, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
