#!/usr/bin/env python3
"""serum_preset_io.py — čtení a zápis `.SerumPreset` (Serum 2) bez pluginu.

Formát: `XferJson\\0` + u64 délka JSON hlavičky + JSON + u32 velikost CBOR + u32 verze (2) + zstd(CBOR).
Hlavička obsahuje `hash` = md5 zstd těla; plugin soubor s cizím hashem tiše ignoruje, proto se při zápisu přepočítá.
Minimální kodek, nezávislý na `neuroman/` (BLUEPRINT: ten se neobnovuje). Zápis `.fxp` se nepodporuje.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path
from typing import Any, Iterator

MAGIC = b"XferJson\0"
VERSION = 2


def read_preset(src: bytes | str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Vrátí (hlavička, CBOR slovník). Chyba formátu = ValueError."""
    import cbor2
    import zstandard
    b = Path(src).read_bytes() if isinstance(src, (str, Path)) else src
    if b[:9] != MAGIC:
        raise ValueError("není XferJson")
    n = struct.unpack("<Q", b[9:17])[0]
    meta = json.loads(b[17:17 + n])
    size, ver = struct.unpack("<II", b[17 + n:25 + n])
    if ver != VERSION:
        raise ValueError(f"neznámá verze XferJson {ver}")
    raw = zstandard.ZstdDecompressor().decompressobj().decompress(b[25 + n:])
    if len(raw) != size:
        raise ValueError("velikost CBOR neodpovídá hlavičce")
    return meta, cbor2.loads(raw)


def write_preset(meta: dict[str, Any], cbor_dict: dict[str, Any]) -> bytes:
    """Zabalí preset; `hash` v hlavičce se přepočítá (md5 zstd těla)."""
    import cbor2
    import zstandard
    raw = cbor2.dumps(cbor_dict)
    z = zstandard.ZstdCompressor().compress(raw)
    meta = dict(meta, hash=hashlib.md5(z).hexdigest())
    js = json.dumps(meta, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return MAGIC + struct.pack("<Q", len(js)) + js + struct.pack("<II", len(raw), VERSION) + z


def plain_params(cbor_dict: dict[str, Any]) -> Iterator[tuple[str, str, Any]]:
    """(modul, klíč, hodnota) pro všechny `plainParams` (jen parametry, které se liší od výchozích)."""
    for mod, body in cbor_dict.items():
        pp = body.get("plainParams") if isinstance(body, dict) else None
        if isinstance(pp, dict):   # u některých modulů je plainParams text nebo chybí
            for k, v in pp.items():
                yield mod, k, v


def module_kind(name: str) -> str:
    """Modul bez pořadového čísla: `Oscillator3` → `Oscillator`, `ModSlot12` → `ModSlot`."""
    return re.sub(r"\d+$", "", name)


def safe_file_stem(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .") or "preset"
