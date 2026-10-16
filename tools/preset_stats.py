#!/usr/bin/env python3
"""preset_stats.py — souhrnné statistiky presetů po rolích a packách (jen čísla z `data/presets/`).

Co dělá:
  - per role (z názvu = hypothesis) a per pack: medián a kvartily parametrů (features) a deskriptorů zvuku (audio E1),
  - kontrast role proti ostatním (Cliffovo delta + Mann-Whitney, Bonferroni), jen uvnitř jednoho readeru,
  - shoda role z názvu a rodiny ze zvuku.

Pravidla pravdivosti:
  - skupina s n < 10 dostane jen počet, žádná čísla ani závěry,
  - S1 (reader serum1_host) a S2 (reader s2) se nemíchají: jednotky parametrů se mezi enginy nemusí shodovat,
  - parametr, který reader nečte (null), se do n nepočítá; skupina s < 10 hodnotami parametr nedostane,
  - kontrast se označí varováním, když jeden pack tvoří víc než polovinu skupiny (role × pack se zaměňují),
  - role jsou jen z názvů (hypothesis), čísla jsou naměřená ze souboru nebo z renderu jedné noty.
Použití: py -3.12 tools/preset_stats.py [--write] [--md CESTA.md]
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parent.parent
PRESETS = REPO / "data" / "presets"
MIN_N = 10
TOP = 6          # kolik rozlišujících parametrů ukázat na roli
MIN_DELTA = 0.3  # |Cliffovo delta| pod tímto prahem se nehlásí (malý efekt)
AUDIO_KEYS = ["rms_db", "crest_db", "band_sub_pct", "band_low_pct", "band_mid_pct", "band_high_pct", "centroid_hz",
              "harmonic_pct", "am_depth", "side_minus_mid_db", "upper_flatness", "upper_motion"]


def load_dir(root: Path, d: str) -> list[dict]:
    return [json.loads(line) for f in sorted((root / d).glob("*.jsonl"))
            for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]


def finite(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and np.isfinite(v)


def describe(vals: list[float]) -> dict[str, float]:
    a = np.asarray(vals, dtype=float)
    q1, med, q3 = np.percentile(a, [25, 50, 75])
    return {"n": int(len(a)), "median": round(float(med), 4), "p25": round(float(q1), 4), "p75": round(float(q3), 4)}


def group_stats(rows: list[dict], keys: list[str], getter) -> dict[str, Any]:
    """{n, features: {klíč: describe}} jen pro klíče s alespoň MIN_N hodnotami; jinak jen n."""
    out: dict[str, Any] = {"n": len(rows)}
    if len(rows) < MIN_N:
        out["note"] = f"n < {MIN_N}: bez čísel"
        return out
    feats = {}
    for k in keys:
        vals = [v for r in rows if finite(v := getter(r, k))]
        if len(vals) >= MIN_N:
            feats[k] = describe(vals)
    out["features"] = feats
    return out


def cliffs_delta(a: np.ndarray, b: np.ndarray) -> float:
    # (P(a > b) - P(a < b)) přes pořadí; O(n log n) místo O(n·m)
    allv = np.concatenate([a, b])
    order = allv.argsort(kind="mergesort")
    ranks = np.empty(len(allv))
    sv = allv[order]
    i = 0
    r = np.arange(1, len(allv) + 1, dtype=float)
    while i < len(sv):
        j = i
        while j + 1 < len(sv) and sv[j + 1] == sv[i]:
            j += 1
        r[i:j + 1] = (i + 1 + j + 1) / 2
        i = j + 1
    ranks[order] = r
    u = ranks[: len(a)].sum() - len(a) * (len(a) + 1) / 2
    return float(2 * u / (len(a) * len(b)) - 1)


def mwu_p(a: np.ndarray, b: np.ndarray) -> float | None:
    try:
        from scipy.stats import mannwhitneyu
    except ImportError:
        return None
    return float(mannwhitneyu(a, b, alternative="two-sided").pvalue)


def contrast(rows: list[dict], role: str, keys: list[str], getter) -> dict[str, Any]:
    """Role proti ostatním ve stejném readeru: které parametry ji odlišují (Cliffovo delta, Bonferroni)."""
    inn = [r for r in rows if r["role"] == role]
    out = [r for r in rows if r["role"] != role]
    res = {"n_role": len(inn), "n_rest": len(out), "features": []}
    if len(inn) < MIN_N or len(out) < MIN_N:
        return res
    top_pack, top_n = collections.Counter(r["source_id"] for r in inn).most_common(1)[0]
    if top_n / len(inn) > 0.5:
        res["warning"] = f"{round(100 * top_n / len(inn))} % skupiny je z jednoho packu ({top_pack}): role a pack se zaměňují"
    cand = []
    for k in keys:
        a = np.array([v for r in inn if finite(v := getter(r, k))], dtype=float)
        b = np.array([v for r in out if finite(v := getter(r, k))], dtype=float)
        if len(a) < MIN_N or len(b) < MIN_N or (np.ptp(a) == 0 and np.ptp(b) == 0):
            continue
        cand.append((k, a, b))
    for k, a, b in cand:
        d = cliffs_delta(a, b)
        if abs(d) < MIN_DELTA:
            continue
        p = mwu_p(a, b)
        sig = p is not None and p * max(len(cand), 1) < 0.01  # Bonferroni přes parametry v testu
        if p is not None and not sig:
            continue
        res["features"].append({"key": k, "delta": round(d, 3), "median_role": round(float(np.median(a)), 4),
                                "median_rest": round(float(np.median(b)), 4), "n_role": len(a), "n_rest": len(b)})
    res["features"].sort(key=lambda x: -abs(x["delta"]))
    res["features"] = res["features"][:TOP]
    return res


def build(root: Path = PRESETS, sources_path: Path | None = None) -> dict[str, Any]:
    meta = {r["id"]: r for d in ("index", "fxp") for r in load_dir(root, d)}
    feat = {r["id"]: r for r in load_dir(root, "features") if r["id"] in meta}
    audio = {r["id"]: r["audio"] for r in load_dir(root, "audio") if r["id"] in meta and not r["audio"].get("silent")}
    aroles = {r["id"]: r for r in load_dir(root, "roles")} if (root / "roles").exists() else {}
    authors: dict[str, str] = {}
    sp = sources_path or REPO / "knowledge" / "sources.jsonl"
    if sp.exists():
        for line in sp.read_text(encoding="utf-8").splitlines():
            if line.strip():
                s = json.loads(line)
                authors[s["id"]] = s.get("author", "")
    rows = []
    for i, f in feat.items():
        m = meta[i]
        rows.append({"id": i, "role": m.get("role", "other"), "source_id": m["source_id"],
                     "reader": f.get("reader") or ("serum1_host" if m.get("reader") == "serum1_host" else "s2"),
                     "features": f["features"], "audio": audio.get(i)})
    fkeys = sorted({k for r in rows for k in r["features"]})
    gf = lambda r, k: r["features"].get(k)            # noqa: E731
    ga = lambda r, k: (r["audio"] or {}).get(k)       # noqa: E731
    out: dict[str, Any] = {"min_n": MIN_N, "basis": "preset_file + render_E1 (naměřeno); role z názvu (hypothesis)",
                           "readers": {}, "audio_roles_agreement": None}
    for reader in ("serum1_host", "s2"):
        rr = [r for r in rows if r["reader"] == reader]
        if not rr:
            continue
        roles = collections.Counter(r["role"] for r in rr)
        packs = collections.Counter(r["source_id"] for r in rr)
        ar = [r for r in rr if r["audio"]]
        out["readers"][reader] = {
            "n": len(rr), "n_with_audio": len(ar),
            "roles": {x: {"params": group_stats([r for r in rr if r["role"] == x], fkeys, gf),
                          "audio": group_stats([r for r in ar if r["role"] == x], AUDIO_KEYS, ga),
                          "contrast": contrast(rr, x, fkeys, gf)} for x in sorted(roles, key=lambda y: -roles[y])},
            "packs": {x: {"author": authors.get(x, ""), "params": group_stats([r for r in rr if r["source_id"] == x], fkeys, gf),
                          "audio": group_stats([r for r in ar if r["source_id"] == x], AUDIO_KEYS, ga)}
                      for x in sorted(packs, key=lambda y: -packs[y])},
        }
    both = [(r["role"], aroles[r["id"]]) for r in rows if r["id"] in aroles and aroles[r["id"]].get("agree") is not None]
    if both:
        out["audio_roles_agreement"] = {"n": len(both), "agree": round(sum(1 for _, a in both if a["agree"]) / len(both), 3),
                                        "note": "shoda rodiny z názvu a rodiny ze zvuku (kNN, estimated); ne přesnost"}
    return out


def _fmt(d: dict[str, float] | None) -> str:
    return "–" if not d else f"{d['median']:g} ({d['p25']:g}–{d['p75']:g})"


def markdown(stats: dict[str, Any]) -> str:
    L = ["# Presety — statistiky", "",
         f"> Generováno `tools/preset_stats.py`. Čísla jsou naměřená ze souborů presetů a z renderu jedné noty E1; **role jsou jen z názvů** (hypothesis). "
         f"Skupina s n < {stats['min_n']} má jen počet. Serum 1 (čtené přes hostovaný plugin) a Serum 2 (čtené ze souboru) se nemíchají.", ""]
    for reader, r in stats["readers"].items():
        L += [f"## {'Serum 1 (.fxp, hostované Serum 1)' if reader == 'serum1_host' else 'Serum 2 (.SerumPreset)'}: {r['n']} presetů, {r['n_with_audio']} s renderem", "",
              "### Role", "", "| Role | n | oscilátory | unison max | filtr zap. | FX | distorze | zvuk: RMS dB | centroid Hz | harmonické % |", "|---|---|---|---|---|---|---|---|---|---|"]
        for role, g in r["roles"].items():
            p, a = g["params"], g["audio"]
            pf, af = p.get("features", {}), a.get("features", {})
            L.append(f"| {role} | {p['n']} | {_fmt(pf.get('osc_on'))} | {_fmt(pf.get('unison_max'))} | {_fmt(pf.get('filters_on'))} | "
                     f"{_fmt(pf.get('fx_count'))} | {_fmt(pf.get('fx_distortion'))} | {_fmt(af.get('rms_db'))} | {_fmt(af.get('centroid_hz'))} | {_fmt(af.get('harmonic_pct'))} |")
        L += ["", "Buňky: medián (kvartily). „–“ = méně než 10 hodnot.", "", "### Čím se role liší od ostatních", ""]
        for role, g in r["roles"].items():
            c = g["contrast"]
            if not c["features"] and "warning" not in c:
                continue
            L.append(f"**{role}** (n {c['n_role']} proti {c['n_rest']})" + (f" — ⚠ {c['warning']}" if "warning" in c else ""))
            for f in c["features"]:
                same = " (stejný medián, liší se rozložení)" if f["median_role"] == f["median_rest"] else ""
                L.append(f"- `{f['key']}`: medián {f['median_role']:g} proti {f['median_rest']:g}{same}, Cliffovo delta {f['delta']:+.2f}")
            L.append("")
        L += ["### Packy", "", "| Pack | autor | n | oscilátory | unison max | FX |", "|---|---|---|---|---|---|"]
        for pid, g in r["packs"].items():
            pf = g["params"].get("features", {})
            L.append(f"| {pid} | {g['author'] or '?'} | {g['params']['n']} | {_fmt(pf.get('osc_on'))} | {_fmt(pf.get('unison_max'))} | {_fmt(pf.get('fx_count'))} |")
        L.append("")
    ag = stats.get("audio_roles_agreement")
    if ag:
        L += ["## Shoda název × zvuk", "", f"Rodina z názvu se shoduje s rodinou ze zvuku u {round(100 * ag['agree'])} % presetů (n {ag['n']}). {ag['note']}.", ""]
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--write", action="store_true", help="zapsat data/presets/stats/preset-stats.json")
    p.add_argument("--md", type=Path, help="zapsat Markdown přehled (např. do vaultu)")
    a = p.parse_args(argv)
    st = build()
    for reader, r in st["readers"].items():
        print(f"{reader}: {r['n']} presetů, {r['n_with_audio']} s renderem, {len(r['roles'])} rolí, {len(r['packs'])} packů")
        small = [x for x, g in r["roles"].items() if g["params"]["n"] < MIN_N]
        print("  role s n < 10 (bez čísel):", small or "-")
    if a.write:
        out = PRESETS / "stats"
        out.mkdir(parents=True, exist_ok=True)
        (out / "preset-stats.json").write_text(json.dumps(st, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    if a.md:
        a.md.write_text(markdown(st), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
