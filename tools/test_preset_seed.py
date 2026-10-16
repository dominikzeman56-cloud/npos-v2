import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import preset_seed as ps  # noqa: E402
import serum_preset_io as sio  # noqa: E402

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


def test_codec_keeps_float32_width_and_is_byte_exact():
    cb = {"a": {"plainParams": {"x": sio.F32(0.25), "y": 0.1, "z": 7, "n": -3, "s": "t", "b": True}}, "l": [sio.F32(1.5), 2, None],
          "big": {str(i): i for i in range(300)}}
    parts: list[bytes] = []
    sio._encode(cb, parts)
    raw = b"".join(parts)
    back, end = sio._decode(raw)
    assert end == len(raw) and back == cb
    assert isinstance(back["a"]["plainParams"]["x"], sio.F32) and not isinstance(back["a"]["plainParams"]["y"], sio.F32)
    parts2: list[bytes] = []
    sio._encode(back, parts2)
    assert b"".join(parts2) == raw
    assert raw[raw.index(b"\x61x") + 2] == 0xFA and raw[raw.index(b"\x61y") + 2] == 0xFB  # x je float32, y float64


def test_mutated_float32_stays_float32():
    cb = {"VoiceFilter0": {"plainParams": {"kParamFreq": sio.F32(0.3)}}}
    cs = [{"VoiceFilter0": {"plainParams": {"kParamFreq": sio.F32(0.02 * i)}}} for i in range(30)]
    ms = ps.mutate(cb, ps.build_ranges(cs), random.Random(1), k=1)
    assert ms and isinstance(cb["VoiceFilter0"]["plainParams"]["kParamFreq"], sio.F32)


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
    assert ps.out_dir_ok(ps.REPO.parent / "elsewhere-output")
    assert not ps.out_dir_ok(Path(r"\\localhost\share\x"))         # UNC cesta může vést zpět do repa


def test_role_ranges_need_ten_presets_and_override_global():
    bass = [({"role": "bass"}, None, preset(0.02 * i)) for i in range(12)]           # kParamFreq 0..0,22
    lead = [({"role": "lead"}, None, preset(0.5 + 0.02 * i)) for i in range(12)]     # 0,5..0,72
    few = [({"role": "pad"}, None, preset(0.9))]
    by = ps.build_ranges_by_role(bass + lead + few)
    assert set(by) == {"bass", "lead"}                                              # pad má 1 preset, bez rozsahu
    g = ps.build_ranges([cb for _, _, cb in bass + lead])
    rb = ps.ranges_for("bass", g, by)
    assert rb[("VoiceFilter", "kParamFreq")][1] < 0.3 < g[("VoiceFilter", "kParamFreq")][1]
    assert ps.ranges_for("pad", g, by) == g


def test_sanity_gate():
    src = {"silent": False, "rms_db": -10.0, "centroid_hz": 200.0}
    assert ps.sane(src, {"silent": False, "rms_db": -12.0, "centroid_hz": 300.0})[0]
    assert ps.sane(src, {"silent": True, "rms_db": -60.0})[1] == "ticho"
    assert not ps.sane(src, {"silent": False, "rms_db": -20.0, "centroid_hz": 200.0})[0]
    assert not ps.sane(src, {"silent": False, "rms_db": -10.0, "centroid_hz": 700.0})[0]
    assert not ps.sane(src, {"silent": False, "rms_db": -10.0, "centroid_hz": 50.0})[0]


def test_integer_valued_and_curve_params_are_never_mutated():
    cs = []
    for i in range(30):
        cs.append({"Oscillator1": {"plainParams": {"kParamOctave": float(i % 8 - 4), "kParamUnison": float(2 + i % 10), "kParamVolume": 0.3 + 0.01 * i}},
                   "Env0": {"plainParams": {"kParamCurve1": 30.0 + i, "kParamAttack": 0.001 * (i + 1)}}})
    r = ps.build_ranges(cs)
    assert ("Oscillator", "kParamVolume") in r and ("Env", "kParamAttack") in r
    assert ("Oscillator", "kParamOctave") not in r and ("Oscillator", "kParamUnison") not in r and ("Env", "kParamCurve1") not in r


