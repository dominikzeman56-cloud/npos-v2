#!/usr/bin/env python3
"""render_preset.py — vyrenderuje preset jednou notou a změří zvuk (čísla do gitu, audio jen lokálně).

Proč: role a podobnost presetů se doteď určovaly z názvu a z parametrů. Zvuk je měření: spektrum po pásmech,
podíl harmonických, rychlost a hloubka amplitudové modulace, stereo. Platí **jen pro tenhle protokol** (nota, délka,
tempo); zvuk jiné noty nebo s jinak nastavenými makry může vyjít jinak.

Hostuje Serum 1 (`.fxp`) a Serum 2 (`.SerumPreset`) přes pedalboard (`pip install pedalboard`, GPL-3.0, jen lokálně).
Serum 2 přijme `.SerumPreset` jako stav komponenty: hlavička XferJson z výchozího stavu + CBOR/zstd tělo presetu.

Použití:
  py -3.12 tools/render_preset.py s1 "…/S1 Presets/BO" --source-id s1-burr-oak --match-index data/presets/fxp/s1-burr-oak.jsonl \\
      --out data/presets/audio/s1-burr-oak.jsonl [--wav-dir data/presets/_local/audio/s1-burr-oak] [--limit 5]
  py -3.12 tools/render_preset.py s2 _sources/presets/redpill-serum-presets --source-id redpill-serum-presets \\
      --match-index data/presets/index/redpill-serum-presets.jsonl --out data/presets/audio/redpill-serum-presets.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy import signal as sig

sys.path.insert(0, str(Path(__file__).parent))
import analyze_fxp_host as hostmod  # noqa: E402  (juce_b64_*, state_from_fxp)
import analyze_track as at  # noqa: E402  (bass_modulation, mid_side_db)

SR = at.SR  # 48 000 Hz, stejné jako analýza tracků
PROTOCOL = {"note": 28, "note_name": "E1", "f0_hz": 41.2, "velocity": 100, "hold_s": 2.0, "tail_s": 1.0, "sr": SR,
            "bpm": 174, "onset_s": 0.1, "window_s": [0.25, 2.0], "channels": 2}   # okno je od nástupu noty
S2_PLUGIN = r"C:\Program Files\Common Files\VST3\Serum2.vst3\Contents\x86_64-win\Serum2.vst3"
S1_PLUGIN = hostmod.DEFAULT_PLUGIN
BANDS = (("sub", 0, 60), ("low", 60, 200), ("mid", 200, 2000), ("high", 2000, 8000), ("air", 8000, SR / 2))


# ─── deskriptory (čisté funkce, testovatelné bez pluginu) ──────────────────────────────────────────────────────

def _db(x: float) -> float:
    return float(20.0 * np.log10(max(x, 1e-9)))


def descriptors(audio: np.ndarray, protocol: dict | None = None) -> dict[str, Any]:
    """`audio` tvaru (kanály, vzorky) nebo (vzorky, 2) při SR; vrací čísla z okna sustainu."""
    pr = protocol or PROTOCOL
    x = np.asarray(audio, dtype=np.float64)
    if x.ndim == 1:
        x = np.stack([x, x])
    if x.shape[0] <= 8:   # (kanály, vzorky) -> (vzorky, kanály)
        x = x.T
    t0, t1 = pr["window_s"]
    on = pr.get("onset_s", 0.0)
    seg = x[int((on + t0) * SR):int((on + t1) * SR)]
    mono = seg.mean(axis=1)
    peak = float(np.abs(seg).max()) if len(seg) else 0.0
    window = "sustain"
    if peak < 1e-4:   # jednorázové zvuky (kick, snare, hat) doznějí dřív než okno sustainu: změř nástup
        seg = x[int(on * SR):int((on + 0.4) * SR)]
        peak = float(np.abs(seg).max()) if len(seg) else 0.0
        window = "attack"
        mono = seg.mean(axis=1)
    rms = float(np.sqrt(np.mean(mono ** 2))) if len(mono) else 0.0
    out: dict[str, Any] = {"window": window, "peak_db": round(_db(peak), 2), "rms_db": round(_db(rms), 2),
                           "crest_db": round(_db(peak) - _db(rms), 2), "silent": bool(peak < 1e-4)}
    if out["silent"] or len(mono) < SR // 8:
        return out
    win = np.hanning(len(mono))
    spec = np.abs(np.fft.rfft(mono * win)) ** 2
    f = np.fft.rfftfreq(len(mono), 1.0 / SR)
    total = float(spec.sum()) + 1e-30
    for name, lo, hi in BANDS:
        out[f"band_{name}_pct"] = round(100.0 * float(spec[(f >= lo) & (f < hi)].sum()) / total, 2)
    out["centroid_hz"] = round(float((f * spec).sum() / total), 1)
    out["rolloff85_hz"] = round(float(f[min(int(np.searchsorted(np.cumsum(spec) / total, 0.85)), len(f) - 1)]), 1)
    low = (f >= 20) & (f <= 400)
    out["peak_hz"] = round(float(f[low][int(np.argmax(spec[low]))]), 1)
    # podíl výkonu poblíž násobků nominální f0 (±3 %): vysoko = harmonický zvuk, nízko = šum / nepravidelné spektrum
    f0 = pr["f0_hz"]
    near = np.zeros(len(f), dtype=bool)
    for k in range(1, 41):
        near |= np.abs(f - k * f0) <= 0.03 * k * f0
    out["harmonic_pct"] = round(100.0 * float(spec[near].sum()) / total, 2)
    # amplitudová modulace basu: obálka pásma 60–300 Hz (stejná metoda jako analyze_track.bass_modulation)
    bm = at.bass_modulation(seg, 0.0, len(seg) / SR, pr["bpm"])
    out["am_hz"] = bm["primary_hz"]
    out["am_grid"] = bm["grid_match"]
    sos = sig.butter(4, [60.0 / (SR / 2), 300.0 / (SR / 2)], btype="band", output="sos")
    env = np.abs(sig.hilbert(sig.sosfiltfilt(sos, mono)))
    out["am_depth"] = round(float(env.std() / max(env.mean(), 1e-12)), 3)
    m_db, s_db = at.mid_side_db(seg, 60.0, 20000.0)
    out["side_minus_mid_db"] = round(float(s_db - m_db), 2)
    return out


# ─── hostování ─────────────────────────────────────────────────────────────────────────────────────────────────

def _split_xfer(b: bytes) -> tuple[bytes, dict, bytes]:
    if b[:9] != b"XferJson\0":
        raise ValueError("není XferJson")
    n = struct.unpack("<Q", b[9:17])[0]
    return b[:9], json.loads(b[17:17 + n]), b[17 + n:]


def _cbor_of(payload: bytes) -> dict:
    import cbor2
    import zstandard
    size, _ver = struct.unpack("<II", payload[:8])
    raw = zstandard.ZstdDecompressor().decompressobj().decompress(payload[8:])
    if len(raw) != size:
        raise ValueError("velikost CBOR neodpovídá hlavičce")
    return cbor2.loads(raw)


def s2_state(raw_state: bytes, preset: bytes) -> bytes:
    """Stav Serum 2 VST3 s vloženým `.SerumPreset` (ověřeno: zvuk se změní proti výchozímu stavu).

    Stav procesoru je XferJson (hlavička JSON s md5 zstd těla) + zstd(CBOR). CBOR presetu se položí přes CBOR výchozího
    stavu (zůstanou klíče, které preset nemá: component, modMatrixLocked, scalarCurvesLocked), tělo se znovu zkomprimuje
    a hash v hlavičce se přepočítá. Stav s cizím hashem nebo bez `component` plugin tiše ignoruje."""
    import cbor2
    import zstandard
    xml = raw_state[8:].decode("utf-8")
    m = re.search(r"<IComponent>(.*?)</IComponent>", xml, re.S)
    if not m:
        raise ValueError("stav Serum 2 nemá IComponent")
    head, meta, base_payload = _split_xfer(hostmod.juce_b64_decode(m.group(1)))
    _, _, preset_payload = _split_xfer(preset)
    merged = dict(_cbor_of(base_payload))
    merged.update(_cbor_of(preset_payload))
    merged["component"] = "processor"
    raw = cbor2.dumps(merged)
    z = zstandard.ZstdCompressor().compress(raw)
    meta["hash"] = hashlib.md5(z).hexdigest()
    js = json.dumps(meta, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    comp = head + struct.pack("<Q", len(js)) + js + struct.pack("<II", len(raw), 2) + z
    new_xml = xml[:m.start(1)] + hostmod.juce_b64_encode(comp) + xml[m.end(1):]
    body = new_xml.encode("utf-8") + b"\0"
    return raw_state[:4] + struct.pack("<I", len(body)) + body


class Renderer:
    def __init__(self, kind: str, plugin_path: str | None = None):
        try:
            from pedalboard import load_plugin
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("chybí pedalboard (pip install pedalboard)") from e
        self.kind = kind
        if kind == "s2":
            self.plugin = load_plugin(plugin_path or os.environ.get("SERUM2_VST3") or S2_PLUGIN, plugin_name="Serum 2")
        else:
            self.plugin = load_plugin(plugin_path or os.environ.get("SERUM1_VST3") or S1_PLUGIN)
        self.base = self.plugin.raw_state
        self.prev = None
        self.init_audio = self._play()

    def _play(self) -> np.ndarray:
        """Jedna nota; reset=False (kolem 0,1 s místo ~6 s), proto na začátku all-sound-off a all-notes-off."""
        n, v, on, hold = PROTOCOL["note"], PROTOCOL["velocity"], PROTOCOL["onset_s"], PROTOCOL["hold_s"]
        msgs = [(bytes([0xB0, 120, 0]), 0.0), (bytes([0xB0, 123, 0]), 0.0),
                (bytes([0x90, n, v]), on), (bytes([0x80, n, 0]), on + hold)]
        a = self.plugin(msgs, duration=on + hold + PROTOCOL["tail_s"], sample_rate=SR, num_channels=2, reset=False)
        return np.asarray(a, dtype=np.float32)

    def render(self, data: bytes) -> np.ndarray:
        """Načte preset (.fxp u s1, .SerumPreset u s2) a vrátí audio (2, vzorky). Odmítne stav, který plugin nepřijal."""
        self.plugin.raw_state = hostmod.state_from_fxp(self.base, data) if self.kind == "s1" else s2_state(self.base, data)
        a = self._play()
        for name, ref in (("výchozím stavem", self.init_audio), ("předchozím presetem", self.prev)):
            if ref is not None and ref.shape == a.shape and float(np.abs(a - ref).max()) < 1e-6:
                raise RuntimeError(f"plugin preset nepřijal (zvuk je shodný s {name})")
        self.prev = a
        return a


# ─── dávka ─────────────────────────────────────────────────────────────────────────────────────────────────────

def _sha16(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:16]


def collect(kind: str, roots: list[Path]) -> list[tuple[Path, str]]:
    pat = "*.fxp" if kind == "s1" else "*.SerumPreset"
    out = []
    for r in roots:
        if r.is_dir():
            for f in sorted(r.rglob(pat)):
                parts = f.relative_to(r).parts
                out.append((f, parts[0] if len(parts) > 1 else ""))
        else:
            out.append((r, r.parent.name))
    return out


def match_rows(kind: str, files: list[tuple[Path, str]], index: list[dict]) -> list[tuple[Path, dict]]:
    """Přiřadí soubory k řádkům indexu: s1 podle sha256 obsahu, s2 podle (group, file)."""
    if kind == "s1":
        want = {r["container"]["sha256"]: r for r in index if r.get("container", {}).get("sha256")}
        by_sha: dict[str, Path] = {}
        for f, _ in files:
            by_sha.setdefault(_sha16(f.read_bytes()), f)
        return [(by_sha[s], r) for s, r in want.items() if s in by_sha]
    want2 = {(r.get("group", ""), r["file"]): r for r in index}
    return [(f, want2[(g, f.name)]) for f, g in files if (g, f.name) in want2]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def run(renderer: Renderer, pairs: list[tuple[Path, dict]], source_id: str, wav_dir: Path | None, limit: int | None,
        log=print) -> tuple[list[dict], list[str]]:
    rows, bad = [], []
    for i, (f, r) in enumerate(pairs[:limit] if limit else pairs):
        try:
            a = renderer.render(f.read_bytes())
            d = descriptors(a)
        except Exception as e:  # noqa: BLE001 - jeden vadný preset nezastaví dávku
            bad.append(f"{f.name}: {type(e).__name__}: {e}")
            continue
        rows.append({"id": r["id"], "source_id": source_id, "reader": f"render_{renderer.kind}", "protocol": PROTOCOL,
                     "audio": d})
        if wav_dir is not None:
            from scipy.io import wavfile
            wav_dir.mkdir(parents=True, exist_ok=True)
            wavfile.write(wav_dir / f"{r['id']}.wav", SR, (np.clip(a.T, -1, 1) * 32767).astype(np.int16))
        if (i + 1) % 25 == 0:
            log(f"  {i + 1}/{len(pairs)}")
    return rows, bad


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("kind", choices=("s1", "s2"))
    p.add_argument("paths", type=Path, nargs="+")
    p.add_argument("--source-id", required=True)
    p.add_argument("--match-index", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--wav-dir", type=Path, help="jen lokálně (data/presets/_local/audio/…), placené packy se nesdílejí")
    p.add_argument("--plugin")
    p.add_argument("--limit", type=int)
    a = p.parse_args(argv)
    if a.wav_dir and "_local" not in a.wav_dir.parts:
        print("--wav-dir musí být pod _local (gitignored)", file=sys.stderr)
        return 2
    index = [json.loads(line) for line in a.match_index.read_text(encoding="utf-8").splitlines() if line.strip()]
    pairs = match_rows(a.kind, collect(a.kind, a.paths), index)
    if not pairs:
        print("žádný soubor neodpovídá indexu", file=sys.stderr)
        return 1
    try:
        r = Renderer(a.kind, a.plugin)
    except (RuntimeError, ImportError, ValueError) as e:
        print(f"chyba: {e}", file=sys.stderr)
        return 2
    rows, bad = run(r, pairs, a.source_id, a.wav_dir, a.limit)
    for b in bad:
        print("chyba:", b, file=sys.stderr)
    print(f"{len(rows)} z {len(pairs)} vyrenderováno, {len(bad)} chyb")
    if not rows:
        return 1
    if a.limit or len(rows) < len(pairs):
        print("neúplný výstup: zapisuji jen s --out a bez přepsání plného souboru zpět neuděláš", file=sys.stderr)
    write_jsonl(a.out, rows)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
