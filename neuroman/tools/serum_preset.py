"""
serum_preset.py — Serum 2 .SerumPreset format toolkit.

Read, decode, modify, and generate .SerumPreset files.
Format: XferJson → Zstd-CBOR → dict of ~176 modules with plainParams.
"""
from __future__ import annotations

import json
import struct
import zstandard as zstd
from pathlib import Path
from typing import Any

import cbor2

__version__ = "0.3.0"

# ─── XferJson envelope ─────────────────────────────────────────────────

XFERJSON_MAGIC = b"XferJson\x00"
XFERJSON_VERSION = 2


def unwrap_xferjson(blob: bytes, *, expected_version: int | None = 2) -> tuple[dict[str, Any], int, bytes]:
    if not blob.startswith(XFERJSON_MAGIC):
        raise ValueError(f"Bad magic: {blob[:12]!r}")
    pos = len(XFERJSON_MAGIC)
    meta_len = struct.unpack_from("<Q", blob, pos)[0]; pos += 8
    meta: dict = json.loads(blob[pos: pos + meta_len]); pos += meta_len
    uncompressed_size = struct.unpack_from("<I", blob, pos)[0]; pos += 4
    fmt_version = struct.unpack_from("<I", blob, pos)[0]; pos += 4
    if expected_version is not None and fmt_version != expected_version:
        raise ValueError(f"Expected XferJson v{expected_version}, got v{fmt_version}")
    decompressed = zstd.decompress(blob[pos:])
    if len(decompressed) != uncompressed_size:
        raise ValueError(f"Size mismatch: {len(decompressed)} != {uncompressed_size}")
    return meta, fmt_version, decompressed


