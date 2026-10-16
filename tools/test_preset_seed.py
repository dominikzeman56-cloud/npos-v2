import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import preset_seed as ps  # noqa: E402
import serum_preset_io as sio  # noqa: E402

pytest.importorskip("cbor2")
pytest.importorskip("zstandard")


def preset(cut: float, vol: float = 0.5, mode: str = "A") -> dict:
    return {"VoiceFilter0": {"plainParams": {"kParamFreq": cut, "kParamType": mode}},
            "Oscillator0": {"plainParams": {"kParamVolume": vol, "kParamEnable": 1.0}},
            "Global0": {"plainParams": {"kParamMasterVolume": 0.7, "kParamPolyCount": 1.0}},
            "fileType": "SerumPreset"}


def corpus(n=30):
    return [preset(0.02 * i, 0.3 + 0.01 * i) for i in range(n)]


def test_roundtrip_recomputes_hash_and_keeps_content():
    meta = {"fileType": "SerumPreset", "presetName": "x", "hash": "stale"}
    blob = sio.write_preset(meta, preset(0.3))
    m2, cb = sio.read_preset(blob)
    assert m2["presetName"] == "x" and m2["hash"] != "stale" and cb["VoiceFilter0"]["plainParams"]["kParamFreq"] == 0.3
    assert sio.write_preset(m2, cb) == blob  # hash i bajty jsou deterministické
    with pytest.raises(ValueError):
        sio.read_preset(b"nope")


def test_plain_params_tolerates_odd_module_shapes():
    cb = {"A": {"plainParams": "text"}, "B": "x", "C": {"plainParams": None}, "D": {"plainParams": {"k": 1.0}}, "E": 5}
    assert list(sio.plain_params(cb)) == [("D", "k", 1.0)]


def test_ranges_only_for_continuous_params_and_never_list():
    r = ps.build_ranges(corpus())
    assert ("VoiceFilter", "kParamFreq") in r and ("Oscillator", "kParamVolume") in r
    assert ("Global", "kParamMasterVolume") not in r      # NEVER
    assert ("Oscillator", "kParamEnable") not in r        # konstanta = volba, ne spojitý parametr
    assert all(k[1] != "kParamType" for k in r)           # text


def test_mutate_stays_inside_range_changes_at_most_k_and_leaves_rest():
    cs = corpus()
    r = ps.build_ranges(cs)
    cb = preset(0.3, 0.5)
    muts = ps.mutate(cb, r, random.Random(3), k=1)
    assert len(muts) <= 1
    for m in muts:
        lo, hi = r[(sio.module_kind(m["module"]), m["param"])]
        assert min(lo, m["old"]) - 1e-9 <= m["new"] <= max(hi, m["old"]) + 1e-9
    assert cb["Global0"]["plainParams"] == {"kParamMasterVolume": 0.7, "kParamPolyCount": 1.0}
    assert cb["VoiceFilter0"]["plainParams"]["kParamType"] == "A"


def test_make_one_marks_derivation_and_is_deterministic():
    r = ps.build_ranges(corpus())
    meta, cb = {"fileType": "SerumPreset", "presetAuthor": "Someone", "tags": ["Mono"]}, preset(0.3)
    b1, log = ps.make_one(meta, cb, "src-1", "bass", r, random.Random(5), 2, "GEN bass s5-1")
    b2, _ = ps.make_one(meta, cb, "src-1", "bass", r, random.Random(5), 2, "GEN bass s5-1")
    assert b1 == b2 and log["derived_from"] == "src-1" and log["confidence"] == "hypothesis"
    m, _ = sio.read_preset(b1)
    assert m["presetAuthor"] == "NPOS generated" and "Generated" in m["tags"] and "derived_from src-1" in m["presetComment"]
    assert cb["VoiceFilter0"]["plainParams"]["kParamFreq"] == 0.3  # zdroj se nemění (deepcopy)


def test_output_dir_guard():
    assert ps.out_dir_ok(ps.LOCAL / "generated")
    assert not ps.out_dir_ok(ps.REPO / "data" / "presets" / "index")
    assert not ps.out_dir_ok(ps.REPO / "tools")
    assert ps.out_dir_ok(Path("D:/somewhere/else") if sys.platform == "win32" else Path("/tmp/x"))
