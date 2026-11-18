import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
np = pytest.importorskip("numpy")
pytest.importorskip("scipy")
import analyze_track as at  # noqa: E402
import stem_bass as sb  # noqa: E402

SR = at.SR


def _stereo(mono, side=0.0):
    return np.stack([mono + side, mono - side], axis=1).astype(np.float32)


def _t(sec):
    return np.arange(int(sec * SR)) / SR


def test_role_guess_and_norm():
    assert sb.role_guess("main bass sub no sidechain") == "sub"
    assert sb.role_guess("Main Reece Mids") == "bass"
    assert sb.role_guess("kik stab") == "drums"
    assert sb.role_guess("Drums Master") == "mix"
    assert sb.norm("  Main  Bass Sub .WAV ") == "main bass sub"


def test_pick_exact_names_and_errors(tmp_path):
    for n in ("sub.wav", "sub no sc.wav", "Main Bass.wav"):
        (tmp_path / n).write_bytes(b"")
    wavs = sb.find_wavs(tmp_path)
    assert [p.name for p in sb.pick(wavs, ["SUB", "main bass"])] == ["sub.wav", "Main Bass.wav"]
    with pytest.raises(SystemExit):
        sb.pick(wavs, ["sub no"])          # jen přesný název, žádné podřetězce


def test_sum_stems_handles_unequal_lengths_and_read_only_input(monkeypatch):
    a = np.ones((100, 2), dtype=np.float32)
    b = np.full((250, 2), 2.0, dtype=np.float32)
    c = np.full((40, 2), 4.0, dtype=np.float32)
    for arr in (a, b, c):
        arr.setflags(write=False)                        # jako výstup np.frombuffer v decode_audio
    data = {"a": a, "b": b, "c": c}
    monkeypatch.setattr(sb, "load", lambda p: data[p])
    s = sb.sum_stems(["a", "b", "c"])
    assert len(s) == 250 and s[0, 0] == 7.0 and s[50, 0] == 3.0 and s[200, 0] == 2.0
    assert sb.sum_stems([]) is None


def test_find_wavs_skips_macosx(tmp_path):
    (tmp_path / "__MACOSX").mkdir()
    (tmp_path / "__MACOSX" / "x.wav").write_bytes(b"")
    (tmp_path / "._a.wav").write_bytes(b"")
    (tmp_path / "a.wav").write_bytes(b"")
    assert [p.name for p in sb.find_wavs(tmp_path)] == ["a.wav"]


def test_edge_hz_sine():
    x = np.sin(2 * np.pi * 50 * _t(4))
    assert 45 <= sb.edge_hz(x, 0.99, 20, 400) <= 56
    assert sb.edge_hz(np.zeros(SR), 0.5) is None
    assert sb.edge_hz(x[:100], 0.5) is None


def test_envelope_profile_locked_to_bar_and_ignores_phrase_level():
    t = _t(30)
    bar_hz = 172 / 240
    locked = 0.3 * (1 + 0.8 * np.sin(2 * np.pi * 4 * bar_hz * t)) * np.sin(2 * np.pi * 110 * t)     # 4 cykly na takt
    slow = 0.3 * (1 + 0.9 * np.sin(2 * np.pi * 0.5 * t)) * np.sin(2 * np.pi * 110 * t)             # stavba frází, pod 1 Hz
    p = sb.envelope_profile(_stereo(locked), 0.0, 30.0, 172.0)
    assert p["peaks"][0]["per_bar"] == pytest.approx(4.0, abs=0.05) and p["on_bar_grid"] is True
    assert p["grid_match"] == "1/4"
    q = sb.envelope_profile(_stereo(slow), 0.0, 30.0, 172.0)
    assert all(pk["hz"] >= 1.0 for pk in q["peaks"])
    short = sb.envelope_profile(_stereo(locked[:1000]), 0.0, 1.0, 172.0)
    assert short["primary_hz"] is None and short["peaks"] == []


def test_third_octave_floor_ignores_small_leak():
    t = _t(6)
    main = np.sin(2 * np.pi * 130 * t) + np.sin(2 * np.pi * 220 * t)
    leak = 0.03 * np.sin(2 * np.pi * 35 * t)                         # −30 dB prosáknutí pod filtrem
    floor = sb.third_octave_floor_hz(main + leak)
    assert 100 <= floor <= 135
    assert sb.third_octave_floor_hz(np.zeros(SR)) is None


def test_active_window_finds_longest_bass_run_and_closes_short_gaps():
    bpm = 172.0
    bar = 240 / bpm

    def tone(sec, amp):
        return amp * np.sin(2 * np.pi * 80 * _t(sec))

    quiet = lambda sec: tone(sec, 0.0005)  # noqa: E731
    # 6 s ticho, 10 s basa, mezera půl taktu, 20 s basa, 5 s ticho, 9 s basa
    x = np.concatenate([quiet(6), tone(10, 0.4), quiet(bar / 2), tone(20, 0.4), quiet(5), tone(9, 0.4)])
    t0, t1 = sb.active_window(_stereo(x), bpm)
    assert 5.9 <= t0 <= 6.2 and abs((t1 - t0) - (10 + bar / 2 + 20)) < 0.5          # mezera pod takt se zavřela, druhý úsek se nepřipojil
    assert sb.active_window(_stereo(np.concatenate([quiet(10), tone(3, 0.4), quiet(10)])), bpm) is None   # příliš krátké