def wrap_xferjson(meta: dict, cbor_bytes: bytes, *, version: int = 2) -> bytes:
    compressed = zstd.compress(cbor_bytes)
    meta_bytes = json.dumps(meta, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return b"".join([
        XFERJSON_MAGIC,
        struct.pack("<Q", len(meta_bytes)),
        meta_bytes,
        struct.pack("<I", len(cbor_bytes)),
        struct.pack("<I", version),
        compressed,
    ])


# ─── High-level read/write ──────────────────────────────────────────────

_template_path: Path | None = None  # resolved lazily


def _get_template() -> Path:
    global _template_path
    if _template_path is None:
        # Auto-detect: same dir as this file, parent dir, or cwd
        candidates = [
            Path(__file__).parent.parent / "default.SerumPreset",
            Path("neuroman/default.SerumPreset"),
            Path("default.SerumPreset"),
        ]
        for c in candidates:
            if c.exists():
                _template_path = c
                break
        if _template_path is None:
            raise FileNotFoundError(
                "Template default.SerumPreset not found. "
                "Save an init preset from Serum 2 as neuroman/default.SerumPreset"
            )
    return _template_path


def decode_preset(path_or_bytes: str | bytes | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    blob = Path(path_or_bytes).read_bytes() if isinstance(path_or_bytes, (str, Path)) else path_or_bytes
    meta, _, cbor_bytes = unwrap_xferjson(blob)
    return meta, cbor2.loads(cbor_bytes)


def encode_preset(meta: dict, cbor_dict: dict, *, path: str | Path | None = None) -> bytes:
    blob = wrap_xferjson(meta, cbor2.dumps(cbor_dict))
    if path:
        Path(path).write_bytes(blob)
    return blob


# ─── FX Type helpers ────────────────────────────────────────────────────

# Serum 2 FX type IDs reverse-engineered from presets
FX_TYPES = {
    "Distortion": 0,    # FXDistortion — Overdrive, Sin Fold, Soft Clip, Tube
    "Flanger": 1,       # FXFlanger
    "Phaser": 2,        # FXPhaser
    "Chorus": 3,        # FXChorus — incl. High Pass mode
    "Delay": 4,         # FXDelay
    "Compressor": 5,    # FXComp — also Multiband OTT
    "Reverb": 6,        # FXReverb — incl. Vintage
    "EQ": 7,            # FXEQ — 2-band
    "Filter": 8,        # FXFilter — extra filter in FX chain
    "HyperDimension": 9, # FXHyperD — Hyper / Dimension
    "BodeShifter": 10,  # FXBode — frequency shifter
    "Convolver": 11,    # FXConv — convolution reverb
    "Utility": 12,      # FXUtils — width, balance, HPF/LPF
    "Splitter": 13,     # FXSplit — L/H split
    "Splitter3": 14,    # FXSplit3 — L/M/H split
    "SplitterMS": 15,   # FXSplitMS — Mid/Side split
}

FX_MODULE_NAMES = {
    0: "FXDistortion",  1: "FXFlanger",  2: "FXPhaser",  3: "FXChorus",
    4: "FXDelay",       5: "FXComp",     6: "FXReverb",  7: "FXEQ",
    8: "FXFilter",      9: "FXHyperD",   10: "FXBode",   11: "FXConv",
    12: "FXUtils",      13: "FXSplit",   14: "FXSplit3", 15: "FXSplitMS",
}


def make_fx_item(fx_type_id: int, mix: float = 0.0, params: dict | None = None, sub_chain: list | None = None) -> dict:
    """Build an FX list item dict for insertion into FXRack's FX list."""
    mod_name = FX_MODULE_NAMES.get(fx_type_id, f"FX_{fx_type_id}")
    item = {"type": fx_type_id, mod_name: {"plainParams": params or {}}}
    if fx_type_id not in (7, 13, 14, 15):  # EQ, Splitters have no mix
        item["kUIParamMixOrGain"] = mix
    if sub_chain is not None:
        # Splitters have sub-chains (nested FX lists)
        item["chain1"] = sub_chain[0] if len(sub_chain) > 0 else []
        if len(sub_chain) > 1:
            item["chain2"] = sub_chain[1]
        if len(sub_chain) > 2:
            item["chain3"] = sub_chain[2]
        item["kParamModuleCount1"] = float(len(sub_chain[0])) if sub_chain else 0.0
        item["kParamModuleCount2"] = float(len(sub_chain[1])) if len(sub_chain) > 1 else 0.0
    return item


# ─── Preset builder ─────────────────────────────────────────────────────


def load_template() -> tuple[dict[str, Any], dict[str, Any]]:
    return decode_preset(str(_get_template()))


def build_preset(
    *,
    name: str = "Init",
    author: str = "",
    tags: list[str] | None = None,
    params: dict[str, dict[str, Any]] | None = None,
    fx_chain: list[dict] | None = None,
    template_path: str | Path | None = None,
    output_path: str | Path | None = None,
) -> bytes:
    """
    Build a .SerumPreset from template + overrides.

    Args:
        params: {module_name: {param_key: value, ...}}
        fx_chain: list of FX items for FXRack0 (or None to keep template)
    """
    p = template_path or _get_template()
    meta, cb = load_template() if template_path is None else decode_preset(str(template_path))

    meta["presetName"] = name
    meta["presetAuthor"] = author
    if tags is not None:
        meta["tags"] = tags

    if params:
        for mod_name, mod_params in params.items():
            if mod_name not in cb:
                cb[mod_name] = {"plainParams": {}}
            module = cb[mod_name]
            if not isinstance(module, dict):
                cb[mod_name] = {"plainParams": {}}
                module = cb[mod_name]
            pp = module.get("plainParams")
            if not isinstance(pp, dict):
                pp = {}
                module["plainParams"] = pp
            pp.update(mod_params)

    if fx_chain is not None:
        cb["FXRack0"] = {"plainParams": {}, "FX": fx_chain, "displayName": ""}

    cb["presetName"] = name
    if author:
        cb["presetAuthor"] = author

    return encode_preset(meta, cb, path=output_path)


# ─── Skullstep Rave Lead builder ────────────────────────────────────────


def build_skullstep_lead(*, output_path: str | Path | None = None) -> bytes:
    """
    Build the Skullstep Rave Lead preset from the build sheet.

    Sheet: D:\\ObsidianVault\\Hudební produkce\\Build Sheets\\Skullstep_Rave_Lead.md
    """
    # --- Oscillators ---
    osc_params = {
        # OSC A: Saw, -1 oct, Unison 3V, detune -38, Bend +/-
        "Oscillator0": {
            "kParamOctave": -1.0,
            "kParamVolume": 0.0,        # opened via LFO1 envelope
            "kParamUnison": 3.0,
            "kParamDetune": 0.38,       # normalized scale? needs calibration
            "kParamUnisonStereo": 0.0,
        },
        # OSC B: Saw, -1 oct, Unison 3V, detune +38, PWM
        "Oscillator1": {
            "kParamOctave": -1.0,
            "kParamVolume": 0.0,
            "kParamUnison": 3.0,
            "kParamDetune": 0.38,       # opposite polarity handled by Serum?
            "kParamUnisonStereo": 0.0,
        },
        # OSC C (Sub): Basic OPL, -2 oct
        "Oscillator2": {
            "kParamOctave": -2.0,
            "kParamVolume": 0.0,
            "kParamEnable": 1.0,
        },
    }

    # WTOsc waveform params (inside oscillators via sub-modules)
    # Set warp modes on the WTOsc sub-modules
    # We can't easily create sub-modules from scratch, so these will need
    # to be set on top of the template that already has them.

    # --- LFO1 as envelope (rapid exponential decay) ---
    lfo_params = {
        "LFO0": {
            "kParamMode": "Envelope",
            "kParamDefaultMode": 0.0,
        },
        "LFO1": {
            "kParamMode": "Envelope",
            "kParamDefaultMode": 0.0,
        },
    }

    # --- Matrix: LFO1 → Main Tuning +13% ---
    # Uses ModSlot0 for modulation matrix
    mod_matrix_params = {
        "ModSlot0": {
            "kParamAmount": 13.0,       # +13%
            # TODO: source=??, destination=?? need discovery
        },
    }

    # --- Filter ---
    filter_params = {
        "VoiceFilter0": {
            "kParamType": "LB12",       # LBH 12dB — best guess from found types
            "kParamFreq": 0.05,         # ~40Hz (normalized, needs calibration)
            "kParamReso": 4.0,          # ~4%
            "kParamDrive": 5.0,
            "kParamEnable": 1.0,
        },
    }

    all_params = {}
    for d in [osc_params, lfo_params, mod_matrix_params, filter_params]:
        all_params.update(d)

    # --- FX Chain (per build sheet order!) ---
    fx_chain = [
        # 1. Chorus — High Pass mode
        make_fx_item(3, mix=30.0, params={
            "kParamFiltMode": 1.0,      # High Pass mode
            "kParamFilt": 20000.0,      # wide
            "kParamDepth": 10.0,
            "kParamRate": 0.5,
            "kParamWet": 25.0,
            "kParamEnable": 1.0,
        }),
        # 2. Hyper / Dimension — just Dimension
        make_fx_item(9, mix=4.0, params={
            "kParamDimEWet": 4.0,
            "kParamDimESize": 4.0,
            "kParamWet": 4.0,
            "kParamEnable": 1.0,
        }),
        # 3. Distortion — Overdrive, Stack 3x
        make_fx_item(0, mix=0.0, params={
            "kParamMode": "kSoftClip",
            "kParamNumStages": 3.0,
            "kParamDrive": 80.0,
            "kParamWet": 100.0,
            "kParamEnable": 1.0,
        }),
        # 4. EQ — cut low mids, boost highs
        make_fx_item(7, params={
            "kParamFreq1": 300.0,
            "kParamGain1": -3.0,
            "kParamReso1": 48.0,
            "kParamFreq2": 8000.0,
            "kParamGain2": 2.0,
            "kParamReso2": 48.0,
            "kParamEnable": 1.0,
        }),
        # 5. Splitter L/H — ~800Hz-1kHz
        make_fx_item(13, params={
            "kParamFreq": 900.0,
            "kParamEnable": 1.0,
            "kParamModuleCount1": 1.0,   # dry/low branch
            "kParamModuleCount2": 2.0,   # high branch: Delay + Reverb
        }, sub_chain=[
            [],  # chain1: dry / low (empty = passthrough)
            [   # chain2: high → Delay + Reverb
                make_fx_item(4, mix=50.0, params={
                    "kParamBeatSync": 1.0,
                    "kParamTimeL": 0.25,  # 1/16 note
                    "kParamTimeR": 0.25,
                    "kParamFeedback": 20.0,
                    "kParamMode": 1.0,     # ping-pong
                    "kParamWet": 40.0,
                    "kParamEnable": 1.0,
                }),
                make_fx_item(6, mix=30.0, params={
                    "kParamType": "kVintage",
                    "kParamSize": 50.0,
                    "kParamWet": 30.0,
                    "kParamFeedback": 50.0,
                    "kParamWidth": 50.0,
                    "kParamEnable": 1.0,
                }),
            ],
        ]),
        # 6. Compressor — Multiband OTT style
        make_fx_item(5, mix=80.0, params={
            "kParamMultiband": 1.0,
            "kParamAttack": 5.0,
            "kParamRelease": 100.0,
            "kParamRatio": 4.0,
            "kParamThresh": 0.3,
            "kParamMakeup": 3.0,
            "kParamWet": 100.0,
            "kParamEnable": 1.0,
        }),
    ]

    return build_preset(
        name="Skullstep Rave Lead",
        author="NeuroMan",
        tags=["Lead", "Rave", "Skullstep", "Neurofunk", "DnB"],
        params=all_params,
        fx_chain=fx_chain,
        output_path=output_path,
    )


# ─── Known kParam reference ─────────────────────────────────────────────

KNOWN_PARAMS = {
    "kParamOctave": "Octave (float, -3 to 3)",
    "kParamVolume": "Volume / level (0.0-1.0)",
    "kParamDetune": "Detune amount (0.0-1.0 normalized, or cents)",
    "kParamPitch": "Semitone offset (float, 0-12)",
    "kParamEnable": "On/off toggle (0.0/1.0)",
    "kParamUnison": "Unison voice count (1.0-16.0)",
    "kParamUnisonStereo": "Unison stereo spread",
    "kParamMode": "LFO mode: 'Envelope' or 'Free'",
    "kParamDefaultMode": "LFO default mode flag",
    "kParamRate": "LFO rate / speed",
    "kParamFreq": "Filter cutoff / frequency",
    "kParamReso": "Filter resonance",
    "kParamType": "Filter type or FX subtype",
    "kParamWarpMenu": "WTOsc warp mode: kPD_OSC, kPWM, kBendPosNeg, kSync...",
    "kParamTablePos": "Wavetable position",
    "kParamShape": "Sub oscillator shape: kSaw, kSquare, kTriangle, kRoundRect",
    "kParamGlobalTuning": "Master tune (Hz)",
    "kParamNumStages": "Distortion stages / stack count",
    "kParamDrive": "Distortion / filter drive",
    "kParamMultiband": "Compressor multiband mode (0/1)",
    "kParamWet": "FX wet mix",
    "kParamFiltMode": "Chorus filter mode (1=HP)",
    "kParamDimEWet": "Dimension wet mix",
    "kParamDimESize": "Dimension size",
}

# ─── Introspection ──────────────────────────────────────────────────────


def dump_tree(cbor_dict: dict, *, show_params: bool = True, modules: list[str] | None = None) -> str:
    lines: list[str] = []
    keys = sorted(k for k in cbor_dict if isinstance(cbor_dict[k], dict) and (modules is None or k in modules))
    for key in keys:
        val = cbor_dict[key]
        lines.append(f"{key}:")
        pp = val.get("plainParams")
        extras = {k: v for k, v in val.items() if k != "plainParams"}

        for ek, ev in extras.items():
            if isinstance(ev, list):
                lines.append(f"  {ek}: [{len(ev)} items]")
                for i, item in enumerate(ev):
                    if isinstance(item, dict):
                        tid = item.get("type", "?")
                        mod_key = next((k for k in item if k.startswith("FX") and k != "FX"), None)
                        lines.append(f"    [{i}] type={tid} {mod_key}")
                        mod = item.get(mod_key, {}) if mod_key else {}
                        sub_pp = mod.get("plainParams", {}) if isinstance(mod, dict) else {}
                        if isinstance(sub_pp, dict):
                            for sk, sv in sub_pp.items():
                                svs = round(sv, 4) if isinstance(sv, float) else sv
                                lines.append(f"      {sk}: {svs}")
            elif isinstance(ev, dict):
                sub_pp = ev.get("plainParams", {})
                if isinstance(sub_pp, dict) and sub_pp:
                    lines.append(f"  {ek}: ({len(sub_pp)} params)")
                else:
                    lines.append(f"  {ek}: dict")
            elif isinstance(ev, str):
                lines.append(f"  {ek}: {ev!r}")
            else:
                lines.append(f"  {ek}: {type(ev).__name__}")

        if isinstance(pp, dict) and show_params and pp:
            for pk in sorted(pp):
                lines.append(f"  {pk}: {pp[pk]!r}")
    return "\n".join(lines) if lines else "(empty)"


def diff_params(before: dict, after: dict, *, threshold: float = 1e-9) -> dict[str, dict[str, tuple[Any, Any]]]:
    changed: dict = {}
    for mn in set(before) | set(after):
        vb, va = before.get(mn, {}), after.get(mn, {})
        if not isinstance(vb, dict) or not isinstance(va, dict):
            continue
        ppb = vb.get("plainParams", {})
        ppa = va.get("plainParams", {})
        if not isinstance(ppb, dict): ppb = {}
        if not isinstance(ppa, dict): ppa = {}
        mc: dict = {}
        for key in set(ppb) | set(ppa):
            bv, av = ppb.get(key), ppa.get(key)
            if bv is None and av is not None:
                mc[key] = (None, av)
            elif av is None and bv is not None:
                mc[key] = (bv, None)
            elif isinstance(bv, (int, float)) and isinstance(av, (int, float)):
                if abs(bv - av) > threshold:
                    mc[key] = (bv, av)
            elif bv != av:
                mc[key] = (bv, av)
        if mc:
            changed[mn] = mc
    return changed


# ─── CLI ───────────────────────────────────────────────────────────────


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Serum 2 .SerumPreset toolkit")
    ap.add_argument("file", nargs="?", help="Path to .SerumPreset file")
    ap.add_argument("--tree", action="store_true", help="Show module tree")
    ap.add_argument("--params", action="store_true", help="Show all plainParams in tree")
    ap.add_argument("--modules", help="Filter tree to specific modules (comma-sep)")
    ap.add_argument("--info", action="store_true", help="Show metadata + module list")
    ap.add_argument("--diff", metavar="OTHER", help="Diff params against another preset")
    ap.add_argument("--list-params", action="store_true", help="List known kParam names")
    ap.add_argument("--build", metavar="TAG", help="Build preset: skullstep")
    ap.add_argument("--output", help="Output file path for --build")

    args = ap.parse_args()

    if args.list_params:
        print("Known Serum 2 kParam* names (reverse-engineered):")
        for k, desc in sorted(KNOWN_PARAMS.items()):
            print(f"  {k:30s}  {desc}")
        print("\nFX type IDs:")
        for name, tid in sorted(FX_TYPES.items(), key=lambda x: x[1]):
            print(f"  {tid:2d}: {name}")
        return

    if args.build:
        if args.build == "skullstep":
            out = Path(args.output or "Skullstep_Rave_Lead.SerumPreset")
            build_skullstep_lead(output_path=str(out))
            print(f"Built {out}")
        else:
            print(f"Unknown build target: {args.build}")
        return

    if not args.file:
        ap.print_help()
        return

    meta, cb = decode_preset(args.file)

    if args.info:
        print("── Metadata ──")
        for k, v in meta.items():
            print(f"  {k}: {v!r}")
        mods = sorted(k for k in cb if isinstance(cb[k], dict) and "plainParams" in cb[k])
        print(f"\n── Modules with params ({len(mods)}) ──")
        for i in range(0, len(mods), 4):
            row = mods[i: i + 4]
            print("  " + "  ".join(f"{m:28s}" for m in row))
        return

    if args.tree:
        mod_filter = args.modules.split(",") if args.modules else None
        print("── Module Tree ──")
        print(dump_tree(cb, show_params=args.params, modules=mod_filter))
        return

    if args.diff:
        _, other = decode_preset(args.diff)
        changes = diff_params(cb, other)
        if not changes:
            print("No parameter differences found.")
        else:
            for mod in sorted(changes):
                print(f"\n── {mod} ──")
                for pn, (bv, av) in sorted(changes[mod].items()):
                    print(f"  {pn}: {bv!r} → {av!r}")
        return

    print(f"Name: {meta.get('presetName', '?')}")
    print(f"Author: {meta.get('presetAuthor', '?')}")
    print(f"Product: {meta.get('product', '?')} v{meta.get('productVersion', '?')}")
    print(f"Modules: {len(cb)}")
    active = sum(1 for v in cb.values() if isinstance(v, dict) and isinstance(v.get("plainParams", {}), dict) and v["plainParams"])
    print(f"Active param modules: {active}")
    print(f"Tags: {meta.get('tags', [])}")


if __name__ == "__main__":
    main()
