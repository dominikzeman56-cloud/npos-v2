#!/usr/bin/env python3
"""ref_check.py — vlastní bounce proti referenčním trackům z data/tracks. Jen čtení, do repa nic nezapisuje.

Změří plný mix stejnou cestou jako `analyze_track.py` (stejná okna a pásma) a ke každé veličině vypíše,
kde leží vůči referencím: pod rozpětím, v rozpětí, nad rozpětím, a který referenční track je nejblíž.

Porovnává jen to, co jde z plného mixu měřit spolehlivě (BLUEPRINT kap. 7):
crest v dropu, sub a fundament vůči celku, jejich rozdíl, spektrální centroid, side/mid v subu a ve fundamentu.
Modulaci basy neporovnává (z plného mixu je to nejvýš hypotéza).

Rozpětí referencí není norma. Je to pár tracků (počet je v záhlaví), různých žánrů a zdrojů (WAV, FLAC, MP3).
„Mimo rozpětí“ znamená „jinak než tyhle tracky“, ne „špatně“ (P9: hodnoty jsou výchozí body).
Jeden odlišný track rozpětí roztáhne (crossbreed má jiný low end než neurofunk); sloupec „od mediánu“
a výběr referencí přes `--refs` ukážou víc než samotné „v rozpětí“.

Použití:
  py -3.12 tools/ref_check.py --audio "D:/.../Bounce.wav" --bpm 174
  py -3.12 tools/ref_check.py --audio bounce.wav --bpm 174 --refs audio-dont-play,balron-audio-breach --detail
  py -3.12 tools/ref_check.py --analysis data/tracks/first-contact/analysis.json
  py -3.12 tools/ref_check.py --audio bounce.wav --bpm 174 --json D:/kamkoli/ref-check.json   (mimo repo)
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).parent))
from rebuild_track_index import reference_tracks  # noqa: E402

# klíč, popis, jednotka, co znamená „níž“ a „výš“ (výklad je odhad, ne měření)
METRICS = [
    ("crest_db", "crest v dropu", "dB", "hustší, víc slisované", "otevřenější, víc dynamiky"),
    ("sub_rel_db", "sub 20–60 Hz vůči celku", "dB", "slabší sub", "silnější sub"),
    ("fundament_rel_db", "fundament 60–250 Hz vůči celku", "dB", "slabší fundament", "silnější fundament"),
    ("sub_minus_fund_db", "sub mínus fundament", "dB", "těžiště výš (fundament)", "těžiště níž (sub)"),
    ("centroid_hz", "spektrální centroid", "Hz", "tmavší mix", "jasnější mix"),
    ("sub_side_db", "side vůči mid v subu", "dB", "sub víc mono", "sub širší"),
    ("fundament_side_db", "side vůči mid ve fundamentu", "dB", "fundament víc mono", "fundament širší"),
]
MIN_N_MEDIAN = 5   # pod tímhle počtem referencí se medián nevypisuje, jen rozpětí


def metrics_from_analysis(a: dict) -> dict:
    """Vytáhne porovnávané veličiny z analysis.json. Chybějící hodnota = None."""
    b = a.get("bass", {})
    e = b.get("energy", {})
    sub, fund = e.get("sub_rel_db"), e.get("fundament_rel_db")
    return {
        "crest_db": a.get("dynamics", {}).get("crest_factor_drop_db"),
        "sub_rel_db": sub,
        "fundament_rel_db": fund,
        "sub_minus_fund_db": round(sub - fund, 2) if sub is not None and fund is not None else None,
        "centroid_hz": b.get("timbre", {}).get("spectral_centroid_hz"),
        "sub_side_db": b.get("stereo", {}).get("sub_side_db"),
        "fundament_side_db": b.get("stereo", {}).get("fundament_side_db"),
    }


def position(value: float, refs: dict[str, float]) -> dict:
    """Kde leží hodnota vůči referencím. refs = {id tracku: hodnota}."""
    vals = sorted(refs.values())
    lo, hi = vals[0], vals[-1]
    if value < lo:
        where, off = "pod", round(value - lo, 2)
    elif value > hi:
        where, off = "nad", round(value - hi, 2)
    else:
        where, off = "v", 0.0
    nearest = min(refs, key=lambda k: (abs(refs[k] - value), k))
    return {
        "where": where, "offset": off, "min": lo, "max": hi, "n": len(vals),
        "median": round(statistics.median(vals), 2) if len(vals) >= MIN_N_MEDIAN else None,
        "nearest": nearest, "nearest_value": refs[nearest],
    }


def compare(own: dict, references: dict[str, dict]) -> list[dict]:
    """own = veličiny vlastního tracku, references = {id: veličiny}. Vrací řádek na veličinu."""
    rows = []
    for key, label, unit, low_hint, high_hint in METRICS:
        v = own.get(key)
        refs = {rid: m[key] for rid, m in references.items() if m.get(key) is not None}
        r = {"key": key, "label": label, "unit": unit, "value": v}
        if v is None or not refs:
            r["where"] = "bez dat"
        else:
            r.update(position(v, refs))
            r["hint"] = {"pod": low_hint, "nad": high_hint}.get(r["where"], "")
            r["refs"] = refs
        rows.append(r)
    return rows


def load_references(root: Path = ROOT, only: list[str] | None = None) -> dict[str, dict]:
    # Analýzy ze stemů (basis stems) sem nepatří: bas bez bicích a součet stemů bez mastering řetězce
    # dávají jiné sub/fundament/side a bez crestu a centroidu, než naměříme z vydaného plného mixu.
    refs = {meta["id"]: metrics_from_analysis(a) for meta, a in reference_tracks(root)
            if a.get("method", {}).get("basis") != "stems"}
    if only:
        missing = [i for i in only if i not in refs]
        if missing:
            raise SystemExit(f"neznámé reference: {', '.join(missing)} (k dispozici: {', '.join(sorted(refs))})")
        refs = {i: refs[i] for i in only}
    return refs


def _num(v: float, unit: str) -> str:
    return f"{v:.0f}" if unit == "Hz" else f"{v:.2f}"


def render(rows: list[dict], n_refs: int, detail: bool = False, notes: list[str] | None = None) -> str:
    out = [f"Reference: {n_refs} tracků. Rozpětí není norma, výklad je odhad.", ""]
    out.append(f"{'veličina':<33}{'tvoje':>8}  {'rozpětí referencí':<33}{'kde':<19}{'od mediánu':<12}nejblíž")
    for r in rows:
        if r["where"] == "bez dat":
            out.append(f"{r['label']:<33}{'—':>8}  bez dat")
            continue
        u = r["unit"]
        span = f"{_num(r['min'], u)} až {_num(r['max'], u)}"
        from_med = "—"
        if r["median"] is not None:
            span += f" (med. {_num(r['median'], u)})"
            d = r["value"] - r["median"]
            from_med = f"{'+' if d >= 0 else '−'}{_num(abs(d), u)}"
        if r["where"] == "v":
            where = "v rozpětí"
        else:
            where = f"{r['where']} o {_num(abs(r['offset']), u)} {u}"
        out.append(f"{r['label']:<33}{_num(r['value'], u):>8}  {span:<33}{where:<19}{from_med:<12}"
                   f"{r['nearest']} ({_num(r['nearest_value'], u)})")
    outside = [r for r in rows if r.get("where") in ("pod", "nad")]
    out.append("")
    if outside:
        out.append("Mimo rozpětí (odhad výkladu):")
        out += [f"  {r['label']}: {r['hint']}" for r in outside]
    else:
        out.append("Všechny veličiny leží v rozpětí referencí.")
    if detail:
        out.append("")
        out.append("Hodnoty po referencích:")
        for r in rows:
            if "refs" in r:
                vals = ", ".join(f"{k} {_num(v, r['unit'])}" for k, v in sorted(r["refs"].items(), key=lambda kv: kv[1]))
                out.append(f"  {r['label']}: {vals}")
    for n in notes or []:
        out.append("")
        out.append(f"Pozor: {n}")
    return "\n".join(out)


def measure_audio(path: Path, bpm: float) -> tuple[dict, list[str]]:
    """Změří bounce stejně jako analyze_track.py. Vrací (veličiny, upozornění)."""
    import analyze_track as at

    x = at.decode_audio(str(path))
    m = at.measure(x, bpm, "quick")
    dur = len(x) / at.SR
    notes = []
    drops = [s for s in m["sections"] if s["name"].startswith("drop")]
    longest = max((s["end_sec"] - s["start_sec"] for s in drops), default=0.0)
    if not drops or longest > 0.8 * dur:
        notes.append("sekce se nepodařilo rozlišit, pásma a stereo jsou měřené skoro přes celý soubor "
                     "(tichá místa stahují hodnoty). Pro čisté srovnání vybouncuj jen drop.")
    own = {
        "crest_db": m["crest_factor_drop_db"],
        "sub_rel_db": m["sub_rel_db"],
        "fundament_rel_db": m["fundament_rel_db"],
        "sub_minus_fund_db": round(m["sub_rel_db"] - m["fundament_rel_db"], 2),
        "centroid_hz": m["spectral_centroid_hz"],
        "sub_side_db": m["sub_side_db"],
        "fundament_side_db": m["fundament_side_db"],
    }
    return own, notes


def main() -> int:
    ap = argparse.ArgumentParser(description="Vlastní bounce proti referencím z data/tracks (jen čtení).")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--audio", help="plný mix (wav/flac/mp3)")
    src.add_argument("--analysis", help="hotový analysis.json místo měření")
    ap.add_argument("--bpm", type=float, default=174.0, help="tempo (jen pro měření, výsledek tabulky neovlivní)")
    ap.add_argument("--refs", default="", help="id referencí oddělená čárkou (výchozí: všechny)")
    ap.add_argument("--detail", action="store_true", help="vypsat hodnoty po referencích")
    ap.add_argument("--json", default="", help="uložit výsledek jako JSON (cesta mimo repo)")
    args = ap.parse_args()

    notes: list[str] = []
    if args.audio:
        p = Path(args.audio)
        if not p.exists():
            raise SystemExit(f"soubor neexistuje: {p}")
        own, notes = measure_audio(p, args.bpm)
    else:
        own = metrics_from_analysis(json.loads(Path(args.analysis).read_text(encoding="utf-8")))

    references = load_references(only=[s.strip() for s in args.refs.split(",") if s.strip()] or None)
    if not references:
        raise SystemExit("v data/tracks nejsou žádné referenční tracky")
    rows = compare(own, references)
    print(render(rows, len(references), args.detail, notes))

    if args.json:
        out = Path(args.json).resolve()
        if ROOT in out.parents and "_local" not in out.parts:
            raise SystemExit("výstup vlastního tracku do repa nepatří (jen mimo repo nebo do složky _local)")
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {"basis": "full_mix", "confidence": "naměřeno; výklad je odhad", "n_references": len(references),
                   "notes": notes, "rows": rows}
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
