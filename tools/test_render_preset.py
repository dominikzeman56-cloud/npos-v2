import hashlib
import json
import re
import struct
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import analyze_fxp_host as hostmod  # noqa: E402
import render_preset as rp  # noqa: E402

SR = rp.SR


def tone(freq_hz, secs=3.0, am_hz=None, noise=False):
    t = np.arange(int(secs * SR)) / SR
    x = np.random.default_rng(1).normal(0, 0.2, len(t)) if noise else 0.4 * np.sin(2 * np.pi * freq_hz * t)
    if am_hz:
        x = x * (0.6 + 0.4 * np.sin(2 * np.pi * am_hz * t))
    return np.stack([x, x])


def test_sine_on_f0_is_sub_and_harmonic():
    d = rp.descriptors(tone(41.2))
    assert d["band_sub_pct"] > 95 and d["harmonic_pct"] > 90
    assert abs(d["peak_hz"] - 41.2) < 3 and d["silent"] is False


def test_noise_is_not_harmonic_and_bright():
    d = rp.descriptors(tone(0, noise=True))
    assert d["harmonic_pct"] < 20 and d["centroid_hz"] > 3000


def test_amplitude_modulation_rate_found():
    d = rp.descriptors(tone(110.0, am_hz=5.8))
    assert d["am_hz"] is not None and abs(d["am_hz"] - 5.8) < 0.6 and d["am_depth"] > 0.1


def test_silence_is_flagged():
    d = rp.descriptors(np.zeros((2, 3 * SR)))
    assert d["silent"] is True and "centroid_hz" not in d


def xfer(meta: dict, cbor_obj: dict) -> bytes:
    import cbor2
    import zstandard
    raw = cbor2.dumps(cbor_obj)
    z = zstandard.ZstdCompressor().compress(raw)
    js = json.dumps(meta, separators=(",", ":")).encode()
    return b"XferJson\0" + struct.pack("<Q", len(js)) + js + struct.pack("<II", len(raw), 2) + z


def fake_state(comp: bytes) -> bytes:
    xml = f"<?xml version=\"1.0\"?><VST3PluginState><IComponent>{hostmod.juce_b64_encode(comp)}</IComponent></VST3PluginState>"
    body = xml.encode() + b"\0"
    return b"VC2!" + struct.pack("<I", len(body)) + body


def test_s2_state_merges_preset_over_state_and_recomputes_hash():
    pytest.importorskip("cbor2")
    pytest.importorskip("zstandard")
    base = fake_state(xfer({"component": "processor", "hash": "old"}, {"component": "processor", "keep": 1, "Osc": {"a": 1}}))
    preset = xfer({"fileType": "SerumPreset", "hash": "x"}, {"Osc": {"a": 2}, "extra": 3})
    out = rp.s2_state(base, preset)
    comp = hostmod.juce_b64_decode(re.search(r"<IComponent>(.*?)</IComponent>", out[8:].decode(), re.S).group(1))
    head, meta, payload = rp._split_xfer(comp)
    assert meta["component"] == "processor" and meta["hash"] == hashlib.md5(payload[8:]).hexdigest()
    cb = rp._cbor_of(payload)
    assert cb["Osc"] == {"a": 2} and cb["keep"] == 1 and cb["extra"] == 3 and cb["component"] == "processor"
    assert struct.unpack("<I", out[4:8])[0] == len(out) - 8


def test_match_rows_by_group_and_file(tmp_path):
    (tmp_path / "g").mkdir()
    f = tmp_path / "g" / "a.SerumPreset"
    f.write_bytes(b"x")
    pairs = rp.match_rows("s2", rp.collect("s2", [tmp_path]), [{"id": "i1", "group": "g", "file": "a.SerumPreset"}])
    assert pairs and pairs[0][1]["id"] == "i1"


def test_render_with_real_plugin():
    try:
        r = rp.Renderer("s2")
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Serum 2 nebo pedalboard chybí: {e}")
    user = Path(r"D:\VST\Xfer\Serum 2 Presets\Presets\User\TSP_REDPILL_Bass_lazer.SerumPreset")
    if not user.exists():
        pytest.skip("vzorový preset chybí")
    d = rp.descriptors(r.render(user.read_bytes()))
    assert d["silent"] is False and d["band_sub_pct"] + d["band_low_pct"] > 20


def test_upper_motion_separates_moving_formant_from_static_tone():
    t = np.arange(int(3.0 * SR)) / SR
    static = sum(np.sin(2 * np.pi * 41.2 * k * t) / k for k in range(1, 30))
    # "growl": jas nad subem se mění 3x za sekundu (vyšší harmonické zesilují a slábnou)
    lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 3.0 * t)
    moving = sum(np.sin(2 * np.pi * 41.2 * k * t) / k * (lfo if k > 4 else 1.0) for k in range(1, 30))
    a = rp.descriptors(np.stack([static, static]) * 0.1)
    b = rp.descriptors(np.stack([moving, moving]) * 0.1)
    assert b["upper_motion"] > 3 * a["upper_motion"]
    assert abs(b["upper_motion_hz"] - 3.0) < 0.6
    noise = rp.descriptors(tone(0, noise=True))
    assert noise["upper_flatness"] > 0.5 > a["upper_flatness"]


def test_redescribe_from_wav(tmp_path):
    from scipy.io import wavfile
    (tmp_path / "w" / "src").mkdir(parents=True)
    wavfile.write(tmp_path / "w" / "src" / "p1.wav", SR, (tone(41.2).T * 32767).astype(np.int16))
    jp = tmp_path / "a.jsonl"
    jp.write_text(json.dumps({"id": "p1", "source_id": "src", "protocol": rp.PROTOCOL, "audio": {}}) + "\n", encoding="utf-8")
    n, missing = rp.redescribe([jp], tmp_path / "w")
    row = json.loads(jp.read_text(encoding="utf-8"))
    assert n == 1 and not missing and row["audio"]["band_sub_pct"] > 90 and row["audio_basis"] == "wav16"
