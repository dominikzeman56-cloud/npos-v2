import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
np = pytest.importorskip("numpy")
pytest.importorskip("scipy")
import stem_to_live as sl  # noqa: E402

SR = sl.SR


def _clicks(times, dur, f0, decay=30.0, amp=0.8):
    """Krátké tlumené tóny na daných časech (kick = nízký tón, snare = šum by byl dražší, stačí vysoký tón)."""
    t = np.arange(int(dur * SR)) / SR
    x = np.zeros_like(t)
    for t0 in times:
        m = t >= t0
        d = t[m] - t0
        x[m] += amp * np.sin(2 * np.pi * f0 * d) * np.exp(-decay * d) * (1 - np.exp(-d / 0.0005))
    return x


def test_hits_text_numbers_bars_from_clip_start():
    steps = [16 * 8, 16 * 8 + 10, 16 * 9, 16 * 20]            # takty 9, 9, 10 a 21
    assert sl.hits_text(steps, 9, 16, "C1") == "v100 n1/16 C1 1|1,3.5 2|1"
    assert sl.hits_text(steps, 30, 40, "C1") == ""


def test_snare_fix_moves_early_detections_onto_the_beat():
    assert sl.snare_fix([3, 4, 11, 12, 19]) == [4, 12, 20]


def test_bar_offset_finds_downbeat_from_kick_and_snare():
    kick = [o + 16 * b + 5 for b in range(8) for o in (0, 10)]
    snare = [o + 16 * b + 5 for b in range(8) for o in (4, 12)]
    assert sl.bar_offset(kick, snare) == 5


def test_held_notes_smooth_blips_and_break_on_bar_lines():
    steps = [29] * 7 + [30] + [29] * 8 + [29] * 12 + [None] * 4       # takt 1 celý (s jedním škubnutím), takt 2 tři doby
    notes = sl.held_notes(steps, 1, 2)
    assert notes == [(0, 16, 29), (16, 12, 29)]
    assert sl.notes_text(notes, 1) == "v100 n16/16 F0 1|1 n12/16 F0 2|1"
    assert sl.held_notes([None] * 32, 1, 2) == []


def test_rhythm_notes_merge_double_onsets_and_stop_at_silence():
    active = [True] * 3 + [False] * 5 + [True] * 8
    notes = sl.rhythm_notes([0, 1, 8], active, 1, 1, 41)
    assert notes == [(0, 3, 41), (8, 8, 41)]


def test_active_ranges_close_small_gaps_and_drop_short_runs():
    bars = list(range(9, 15)) + list(range(16, 25)) + [40, 41]
    assert sl.active_ranges(bars) == [(9, 24)]


def test_grid_phase_and_steps():
    s16 = 15.0 / 172
    on = np.array([0.02 + k * 4 * s16 for k in range(20)])
    ph, err = sl.grid_phase(on, s16)
    assert abs(ph - 0.02) < 0.001 and err < 0.02
    assert sl.to_steps(on, ph, s16)[:3] == [0, 4, 8]


def test_estimate_bpm_on_click_track():
    beat = 60.0 / 172
    x = _clicks([k * beat for k in range(0, 80, 2)], 30.0, 100.0, decay=15.0) + _clicks([k * beat for k in range(1, 80, 2)], 30.0, 3000.0, decay=60.0)
    assert sl.estimate_bpm(x, 150, 190) == pytest.approx(172.0, abs=0.3)


def test_build_plan_from_synthetic_stems():
    bpm = 172.0
    bar, s16 = 240.0 / bpm, 15.0 / bpm
    dur = 12 * bar + 0.5
    off = 0.2                                   # soubor nezačíná přesně na jedničce
    kick = _clicks([off + b * bar + o * s16 for b in range(12) for o in (0, 10)], dur, 100.0, decay=15.0)
    snare = _clicks([off + b * bar + o * s16 for b in range(12) for o in (4, 12)], dur, 3000.0, decay=60.0)
    t = np.arange(int(dur * SR)) / SR
    sub = 0.4 * np.sin(2 * np.pi * 43.65 * t) * ((t >= off + 2 * bar) & (t < off + 11 * bar))          # F od taktu 3 do 11
    plan = sl.build_plan({"kick": kick, "snare": snare, "sub": sub}, sl.BANDS, bpm, "stems")
    assert plan["grid_source"] == "kick" and plan["grid_error_steps"] < 0.1 and abs(plan["bar1_sec"] - off) < s16 / 2
    assert plan["ranges"] == [[3, 11]] and plan["sub_notes"][0]["note"] == "F0"
    by = {c["role"]: c for c in plan["clips"]}
    assert by["kick"]["notes"].startswith("v100 n1/16 C1 1|1,3.5 2|1,3.5")
    assert "1|2,4" in by["snare"]["notes"]
    assert by["sub"]["notes"].startswith("v100 n16/16 F0 1|1")
    assert "mids" not in by
