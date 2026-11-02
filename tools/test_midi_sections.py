import gzip
import json
import xml.etree.ElementTree as ET

import midi_project as P
import midi_sections as S


def mk(start, end, loop, times, key=36):
    ev = "".join(f'<MidiNoteEvent Time="{t}" Duration="0.25" Velocity="100" IsEnabled="true"/>' for t in times)
    return (f'<MidiClip><CurrentStart Value="{start}"/><CurrentEnd Value="{end}"/><Loop><LoopStart Value="0"/><LoopEnd Value="{loop}"/>'
            f'<StartRelative Value="0"/><LoopOn Value="true"/></Loop><Notes><KeyTracks><KeyTrack><Notes>{ev}</Notes>'
            f'<MidiKey Value="{key}"/></KeyTrack></KeyTracks></Notes></MidiClip>')


def doc(tracks: dict[str, list[str]]) -> ET.Element:
    body = "".join(f'<MidiTrack Id="{i}"><Name><EffectiveName Value="{n}"/></Name><ArrangerAutomation><Events>{"".join(cs)}</Events>'
                   f'</ArrangerAutomation></MidiTrack>' for i, (n, cs) in enumerate(tracks.items()))
    return ET.fromstring(f'<Ableton><LiveSet><Tracks>{body}</Tracks></LiveSet></Ableton>')


def bars(a, b):
    """Klip přes takty a..b (včetně), jeden takt smyčky, čtvrťové nástupy."""
    return mk((a - 1) * 4, b * 4, 4, [0, 1, 2, 3])


def test_clip_crossing_bar_boundary_counts_in_both_bars():
    cl = P.clips(doc({"Kick": [mk(2, 10, 2, [0, 1])]}))   # od 1|3 do 3|3, smyčka 2 doby
    act, last = S.bar_activity(cl)
    assert last == 3 and act[1]["roles"] == {"kick": 2} and act[2]["roles"] == {"kick": 4} and act[3]["roles"] == {"kick": 2}
    assert act[2]["tracks"] == {"Kick": 4}


def test_empty_bars_are_missing_and_count_into_density():
    cl = P.clips(doc({"Kick": [bars(1, 1), bars(4, 4)]}))
    act, last = S.bar_activity(cl)
    assert sorted(act) == [1, 4] and last == 4
    roles, dens, _ = S.profile(act, 1, 4)
    assert roles == ["kick"] and dens == {"kick": 2.0}   # hraje ve 2 ze 4 taktů (polovina stačí); 8 nástupů / 4 takty
    assert S.profile(act, 1, 5)[0] == []
    assert S.sections([]) == {"phrase": 8, "last_bar": 0, "sections": [], "bars": {}}


def test_snap_to_phrase():
    assert [S.snap(b, 8) for b in (1, 4, 5, 8, 9, 15, 16, 17, 21)] == [1, 1, 9, 9, 9, 17, 17, 17, 25]
    assert [S.snap(b, 16) for b in (10, 15, 17, 24, 25)] == [17, 17, 17, 17, 33]


def test_boundaries_snap_and_fill_does_not_split():
    # basa přijde o takt dřív (takt 16), v taktu 24 jeden prázdný takt (fill) → hranice jen 1 a 17
    cl = P.clips(doc({"Kick": [bars(1, 23), bars(25, 32)], "Bass": [bars(16, 23), bars(25, 32)]}))
    act, last = S.bar_activity(cl)
    assert S.boundaries(act, last, 8) == [1, 17, 25]
    r = S.sections(cl)
    assert [(s["start"], s["end"]) for s in r["sections"]] == [(1, 16), (17, 32)]
    assert [s["label"] for s in r["sections"]] == ["intro", "drop"]
    assert S.boundaries(act, last, 16) == [1, 17]


def test_labels_intro_build_drop_break_outro():
    cl = P.clips(doc({"Pad": [bars(1, 16), bars(49, 56)],
                      "Kick": [bars(17, 48), bars(57, 88)], "Snare": [bars(25, 48), bars(65, 88)],
                      "Reese Bass": [bars(33, 48), bars(73, 88)], "SUB": [bars(33, 48)],
                      "Hats": [bars(89, 96)]}))
    r = S.sections(cl)
    got = [(s["start"], s["end"], s["label"]) for s in r["sections"]]
    assert got == [(1, 16, "intro"), (17, 24, "build"), (25, 32, "build"), (33, 48, "drop"), (49, 56, "break"),
                   (57, 64, "build"), (65, 72, "build"), (73, 88, "drop"), (89, 96, "outro")]
    drop = r["sections"][3]
    assert drop["roles"] == ["bass", "kick", "snare", "sub"] and drop["density"]["kick"] == 4.0
    assert r["sections"][-1]["roles"] == ["drums"]


def test_label_rules_without_drop():
    secs = [{"roles": ["kick"]}, {"roles": []}, {"roles": ["kick", "snare"]}, {"roles": ["bass"]}]
    S.label(secs)
    assert [s["label"] for s in secs] == ["intro", "break", "break", "outro"]


def test_cli_json(tmp_path, capsys):
    xml = ET.tostring(doc({"Kick": [bars(1, 16)], "Bass": [bars(9, 16)]}))
    p = tmp_path / "a.als"
    p.write_bytes(gzip.compress(xml))
    assert S.main([str(p), "--json"]) == 0
    r = json.loads(capsys.readouterr().out)
    assert [(s["start"], s["label"]) for s in r["sections"]] == [(1, "intro"), (9, "drop")] and r["bars"]["9"] == {"bass": 4, "kick": 4}
    assert S.main([str(tmp_path / "missing.als")]) == 2
