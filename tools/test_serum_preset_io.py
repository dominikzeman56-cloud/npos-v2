import hashlib
import struct

import pytest

import serum_preset_io as sio

pytest.importorskip("zstandard")


def body():
    return {"Oscillator0": {"plainParams": {"kLevel": sio.F32(0.5), "kOn": True, "kMode": 3}, "name": "Osc A"},
            "FX1": {"plainParams": "none"}, "List": [1, -2, 300, -70000, 1.25, None, "č"]}


def test_roundtrip_keeps_types_and_recomputes_hash():
    data = sio.write_preset({"product": "Serum2", "hash": "stale"}, body())
    meta, cb = sio.read_preset(data)
    assert meta["product"] == "Serum2" and cb == body()
    assert type(cb["Oscillator0"]["plainParams"]["kLevel"]) is sio.F32 and type(cb["List"][4]) is float
    n = struct.unpack("<Q", data[9:17])[0]
    assert meta["hash"] == hashlib.md5(data[25 + n:]).hexdigest() != "stale"
    assert sio.read_preset(sio.write_preset(meta, cb)) == (meta, cb)


def test_read_rejects_bad_input():
    with pytest.raises(ValueError):
        sio.read_preset(b"NotXfer\0\0" + b"\0" * 20)
    data = bytearray(sio.write_preset({}, {}))
    n = struct.unpack("<Q", data[9:17])[0]
    data[21 + n:25 + n] = struct.pack("<I", 9)
    with pytest.raises(ValueError, match="verze"):
        sio.read_preset(bytes(data))


def test_cbor_rejects_unsupported():
    with pytest.raises(ValueError):
        sio._decode(bytes([0xF9, 0, 0]))  # float16
    with pytest.raises(ValueError):
        sio._decode(bytes([0x9F]))  # neurčitá délka
    with pytest.raises(TypeError):
        sio._encode(b"x", [])


def test_helpers():
    assert list(sio.plain_params(body())) == [("Oscillator0", "kLevel", 0.5), ("Oscillator0", "kOn", True), ("Oscillator0", "kMode", 3)]
    assert sio.module_kind("Oscillator3") == "Oscillator" and sio.module_kind("ModSlot12") == "ModSlot"
    assert sio.safe_file_stem("a/b:c?.SerumPreset") == "a_b_c_.SerumPreset" and sio.safe_file_stem("...") == "preset"
