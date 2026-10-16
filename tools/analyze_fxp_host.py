#!/usr/bin/env python3
"""analyze_fxp_host.py — přečte Serum 1 `.fxp` přes hostované Serum 1 VST3 (`pedalboard`) a vyrobí kompaktní index + feature vektory.

Proč: `.fxp` je neveřejný binární stav (`analyze_fxp.py` čte jen kontejner). Samotné Serum 1 ale ten stav umí načíst a
vystavuje ~350 hostovských parametrů (osc, filtr, obálky, FX, matice: amounty). Skript stav z `.fxp` vloží do pluginu
(VST3 state = JUCE XML, `IComponent` = JUCE base64 zlib-chunku, tj. totéž, co je v `.fxp`) a čte hodnoty tak, jak je Serum 1 zobrazuje.

Co je z hostu naměřené (`reader: serum1_host`, `basis: preset_file`): oscilátory A/B (zapnuto, unison, detune z displeje, oktáva,
Fine, hlasitost, typ warpu), Noise a Sub zapnuté, filtr (zapnut, cutoff normalizovaný 0–1, reso a drive v procentech 0–100 jako ve
feature vektorech Serum 2), zapnuté FX (bez pořadí), počet obsazených slotů mod matice (amount ≠ 0). Cutoff a všechny sdílené
feature se shodují s převodem v Serum 2 (ověřeno na páru TSP_REDPILL_Bass_lazer, viz test).

Co z hostu NENÍ k dispozici a zůstává `null`/neznámé: zdroj a cíl modulace (nejsou hostovské parametry; leží ve stavu a čekají na
kalibraci z převedených presetů), pořadí FX, LFO/obálky jako křivky, mono/legato, jména wavetablů a maker. `function`, `role`
a `archetype` jsou návrh z jména (`index_presets.NAME_RULES` / `role_of`) a z naměřených stop, vždy `hypothesis`.

Plné parametry (raw + text) a odkazy na wavetably jdou jen do `--dump-dir` (`data/presets/_local/…`, mimo git); do repa jen kompaktní řádky.

Bezpečnost zápisu: výstup se píše atomicky (dočasný soubor + `os.replace`); při `--match-index` se nepřepíše index, pokud by byl
menší než původní (použij `--allow-partial`), a prázdný výstup se nezapíše. Návratový kód je nenulový, když je cokoli v chybách.

Závislost (volitelná, kvůli ní je modul bez ní importovatelný a testy se přeskočí): `pip install pedalboard` + nainstalované Serum 1 VST3.

Použití:
  py -3.12 tools/analyze_fxp_host.py "…/S1 Presets/BO" --source-id s1-burr-oak \\
      --out-index data/presets/fxp/s1-burr-oak.jsonl --out-features data/presets/features/s1-burr-oak.jsonl \\
      --dump-dir data/presets/_local/s1-burr-oak-host
  # stejná sada souborů a id jako dosavadní index (podle sha256 z `container`), jen s naměřenými stopami:
  py -3.12 tools/analyze_fxp_host.py "…/S1 Presets/BO" --source-id s1-burr-oak --match-index data/presets/fxp/s1-burr-oak.jsonl ...
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import struct
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
import analyze_fxp as fx  # noqa: E402
import analyze_preset as ap  # noqa: E402
import index_presets as ip  # noqa: E402
import rebuild_preset_indexes as rpi  # noqa: E402

DEFAULT_PLUGIN = r"C:\Program Files\Common Files\VST3\Serum.vst3\Contents\x86_64-win\Serum.vst3"
STATE_MAGIC = b"VC2!"
READER = "serum1_host"
EXPECTED_STATES = {172736, 34016, 33872, 28232}  # velikosti stavu .fxp, které načtení do hostu ověřeně zvládlo

# ─── JUCE base64 (MemoryBlock::toBase64Encoding): "<bajty>." + 6bitové znaky od LSB ────────────────────────────

_ALPH = ".ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+"
_IDX = {c: i for i, c in enumerate(_ALPH)}


def juce_b64_encode(data: bytes) -> str:
    out = []
    padded = data + b"\0" * (-len(data) % 3)
    for i in range(0, len(padded), 3):
        g = int.from_bytes(padded[i:i + 3], "little")
        out += (_ALPH[g & 63], _ALPH[(g >> 6) & 63], _ALPH[(g >> 12) & 63], _ALPH[(g >> 18) & 63])
    return f"{len(data)}." + "".join(out)[:-(-len(data) * 8 // 6)]


def juce_b64_decode(text: str) -> bytes:
    size_s, sep, body = text.strip().partition(".")
    if not sep or not (size_s.isascii() and size_s.isdigit()):
        raise ValueError("není JUCE base64 (chybí '<velikost>.')")
    n = int(size_s)
    body += _ALPH[0] * (-len(body) % 4)
    out = bytearray()
    try:
        for i in range(0, len(body), 4):
            g = _IDX[body[i]] | (_IDX[body[i + 1]] << 6) | (_IDX[body[i + 2]] << 12) | (_IDX[body[i + 3]] << 18)
            out += g.to_bytes(3, "little")
    except KeyError as e:
        raise ValueError(f"znak {e.args[0]!r} není v JUCE base64") from e
    if len(out) < n:
        raise ValueError("JUCE base64 je kratší než udaná velikost")
    return bytes(out[:n])


_COMPONENT = re.compile(r"<IComponent>(.*?)</IComponent>", re.S)


def state_from_fxp(base_state: bytes, fxp: bytes) -> bytes:
    """VST3 state hostovaného Serum 1 s `IComponent` nahrazeným zlib-chunkem z `.fxp` (nic nezapisuje na disk)."""
    if base_state[:4] != STATE_MAGIC:
        raise ValueError("neznámý formát VST3 state (čekám 'VC2!')")
    xml = base_state[8:].rstrip(b"\0").decode("utf-8")
    m = _COMPONENT.search(xml)
    if not m:
        raise ValueError("ve VST3 state chybí <IComponent>")
    if len(fxp) < 60 or fxp[:4] != b"CcnK" or fxp[8:12] != b"FPCh":
        raise ValueError("není VST2 .fxp typu FPCh")
    size = struct.unpack_from(">I", fxp, 56)[0]
    chunk = fxp[60:60 + size]
    if len(chunk) != size:
        raise ValueError("chunk je useknutý")
    body = (xml[:m.start(1)] + juce_b64_encode(chunk) + xml[m.end(1):]).encode("utf-8") + b"\0"
    return base_state[:4] + struct.pack("<I", len(body)) + body


# ─── host ──────────────────────────────────────────────────────────────────────────────────────────────────────

class S1Host:
    """Jedna instance Serum 1 VST3 v procesu. Start ~9 s, načtení presetu ~0,1 s (výjimečně 2–3 s)."""

    def __init__(self, plugin: str | None = None):
        try:
            from pedalboard import load_plugin
        except ImportError as e:  # pragma: no cover - závisí na prostředí
            raise RuntimeError("chybí pedalboard (pip install pedalboard)") from e
        path = plugin or os.environ.get("SERUM1_VST3") or DEFAULT_PLUGIN
        if not Path(path).exists():
            raise RuntimeError(f"Serum 1 VST3 nenalezeno: {path} (nastav --plugin nebo SERUM1_VST3)")
        self.plugin = load_plugin(path)
        self.params = self.plugin.parameters          # vytvářet jen jednou (8 s), jinak je to O(n²)
        self.keys = [k for k in self.params if not k.startswith("cc")]   # cc* = 2048 MIDI CC, nezajímavé
        self.base = self.plugin.raw_state
        self.init = self.read()

    def load_fxp(self, fxp: bytes) -> None:
        """Načte `.fxp`. Nejdřív vrátí plugin do výchozího stavu, jinak by nepřijatý stav nechal předchozí preset (tiše)."""
        self.plugin.raw_state = self.base
        self.plugin.raw_state = state_from_fxp(self.base, fxp)
        if self.read() == self.init:
            raise RuntimeError("plugin stav z .fxp nepřijal (parametry jsou výchozí)")

    def read(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for k in self.keys:
            p = self.params[k]
            try:
                raw: float | None = round(float(p.raw_value), 5)
            except AttributeError:   # macro_1..4 nemají raw_value
                raw = None
            try:
                text = str(p.string_value)
            except AttributeError:
                text = ""
            out[k] = {"raw": raw, "text": text}
        return out


# ─── měření (čisté funkce, testovatelné bez pluginu) ───────────────────────────────────────────────────────────

# (klíč enable, název jako ve Serum 2 indexu, kind pro features, klíč s typem v textu)
FX_HOST = [("hyp_enable", "HyperD", "hyper", None), ("dist_enable", "Distortion", "distortion", "dist_mode"),
           ("flg_enable", "Flanger", "flanger", None), ("phs_enable", "Phaser", "phaser", None),
           ("cho_enable", "Chorus", "chorus", None), ("dly_enable", "Delay", "delay", None),
           ("comp_enable", "Comp", "comp", "cmpmbnd"), ("rev_enable", "Reverb", "reverb", None),
           ("eq_enable", "EQ", "eq", None), ("fx_fil_enable", "Filter", "filter", "fx_fil_type")]
# FM/AM/RM/PM z jiného zdroje: text menu Serum 1 → klíč zapnutí zdrojového oscilátoru
CROSS_WARP = re.compile(r"^(?:FM|AM|RM|PM)\s*\((from A|from B|Noise|Sub)\)$", re.I)
CROSS_SOURCE = {"from a": "osc_a_on", "from b": "osc_b_on", "noise": "osc_n_on", "sub": "osc_s_on"}


def _raw(p: dict, k: str) -> float | None:
    v = p.get(k, {}).get("raw")
    return float(v) if isinstance(v, (int, float)) else None


def _norm(p: dict, k: str) -> float | None:
    """Normalizovaná hodnota 0–1 zaokrouhlená jako ve feature vektorech Serum 2 (4 desetinná místa)."""
    v = _raw(p, k)
    return None if v is None else round(v, 4)


def _pct(p: dict, k: str) -> float | None:
    """Hodnota 0–100 (reso, drive ve feature vektorech Serum 2 jsou v procentech)."""
    v = _raw(p, k)
    return None if v is None else round(v * 100, 4)


def _on(p: dict, k: str) -> bool:
    v = _raw(p, k)
    return v is not None and v >= 0.5


def _text(p: dict, k: str) -> str:
    return str(p.get(k, {}).get("text", "")).strip()


def _num_text(p: dict, k: str) -> float | None:
    try:
        v = float(_text(p, k).replace("+", ""))
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def _osc(p: dict, x: str) -> dict[str, Any] | None:
    """Oscilátor A/B jako hodnoty tak, jak je ukazuje Serum 1; `None`, když je vypnutý."""
    if not _on(p, f"osc_{x}_on"):
        return None
    u = _raw(p, f"{x}_unison")
    vol = _raw(p, f"{x}_vol")
    shown = _num_text(p, f"{x}_unison")
    return {"unison": int(shown) if shown else 1 + round((u or 0) * 15),
            "detune": _num_text(p, f"{x}_unidet") or 0.0, "oct": _num_text(p, f"{x}_octave_oct") or 0.0,
            "fine": _num_text(p, f"{x}_fine_cents") or 0.0, "audible": bool(vol and vol > 0),
            "warp": _text(p, f"warposc{x}") or "Off"}


def _slot_active(p: dict, k: str) -> bool:
    """Slot mod matice je obsazený, když Serum 1 ukazuje amount ≠ 0 (bez textu: raw ≠ 0,5)."""
    shown = _num_text(p, k)
    if shown is not None:
        return shown != 0
    r = _raw(p, k)
    return r is not None and r != 0.5


def measure(p: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """(cues, features, fx_chain) z hostovských parametrů {klíč: {raw, text}}. Co hostem zjistit nejde, je `None`."""
    osc = [o for o in (_osc(p, "a"), _osc(p, "b")) if o]
    noise, sub = _on(p, "osc_n_on"), _on(p, "osc_s_on")
    modes = sorted({o["warp"] for o in osc if o["warp"].lower() != "off"})
    cross = sorted({w for w in modes if (m := CROSS_WARP.match(w)) and _on(p, CROSS_SOURCE[m.group(1).lower()])})
    fine_spread = any(a["oct"] == b["oct"] and a["fine"] != b["fine"] and a["audible"] and b["audible"]
                      for i, a in enumerate(osc) for b in osc[i + 1:])
    mod_slots = sum(1 for k in p if re.fullmatch(r"mod_?\d+_amt", k) and _slot_active(p, k))
    fx_on = [(label, kind, detail) for key, label, kind, detail in FX_HOST if _on(p, key)]
    # pořadí FX v Serum 1 není hostovský parametr: seznam je abecedně, jeho pořadí nic neznamená
    fx_chain = sorted(f"{label} ({_text(p, detail)})" if detail and _text(p, detail) else label for label, _, detail in fx_on)
    f_on = _on(p, "filter_on")
    cues = {
        "active_osc": len(osc), "noise": noise, "sub": sub,
        "max_unison": max((o["unison"] for o in osc), default=1),
        # jen FM/AM/RM/PM z jiného zdroje, který je zapnutý (text menu Serum 1, ne enum Serum 2); ostatní warpy jsou v warp_modes
        "cross_warp": cross,
        "warp_modes": modes,                       # jen Serum 1: všechny typy warpu zapnutých oscilátorů
        "silent_mod_osc": None,                    # hlasitost 0 může otevírat modulace, jejíž cíl neznáme
        "zero_vol_osc": sum(1 for o in osc if not o["audible"]),   # jen Serum 1
        "fine_spread": fine_spread,                # jen z Fine/oktávy; protisměrná modulace Fine není známá
        "lfo_to_filter": None,                     # zdroj/cíl modulace nejsou hostovské parametry
        "mod_slots": mod_slots,
        "mono": None,
        "fx_count": len(fx_on),
    }
    feats: dict[str, Any] = {
        "osc_on": len(osc), "unison_max": max((o["unison"] for o in osc), default=0),
        "unison_sum": sum(o["unison"] for o in osc),
        # detune: UniDet z displeje Serum 1 (0–1) jen u oscilátorů, kde unison > 1 (Serum 2: uložený kParamDetune všech zapnutých)
        "detune_max": max([o["detune"] for o in osc if o["unison"] > 1] or [0]),
        "warp_slots": sum(1 for o in osc if o["warp"].lower() != "off"),
        "noise_on": int(noise), "sub_on": int(sub), "filters_on": int(f_on),
        "filter_freq": _norm(p, "fil_cutoff_hz") if f_on else None,
        "filter_reso": _pct(p, "fil_reso") if f_on else None,
        "filter_drive": _pct(p, "fil_driv") if f_on else None,
        "fx_count": len(fx_on), "mod_slots": mod_slots,
        "mod_lfo": None, "mod_env": None, "mod_macro": None, "mod_to_osc": None, "mod_to_filter": None,
        "lfo_curves": None, "lfo_points": None, "env_count": None, "macro_count": None, "mono": None,
    }
    for name in rpi.FX_KINDS.values():
        feats[f"fx_{name}"] = 0
    for _, kind, _ in fx_on:
        feats[f"fx_{kind}"] += 1
    return cues, feats, fx_chain


def propose(name: str, c: dict[str, Any]) -> tuple[str, str, list[str]]:
    """Návrh (function, archetype, why). Jen to, co se dá doložit z hostu; bez zdroje/cíle modulace nic dalšího."""
    n = name.lower()
    func = next((f for f, pat in ip.NAME_RULES if re.search(pat, n)), "other")
    why = [f"jméno → {func}"]
    if func == "body" and "sub" in n:
        func = "sub"
    arch = "unclassified"
    if func == "sub":
        clean = not c["warp_modes"] and c["max_unison"] <= 1 and not c["noise"]
        if clean:
            arch = "clean-sub-sine"
        else:
            why.append("jméno → sub, ale naměřené stopy čistý sinus nepotvrzují (warp, unison nebo noise)")
    elif func == "body":
        if c["cross_warp"] and any(w.upper().startswith("FM") for w in c["cross_warp"]):
            arch = "fm-distorted-body"
            why.append("FM z jiného zapnutého zdroje (Serum 1)")
        elif c["fine_spread"]:
            arch = "detuned-unison-reese"
            why.append("rozladění Fine mezi oscilátory")
        else:
            why.append("zdroj/cíl modulace neznámý → bez dalšího návrhu archetypu")
    return func, arch, why


def build_rows(params: dict, base: dict[str, Any]) -> tuple[dict, dict]:
    """Index řádek + feature řádek. `base` nese id/source_id/name/group/file/container (z kontejneru nebo ze starého indexu)."""
    cues, feats, chain = measure(params)
    func, arch, why = propose(base["name"], cues)
    index = {"id": base["id"], "source_id": base["source_id"], "name": base["name"], "group": base["group"], "file": base["file"],
             "synth": "Serum1 (fxp)", "tags": [], "function": func, "role": ip.role_of(base["name"]), "archetype": arch,
             "confidence": "hypothesis", "cues_basis": "preset_file", "reader": READER, "cues": cues, "why": why,
             "fx_chain": chain, "fx_order": "unknown", "container": base["container"]}
    feature = {"id": base["id"], "source_id": base["source_id"], "function": func, "role": index["role"], "archetype": arch,
               "confidence": "hypothesis", "basis": "preset_file", "reader": READER, "features": feats}
    return index, feature


# ─── soubory ───────────────────────────────────────────────────────────────────────────────────────────────────

def discover(paths: list[Path]) -> list[tuple[Path, str]]:
    out = []
    for x in paths:
        if x.is_dir():
            for f in sorted(x.rglob("*.fxp")):
                parts = f.relative_to(x).parts
                out.append((f, parts[0] if len(parts) > 1 else ""))
        else:
            out.append((x, x.parent.name))
    return out


def load_index(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run(paths: list[Path], source_id: str, host: Any, match: list[dict] | None = None, dump_dir: Path | None = None,
        limit: int | None = None, log=print) -> tuple[list[dict], list[dict], list[str]]:
    """Vrátí (index_rows, feature_rows, chyby). `host` má load_fxp(bytes) a read(); pořadí podle `match`, jinak podle cest."""
    pinned = {r["container"]["sha256"]: r for r in match} if match else None
    todo: list[tuple[Path, dict, dict]] = []
    seen: set[str] = set()
    bad: list[str] = []
    for f, group in discover(paths):
        try:
            c = fx.read_fxp(f)
        except (ValueError, OSError) as e:
            bad.append(f"{f.name}: {e}")
            continue
        sha = c["sha256"]
        if sha in seen or (pinned is not None and sha not in pinned):
            continue
        seen.add(sha)
        # do repa jen počet odkazů na wavetably (jména a cesty patří k placeným packům a jdou jen do dumpu v _local/)
        container = {k: c[k] for k in ("fx_id", "is_serum1", "plugin_version", "num_params", "state_bytes", "sha256")} | {"wav_count": len(c["wavs"])}
        if pinned is not None:
            r = pinned[sha]
            base = {k: r[k] for k in ("id", "name", "group", "file")} | {"source_id": source_id, "container": container}
        else:
            name = c["name"] or f.stem
            base = {"id": ap.slugify(f"{source_id}-{group[:32]}-{f.stem}"), "source_id": source_id, "name": name,
                    "group": group, "file": f.name, "container": container}
        todo.append((f, base, c))
    if pinned is not None:
        bad += [f"{r['id']}: soubor se sha256 {s} nenalezen v zadaných cestách" for s, r in pinned.items() if s not in seen]
        order = {r["container"]["sha256"]: i for i, r in enumerate(match)}
        todo.sort(key=lambda t: order[t[1]["container"]["sha256"]])
    # stejné jméno ve stejné skupině (jiný obsah) dává stejné id: kolidující id dostanou příponu ze sha256, ať jsou jednoznačná
    counts: dict[str, int] = {}
    for _, base, _ in todo:
        counts[base["id"]] = counts.get(base["id"], 0) + 1
    for _, base, _ in todo:
        if counts[base["id"]] > 1:
            base["id"] = ap.slugify(f"{base['id']}-{base['container']['sha256'][:6]}")
    if limit:
        todo = todo[:limit]
    idx_rows, feat_rows = [], []
    for n, (f, base, c) in enumerate(todo, 1):
        if not c["is_serum1"]:
            bad.append(f"{f.name}: není Serum 1 (fxID {c['fx_id']!r})")
            continue
        if c["state_bytes"] not in EXPECTED_STATES:
            bad.append(f"{f.name}: neznámá velikost stavu {c['state_bytes']} (host ověřen jen pro {sorted(EXPECTED_STATES)})")
            continue
        try:
            host.load_fxp(f.read_bytes())
            params = host.read()
            index, feature = build_rows(params, base)
        except Exception as e:  # noqa: BLE001 - plugin i měření mohou selhat libovolně, jeden preset nesmí shodit dávku
            bad.append(f"{f.name}: {type(e).__name__}: {e}")
            continue
        idx_rows.append(index)
        feat_rows.append(feature)
        if dump_dir:
            dump_dir.mkdir(parents=True, exist_ok=True)
            (dump_dir / f"{base['id']}.json").write_text(json.dumps(
                {"id": base["id"], "file": f.name, "container": base["container"] | {"wavs": c["wavs"]},
                 "host": {k: [v["raw"], v["text"]] for k, v in params.items()}},
                ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        if n % 100 == 0:
            log(f"  {n}/{len(todo)}")
    return idx_rows, feat_rows, bad


def write_jsonl(path: Path, rows: list[dict]) -> None:
    """Atomicky: dočasný soubor vedle cíle + os.replace, takže přerušený běh nenechá poloprázdný index."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("paths", type=Path, nargs="+", help="složka(y) nebo .fxp soubory")
    p.add_argument("--source-id", required=True)
    p.add_argument("--match-index", type=Path, help="stávající index (JSONL): stejná sada souborů (podle sha256) a stejná id/group/name")
    p.add_argument("--out-index", type=Path, help="kompaktní index řádky (do repa, data/presets/fxp/<id>.jsonl)")
    p.add_argument("--out-features", type=Path, help="feature vektory (do repa, data/presets/features/<id>.jsonl)")
    p.add_argument("--dump-dir", type=Path, help="plné hostovské parametry (jen lokálně, data/presets/_local/…)")
    p.add_argument("--plugin", help=f"cesta k Serum 1 VST3 (jinak $SERUM1_VST3, jinak {DEFAULT_PLUGIN})")
    p.add_argument("--limit", type=int, help="jen prvních N (zkouška); nelze s přepsáním --match-index")
    p.add_argument("--allow-partial", action="store_true", help="zapsat i menší výstup, než je --match-index")
    a = p.parse_args(argv)

    # levné kontroly dřív než ~19 s start pluginu
    missing = [str(x) for x in a.paths if not x.exists()]
    if missing:
        print("neexistuje:", ", ".join(missing), file=sys.stderr)
        return 2
    match = None
    if a.match_index:
        try:
            match = load_index(a.match_index)
        except (OSError, json.JSONDecodeError, KeyError) as e:
            print(f"--match-index nejde přečíst: {e}", file=sys.stderr)
            return 2
        if a.limit and any(o and o.resolve() == a.match_index.resolve() for o in (a.out_index, a.out_features)):
            print("--limit s přepsáním --match-index by zmenšil index; použij jiný --out-index", file=sys.stderr)
            return 2
    try:
        host = S1Host(a.plugin)
    except RuntimeError as e:
        print(f"chyba: {e}", file=sys.stderr)
        return 2
    idx, feats, bad = run(a.paths, a.source_id, host, match, a.dump_dir, a.limit)
    for b in bad:
        print("chyba:", b, file=sys.stderr)
    print(f"{len(idx)} presetů přečteno hostem, {len(bad)} chyb")
    if not idx:
        print("žádný výstup, nic se nezapisuje", file=sys.stderr)
        return 1
    if match and len(idx) < len(match) and not a.limit and not a.allow_partial:
        print(f"výstup má {len(idx)} řádků, --match-index {len(match)}: nezapisuji (--allow-partial to vynutí)", file=sys.stderr)
        return 1
    if a.out_index:
        write_jsonl(a.out_index, idx)
    if a.out_features:
        write_jsonl(a.out_features, feats)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