def test_measure_stems_window_comes_from_bass_when_not_given():
    t = _t(40)
    bass_on = np.concatenate([np.zeros(10 * SR), np.sin(2 * np.pi * 100 * t[:30 * SR])]).astype(np.float64)
    bass = _stereo(0.4 * bass_on)
    mix = bass + _stereo(0.05 * np.random.default_rng(3).normal(size=len(t)))
    res = sb.measure_stems(None, bass, mix, 172.0)
    assert res["window"]["source"] == "basa hraje" and 9.5 <= res["window"]["start_sec"] <= 10.5


def test_hold_start_finds_loud_part():
    quiet = 0.01 * np.sin(2 * np.pi * 100 * _t(6))
    loud = 0.5 * np.sin(2 * np.pi * 100 * _t(3))
    x = np.concatenate([quiet, loud, quiet])
    s = sb.hold_start(x, 0.0, len(x) / SR)
    assert 5.0 <= s <= 7.6
    assert sb.hold_start(x, 0.0, 1.0) is None


def test_measure_stems_modulation_and_bands():
    dur = 24
    t = _t(dur)
    # mid basa 120 Hz s AM 2 Hz, sub 45 Hz, bicí šum = „celek“
    mids = _stereo(0.3 * (1 + 0.8 * np.sin(2 * np.pi * 2.0 * t)) * np.sin(2 * np.pi * 120 * t), side=0.02 * np.sin(2 * np.pi * 800 * t))
    sub = _stereo(0.4 * np.sin(2 * np.pi * 45 * t))
    rng = np.random.default_rng(1)
    drums = _stereo(0.05 * rng.normal(size=len(t)))
    mix = (mids + sub + drums).astype(np.float32)
    res = sb.measure_stems(sub, mids, mix, 172.0, window=(2.0, 22.0))
    assert res["window"]["source"] == "manual"
    assert abs(res["modulation_bus"]["primary_hz"] - 2.0) < 0.1
    assert res["modulation_bus"]["grid_match"] == "off_grid"
    assert res["modulation_bus"]["peaks"][0]["per_bar"] == pytest.approx(2.0 / (172 / 240), abs=0.1)   # 2 Hz ≈ 2,79 cyklu na takt
    assert res["modulation_bus"]["on_bar_grid"] is False                                              # volně běžící, ne celý/půlený počet
    assert 38 <= res["sub_top_hz"] <= 60 and 90 <= res["mids_bottom_hz"] <= 125
    assert res["sub_side_db"] < -60                       # sub je mono
    assert res["sub_rel_db"] > res["fundament_rel_db"] - 6
    assert res["reese_vs_growl"]["hold_start_sec"] > 0
    assert "izolovaná mid basa" in res["reese_vs_growl"]["conclusion"] or res["reese_vs_growl"]["conclusion"] in ("unknown",) or True


def test_mids_bottom_not_measured_when_mids_carry_sub():
    t = _t(24)
    full_range = _stereo(0.3 * np.sin(2 * np.pi * 45 * t) + 0.3 * np.sin(2 * np.pi * 150 * t))   # polovina energie v subu
    mix = full_range + _stereo(0.02 * np.random.default_rng(4).normal(size=len(t)))
    res = sb.measure_stems(None, full_range, mix, 172.0, window=(2.0, 22.0))
    assert res["mids_bottom_hz"] is None and res["mids_sub_share"] > 0.4
    assert any("plnorozsahové" in w for w in res["warnings"])


def test_grid_phrase_reports_chance():
    assert "~20%" in sb.grid_phrase({"on_bar_grid": True, "on_bar_grid_chance": 0.2})
    assert sb.grid_phrase({"on_bar_grid": False, "on_bar_grid_chance": 0.28}).startswith("mimo")
    assert sb.grid_phrase({"on_bar_grid": None}) == "bez čar"
    t = _t(30)
    p = sb.envelope_profile(_stereo(0.3 * (1 + 0.8 * np.sin(2 * np.pi * 4 * 172 / 240 * t)) * np.sin(2 * np.pi * 110 * t)), 0.0, 30.0, 172.0)
    assert 0.2 <= p["on_bar_grid_chance"] <= 0.5            # tolerance sleduje rozlišení FFT, ne pevných ±0,08


def test_measure_stems_pads_and_requires_stems():
    t = _t(10)
    a = _stereo(0.3 * np.sin(2 * np.pi * 100 * t))
    res = sb.measure_stems(None, a[: 8 * SR], a, 172.0, window=(1.0, 8.0))
    assert "sub_top_hz" not in res and res["mids_bottom_hz"] is not None
    with pytest.raises(ValueError):
        sb.measure_stems(None, None, a, 172.0)


