import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import midi_skeleton as S
import midi_stats as M


def _gen(seed=1, bars=8, density=2, layers=None, key="F", scale="minor"):
    return S.generate(S.parse_key(key), scale, bars, seed, density, layers or S.DEFAULT_LAYERS)


def test_deterministic_per_seed():
    assert _gen(seed=7) == _gen(seed=7)
    assert _gen(seed=7) != _gen(seed=8)


def test_notes_inside_clip_and_valid_midi_range():
    for bars in (4, 8, 16):
        for name, notes in _gen(bars=bars, layers=list(S.LAYERS)).items():
            assert notes, name
            for start, dur, pitch, vel in notes:
                assert 0 <= start and start + dur <= bars * 4 + 1e-9, (name, start, dur)
                assert 0 <= pitch <= 127 and 1 <= vel <= 127, (name, pitch, vel)


def test_drum_grid_matches_measured_basics():
    made = _gen(bars=8)
    kicks = {t % 4 for t, *_ in made["kick"]}
    assert 0.0 in kicks and 2.5 in kicks  # 1. doba a "and" 3. doby
    snare_first_bars = {t % 4 for t, *_ in made["snare"] if t < 28}
    assert snare_first_bars == {1.0, 3.0} or snare_first_bars >= {1.0, 3.0}
    assert {n[2] for n in made["sc"]} == {36}


def test_sub_is_monophonic_and_in_scale():
    key = S.parse_key("C#")
    made = S.generate(key, "phrygian", 8, 3, 2, ["sub"])
    notes = sorted(made["sub"])
    for a, b in zip(notes, notes[1:]):
        assert a[0] + a[1] <= b[0] + 1e-9  # žádný překryv
    allowed = {(key + i) % 12 for i in S.SCALES["phrygian"]}
    assert {p % 12 for _s, _d, p, _v in notes} <= allowed


def test_midi_roundtrip_with_existing_reader(tmp_path):
    made = _gen(layers=["sub", "kick"])
    S.write_midi(tmp_path / "x.mid", {"sub": made["sub"]}, 174.0)
    back = M.read_smf((tmp_path / "x.mid").read_bytes())
    assert len(back) == len(made["sub"])
    first = sorted(back)[0]
    assert abs(first[0] - 0.0) < 1e-6 and first[2] == made["sub"][0][2]


def test_barbeat_tokens():
    assert S.note_name(60) == "C3" and S.note_name(29) == "F0"
    assert S.dur_token(4.0) == "1bar" and S.dur_token(1.0) == "n/4"
    assert S.dur_token(0.25) == "n/16" and S.dur_token(3.5) == "n7/8"
    assert S.to_barbeat([(5.5, 1.0, 36, 100)]) == "v100 n/4 C1 2|2.5"


def test_cli_writes_expected_files(tmp_path):
    out = tmp_path / "k"
    assert S.main(["--name", "T", "--key", "A", "--seed", "5", "--bars", "4", "--out", str(out)]) == 0
    names = {p.name for p in out.iterdir()}
    assert {"00_ALL_TRACKS.mid", "skeleton.json", "PPAL_notes.md", "01_sub_bass_4bar.mid", "08_lead_4bar.mid"} <= names
