import xml.etree.ElementTree as ET

import midi_project as P


def ev(t, d=0.5):
    return f'<MidiNoteEvent Time="{t}" Duration="{d}" Velocity="100" IsEnabled="true"/>'


def doc(clips):
    body = "".join(
        f'<MidiClip><CurrentStart Value="{s}"/><CurrentEnd Value="{e}"/><Loop><LoopStart Value="0"/><LoopEnd Value="{ln}"/></Loop>'
        f'<Notes><KeyTracks><KeyTrack><Notes>{"".join(ev(t) for t in ts)}</Notes><MidiKey Value="{k}"/></KeyTrack></KeyTracks></Notes></MidiClip>'
        for s, e, ln, ts, k in clips)
    return ET.fromstring(f'<Ableton><LiveSet><Tracks><MidiTrack Id="1"><Name><EffectiveName Value="Bass"/></Name>{body}</MidiTrack></Tracks></LiveSet></Ableton>')


def test_grid_marks_hits_and_off_grid():
    assert P.grid([(0, .25, 36, 100), (0.75, .25, 36, 100), (1.6, .25, 36, 100)], 2.0) == "x..x..+."


def test_pitch_names_follow_live_convention():
    assert P.pitch_name(60) == "C3" and P.pitch_name(24) == "C0" and P.pitch_name(37) == "C#1"


def test_same_pattern_gets_one_id_and_positions():
    cl = P.clips(doc([(0, 4, 4, [0, 0.75], 38), (8, 12, 4, [0, 0.75], 38), (12, 16, 4, [0, 1.0], 38)]))
    r = P.report(cl)["Bass"]
    assert r["clips"] == 3 and len(r["patterns"]) == 2
    first = r["patterns"][0]
    assert [u["at"] for u in first["uses"]] == ["1|1", "3|1"] and first["grid"] == "x..x............"


def test_track_filter_and_clips_without_arrangement_skipped():
    cl = P.clips(doc([(0, 4, 4, [0], 38)]))
    assert P.report(cl, "zzz") == {} and "Bass" in P.report(cl, "bas")
