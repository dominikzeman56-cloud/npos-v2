#!/usr/bin/env python3
"""rebuild_preset_indexes.py — hromadně přeindexuje a spočítá feature vektory všech packů presetů.

Zdrojová složka `_sources/presets/<source_id>/` vzniká přes `tools/collect_local_sources.py`. Pro každý pack:
  - spočítá kompaktní index (`tools/index_presets.py`) a porovná ho s committed `data/presets/index/<source_id>.jsonl`,
  - spočítá feature vektor každého presetu (jen odvozená čísla, viz `features()`) a porovná ho s committed
    `data/presets/features/<source_id>.jsonl`,
  - s `--write` přepíše index i vektory a plné dumpy uloží do `data/presets/_local/` (mimo git).

Vektor záměrně nenese názvy wavetablů, přepisy modulací ani hodnoty parametrů (placené packy,
`redistribution: none`); jsou v něm počty, příznaky a pár normalizovaných hodnot pro generátor presetů.

Bez `--write` nic nezapisuje a vrací kód 1, pokud se nějaký index liší (hodí se jako kontrola po změně heuristik).

Použití:
  py -3.12 tools/rebuild_preset_indexes.py              # jen porovná
  py -3.12 tools/rebuild_preset_indexes.py --write      # přepíše indexy a dumpy
  py -3.12 tools/rebuild_preset_indexes.py --only letsynthesize-preset-files
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import index_presets as ip  # noqa: E402

# složky plných dumpů mimo git (zpětná kompatibilita s dřívějšími názvy)
DUMP_DIR = {"letsynthesize-preset-files": "letsynthesize"}
COMPARE = ("id", "name", "group", "function", "role", "archetype", "confidence", "cues", "fx_chain")


FX_KINDS = {"FXDistortion": "distortion", "FXFilter": "filter", "FXComp": "comp", "FXEQ": "eq", "FXReverb": "reverb", "FXDelay": "delay",
            "FXChorus": "chorus", "FXHyperD": "hyper", "FXPhaser": "phaser", "FXFlanger": "flanger", "FXBode": "bode", "FXConv": "conv",
            "FXUtils": "utils", "FXSplit": "split"}


def _num(v) -> float | None:
    return round(float(v), 4) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def features(reading: dict) -> dict:
    """Feature vektor z `reading` (výstup analyze_preset.py): jen čísla a příznaky, žádné názvy ani přepisy."""
    osc = [o for o in reading.get("oscillators", []) if o.get("slot", 9) <= 2]
    on = [o for o in osc if o.get("enabled")]
    byslot = {o["slot"]: o for o in reading.get("oscillators", [])}
    mods = reading.get("modulation", [])
    src = lambda prefix: sum(1 for m in mods if str(m.get("source", "")).startswith(prefix))  # noqa: E731
    dst = lambda prefix: sum(1 for m in mods if str(m.get("dest_module", "")).startswith(prefix))  # noqa: E731
    fx = reading.get("fx", [])
    filters = [f for f in reading.get("voice_filters", []) if f.get("params", {}).get("kParamEnable", 1) != 0]
    f0 = (filters[0].get("params", {}) if filters else {})
    lfos = reading.get("lfos", [])
    v = {
        "osc_on": len(on),
        "unison_max": max([o.get("unison_voices", 1) for o in on] or [0]),
        "unison_sum": sum(o.get("unison_voices", 1) for o in on),
        "detune_max": max([_num(o.get("params", {}).get("kParamDetune")) or 0 for o in on] or [0]),
        "warp_slots": sum(1 for o in on if o.get("kind_params", {}).get("kParamWarpMenu")) + sum(1 for o in on if o.get("kind_params", {}).get("kParamWarpMenu2")),
        "noise_on": int(bool(byslot.get(3, {}).get("enabled"))),
        "sub_on": int(bool(byslot.get(4, {}).get("enabled"))),
        "filters_on": len(filters),
        "filter_freq": _num(f0.get("kParamFreq")),
        "filter_reso": _num(f0.get("kParamReso")),
        "filter_drive": _num(f0.get("kParamDrive")),
        "fx_count": len(fx),
        "mod_slots": len(mods),
        "mod_lfo": src("LFO"), "mod_env": src("Env"), "mod_macro": src("Macro"),
        "mod_to_osc": dst("WTOsc") + dst("Oscillator"), "mod_to_filter": dst("VoiceFilter") + dst("FXFilter"),
        "lfo_curves": sum(1 for l in lfos if l.get("curve")),
        "lfo_points": sum(len(l["curve"]["x"]) for l in lfos if l.get("curve")),
        "env_count": len(reading.get("envs", [])),
        "macro_count": len(reading.get("macros", [])),
        "mono": int(reading.get("voice", {}).get("kParamMonoToggle") == 1 or reading.get("voice", {}).get("kParamPolyCount") == 1),  # same rule as index_presets.cues()
    }
    for name in FX_KINDS.values():
        v[f"fx_{name}"] = 0
    for e in fx:
        v[f"fx_{FX_KINDS.get(e.get('module'), 'other')}"] = v.get(f"fx_{FX_KINDS.get(e.get('module'), 'other')}", 0) + 1
    return v


def feature_rows(rows: list[dict], dump_dir: Path) -> list[dict]:
    out = []
    for r in rows:
        f = dump_dir / f"{r['id']}.json"
        if not f.exists():
            continue
        reading = json.loads(f.read_text(encoding="utf-8")).get("reading", {})
        out.append({"id": r["id"], "source_id": r["source_id"], "function": r["function"], "role": r.get("role", "other"), "archetype": r["archetype"],
                    "confidence": "hypothesis", "basis": "preset_file", "features": features(reading)})
    return out


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def diff(old: list[dict], new: list[dict]) -> list[str]:
    o = {r["id"]: r for r in old}
    n = {r["id"]: r for r in new}
    out = [f"chybí v novém: {i}" for i in o.keys() - n.keys()] + [f"nové: {i}" for i in n.keys() - o.keys()]
    for i in o.keys() & n.keys():
        bad = [k for k in COMPARE if o[i].get(k) != n[i].get(k)]
        if bad:
            out.append(f"{i}: liší se {', '.join(bad)}")
    return sorted(out)


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap_ = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap_.add_argument("--root", type=Path, default=REPO / "_sources" / "presets", help="složka s podsložkami <source_id>")
    ap_.add_argument("--write", action="store_true", help="přepsat indexy a dumpy")
    ap_.add_argument("--only", action="append", default=[], help="jen tyhle source_id (lze opakovat)")
    a = ap_.parse_args(argv)

    if not a.root.is_dir():
        print(f"složka {a.root} neexistuje (spusť tools/collect_local_sources.py)", file=sys.stderr)
        return 2
    packs = sorted(p for p in a.root.iterdir() if p.is_dir() and (not a.only or p.name in a.only))
    if not packs:
        print("žádné packy", file=sys.stderr)
        return 2

    changed = failed = 0
    import tempfile
    for pack in packs:
        sid = pack.name
        out = REPO / "data" / "presets" / "index" / f"{sid}.jsonl"
        fout = REPO / "data" / "presets" / "features" / f"{sid}.jsonl"
        with tempfile.TemporaryDirectory() as tmp:
            dump = REPO / "data" / "presets" / "_local" / DUMP_DIR.get(sid, sid) if a.write else Path(tmp)
            rows, bad = ip.index([pack], sid, dump)
            order = {r['id']: i for i, r in enumerate(load(out))}  # keep the committed order, new presets go last
            rows.sort(key=lambda r: order.get(r['id'], len(order)))
            frows = feature_rows(rows, dump)
        d = diff(load(out), rows)
        fd = [f"vektor {i}" for i, (o, n) in enumerate(zip(load(fout), frows)) if o != n] + ([f"počet vektorů {len(load(fout))} → {len(frows)}"] if len(load(fout)) != len(frows) else [])
        status = "beze změny" if not d and not fd else f"{len(d)} rozdílů v indexu, {len(fd)} ve vektorech"
        print(f"{sid:<32} {len(rows):>4} presetů  {status}" + (f"  ({len(bad)} chyb)" if bad else ""))
        for line in (d + fd)[:5]:
            print("   ", line)
        for b in bad:
            print("    chyba:", b, file=sys.stderr)
        failed += bool(bad)
        changed += bool(d or fd)
        if a.write and (d or fd):  # untouched packs are not rewritten (keeps git diffs and line endings clean)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="\n")
            fout.parent.mkdir(parents=True, exist_ok=True)
            fout.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in frows), encoding="utf-8", newline="\n")
    return 1 if failed or (changed and not a.write) else 0


if __name__ == "__main__":
    sys.exit(main())
