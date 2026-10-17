import numpy as np
import soundfile as sf

import stem_grid as S

SR = 22050


def click_track(bpm, bars, hits, freq=80.0, ph=0.37):
    """Syntetické bicí: tón o dané frekvenci na zadaných šestnáctinách každého taktu, posun ph sekund."""
    bar = 240.0 / bpm
    x = np.zeros(int((bars * bar + ph + 1) * SR), dtype=np.float32)
    n = int(0.08 * SR)
    t = np.arange(n) / SR
    burst = (np.sin(2 * np.pi * freq * t) * np.exp(-t * 40)).astype(np.float32)
    for b in range(bars):
        for h in hits:
            i = int((ph + b * bar + h * bar / 16) * SR)
            x[i:i + n] += burst[: len(x) - i][:n]
    return x


def test_gap_signature():
    assert S.gap_signature("x.........x.....") == "10-6"
    assert S.gap_signature("....x.......x...") == "8-8"
    assert S.gap_signature("x...............") == "16"
    assert S.gap_signature("................") == ""


def test_runs():
    assert S.runs([False, True, True, False, True]) == [(2, 3), (5, 5)]


def test_kick_grid_and_tempo_recovered(tmp_path):
    drums = click_track(174.0, 16, [0, 10], freq=70.0)
    sf.write(tmp_path / "drums.wav", drums, SR)
    r = S.analyze(tmp_path, 174.3)
    assert abs(r["bpm"] - 174.0) < 0.25 and r["bars"] >= 15
    mid = r["grids"]["kick"][4:12]
    assert all(g == "x.........x....." for g in mid), mid


def test_snare_band_separated_from_kick(tmp_path):
    kick = click_track(174.0, 12, [0, 10], freq=70.0)
    snare = click_track(174.0, 12, [4, 12], freq=3000.0)
    sf.write(tmp_path / "drums.wav", kick + snare, SR)
    r = S.analyze(tmp_path, 174.0)
    assert all(g == "....x.......x..." for g in r["grids"]["snare"][3:9]), r["grids"]["snare"][3:9]
    assert all(g == "x.........x....." for g in r["grids"]["kick"][3:9]), r["grids"]["kick"][3:9]


def test_bar_activity_marks_silence(tmp_path):
    drums = click_track(174.0, 12, [0, 8], freq=70.0)
    bar = int(240.0 / 174.0 * SR)
    drums[int(0.37 * SR) + 6 * bar: int(0.37 * SR) + 9 * bar] = 0
    sf.write(tmp_path / "drums.wav", drums, SR)
    r = S.analyze(tmp_path, 174.0)
    runs = r["active_runs"]["drums"]
    assert runs[0][0] == 1 and len(runs) >= 2


def test_custom_file_names(tmp_path):
    sf.write(tmp_path / "beat-drums group.wav", click_track(174.0, 12, [0, 10], freq=70.0), SR)
    r = S.analyze(tmp_path, 174.0, {"drums": tmp_path / "beat-drums group.wav"})
    assert r["bars"] >= 11 and r["grids"]["kick"][5] == "x.........x....."
