#!/usr/bin/env python3
"""analyze_fxp.py — čtečka kontejneru Serum 1 `.fxp` (VST2 preset, chunk FPCh, fxID XfsX).

Co umí (vše `measured`, čte se přímo ze souboru):
  hlavička (verze, počet parametrů, jméno), zlib-rozbalený stav syntezátoru (velikost),
  jména makro knobů, odkazy na vlnové soubory (.wav), role navržená z jména (`hypothesis`).

Co neumí: význam jednotlivých parametrů. Binární stav Serum 1 není zdokumentovaný a nic z něj tu netvrdíme.
Plnou analýzu (oscilátory, warp, filtry, FX, modulace) dostaneš tak, že `.fxp` otevřeš v Serum 2 (načte presety
ze Serum 1) a uložíš jako `.SerumPreset`; ten čte `analyze_preset.py` / `index_presets.py`.

Použití:
  py -3.12 tools/analyze_fxp.py SLOŽKA_NEBO_SOUBOR --source-id letsynthesize-old [--out data/presets/fxp/ID.jsonl]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import analyze_preset as ap  # noqa: E402
import index_presets as ip  # noqa: E402

HEADER = struct.Struct(">4sI4sIII")  # CcnK, délka, typ, verze formátu, fxID, verze pluginu
SERUM1_ID = b"XfsX"


def read_fxp(path: Path) -> dict:
    d = path.read_bytes()
    if len(d) < 60 or d[:4] != b"CcnK":
        raise ValueError("není VST2 .fxp (chybí CcnK)")
    kind = d[8:12]
    if kind != b"FPCh":
        raise ValueError(f"nepodporovaný typ {kind!r} (čekám FPCh, tedy chunk preset)")
    _, _, _, fmt_ver, fx_id, plug_ver = HEADER.unpack_from(d)
    fx_id_b = struct.pack(">I", fx_id)
    num_params = struct.unpack_from(">I", d, 24)[0]
    name = d[28:56].split(b"\0", 1)[0].decode("latin-1")
    size = struct.unpack_from(">I", d, 56)[0]
    z = d[60:60 + size]
    if len(z) != size:
        raise ValueError("chunk je useknutý")
    try:
        raw = zlib.decompressobj().decompress(z)
    except zlib.error as e:
        raise ValueError(f"chunk nejde rozbalit: {e}") from e
    strs = [s.decode("latin-1") for s in re.findall(rb"[\x20-\x7e]{4,}", raw)]
    return {
        "name": name, "fx_id": fx_id_b.decode("latin-1"), "is_serum1": fx_id_b == SERUM1_ID,
        "plugin_version": plug_ver, "format_version": fmt_ver, "num_params": num_params,
        "chunk_bytes": size, "state_bytes": len(raw), "sha256": hashlib.sha256(d).hexdigest()[:16],
        "wavs": sorted({s for s in strs if s.lower().endswith(".wav")}),
        "macros": [m for m in re.findall(r"Macro \d", " ".join(strs))],
    }


def row(path: Path, source_id: str, group: str) -> dict:
    a = read_fxp(path)
    name = a["name"] or path.stem
    func = next((f for f, pat in ip.NAME_RULES if __import__("re").search(pat, name.lower())), "other")
    return {"id": ap.slugify(f"{source_id}-{group[:32]}-{path.stem}"), "source_id": source_id, "name": name, "group": group,
            "file": path.name, "synth": "Serum1 (fxp)", "function": func, "role": ip.role_of(name), "confidence": "hypothesis",
            "cues_basis": "fxp_container", "container": {k: a[k] for k in ("fx_id", "is_serum1", "plugin_version", "num_params", "state_bytes", "sha256", "wavs")},
            "convert": "otevřít v Serum 2 a uložit jako .SerumPreset pro plnou analýzu"}


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("paths", type=Path, nargs="+")
    p.add_argument("--source-id", required=True)
    p.add_argument("--out", type=Path)
    p.add_argument("--dedupe", action="store_true", help="vynechat soubory s identickým obsahem (sha256), první vyhrává")
    a = p.parse_args(argv)
    files = []
    for x in a.paths:
        files += [(f, f.relative_to(x).parts[0] if len(f.relative_to(x).parts) > 1 else "") for f in sorted(x.rglob("*.fxp"))] if x.is_dir() else [(x, x.parent.name)]
    rows, bad = [], []
    seen = set()
    for f, g in files:
        try:
            r = row(f, a.source_id, g)
            if a.dedupe and r["container"]["sha256"] in seen:
                continue
            seen.add(r["container"]["sha256"])
            rows.append(r)
        except (ValueError, OSError) as e:
            bad.append(f"{f.name}: {e}")
    for b in bad:
        print("chyba:", b, file=sys.stderr)
    print(f"{len(rows)} fxp načteno, {len(bad)} chyb")
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="\n")
    else:
        for r in rows[:20]:
            print(f"  {r['role']:<8} {r['name']}")
    return 1 if bad and not rows else 0


if __name__ == "__main__":
    sys.exit(main())
