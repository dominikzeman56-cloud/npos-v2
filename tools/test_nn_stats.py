import mido

import nn_stats as N

PPQ = 960


def write_mid(path, bpm, notes, name="Bass"):
    """notes: (začátek v dobách, délka v dobách, výška)."""
    m = mido.MidiFile(ticks_per_beat=PPQ)
    tempo = mido.MidiTrack()
    tempo.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    m.tracks.append(tempo)
    t = mido.MidiTrack()
    t.append(mido.MetaMessage("track_name", name=name, time=0))
    ev = []
    for s, d, p in notes:
        ev.append((round(s * PPQ), 1, p))
        ev.append((round((s + d) * PPQ), 0, p))
    ev.sort(key=lambda e: (e[0], e[1]))
    last = 0
    for tick, on, p in ev:
        t.append(mido.Message("note_on", note=p, velocity=100 if on else 0, time=tick - last))
        last = tick
    m.tracks.append(t)
    m.save(str(path))


def song(bars=16):
    """Call (1 | 1 | 1 | 1,1,0.5,0.5,1) o oktávu výš, potom rovné osminy o oktávu níž, tónika E."""
    notes = []
    for b in range(bars):
        s = 4 * b
        if b % 4 in (0, 1):
            notes += [(s, 1, 40), (s + 1, 1, 40), (s + 2, .5, 40), (s + 2.5, .5, 40), (s + 3, 1, 40)]
        else:
            notes += [(s + .5 * i, .5, 28) for i in range(8)]
    return notes


def test_grid_phase_finds_constant_offset():
    starts = [0.2 + 0.25 * i for i in range(20)]
    assert abs(N.grid_phase(starts) - 0.2) < 0.01


def test_classify_call_eighths_and_long():
    call = [(0, 1, 40, 100), (1, 1, 40, 100), (2, .5, 40, 100), (2.5, .5, 40, 100), (3, 1, 40, 100)]
    assert N.classify(call, 0)[0] == "call"
    eig = [(.5 * i, .5, 28, 100) for i in range(8)]
    assert N.classify(eig, 0)[0] == "eighths"
    assert N.classify([(0, 4, 40, 100)], 0)[0] == "long"
    six = [(.25 * i, .25, 28, 100) for i in range(16)]
    assert N.classify(six, 0)[0] == "sixteenths"


def test_analyse_counts_classes_and_octave_drop(tmp_path):
    p = tmp_path / "x_NNTranscription.mid"
    write_mid(p, 174, song(16))
    r, rows = N.analyse(p)
    assert r["bpm"] == 174.0 and r["bars"] == 16
    assert r["bar_classes"] == {"call": 8, "eighths": 8}
    assert r["call_to_eighths_octave_drops"] == 4
    assert r["roots_vs_tonic"] == {"0": 16}
    assert r["note_length_share"]["2"] > 0.5  # délky jsou v šestnáctinách: 2 = osmina


def test_too_few_bass_notes_is_skipped(tmp_path):
    p = tmp_path / "y_NNTranscription.mid"
    write_mid(p, 174, [(0, 1, 40), (1, 1, 40)])
    assert N.analyse(p) == (None, [])


def test_main_writes_numbers_only(tmp_path):
    write_mid(tmp_path / "z_NNTranscription.mid", 174, song(8))
    out = tmp_path / "o.json"
    assert N.main(["--dir", str(tmp_path), "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "NNTranscription" not in text and '"files": 1' in text
