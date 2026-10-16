#!/usr/bin/env python3
"""preset_seed.py — startovní bod pro nový zvuk: reálný Serum 2 preset s několika zmutovanými parametry.

Neskládá zvuk od nuly. Vybere reálný `.SerumPreset` dané role (z `data/presets/index/`, soubory z lokálních packů), zkopíruje ho
celý (mod matice, FX, LFO) a změní jen K spojitých parametrů, každý v rozsahu pozorovaném napříč korpusem (p10–p90) a poblíž
původní hodnoty. Tím zůstává zvuk uvnitř toho, co existuje, a mění se barva, ne konstrukce.

Pravidla (BLUEPRINT: povolený offline zápis, ne náhrada sound designu, ne generátor tracků):
  - výstup jen mimo repo nebo do `data/presets/_local/` (gitignored); odvozeno z placených packů, nikdy se nenahrává ani necommituje,
  - metadata: `derived_from`, mutované parametry, `confidence: hypothesis`; poslechem ho potvrdí jen člověk,
  - mutuje se jen to, co už preset obsahuje v `plainParams`; parametry s méně než 8 pozorovanými hodnotami (volby, režimy) se nemění,
  - zdrojem semínka je Serum 2; Serum 1 `.fxp` je třeba nejdřív převést v Serum 2.
Použití: py -3.12 tools/preset_seed.py --roots "<složka s .SerumPreset>" --role bass --n 3 --seed 1 --out "<složka User/Generated>"
         [--from-id ID] [--mutate 4] [--check]   (--check vyrenderuje zdroj a mutant a vypíše změnu deskriptorů; potřebuje pedalboard)
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import serum_preset_io as sio  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
PRESETS = REPO / "data" / "presets"
LOCAL = PRESETS / "_local"
MIN_OBS = 8          # tolik pozorovaných hodnot musí parametr mít, aby šel mutovat (jinak je to volba/režim)
MIN_DISTINCT = 8
NEVER = {"kParamMasterVolume", "kParamPolyCount", "kParamS1Compatibility", "kParamOversampling"}


def is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and np.isfinite(v)


def build_ranges(presets: list[dict[str, Any]]) -> dict[tuple[str, str], tuple[float, float]]:
    """(druh modulu, klíč) → (p10, p90) napříč presety; jen spojité parametry (>= MIN_DISTINCT různých hodnot)."""
    obs: dict[tuple[str, str], list[float]] = collections.defaultdict(list)
    for cb in presets:
        for mod, k, v in sio.plain_params(cb):
            if is_num(v):
                obs[(sio.module_kind(mod), k)].append(float(v))
    out = {}
    for key, vals in obs.items():
        if len(vals) >= MIN_OBS and len(set(round(x, 6) for x in vals)) >= MIN_DISTINCT and key[1] not in NEVER:
            lo, hi = np.percentile(vals, [10, 90])
            if hi > lo:
                out[key] = (float(lo), float(hi))
    return out


def mutate(cb: dict[str, Any], ranges: dict[tuple[str, str], tuple[float, float]], rng: random.Random, k: int = 4,
           spread: float = 0.25) -> list[dict[str, Any]]:
    """Změní nejvýš k parametrů v místě (cb se upraví). Nová hodnota = stará + N(0, spread·(p90−p10)), omezená na rozsah
    korpusu rozšířený o původní hodnotu (existující preset nikdy nevyhodíme z jeho vlastního rozsahu)."""
    cand = [(m, key, v) for m, key, v in sio.plain_params(cb)
            if is_num(v) and (sio.module_kind(m), key) in ranges]
    rng.shuffle(cand)
    done = []
    for mod, key, old in cand[:k]:
        lo, hi = ranges[(sio.module_kind(mod), key)]
        lo, hi = min(lo, float(old)), max(hi, float(old))
        new = float(np.clip(old + rng.gauss(0.0, spread * (hi - lo)), lo, hi))
        if isinstance(old, sio.F32):       # zachovat šířku uloženého čísla (float32), jinak se preset zvětší a liší od Serum
            new = float(np.float32(new))
        if new == float(old):
            continue
        cb[mod]["plainParams"][key] = type(old)(new)
        done.append({"module": mod, "param": key, "old": round(float(old), 6), "new": round(new, 6)})
    return done


def make_one(meta: dict[str, Any], cb: dict[str, Any], derived_from: str, role: str, ranges, rng: random.Random,
             k: int, label: str) -> tuple[bytes, dict[str, Any]]:
    import copy
    cb2 = copy.deepcopy(cb)
    muts = mutate(cb2, ranges, rng, k)
    m2 = dict(meta)
    m2["presetName"] = label
    m2["presetAuthor"] = "NPOS generated"
    m2["presetDescription"] = ""
    m2["presetComment"] = f"derived_from {derived_from}; {len(muts)} parametrů zmutováno; hypothesis, neposlechnuto"
    m2["tags"] = list(dict.fromkeys(list(meta.get("tags") or []) + ["Generated"]))
    log = {"name": label, "derived_from": derived_from, "role": role, "mutations": muts, "confidence": "hypothesis"}
    return sio.write_preset(m2, cb2), log


def out_dir_ok(out: Path) -> bool:
    """Mimo repo, nebo pod `data/presets/_local` (gitignored)."""
    out = out.resolve()
    if LOCAL.resolve() in (out, *out.parents):
        return True
    return REPO.resolve() not in (out, *out.parents)


def load_corpus(roots: list[Path], index: list[dict[str, Any]]) -> list[tuple[dict, Path, dict]]:
    import render_preset as rp
    pairs = rp.match_rows("s2", rp.collect("s2", roots), index)
    out = []
    for f, row in pairs:
        try:
            _meta, cb = sio.read_preset(f)
        except Exception:  # noqa: BLE001 - poškozený soubor se přeskočí
            continue
        out.append((row, f, cb))
    return out


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--roots", type=Path, nargs="+", required=True, help="složky s Serum 2 presety (stejné jako při indexaci)")
    p.add_argument("--role", help="role z názvu (bass, reese, lead, pad, ...)")
    p.add_argument("--from-id", help="konkrétní semínko podle id v indexu")
    p.add_argument("--n", type=int, default=3)
    p.add_argument("--mutate", type=int, default=4, help="kolik parametrů změnit")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--out", type=Path, default=LOCAL / "generated")
    p.add_argument("--check", action="store_true", help="vyrenderovat zdroj a mutant (pedalboard) a vypsat změnu deskriptorů")
    a = p.parse_args(argv)
    if not (a.role or a.from_id):
        p.error("zadej --role nebo --from-id")
    if not out_dir_ok(a.out):
        print("výstup musí být mimo repo nebo pod data/presets/_local (odvozeno z placených packů)", file=sys.stderr)
        return 2
    index = [json.loads(line) for f in sorted((PRESETS / "index").glob("*.jsonl"))
             for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]
    corpus = load_corpus(a.roots, index)
    if not corpus:
        print("žádný preset z indexu nenalezen v --roots", file=sys.stderr)
        return 1
    ranges = build_ranges([cb for _, _, cb in corpus])
    pool = [c for c in corpus if (c[0]["id"] == a.from_id if a.from_id else c[0].get("role") == a.role)]
    if not pool:
        print(f"žádné semínko pro {a.from_id or a.role}", file=sys.stderr)
        return 1
    rng = random.Random(a.seed)
    a.out.mkdir(parents=True, exist_ok=True)
    renderer = None
    if a.check:
        import render_preset as rp
        renderer = rp.Renderer("s2")
    logs = []
    for i in range(a.n):
        row, f, cb = rng.choice(pool)
        meta, _ = sio.read_preset(f)
        label = f"GEN {row.get('role', 'x')} s{a.seed}-{i + 1}"
        blob, log = make_one(meta, cb, row["id"], row.get("role", "?"), ranges, rng, a.mutate, label)
        (a.out / f"{sio.safe_file_stem(label)}.SerumPreset").write_bytes(blob)
        if renderer is not None:
            import render_preset as rp
            d0 = rp.descriptors(renderer.render(f.read_bytes()), renderer.protocol)
            d1 = rp.descriptors(renderer.render(blob), renderer.protocol)
            log["render_delta"] = {k: round(d1[k] - d0[k], 3) for k in ("rms_db", "centroid_hz", "harmonic_pct", "band_sub_pct", "band_mid_pct")
                                   if isinstance(d0.get(k), (int, float)) and isinstance(d1.get(k), (int, float))}
        logs.append(log)
        print(f"{label}: z {row['id']}, {len(log['mutations'])} parametrů" + (f", Δ {log['render_delta']}" if "render_delta" in log else ""))
    with (a.out / "generated.jsonl").open("a", encoding="utf-8", newline="\n") as fh:
        fh.writelines(json.dumps(x, ensure_ascii=False) + "\n" for x in logs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
