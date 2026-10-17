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


def mk(start, end, loop, times, key=36, loop_on="true", rel=0):
    notes = "".join(ev(t) for t in times)
    return (f'<MidiClip><CurrentStart Value="{start}"/><CurrentEnd Value="{end}"/><Loop><LoopStart Value="0"/><LoopEnd Value="{loop}"/>'
            f'<StartRelative Value="{rel}"/><LoopOn Value="{loop_on}"/></Loop>'
            f'<Notes><KeyTracks><KeyTrack><Notes>{notes}</Notes><MidiKey Value="{key}"/></KeyTrack></KeyTracks></Notes></MidiClip>')


def doc2(*clips_xml):
    return ET.fromstring('<Ableton><LiveSet><Tracks><MidiTrack Id="1"><Name><EffectiveName Value="Kick"/></Name>' + "".join(clips_xml)
                         + '</MidiTrack></Tracks></LiveSet></Ableton>')


def test_timeline_unrolls_loop_to_clip_end():
    cl = P.clips(doc2(mk(0, 8, 2, [0, 1])))   # smyčka 2 doby, klip 8 dob = 2 takty
    tl = P.timeline(cl, "Kick")
    assert "".join(tl[1]["cells"]) == "x...x...x...x..." and "".join(tl[2]["cells"]) == "x...x...x...x..."


def test_timeline_merges_clips_and_marks_off_grid():
    cl = P.clips(doc2(mk(0, 4, 4, [0]), mk(4.5, 5.5, 1, [0.1], 38)))
    tl = P.timeline(cl, "Kick")
    assert tl[1]["cells"][0] == "x" and tl[2]["cells"][2] == "+" and tl[2]["pitches"] == {38}


def test_timeline_loop_off_plays_once_and_start_relative_wraps():
    once = P.timeline(P.clips(doc2(mk(0, 8, 2, [0], loop_on="false"))), "Kick")
    assert sum(c == "x" for c in once[1]["cells"]) == 1 and 2 not in once
    shifted = P.timeline(P.clips(doc2(mk(0, 4, 4, [0, 2], rel=1))), "Kick")
    assert shifted[1]["cells"][4] == "x" and shifted[1]["cells"][12] == "x"  # 2 → 1 dobu po startu, 0 → obtočí na 3. dobu


def test_runs_compress_equal_bars():
    cl = P.clips(doc2(mk(0, 16, 4, [0, 2])))
    r = P.runs(P.timeline(cl, "Kick"), 1, 5)
    assert r[0][:2] == (1, 4) and r[1][:2] == (5, 5) and set(r[1][2]) == {"."}
