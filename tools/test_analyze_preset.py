import json
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
cbor2 = pytest.importorskip("cbor2")
zstandard = pytest.importorskip("zstandard")
import analyze_preset as ap  # noqa: E402


def make_blob(cb: dict, meta: dict | None = None) -> bytes:
    meta = meta or {"presetName": "Test Reese", "product": "Serum2", "productVersion": "2.0.0",
                    "tags": ["Mono"], "hash": "abc"}
    raw = cbor2.dumps(cb)
    mb = json.dumps(meta).encode()
    return (ap.MAGIC + struct.pack("<Q", len(mb)) + mb + struct.pack("<I", len(raw))
            + struct.pack("<I", 2) + zstandard.ZstdCompressor().compress(raw))


CB = {
    "Oscillator0": {"plainParams": {"kParamOctave": -2.0, "kParamVolume": 0.5},
                    "WTOsc0": {"plainParams": {"kParamWarpMenu": "kPD_OSC"}, "relativePathToWT": "T/x.wav"}},
    "VoiceFilter0": {"plainParams": {"kParamType": "MgL24", "kParamFreq": 0.3}},
    "FXRack0": {"FX": [{"type": 0, "FXDistortion": {"plainParams": {"kParamDrive": 50.0, "kParamMode": "kAsym"}},
                        "kUIParamMixOrGain": 0.0}]},
    "ModSlot0": {"source": [6, 0], "destModuleTypeString": "VoiceFilter", "destModuleID": 0,
                 "destModuleParamName": "kParamFreq", "plainParams": {"kParamAmount": 40.0}},
    "ModSlot1": {"source": [99, 0], "destModuleTypeString": "FXEQ", "destModuleID": 1,
                 "destModuleParamName": "kParamGain1", "plainParams": {"kParamAmount": 10.0}},
    "ModSlot2": {"plainParams": {}},
    "Global0": {"plainParams": {"kParamMonoToggle": 1.0}},
}


def test_roundtrip_and_reading(tmp_path):
    f = tmp_path / "t.SerumPreset"
    f.write_bytes(make_blob(CB))
    a = ap.analyze(f, source_id="s-1", function="movement")
    assert a["basis"] == "preset_file" and a["synth"] == "Serum2 2.0.0"
    r = a["reading"]
    assert r["oscillators"][0]["kind"] == "WTOsc"
    assert r["oscillators"][0]["wavetable"] == "T/x.wav"
    assert a["fx_chain"] == ["Distortion (kAsym)"]
    assert [m["slot"] for m in r["modulation"]] == [0, 1]       # prázdný ModSlot2 se přeskočí
    assert r["voice"] == {"kParamMonoToggle": 1.0}


def test_unknown_source_ids_are_not_guessed():
    assert ap.source_name(6) == "LFO 1" and ap.source_name(7) == "LFO 2"
    assert ap.source_name(2) == "Env 1" and ap.source_name(25) == "Macro 1"
    assert "nezmapováno" in ap.source_name(17)


def test_output_validates_against_schema(tmp_path):
    sys.path.insert(0, str(Path(__file__).parent))
    import check_repo
    f = tmp_path / "t.SerumPreset"
    f.write_bytes(make_blob(CB))
    a = ap.analyze(f, source_id="s-1")
    schema = json.loads((Path(__file__).parent.parent / "core" / "preset-analysis.schema.json").read_text(encoding="utf-8"))
    errs: list[str] = []
    check_repo.check_object(a, schema, "preset", errs)
    assert errs == []


def test_rejects_foreign_file(tmp_path):
    f = tmp_path / "x.SerumPreset"
    f.write_bytes(b"\x00\x05\x16\x07 not a preset")
    with pytest.raises(ValueError):
        ap.analyze(f, source_id="s-1")


def test_cli_requires_source_id(tmp_path, capsys):
    f = tmp_path / "t.SerumPreset"
    f.write_bytes(make_blob(CB))
    with pytest.raises(SystemExit):
        ap.main([str(f)])
    assert ap.main([str(f), "--summary"]) == 0