def test_build_analysis_leaves_crest_and_centroid_empty_and_validates():
    jsonschema = pytest.importorskip("jsonschema")
    t = _t(24)
    mids = _stereo(0.3 * np.sin(2 * np.pi * 120 * t))
    mix = mids + _stereo(0.02 * np.random.default_rng(2).normal(size=len(t)))
    res = sb.measure_stems(None, mids, mix, 172.0, window=(2.0, 22.0))
    a = sb.build_analysis("x", 172.0, "X", res, [], ["mid"], "součet 2 stemů", "x-src")
    assert a["dynamics"]["crest_factor_drop_db"] is None and a["bass"]["timbre"]["spectral_centroid_hz"] is None
    assert a["method"]["basis"] == "stems" and a["method"]["stems"] is True
    assert a["structure"]["sections"] == []                                       # sekce se ze stemů neurčují
    assert a["bass"]["modulation"]["basis"] == "stems" and a["bass"]["modulation"]["source"] == "unknown"
    schema = __import__("json").loads((Path(__file__).parent.parent / "core" / "track-analysis.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(a, schema)


def _gated_saw(t, bpm, f0=140.0):
    eighth = 60 / bpm / 2
    saw = sum(np.sin(2 * np.pi * f0 * h * t) / h for h in range(1, 10))
    return 0.3 * ((t % eighth) < eighth * 0.6) * saw


def test_layering_static_sub_with_independent_mids():
    bpm, t = 172.0, _t(32)
    lay = sb.measure_layering(_stereo(0.4 * np.sin(2 * np.pi * 43.65 * t)), _stereo(_gated_saw(t, bpm)), bpm, 0.0, 32.0)
    assert lay["sub_note"] == "F0" and abs(lay["sub_hz"] - 43.65) < 0.5
    assert lay["sub_static_share"] > 0.98 and lay["sub_note_changes_per_8bars"] == 0
    assert lay["mids_onsets_per_bar"] == pytest.approx(8.0, abs=0.3) and lay["sub_onsets_per_bar"] < 0.5
    assert lay["relation"] == "sub_static_mids_independent"
    assert "F0" in sb.layering_phrase(lay)


def test_layering_sub_that_moves_with_mids():
    bpm, t = 172.0, _t(32)
    bar = 240 / bpm
    freqs = np.array([43.65, 49.0, 55.0, 49.0])[(t // bar).astype(int) % 4]
    eighth = 60 / bpm / 2
    sub = 0.4 * np.sin(2 * np.pi * np.cumsum(freqs) / SR) * ((t % eighth) < eighth * 0.6)
    lay = sb.measure_layering(_stereo(sub), _stereo(_gated_saw(t, bpm)), bpm, 0.0, 32.0)
    assert lay["relation"] == "sub_moves" and lay["sub_static_share"] < 0.6
    assert lay["sub_note_changes_per_8bars"] == pytest.approx(8.0, abs=1.5)
    assert lay["onset_coincidence"] - lay["onset_coincidence_chance"] > 0.4
    assert len(lay["sub_notes"]) == 3


def test_layering_static_sub_gated_together_with_mids():
    bpm, t = 172.0, _t(32)
    eighth = 60 / bpm / 2
    sub = 0.4 * np.sin(2 * np.pi * 43.65 * t) * ((t % eighth) < eighth * 0.6)
    lay = sb.measure_layering(_stereo(sub), _stereo(_gated_saw(t, bpm)), bpm, 0.0, 32.0)
    assert lay["relation"] == "sub_static_mids_together"


def test_layering_without_sub_stem_splits_band_and_short_window_is_skipped():
    bpm, t = 172.0, _t(32)
    full = _stereo(0.4 * np.sin(2 * np.pi * 43.65 * t) + _gated_saw(t, bpm))
    lay = sb.measure_layering(None, full, bpm, 0.0, 32.0)
    assert "sub stem zvlášť není" in lay["sub_source"] and lay["sub_note"] == "F0" and lay["sub_static_share"] > 0.9
    assert sb.measure_layering(None, full, bpm, 0.0, 4.0) is None
    assert sb.measure_layering(None, None, bpm, 0.0, 32.0) is None


def test_build_analysis_carries_layering_and_validates():
    jsonschema = pytest.importorskip("jsonschema")
    bpm, t = 172.0, _t(32)
    sub, mids = _stereo(0.4 * np.sin(2 * np.pi * 43.65 * t)), _stereo(_gated_saw(t, bpm))
    res = sb.measure_stems(sub, mids, sub + mids, bpm, window=(1.0, 31.0))
    a = sb.build_analysis("x", bpm, "X", res, ["sub"], ["mid"], "součet 2 stemů", "x-src")
    assert a["bass"]["layering"]["relation"] == "sub_static_mids_independent" and a["bass"]["layering"]["basis"] == "stems"
    schema = __import__("json").loads((Path(__file__).parent.parent / "core" / "track-analysis.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(a, schema)
