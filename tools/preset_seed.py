#!/usr/bin/env python3
"""preset_seed.py — startovní bod pro nový zvuk: reálný Serum 2 preset s několika zmutovanými parametry.

Neskládá zvuk od nuly. Vybere reálný `.SerumPreset` dané role (z `data/presets/index/`, soubory z lokálních packů), zkopíruje ho
celý a změní jen K spojitých parametrů. Routing (kdo moduluje co), FX řetěz a výběr wavetable zůstávají, mění se hodnoty:
amounty modulací, rezonance, rate LFO, hlasitosti oscilátorů…

Pravidla (BLUEPRINT 7.1: povolený offline zápis, ne náhrada sound designu, ne generátor tracků):
  - výstup jen mimo repo nebo do `data/presets/_local/` (gitignored); odvozeno z placených packů, nikdy se nenahrává ani necommituje,
  - metadata: `derived_from`, mutované parametry, `confidence: hypothesis`; poslechem ho potvrdí jen člověk,
  - mutuje se jen to, co už preset obsahuje v `plainParams` a co je spojité: parametr musí mít v korpusu aspoň 8 různých hodnot a
    nesmí být (z 98 % a víc) celočíselný ani volba (oktávy, počty hlasů, výška), nesmí to být master volume, počet hlasů, oversampling ani tvar křivek obálek,
  - nuly (vypnuto) a modulace, které míří na výšku, se nemění;
  - nová hodnota = stará + N(0, spread · šířka), šířka = rozsah p10–p90 korpusu rozšířený o původní hodnotu; výsledek zůstává v tomto
    rozšířeném rozsahu a nemění znaménko ani neklesne pod 10 % původní velikosti (neumlčí oscilátor, neobrátí modulaci),
  - rozsah se bere z presetů stejné role (od 10 kusů); co role nepokrývá, doplní celý korpus,
  - zdrojem semínka je Serum 2; Serum 1 `.fxp` je třeba nejdřív převést v Serum 2.
Použití: py -3.12 tools/preset_seed.py --roots "<složka s .SerumPreset>" --role bass --n 3 --seed 1 --out "<složka User/Generated>"
         [--from-id ID] [--mutate 4] [--spread 0.25] [--check]
         --check vyrenderuje zdroj a mutant (potřebuje lokálně pedalboard a plugin), vypíše změnu deskriptorů a zahodí mutanty,
         které umlkly, změnily hlasitost o > 6 dB nebo posunuly těžiště spektra > 3×. Nezměněný mutant tím nepoznáš (render není bitově
         opakovatelný kvůli náhodné fázi); mutant bez jediné změny se zahodí už před renderem.
Prostředí: NPOS_SERUM_PRESETS (složky s presety, oddělené středníkem na Windows) nahradí --roots, NPOS_SERUM_OUT nahradí --out.
Preset, který v indexu není (cizí složka, vlastní presety), dostane roli z názvu souboru stejnými pravidly jako index_presets.py.
--list-roles vypíše JSON {role: počet} a skončí, --json vypíše na konci JSON se seznamem souborů.
--export-seeds DIR --seed-plan bass=12,lead=10,stab=8 zkopíruje z --roots malou sadu semínek (rozmanitou, bez obřích souborů) do DIR;
generování nad 20–30 presety je rychlé a sadu si každý poskládá ze svých vlastních presetů. DIR musí splnit stejné pravidlo jako --out.
Návratový kód: 0 = vzniklo všech --n souborů, 1 = méně, 2 = chyba prostředí.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
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
DISCRETE = {"kParamOctave", "kParamUnison", "kParamPitch", "kParamPitchRatio", "kParamCoarsePit", "kParamKeyZoneMin", "kParamKeyZoneMax"}   # celočíselné volby
PITCH_DEST = {"kParamCoarsePit", "kParamMasterTuning", "kParamFine", "kParamOctave", "kParamPitch", "kParamShift"}   # modulace výšky: změna by přeladila preset
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
        if key[1] in NEVER or key[1] in DISCRETE or key[1].startswith(NEVER_PREFIX):
            continue
        whole = sum(1 for x in vals if x == round(x)) / len(vals)
        if len(set(round(x, 6) for x in vals)) < MIN_DISTINCT or whole >= 0.98:   # volba, režim, celé číslo (pár zatoulaných desetinných hodnot to nezmění)
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
    def pitch_slot(m: str) -> bool:      # amount modulace, která míří na výšku, by preset přeladila
        return m.startswith("ModSlot") and isinstance(cb.get(m), dict) and cb[m].get("destModuleParamName") in PITCH_DEST

    cand = [(m, key, v) for m, key, v in sio.plain_params(cb)
            if is_num(v) and float(v) != 0.0 and not pitch_slot(m) and (range_kind(m), key) in ranges]   # nula = vypnuto, nezapínáme
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
        if new == old_f or not math.isfinite(new):
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
    m2.pop("presetAuthorLocked", None)
    for k in ("presetName", "presetAuthor", "presetDescription", "tags"):   # tělo musí říkat totéž co hlavička, jinak se po uložení v Serum vrátí původní autor
        if k in cb2:
            cb2[k] = m2[k]
    if "presetAuthorLocked" in cb2:
        cb2["presetAuthorLocked"] = False
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


def scan_rows(roots: list[Path], index: list[dict[str, Any]]) -> list[tuple[dict, Path]]:
    """Soubory z `roots` s řádkem indexu podle (složka, jméno souboru), jinak s rolí z názvu. Nic se nedekóduje (rychlé)."""
    want = {(r.get("group", ""), r["file"]): r for r in index}
    out: list[tuple[dict, Path]] = []
    for root in roots:
        files = sorted(root.rglob("*.SerumPreset")) if root.is_dir() else [root]
        for f in files:
            parts = f.relative_to(root).parts if root.is_dir() else ()
            group = parts[0] if len(parts) > 1 else (root.parent.name if not root.is_dir() else "")
            row = want.get((group, f.name))
            if row is None:                    # cizí složka nebo vlastní preset: role z názvu, id z cesty
                try:
                    from index_presets import role_of
                    role = role_of(f.stem)
                except Exception:  # noqa: BLE001 - bez pravidel jen neznámá role
                    role = "other"
                row = {"id": "local-" + hashlib.md5(str(f.resolve()).encode("utf-8")).hexdigest()[:12], "role": role, "name": f.stem}
            out.append((row, f))
    seen: set[Path] = set()                # překrývající se --roots by jinak započítaly preset dvakrát
    uniq = []
    for row, f in out:
        r = f.resolve()
        if r not in seen:
            seen.add(r)
            uniq.append((row, f))
    return uniq


MAX_DECODE = 200   # nejvýš tolik presetů role a tolik ostatních se dekóduje (~30 ms na soubor), ať velká složka netrvá minuty


def load_corpus(roots: list[Path], index: list[dict[str, Any]], want_role: str | None = None, from_id: str | None = None,
                cap: int = MAX_DECODE) -> tuple[list[tuple[dict, Path, dict]], collections.Counter]:
    """Dekóduje presety hledané role (nebo semínko) a vzorek ostatních pro rozsahy. Výběr je deterministický (podle otisku cesty).
    Nečitelné soubory se spočítají podle chyby."""
    items = scan_rows(roots, index)
    key = lambda it: hashlib.md5(str(it[1]).encode("utf-8")).hexdigest()  # noqa: E731
    mine = sorted([it for it in items if (from_id and it[0]["id"] == from_id) or (want_role and it[0].get("role") == want_role)], key=key)[:cap]
    ids = {it[0]["id"] for it in mine}
    chosen = mine + sorted([it for it in items if it[0]["id"] not in ids], key=key)[:cap]
    out, skipped = [], collections.Counter()
    for row, f in chosen:
        try:
            _meta, cb = sio.read_preset(f)
        except Exception as e:  # noqa: BLE001 - poškozený soubor se přeskočí, ale spočítá
            skipped[type(e).__name__] += 1
            continue
        out.append((row, f, cb))
    return out, skipped


SEED_SKIP = re.compile(r"^GEN |\bkit\b", re.I)   # vlastní výstupy generátoru a bicí kity (role z názvu je u nich špatně)
MAX_SEED_BYTES = 3_000_000   # obří soubory nesou vložené wavetably, nejsou to dobrá semínka a zdržují


def pick_seeds(items: list[tuple[dict, Path]], plan: dict[str, int]) -> list[tuple[dict, Path]]:
    """Pro každou roli z plánu vybere až N presetů střídavě z různých složek (rozmanitost), deterministicky podle otisku cesty."""
    out: list[tuple[dict, Path]] = []
    for role, n in plan.items():
        by_group: dict[str, list[tuple[dict, Path]]] = collections.defaultdict(list)
        for row, f in items:
            if row.get("role") == role and f.stat().st_size <= MAX_SEED_BYTES and not SEED_SKIP.search(f.stem):
                by_group[f.parent.name].append((row, f))
        for g in by_group.values():
            g.sort(key=lambda it: hashlib.md5(str(it[1]).encode("utf-8")).hexdigest())
        picked: list[tuple[dict, Path]] = []
        while len(picked) < n and any(by_group.values()):
            for g in sorted(by_group):
                if by_group[g] and len(picked) < n:
                    picked.append(by_group[g].pop(0))
        out.extend(picked)
    return out


def parse_plan(text: str) -> dict[str, int]:
    plan = {}
    for part in text.split(","):
        role, _, n = part.partition("=")
        if not role.strip() or not n.strip().isdigit() or not 1 <= int(n) <= 100:
            raise ValueError(f"neplatný plán '{part}' (čekám role=počet, např. bass=12,lead=10)")
        plan[role.strip()] = int(n)
    return plan


def _spread(text: str) -> float:
    v = float(text)
    if not math.isfinite(v) or not 0 < v <= 1:
        raise argparse.ArgumentTypeError("spread musí být číslo v (0, 1]")
    return v


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--roots", type=Path, nargs="+", help="složky s Serum 2 presety (výchozí z NPOS_SERUM_PRESETS)")
    p.add_argument("--role", help="role z názvu (bass, reese, lead, pad, ...)")
    p.add_argument("--from-id", help="konkrétní semínko podle id v indexu")
    p.add_argument("--n", type=int, default=3)
    p.add_argument("--mutate", type=int, default=4, help="kolik parametrů změnit")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--out", type=Path, default=Path(os.environ["NPOS_SERUM_OUT"]) if os.environ.get("NPOS_SERUM_OUT") else LOCAL / "generated")
    p.add_argument("--list-roles", action="store_true", help="vypsat JSON {role: počet} a skončit")
    p.add_argument("--export-seeds", type=Path, help="zkopírovat malou sadu semínek do této složky a skončit")
    p.add_argument("--seed-plan", default="bass=12,lead=10,stab=8", help="kolik semínek které role (role=počet, oddělené čárkou)")
    p.add_argument("--json", action="store_true", help="na konci vypsat JSON se seznamem vzniklých souborů")
    p.add_argument("--spread", type=_spread, default=0.25, help="síla mutace jako zlomek rozsahu (0,25 jemná, 0,4–0,5 výrazná)")
    p.add_argument("--check", action="store_true", help="vyrenderovat zdroj a mutant a zahodit nepovedené (viz začátek souboru)")
    a = p.parse_args(argv)
    if not a.roots and os.environ.get("NPOS_SERUM_PRESETS"):
        a.roots = [Path(x) for x in os.environ["NPOS_SERUM_PRESETS"].split(os.pathsep) if x]
    if not a.roots:
        p.error("zadej --roots nebo nastav NPOS_SERUM_PRESETS")
    if not (a.role or a.from_id or a.list_roles or a.export_seeds):
        p.error("zadej --role, --from-id, --list-roles nebo --export-seeds")
    try:
        import zstandard  # noqa: F401 - bez něj nejde číst ani psát presety; ať to selže nahlas
    except ImportError:
        print("chybí zstandard (pip install zstandard); spusť přes py -3.12", file=sys.stderr)
        return 2
    if not a.list_roles and not out_dir_ok(a.out):
        print("výstup musí být mimo repo nebo pod data/presets/_local (odvozeno z placených packů)", file=sys.stderr)
        return 2
    index = [json.loads(line) for f in sorted((PRESETS / "index").glob("*.jsonl"))
             for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]
    if a.export_seeds:
        import shutil
        if not out_dir_ok(a.export_seeds):
            print("sada semínek musí být mimo repo nebo pod data/presets/_local (kopie placených packů)", file=sys.stderr)
            return 2
        try:
            plan = parse_plan(a.seed_plan)
        except ValueError as e:
            print(e, file=sys.stderr)
            return 2
        picked = pick_seeds(scan_rows(a.roots, index), plan)
        a.export_seeds.mkdir(parents=True, exist_ok=True)
        listing = []
        for row, f in picked:
            dst = free_path(a.export_seeds, sio.safe_file_stem(f.stem))
            shutil.copyfile(f, dst)
            listing.append({"file": dst.name, "role": row.get("role"), "from_folder": f.parent.name})
        got = collections.Counter(x["role"] for x in listing)
        print(f"zkopírováno {len(listing)} semínek do {a.export_seeds}: {dict(got)}")
        for r, n in plan.items():
            if got[r] < n:
                print(f"  role {r}: jen {got[r]} z {n} (v --roots není víc vhodných)", file=sys.stderr)
        return 0 if listing else 1
    if a.list_roles:
        rows = scan_rows(a.roots, index)
        print(json.dumps(dict(collections.Counter(r.get("role", "other") for r, _ in rows)), ensure_ascii=False))
        return 0
    corpus, skipped = load_corpus(a.roots, index, a.role, a.from_id)
    if skipped:
        print(f"nečitelných souborů: {dict(skipped)}", file=sys.stderr)
    if not corpus:
        print("žádný preset nenalezen v --roots", file=sys.stderr)
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
    if a.json:
        print(json.dumps({"files": [{"file": x["file"], "derived_from": x["derived_from"], "mutations": len(x["mutations"])} for x in logs],
                          "rejected": dict(rejected), "requested": a.n}, ensure_ascii=False))
    if kept < a.n:
        print(f"vzniklo jen {kept} z {a.n}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
