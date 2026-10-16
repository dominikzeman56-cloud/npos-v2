import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pytest  # noqa: E402

import analyze_fxp as fx  # noqa: E402


def make(path: Path, name="Main Bass", fx_id=b"XfsX", state=b"\0\0\0\0Analog\x.wav\0Macro 1\0Macro 2\0", kind=b"FPCh"):
    z = zlib.compress(state)
    d = b"CcnK" + struct.pack(">I", 0) + kind + struct.pack(">I", 1) + fx_id + struct.pack(">II", 1, 1) + name.encode().ljust(28, b"\0") + struct.pack(">I", len(z)) + z
    path.write_bytes(d)
    return path


def test_reads_container(tmp_path):
    a = fx.read_fxp(make(tmp_path / "a.fxp"))
    assert a["name"] == "Main Bass" and a["is_serum1"] and a["fx_id"] == "XfsX"
    assert a["macros"] == ["Macro 1", "Macro 2"] and any(w.endswith(".wav") for w in a["wavs"])


def test_role_from_name(tmp_path):
    assert fx.row(make(tmp_path / "b.fxp", name="Best Reese"), "t", "g")["role"] == "reese"


def test_rejects_garbage(tmp_path):
    (tmp_path / "x.fxp").write_bytes(b"nope" * 20)
    with pytest.raises(ValueError):
        fx.read_fxp(tmp_path / "x.fxp")
    with pytest.raises(ValueError):
        fx.read_fxp(make(tmp_path / "bank.fxp", kind=b"FBCh"))
