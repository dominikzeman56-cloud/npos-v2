#!/usr/bin/env python3
"""analyze_preset.py — přečte Serum 2 `.SerumPreset` a vyrobí návrh `data/presets/<id>.json`.

Formát: XferJson (hlavička + JSON meta) -> Zstd -> CBOR (slovník modulů). Soubor ukládá jen hodnoty,
které se liší od výchozích; chybějící parametr znamená „výchozí“, ne nulu. Hodnoty jsou normalizované
(např. kParamFreq filtru 0–1) a jednotky NEJSOU ověřené proti Serum UI — proto výstup nese
`basis: preset_file` a jednotky se bez A/B ověření nepřepočítávají na Hz/dB.

Co skript dělá:  čte (oscilátory, filtry, FX řetěz, modulační matice, voice, LFO, makra).
Co NEdělá:       neinterpretuje (archetyp a funkce vrstvy zadává člověk), nic nezapisuje do presetu.

Použití:
  python tools/analyze_preset.py PRESET.SerumPreset --source-id letsynthesize-noisia-course --function body
  python tools/analyze_preset.py PRESET.SerumPreset --summary
  python tools/analyze_preset.py PRESET.SerumPreset --out data/presets/muj-preset.json ...

Závislosti: cbor2, zstandard (`pip install cbor2 zstandard`).
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from datetime import date
from pathlib import Path
from typing import Any

MAGIC = b"XferJson\x00"
OSC_KINDS = ("WTOsc", "SampleOsc", "MultiSampleOsc", "GranularOsc", "SpectralOsc")
FUNCTIONS = ("sub", "body", "movement", "noise", "texture", "lead", "pad", "fx", "other")


# ─── čtení souboru ───────────────────────────────────────────────────────────

def decode_preset(blob: bytes) -> tuple[dict[str, Any], dict[str, Any], int]:
    """Vrátí (meta, cbor_dict, format_version). Selže s ValueError na cizím souboru."""
    import cbor2
    import zstandard

    if not blob.startswith(MAGIC):
        raise ValueError(f"není XferJson (magic {blob[:12]!r})")
    pos = len(MAGIC)
    meta_len = struct.unpack_from("<Q", blob, pos)[0]
    pos += 8
    meta = json.loads(blob[pos:pos + meta_len])
    pos += meta_len
    raw_size = struct.unpack_from("<I", blob, pos)[0]
    pos += 4
    fmt = struct.unpack_from("<I", blob, pos)[0]
    pos += 4
    raw = zstandard.ZstdDecompressor().decompress(blob[pos:], max_output_size=max(raw_size, 1) * 2)
    if len(raw) != raw_size:
        raise ValueError(f"nesedí velikost po dekompresi: {len(raw)} != {raw_size}")
    return meta, cbor2.loads(raw), fmt


def _params(module: Any) -> dict[str, Any]:
    """plainParams modulu, nebo {} (Serum občas ukládá řetězec 'default')."""
    if not isinstance(module, dict):
        return {}
    pp = module.get("plainParams")
    return dict(pp) if isinstance(pp, dict) else {}


def _round(v: Any) -> Any:
    return round(v, 4) if isinstance(v, float) else v


def _round_params(pp: dict[str, Any]) -> dict[str, Any]:
    return {k: _round(v) for k, v in sorted(pp.items())}


# ─── jednotlivé části presetu ────────────────────────────────────────────────

def read_oscillators(cb: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for i in range(5):
        osc = cb.get(f"Oscillator{i}")
        if not isinstance(osc, dict):
            continue
        entry: dict[str, Any] = {"slot": i, "params": _round_params(_params(osc))}
        for kind in OSC_KINDS:
            sub = osc.get(f"{kind}{i}")
            if not isinstance(sub, dict):
                continue
            has_content = bool(_params(sub)) or any(k != "plainParams" and sub[k] not in ({}, [], None) for k in sub)
            if not has_content:
                continue
            entry["kind"] = kind
            entry["kind_params"] = _round_params(_params(sub))
            if sub.get("relativePathToWT"):
                entry["wavetable"] = sub["relativePathToWT"]
            if sub.get("tableDisplayName"):
                entry["table_name"] = sub["tableDisplayName"]
        if entry["params"] or "kind" in entry:
            pp = entry["params"]
            # Odvozeno z defaultů (ověřeno na 103 presetech Letsynthesize): slot 0 je zapnutý a v souboru
            # se objeví jen kParamEnable 0.0; sloty 1–4 jsou vypnuté a objeví se jen 1.0. Unison default = 1 hlas.
            entry["enabled"] = bool(pp.get("kParamEnable", 1.0 if i == 0 else 0.0))
            entry["unison_voices"] = int(pp.get("kParamUnison", 1))
            out.append(entry)
    return out


def read_filters(cb: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for i in range(2):
        pp = _params(cb.get(f"VoiceFilter{i}"))
        if pp:
            out.append({"slot": i, "params": _round_params(pp)})
    return out


def read_fx(cb: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    rack = cb.get("FXRack0")
    items = rack.get("FX", []) if isinstance(rack, dict) else []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        name = next((k for k in item if k.startswith("FX") and isinstance(item[k], dict)), None)
        entry: dict[str, Any] = {"index": idx, "type_id": item.get("type"), "module": name or "?"}
        if name:
            entry["params"] = _round_params(_params(item[name]))
        mix = {k: _round(v) for k, v in item.items() if k.startswith("kUIParam") and isinstance(v, (int, float))}
        if mix:
            entry["mix"] = mix
        chains = [item[k] for k in ("chain1", "chain2", "chain3") if isinstance(item.get(k), list) and item[k]]
        if chains:
            entry["sub_chains"] = [len(c) for c in chains]
        out.append(entry)
    return out


def source_name(source_id: int) -> str:
    """Jen rozsahy, které jsou doložené: LFO (ověřeno na presetu s vlastní LFO křivkou), Env, Macro.
    Ostatní ID se NEhádají."""
    if 2 <= source_id <= 5:
        return f"Env {source_id - 1}"
    if 6 <= source_id <= 15:
        return f"LFO {source_id - 5}"
    if 25 <= source_id <= 32:
        return f"Macro {source_id - 24}"
    return f"source_{source_id} (nezmapováno)"


def read_modulation(cb: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    slots = sorted((k for k in cb if re.fullmatch(r"ModSlot\d+", k)), key=lambda s: int(s[7:]))
    for key in slots:
        s = cb[key]
        if not isinstance(s, dict) or not s.get("destModuleTypeString"):
            continue
        src = s.get("source") or [None]
        sid = src[0] if isinstance(src, (list, tuple)) and src else None
        out.append({
            "slot": int(key[7:]),
            "source_id": sid,
            "source": source_name(sid) if isinstance(sid, int) else "?",
            "dest_module": s.get("destModuleTypeString"),
            "dest_module_id": s.get("destModuleID"),
            "dest_param": s.get("destModuleParamName"),
            "amount": _round(_params(s).get("kParamAmount")),
            # zbytek parametrů slotu (bipolár, bypass, vyhlazení, křivky) — bez interpretace
            "extra": {k: v for k, v in _round_params(_params(s)).items()
                      if k != "kParamAmount" and not isinstance(v, (dict, list, bytes))},
            "has_curve": any(k in _params(s) for k in ("kParamMainCurveData", "kParamAuxCurveData")),
        })
    return out


def read_lfos(cb: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for key in sorted((k for k in cb if re.fullmatch(r"LFO\d+", k)), key=lambda s: int(s[3:])):
        lfo = cb[key]
        if not isinstance(lfo, dict):
            continue
        pp = _params(lfo)
        curve = lfo.get("curveData") if isinstance(lfo.get("curveData"), dict) else {}
        name = lfo.get("curveDisplayName")
        path = lfo.get("pathData") if isinstance(lfo.get("pathData"), dict) else {}
        if pp or curve.get("numPoints") or path.get("numPoints") or (name and name != "Custom"):
            e: dict[str, Any] = {"index": int(key[3:]), "params": _round_params(pp)}
            if name:
                e["shape"] = name
            if curve.get("numPoints"):
                e["curve_points"] = curve["numPoints"]
            c = _curve(curve)
            if c:
                e["curve"] = c
            p = _curve(path)
            if p:
                e["path"] = dict(p, open=path.get("isOpen"), name=lfo.get("pathDisplayName"))
            out.append(e)
    return out


def _curve(cd: dict[str, Any]) -> dict[str, Any] | None:
    """Body křivky LFO/dráhy: x, y (0–1) a `c` = zakřivení segmentu k tomuto bodu (0.5 = rovně).
    Pozice bodů jsou ze souboru; mapování `c` na tvar křivky je odhad (neověřeno proti Serum UI).
    `numPoints` je počet segmentů, bodů je o jeden víc."""
    xs, ys = cd.get("xVals"), cd.get("yVals")
    if not (isinstance(xs, list) and isinstance(ys, list) and xs and len(xs) == len(ys)):
        return None
    out: dict[str, Any] = {"x": [_round(v) for v in xs], "y": [_round(v) for v in ys]}
    cv = cd.get("curveVals")
    if isinstance(cv, list):
        out["c"] = [_round(v) for v in cv]
    if cd.get("loopbackPointNum") is not None:
        out["loopback"] = cd["loopbackPointNum"]
    return out


def read_envs(cb: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for key in sorted((k for k in cb if re.fullmatch(r"Env\d+", k)), key=lambda s: int(s[3:])):
        pp = _params(cb[key])
        if pp:
            out.append({"index": int(key[3:]), "params": _round_params(pp)})
    return out


def read_routing(cb: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for key in sorted((k for k in cb if re.fullmatch(r"RoutingSlot\d+", k)), key=lambda s: int(s[11:])):
        pp = _params(cb[key])
        if pp:
            out.append({"slot": int(key[11:]), "params": _round_params(pp)})
    return out


def read_macros(cb: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for key in sorted((k for k in cb if re.fullmatch(r"Macro\d+", k)), key=lambda s: int(s[5:])):
        m = cb[key]
        pp = _params(m)
        name = m.get("displayName") if isinstance(m, dict) else None
        if pp or name:
            out.append({"index": int(key[5:]), "name": name, "params": _round_params(pp)})
    return out


def read_voice(cb: dict[str, Any]) -> dict[str, Any]:
    return _round_params(_params(cb.get("Global0")))


# ─── sestavení výstupu ───────────────────────────────────────────────────────

def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "preset"


def fx_label(e: dict[str, Any]) -> str:
    name = e["module"].replace("FX", "", 1)
    mode = e.get("params", {}).get("kParamMode") or e.get("params", {}).get("kParamType")
    return f"{name} ({mode})" if isinstance(mode, str) else name


def mod_label(m: dict[str, Any]) -> str:
    param = (m["dest_param"] or "").replace("kParam", "")
    return f"{m['source']} → {m['dest_module']}{m['dest_module_id']} {param} {m['amount']}"


def analyze(path: Path, *, source_id: str, archetype: str = "unclassified", function: str = "other",
            preset_id: str | None = None) -> dict[str, Any]:
    meta, cb, fmt = decode_preset(path.read_bytes())
    name = meta.get("presetName") or path.stem
    osc = read_oscillators(cb)
    fx = read_fx(cb)
    mods = read_modulation(cb)
    return {
        "id": preset_id or slugify(f"{source_id}-{name}"),
        "name": name,
        "synth": f"{meta.get('product', 'Serum')} {meta.get('productVersion', '')}".strip(),
        "source_id": source_id,
        "archetype": archetype,
        "function": function,
        "basis": "preset_file",
        "confidence": "measured",
        "modulation": "; ".join(mod_label(m) for m in mods) if mods else "matice je prázdná",
        "fx_chain": [fx_label(e) for e in fx],
        "tags": list(meta.get("tags", [])),
        "reading": {
            "note": ("Hodnoty přečtené ze souboru. Chybějící parametr = výchozí hodnota Serum. Hodnoty jsou "
                     "normalizované a jednotky nejsou ověřené proti UI. Interpretace (archetyp, funkce, proč) "
                     "je ruční doplněk."),
            "file": path.name,
            "read_on": date.today().isoformat(),
            "format_version": fmt,
            "preset_hash": meta.get("hash"),
            "author": meta.get("presetAuthor") or None,
            "oscillators": osc,
            "voice_filters": read_filters(cb),
            "fx": fx,
            "modulation": mods,
            "lfos": read_lfos(cb),
            "envs": read_envs(cb),
            "routing": read_routing(cb),
            "macros": read_macros(cb),
            "voice": read_voice(cb),
            "voice_panel": _round_params(_params(cb.get("VoicePanel0"))),
            "arp": _round_params(_params(cb.get("Arp0"))),
        },
    }


def summary(a: dict[str, Any]) -> str:
    r = a["reading"]
    lines = [f"{a['name']}  [{a['synth']}]  tagy: {', '.join(a['tags']) or '-'}"]
    for o in r["oscillators"]:
        wt = o.get("table_name") or o.get("wavetable") or ""
        state = "on" if o["enabled"] else "off"
        lines.append(f"  osc{o['slot']} [{state}, unison {o['unison_voices']}] {o.get('kind', '?')} {wt}  "
                     f"{o['params']}  {o.get('kind_params', '')}")
    for f in r["voice_filters"]:
        lines.append(f"  filtr{f['slot']}  {f['params']}")
    for e in r["fx"]:
        lines.append(f"  fx[{e['index']}] {e['module']}  {e.get('params', {})}  {e.get('mix', '')}")
    for m in r["modulation"]:
        lines.append(f"  mod: {mod_label(m)}")
    if r["voice"]:
        lines.append(f"  voice: {r['voice']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="Přečte Serum 2 .SerumPreset do návrhu preset-analysis JSON.")
    ap.add_argument("preset", type=Path)
    ap.add_argument("--source-id", default=None, help="id ze knowledge/sources.jsonl (povinné pro JSON výstup)")
    ap.add_argument("--archetype", default="unclassified")
    ap.add_argument("--function", default="other", choices=FUNCTIONS)
    ap.add_argument("--id", dest="preset_id", default=None)
    ap.add_argument("--out", type=Path, default=None, help="zapíše JSON sem (jinak stdout)")
    ap.add_argument("--summary", action="store_true", help="lidsky čitelný výpis místo JSON")
    args = ap.parse_args(argv)

    if not args.summary and not args.source_id:
        ap.error("--source-id je povinné (žádný preset bez ověřeného zdroje); pro pouhý náhled použij --summary")
    try:
        a = analyze(args.preset, source_id=args.source_id or "unknown", archetype=args.archetype,
                    function=args.function, preset_id=args.preset_id)
    except (ValueError, OSError, struct.error) as e:
        print(f"chyba: {args.preset.name}: {e}", file=sys.stderr)
        return 1
    if args.summary:
        print(summary(a))
        return 0
    text = json.dumps(a, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8", newline="\n")
        print(f"zapsáno {args.out}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