def test_noise_and_sub_oscillators_have_their_own_ranges():
    cs = [{"Oscillator1": {"plainParams": {"kParamVolume": 0.5 + 0.01 * i}}, "Oscillator3": {"plainParams": {"kParamVolume": 0.05 + 0.002 * i}},
           "Oscillator4": {"plainParams": {"kParamVolume": 0.2 + 0.004 * i}}} for i in range(30)]
    r = ps.build_ranges(cs)
    assert {("Oscillator", "kParamVolume"), ("OscNoise", "kParamVolume"), ("OscSub", "kParamVolume")} <= set(r)
    assert r[("OscNoise", "kParamVolume")][1] < r[("Oscillator", "kParamVolume")][0]


def test_mutation_never_silences_or_inverts_and_fills_k_changes():
    cs = [{"ModSlot0": {"plainParams": {"kParamAmount": -50.0 + 4 * i}}, "Oscillator0": {"plainParams": {"kParamVolume": 0.01 * i + 0.01}},
           "VoiceFilter0": {"plainParams": {"kParamFreq": 0.02 * i}}, "LFO0": {"plainParams": {"kParamRate": 0.5 + i}}} for i in range(30)]
    r = ps.build_ranges(cs)
    for seed in range(60):
        cb = {"ModSlot0": {"plainParams": {"kParamAmount": 40.0}}, "Oscillator0": {"plainParams": {"kParamVolume": 0.2}},
              "VoiceFilter0": {"plainParams": {"kParamFreq": 0.5}}, "LFO0": {"plainParams": {"kParamRate": 5.0}}}
        before = {m: dict(b["plainParams"]) for m, b in cb.items()}
        muts = ps.mutate(cb, r, random.Random(seed), k=4, spread=0.6)
        assert len(muts) >= 3, muts                                    # k se doplňuje, kandidáti na hranici nevadí
        assert cb["ModSlot0"]["plainParams"]["kParamAmount"] >= 4.0 and cb["Oscillator0"]["plainParams"]["kParamVolume"] >= 0.02
        assert before["ModSlot0"]["kParamAmount"] > 0 and cb["ModSlot0"]["plainParams"]["kParamAmount"] > 0


def test_files_are_never_overwritten(tmp_path):
    (tmp_path / "GEN bass s1-1 abc.SerumPreset").write_bytes(b"x")
    p = ps.free_path(tmp_path, "GEN bass s1-1 abc")
    assert p.name == "GEN bass s1-1 abc (2).SerumPreset"


def test_derived_preset_keeps_original_author_in_description():
    r = ps.build_ranges(corpus())
    blob, log = ps.make_one({"fileType": "SerumPreset", "presetName": "Orig", "presetAuthor": "Someone"}, preset(0.3), "id-1", "bass", r, random.Random(2), 2, "GEN bass s2-1")
    m, _ = sio.read_preset(blob)
    assert "Orig" in m["presetDescription"] and "Someone" in m["presetDescription"] and m["presetAuthor"] == "NPOS generated"


def test_seed_plan_parsing_and_diverse_picking(tmp_path):
    assert ps.parse_plan("bass=12,lead=10,stab=8") == {"bass": 12, "lead": 10, "stab": 8}
    for bad in ("bass", "bass=0", "bass=x", "=3", "bass=101"):
        with pytest.raises(ValueError):
            ps.parse_plan(bad)
    items = []
    for g, n in (("A", 6), ("B", 2), ("C", 1)):
        d = tmp_path / g
        d.mkdir()
        for i in range(n):
            f = d / f"BS {g}{i}.SerumPreset"
            f.write_bytes(b"x")
            items.append(({"id": f"{g}{i}", "role": "bass"}, f))
    big = tmp_path / "A" / "BS huge.SerumPreset"
    big.write_bytes(b"x" * (ps.MAX_SEED_BYTES + 1))
    gen = tmp_path / "A" / "GEN bass s1-1.SerumPreset"
    gen.write_bytes(b"x")
    kit = tmp_path / "C" / "KIT - 808 Basic Kit.SerumPreset"
    kit.write_bytes(b"x")
    items += [({"id": "H", "role": "bass"}, big), ({"id": "G", "role": "bass"}, gen), ({"id": "K", "role": "bass"}, kit)]
    picked = ps.pick_seeds(items, {"bass": 4})
    names = [f.parent.name for _, f in picked]
    assert len(picked) == 4 and set(names) == {"A", "B", "C"}          # střídá složky, nebere jednu dokola
    assert not any(f in (big, gen, kit) for _, f in picked)             # obří soubory, vlastní výstupy a kity ne
    assert [f for _, f in ps.pick_seeds(items, {"bass": 4})] == [f for _, f in picked]   # deterministické
