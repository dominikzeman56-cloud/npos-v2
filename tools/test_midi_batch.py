import gzip
import xml.etree.ElementTree as ET

import midi_batch as B


def test_gap_signature_wraps_to_next_bar():
    assert B.gap_signature("x...x...x...x...") == "4-4-4-4"
    assert B.gap_signature("x...............") == "16"
    assert B.gap_signature("................") == ""
    assert B.gap_signature("x..x..x.x..x..x.") == "3-3-2-3-3-2"
    assert B.gap_signature("..x...x...x...x.") == "4-4-4-4"


def test_dominant_bar_counts_nonempty_bars_only():
    tl = {1: {"cells": list("x...............")}, 2: {"cells": list("x...............")}, 3: {"cells": list("................")},
          4: {"cells": list("x...x...........")}}
    assert B.dominant_bar(tl) == ("x...............", 2, 3)
    assert B.dominant_bar({1: {"cells": list("." * 16)}}) is None


def test_role_of_track():
    assert B.role_of_track("PHNM_DA_KICK_19 #3") == "kick" and B.role_of_track("Snare top") == "snare"
    assert B.role_of_track("bass_mid") == "bass" and B.role_of_track("SUB") == "sub" and B.role_of_track("Pad") is None


def test_aggregate_small_group_only_count_and_no_names():
    assert "note" in B.aggregate([{"roles": {}, "tempo": 174, "last_midi_bar": 4}] * 3)
    pr = {"roles": {"bass": [{"track": "SecretName", "grid": "x...", "repeats": 5, "bars": 5, "signature": "4-4-4-4", "pitches": [36]}]},
          "tempo": 174.0, "last_midi_bar": 64}
    agg = B.aggregate([pr] * 10)
    assert agg["bass"]["signatures_by_projects"] == {"4-4-4-4": 10} and "SecretName" not in str(agg)


def clip(start, end, loop, times, key):
    ev = "".join(f'<MidiNoteEvent Time="{t}" Duration="0.25" Velocity="100" IsEnabled="true"/>' for t in times)
    return (f'<MidiClip><CurrentStart Value="{start}"/><CurrentEnd Value="{end}"/><Loop><LoopStart Value="0"/><LoopEnd Value="{loop}"/>'
            f'<StartRelative Value="0"/><LoopOn Value="true"/></Loop><Notes><KeyTracks><KeyTrack><Notes>{ev}</Notes>'
            f'<MidiKey Value="{key}"/></KeyTrack></KeyTracks></Notes></MidiClip>')


def test_analyze_project_and_dedupe_copies(tmp_path):
    xml = ('<Ableton><LiveSet><Tracks><MidiTrack Id="1"><Name><EffectiveName Value="Kick"/></Name>' + clip(0, 16, 4, [0, 1.75], 36)
           + '</MidiTrack></Tracks><MainTrack><DeviceChain><Mixer><Tempo><Manual Value="174"/></Tempo></Mixer></DeviceChain></MainTrack></LiveSet></Ableton>')
    data = gzip.compress(ET.tostring(ET.fromstring(xml)))
    (tmp_path / "a.als").write_bytes(data)
    (tmp_path / "a Copy.als").write_bytes(data)
    sets, bad = B.find_sets(tmp_path)
    assert len(sets) == 1 and bad == 0
    r = B.analyze_project(sets[0])
    assert r["roles"]["kick"][0]["signature"] == "7-9" and r["last_midi_bar"] == 4


def test_chop_summary_counts_projects_without_names():
    pr = lambda n: {"roles": {}, "tempo": 174, "last_midi_bar": 64, "audio_clips": 50, "chopped_tracks": n, "chopped_clips": 30 * n,
                    "chopped_roles": {"bass": 1} if n else {}}
    agg = B.aggregate([pr(1)] * 6 + [pr(0)] * 6)
    ac = agg["audio_chops"]
    assert ac["projects_with_audio_clips"] == 12 and ac["projects_with_chopped_tracks"] == 6 and ac["share_with_chopped_tracks"] == 0.5
    assert ac["projects_by_chopped_role"]["bass"] == 6 and ac["chopped_clips"] == {"n": 6}


def test_analyze_project_reports_chopped_audio(tmp_path):
    clips = "".join(f'<AudioClip><CurrentStart Value="{i * 0.5}"/><CurrentEnd Value="{i * 0.5 + 0.25}"/><Name Value="c"/></AudioClip>' for i in range(10))
    xml = f'<Ableton><LiveSet><Tracks><AudioTrack Id="1"><Name><EffectiveName Value="Bass Resample"/></Name>{clips}</AudioTrack></Tracks></LiveSet></Ableton>'
    p = tmp_path / "a.als"
    p.write_bytes(gzip.compress(xml.encode()))
    r = B.analyze_project(p)
    assert r["chopped_tracks"] == 1 and r["chopped_clips"] == 10 and r["chopped_roles"] == {"bass": 1}
