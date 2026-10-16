#!/usr/bin/env python3
"""preset_seed.py — startovní bod pro nový zvuk: reálný Serum 2 preset s několika zmutovanými parametry.

Neskládá zvuk od nuly. Vybere reálný `.SerumPreset` dané role (z `data/presets/index/`, soubory z lokálních packů), zkopíruje ho
celý a změní jen K spojitých parametrů. Routing (kdo moduluje co), FX řetěz a výběr wavetable zůstávají, mění se hodnoty:
amounty modulací, rezonance, rate LFO, hlasitosti oscilátorů…

Pravidla (BLUEPRINT 7.1: povolený offline zápis, ne náhrada sound designu, ne generátor tracků):
  - výstup jen mimo repo nebo do `data/presets/_local/` (gitignored); odvozeno z placených packů, nikdy se nenahrává ani necommituje,
  - metadata: `derived_from`, mutované parametry, `confidence: hypothesis`; poslechem ho potvrdí jen člověk,
  - mutuje se jen to, co už preset obsahuje v `plainParams` a co je spojité: parametr musí mít v korpusu aspoň 8 různých hodnot a
    nesmí být celočíselný (oktávy, počty hlasů), nesmí to být master volume, počet hlasů, oversampling ani tvar křivek obálek,
  - nová hodnota = stará + N(0, spread · šířka), šířka = rozsah p10–p90 korpusu rozšířený o původní hodnotu; výsledek zůstává v tomto
    rozšířeném rozsahu a nemění znaménko ani neklesne pod 10 % původní velikosti (neumlčí oscilátor, neobrátí modulaci),
  - rozsah se bere z presetů stejné role (od 10 kusů); co role nepokrývá, doplní celý korpus,
  - zdrojem semínka je Serum 2; Serum 1 `.fxp` je třeba nejdřív převést v Serum 2.
Použití: py -3.12 tools/preset_seed.py --roots "<složka s .SerumPreset>" --role bass --n 3 --seed 1 --out "<složka User/Generated>"
         [--from-id ID] [--mutate 4] [--spread 0.25] [--check]
         --check vyrenderuje zdroj a mutant (potřebuje lokálně pedalboard a plugin), vypíše změnu deskriptorů a zahodí mutanty,
         které se nezměnily, umlkly, změnily hlasitost o > 6 dB nebo posunuly těžiště spektra > 3×.
Návratový kód: 0 = vzniklo všech --n souborů, 1 = méně, 2 = chyba prostředí.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import random
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import serum_preset_io as sio  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
PRESETS = REPO / "data" / "presets"
LOCAL = PRESETS / "_local"
MIN_DISTINCT = 8      # tolik různých pozorovaných hodnot musí parametr mít, aby šel mutovat (jinak je to volba nebo režim)
NEVER = {"kParamMasterVolume", "kParamPolyCount", "kParamS1Compatibility", "kParamOversampling"}
NEVER_PREFIX = ("kParamCurve",)   # tvary obálek: kdyby se mutovaly, tvořily by třetinu změn a nejméně slyšitelnou
KEEP_FRACTION = 0.1   # mutace nesmí zmenšit velikost nenulového parametru pod 10 % původní hodnoty


def is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and np.isfinite(v)


def range_kind(mod: str) -> str:
    """Druh modulu pro rozsahy: `Oscillator3` a `Oscillator4` jsou Noise a Sub, ne wavetable oscilátory, mají jiné klíče a rozsahy."""
    m = re.fullmatch(r"Oscillator(\d+)", mod)
    if m:
        n = int(m.group(1))
        return "Oscillator" if n < 3 else "OscNoise" if n == 3 else "OscSub"
    return sio.module_kind(mod)


def build_ranges(presets: list[dict[str, Any]]) -> dict[tuple[str, str], tuple[float, float]]:
    """(druh modulu, klíč) → (p10, p90) napříč presety; jen spojité parametry."""
    obs: dict[tuple[str, str], list[float]] = collections.defaultdict(list)
    for cb in presets:
        for mod, k, v in sio.plain_params(cb):
            if is_num(v):
                obs[(range_kind(mod), k)].append(float(v))
    out = {}
    for key, vals in obs.items():
        if key[1] in NEVER or key[1].startswith(NEVER_PREFIX):
            continue
        if len(set(round(x, 6) for x in vals)) < MIN_DISTINCT or all(x == round(x) for x in vals):   # volba, režim, celé číslo
            continue
        lo, hi = np.percentile(vals, [10, 90])
        if hi > lo:
            out[key] = (float(lo), float(hi))
    return out


def build_ranges_by_role(corpus: list[tuple[dict[str, Any], Any, dict[str, Any]]], min_role: int = 10) -> dict[str, dict]:
    """Role → rozsahy jen z presetů té role (jen role s >= min_role presety; menší skupina nemá vypovídací hodnotu)."""
    by: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row, _f, cb in corpus:
        by[row.get("role", "other")].append(cb)
    return {role: build_ranges(cbs) for role, cbs in by.items() if len(cbs) >= min_role}


def ranges_for(role: str, global_ranges: dict, by_role: dict[str, dict]) -> dict:
    """Rozsah role má přednost; parametr, který v roli nemá aspoň MIN_DISTINCT různých hodnot, vezme rozsah z celého korpusu."""
    return {**global_ranges, **by_role.get(role, {})}


def sane(src: dict[str, Any], new: dict[str, Any]) -> tuple[bool, str]:
    """Hrubá brána mutantu proti zdroji (hypothesis, prahy nejsou kalibrované): zvuk neumlkl, hlasitost se nezměnila o víc
    než 6 dB a těžiště spektra se neposunulo víc než 3× nahoru ani dolů."""
    if new.get("silent"):
        return False, "ticho"
    if abs(new["rms_db"] - src["rms_db"]) > 6.0:
        return False, f"hlasitost {new['rms_db'] - src['rms_db']:+.1f} dB"
    a, b = src.get("centroid_hz"), new.get("centroid_hz")
    if a and b and not (1 / 3 <= b / a <= 3):
        return False, f"centroid x{b / a:.1f}"
    return True, ""


def mutate(cb: dict[str, Any], ranges: dict[tuple[str, str], tuple[float, float]], rng: random.Random, k: int = 4,
           spread: float = 0.25) -> list[dict[str, Any]]:
    """Změní nejvýš k parametrů v místě (cb se upraví) a bere kandidáty, dokud nenastane k skutečných změn nebo nedojdou.
    Nová hodnota = stará + N(0, spread · (hi − lo)), kde lo a hi jsou p10 a p90 korpusu rozšířené o původní hodnotu; výsledek
    zůstává v [lo, hi], nemění znaménko a nesmí klesnout pod 10 % původní velikosti."""
    cand = [(m, key, v) for m, key, v in sio.plain_params(cb) if is_num(v) and (range_kind(m), key) in ranges]
    rng.shuffle(cand)
    done: list[dict[str, Any]] = []
    for mod, key, old in cand:
        if len(done) >= k:
            break
        old_f = float(old)
        lo, hi = ranges[(range_kind(mod), key)]
        lo, hi = min(lo, old_f), max(hi, old_f)
        if old_f > 0:
            lo = max(lo, KEEP_FRACTION * old_f)
        elif old_f < 0:
            hi = min(hi, KEEP_FRACTION * old_f)
        if hi <= lo:
            continue
        new = float(np.clip(old_f + rng.gauss(0.0, spread * (hi - lo)), lo, hi))
        if isinstance(old, sio.F32):       # zachovat šířku uloženého čísla (float32), jinak se preset zvětší a liší od Serum
            new = float(np.float32(new))
        if new == old_f:
            continue
        cb[mod]["plainParams"][key] = type(old)(new)
        done.append({"module": mod, "param": key, "old": round(old_f, 6), "new": round(new, 6)})
    return done


def make_one(meta: dict[str, Any], cb: dict[str, Any], derived_from: str, role: str, ranges, rng: random.Random,
             k: int, label: str, spread: float = 0.25) -> tuple[bytes, dict[str, Any]]:
    import copy
    cb2 = copy.deepcopy(cb)
    muts = mutate(cb2, ranges, rng, k, spread)
    m2 = dict(meta)
    m2["presetName"] = label
    m2["presetAuthor"] = "NPOS generated"
    m2["presetDescription"] = f"Odvozeno z '{meta.get('presetName', '?')}' ({meta.get('presetAuthor') or 'autor neuveden'})"
    m2["presetComment"] = f"derived_from {derived_from}; {len(muts)} parametrů zmutováno; hypothesis, neposlechnuto"
    m2["tags"] = list(dict.fromkeys(list(meta.get("tags") or []) + ["Generated"]))
    log = {"name": label, "derived_from": derived_from, "role": role, "mutations": muts, "confidence": "hypothesis"}
    return sio.write_preset(m2, cb2), log


def out_dir_ok(out: Path) -> bool:
    """Mimo repo, nebo pod `data/presets/_local` (gitignored). Cesty UNC a `\\\\?\\` se odmítají: vedou do repa mimo `resolve()`."""
    if str(out).startswith("\\\\") or str(out.resolve()).startswith("\\\\"):
        return False
    out = out.resolve()
    if LOCAL.resolve() in (out, *out.parents):
        return True
    return REPO.resolve() not in (out, *out.parents)


def free_path(out: Path, stem: str) -> Path:
    """Nepřepíše existující soubor: při shodě přidá číslo."""
    p = out / f"{stem}.SerumPreset"
    i = 2
    while p.exists():
        p = out / f"{stem} ({i}).SerumPreset"
        i += 1
    return p


def load_corpus(roots: list[Path], index: list[dict[str, Any]]) -> tuple[list[tuple[dict, Path, dict]], collections.Counter]:
    """Soubory z `roots` spárované s řádky indexu podle (složka, jméno souboru). Nečitelné soubory se spočítají podle chyby."""
    want = {(r.get("group", ""), r["file"]): r for r in index}
    out, skipped = [], collections.Counter()
    for root in roots:
        files = sorted(root.rglob("*.SerumPreset")) if root.is_dir() else [root]
        for f in files:
            parts = f.relative_to(root).parts if root.is_dir() else ()
            group = parts[0] if len(parts) > 1 else (root.parent.name if not root.is_dir() else "")
            row = want.get((group, f.name))
            if row is None:
                continue
            try:
                _meta, cb = sio.read_preset(f)
            except Exception as e:  # noqa: BLE001 - poškozený soubor se přeskočí, ale spočítá
                skipped[type(e).__name__] += 1
                continue
            out.append((row, f, cb))
    return out, skipped


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
    p.add_argument("--spread", type=float, default=0.25, help="síla mutace jako zlomek rozsahu (0,25 jemná, 0,4–0,5 výrazná)")
    p.add_argument("--check", action="store_true", help="vyrenderovat zdroj a mutant a zahodit nepovedené (viz začátek souboru)")
    a = p.parse_args(argv)
    if not (a.role or a.from_id):
        p.error("zadej --role nebo --from-id")
    try:
        import zstandard  # noqa: F401 - bez něj nejde číst ani psát presety; ať to selže nahlas
    except ImportError:
        print("chybí zstandard (pip install zstandard); spusť přes py -3.12", file=sys.stderr)
        return 2
    if not out_dir_ok(a.out):
        print("výstup musí být mimo repo nebo pod data/presets/_local (odvozeno z placených packů)", file=sys.stderr)
        return 2
    index = [json.loads(line) for f in sorted((PRESETS / "index").glob("*.jsonl"))
             for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]
    corpus, skipped = load_corpus(a.roots, index)
    if skipped:
        print(f"nečitelných souborů: {dict(skipped)}", file=sys.stderr)
    if not corpus:
        print("žádný preset z indexu nenalezen v --roots", file=sys.stderr)
        return 1
    ranges = build_ranges([cb for _, _, cb in corpus])
    by_role = build_ranges_by_role(corpus)
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
    src_desc: dict[Path, dict] = {}
    logs = []
    kept = tries = 0
    rejected: collections.Counter = collections.Counter()
    while kept < a.n and tries < a.n * (6 if renderer else 2):
        tries += 1
        row, f, cb = rng.choice(pool)
        meta, _ = sio.read_preset(f)
        tag = hashlib.md5(row["id"].encode("utf-8")).hexdigest()[:6]
        label = f"GEN {row.get('role', 'x')} s{a.seed}-{kept + 1}"
        rg = ranges_for(row.get("role", "other"), ranges, by_role)
        blob, log = make_one(meta, cb, row["id"], row.get("role", "?"), rg, rng, a.mutate, label, a.spread)
        if not log["mutations"]:
            rejected["bez změny"] += 1
            continue
        if renderer is not None:
            import render_preset as rp
            try:
                if f not in src_desc:               # zdroj se renderuje jednou; renderer porovnává s předchozím zvukem, proto ho uvolníme
                    renderer.prev = None
                    src_desc[f] = rp.descriptors(renderer.render(f.read_bytes()), renderer.protocol)
                renderer.prev = None
                d1 = rp.descriptors(renderer.render(blob), renderer.protocol)
            except RuntimeError:                    # plugin stav nepřijal nebo se zvuk neliší od výchozího
                rejected["nezměněn"] += 1
                continue
            d0 = src_desc[f]
            ok, why = sane(d0, d1)
            if not ok:
                rejected[why.split(" ")[0]] += 1
                continue
            log["render_delta"] = {k: round(d1[k] - d0[k], 3) for k in ("rms_db", "centroid_hz", "harmonic_pct", "band_sub_pct", "band_mid_pct")
                                   if isinstance(d0.get(k), (int, float)) and isinstance(d1.get(k), (int, float))}
        path = free_path(a.out, sio.safe_file_stem(f"{label} {tag}"))
        path.write_bytes(blob)
        log["file"] = path.name
        kept += 1
        logs.append(log)
        names = ", ".join(f"{m['module']}.{m['param']}" for m in log["mutations"])
        print(f"{path.name}: z {row['id']}, {len(log['mutations'])} parametrů ({names})"
              + (f", Δ {log['render_delta']}" if "render_delta" in log else ""))
    if logs:
        with (a.out / "generated.jsonl").open("a", encoding="utf-8", newline="\n") as fh:
            fh.writelines(json.dumps(x, ensure_ascii=False) + "\n" for x in logs)
    if rejected:
        print(f"zahozeno {sum(rejected.values())} mutantů: {dict(rejected)}")
    if kept < a.n:
        print(f"vzniklo jen {kept} z {a.n}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
