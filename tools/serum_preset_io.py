#!/usr/bin/env python3
"""serum_preset_io.py — čtení a zápis `.SerumPreset` (Serum 2) bez pluginu.

Formát: `XferJson\\0` + u64 délka JSON hlavičky + JSON + u32 velikost CBOR + u32 verze (2) + zstd(CBOR).
Hlavička obsahuje `hash` = md5 zstd těla; plugin soubor s cizím hashem tiše ignoruje, proto se při zápisu přepočítá.
Minimální kodek, nezávislý na `neuroman/` (BLUEPRINT: ten se neobnovuje). Vlastní CBOR kodek zachovává šířku čísel (float32);
cbor2 by je přepsal na float64 a preset by narostl (medián +6 %, největší soubor až +80 %) a neodpovídal tomu, co píše Serum.
Ověřeno: dekomprimované CBOR tělo a JSON hlavička se po načtení a zápisu shodují bajt po bajtu u všech zkoušených
presetů (115 z indexu, 600 z Xfer složky). Zstd obal se přebalí s jinou kompresí, takže celý soubor se liší a hash se
přepočítá. Float16, tagy a neurčité délky v CBOR kodek odmítne (ValueError), Serum je nepoužívá. Zápis `.fxp` se nepodporuje.
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


class F32(float):
    """Hodnota uložená v CBOR jako float32. Serum ukládá drtivou většinu čísel jako float32 (tisíce hodnot vlnových tabulek);
    běžné cbor2.dumps by je přepsalo na float64, soubor by narostl o ~80 % a nebyl by shodný s tím, co plugin píše."""


def _decode(b: bytes, p: int = 0) -> tuple[Any, int]:
    """Minimální CBOR dekodér pro to, co Serum používá: čísla, text, pole, mapy, bool; float32 zůstane F32. Bez tagů a
    neurčitých délek (u nich ValueError, ať se nic tiše nezkomolí)."""
    ib = b[p]
    mt, ai = ib >> 5, ib & 31
    if mt == 7:
        if ai == 20 or ai == 21:
            return ai == 21, p + 1
        if ai == 25:
            raise ValueError("CBOR float16 se nepodporuje (nešel by zapsat zpět beze změny)")
        if ai == 26:
            return F32(struct.unpack(">f", b[p + 1:p + 5])[0]), p + 5
        if ai == 27:
            return struct.unpack(">d", b[p + 1:p + 9])[0], p + 9
        if ai == 22:
            return None, p + 1
        raise ValueError(f"nepodporovaný CBOR simple {ai}")
    if ai < 24:
        v, q = ai, p + 1
    elif ai in (24, 25, 26, 27):
        w = 1 << (ai - 24)
        v, q = int.from_bytes(b[p + 1:p + 1 + w], "big"), p + 1 + w
    else:
        raise ValueError("neurčitá délka nebo tag v CBOR")
    if mt == 0:
        return v, q
    if mt == 1:
        return -1 - v, q
    if mt == 3:
        return b[q:q + v].decode("utf-8"), q + v
    if mt == 4:
        out = []
        for _ in range(v):
            x, q = _decode(b, q)
            out.append(x)
        return out, q
    if mt == 5:
        d = {}
        for _ in range(v):
            k, q = _decode(b, q)
            d[k], q = _decode(b, q)
        return d, q
    raise ValueError(f"nepodporovaný CBOR typ {mt}")


def _head(mt: int, v: int) -> bytes:
    if v < 24:
        return bytes([mt << 5 | v])
    for ai, w in ((24, 1), (25, 2), (26, 4), (27, 8)):
        if v < 1 << (8 * w):
            return bytes([mt << 5 | ai]) + v.to_bytes(w, "big")
    raise ValueError("číslo mimo rozsah CBOR")


def _encode(o: Any, out: list[bytes]) -> None:
    if isinstance(o, bool):
        out.append(bytes([0xF5 if o else 0xF4]))
    elif o is None:
        out.append(bytes([0xF6]))
    elif isinstance(o, F32):
        out.append(bytes([0xFA]) + struct.pack(">f", o))
    elif isinstance(o, float):
        out.append(bytes([0xFB]) + struct.pack(">d", o))
    elif isinstance(o, int):
        out.append(_head(0, o) if o >= 0 else _head(1, -1 - o))
    elif isinstance(o, str):
        e = o.encode("utf-8")
        out.append(_head(3, len(e)) + e)
    elif isinstance(o, (list, tuple)):
        out.append(_head(4, len(o)))
        for x in o:
            _encode(x, out)
    elif isinstance(o, dict):
        out.append(_head(5, len(o)))
        for k, v in o.items():
            _encode(k, out)
            _encode(v, out)
    else:
        raise TypeError(f"CBOR: nepodporovaný typ {type(o).__name__}")


def read_preset(src: bytes | str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Vrátí (hlavička, CBOR slovník). Chyba formátu = ValueError."""
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
    cb, end = _decode(raw)
    if end != len(raw):
        raise ValueError("za CBOR zbývají data")
    return meta, cb


def write_preset(meta: dict[str, Any], cbor_dict: dict[str, Any]) -> bytes:
    """Zabalí preset; `hash` v hlavičce se přepočítá (md5 zstd těla)."""
    import zstandard
    parts: list[bytes] = []
    _encode(cbor_dict, parts)
    raw = b"".join(parts)
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
