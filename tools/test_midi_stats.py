import struct
import xml.etree.ElementTree as ET

import midi_stats as M


def vlq(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def smf(notes, ppq=480):
    ev, t = [], 0
    for s, d, p in sorted(notes):
        ev.append((int(s * ppq), 0x90, p, 100))
        ev.append((int((s + d) * ppq), 0x80, p, 0))
    ev.sort(key=lambda e: (e[0], e[1] == 0x90))
    body = b""
    for tick, st, p, v in ev:
        body += vlq(tick - t) + bytes([st, p, v])
        t = tick
    body += b"\x00\xff\x2f\x00"
    return b"MThd" + struct.pack(">IHHH", 6, 0, 1, ppq) + b"MTrk" + struct.pack(">I", len(body)) + body


def test_read_smf_beats_and_running_status():
    notes = M.read_smf(smf([(0, 0.5, 36), (1.0, 0.25, 40), (2.5, 1.0, 36)]))
    assert [(n[0], round(n[1], 2), n[2]) for n in notes] == [(0.0, 0.5, 36), (1.0, 0.25, 40), (2.5, 1.0, 36)]


def test_read_smf_rejects_garbage():
    for bad in (b"", b"RIFFxxxx", b"MThd" + b"\x00" * 3):
        try:
            M.read_smf(bad)
        except (ValueError, IndexError, struct.error):
            continue
        raise AssertionError("měla být chyba")


def n(*rows):
    return [(s, d, p, 100) for s, d, p in rows]


def test_describe_grid_shares_and_steps():
    # čtyři osminy a dvě šestnáctiny + jedna mimo mřížku; 1 takt
    notes = n((0, .25, 36), (1, .25, 36), (1.5, .25, 43), (2.0, .25, 36), (2.75, .25, 48), (3.1, .1, 36))
    d = M.describe(notes, 4.0)
    assert d["bars"] == 1 and round(d["density"], 2) == 6.0
    assert round(d["onbeat"] + d["eighth"] + d["sixteenth"] + d["triplet"] + d["off_grid"], 6) == 1
    assert d["off_grid"] > 0 and d["sixteenth"] > 0 and d["leap"] > 0
    assert d["slots"][0] == 1 and d["slots"][11] == 1


def test_too_short_or_too_long_is_skipped():
    assert M.describe(n((0, 1, 36), (1, 1, 36)), 4.0) is None
    assert M.describe(n(*[(i * .5, .25, 36) for i in range(8)]), 4.0 * 40) is None


def test_bar_repeat_and_empty_bars():
    bar = [(0, .25, 36), (1, .25, 40), (2, .25, 36), (3, .25, 43)]
    notes = n(*bar, *[(s + 4, d, p) for s, d, p in bar], *[(s + 12, d, p) for s, d, p in bar])
    d = M.describe(notes, 16.0)
    assert d["bar_repeat"] == 1 / 3 and d["empty_bars"] == 0.25


def test_dedupe_by_fingerprint():
    a = n((0, 1, 36), (1, 1, 36), (2, 1, 36), (3, 1, 36))
    r = {"fp": M.fingerprint(a)}
    assert len(M.dedupe([r, dict(r), {"fp": "x"}])) == 2


def test_roles():
    assert M.role_of("01_SUB_BASS_call") == "sub" and M.role_of("Reese 2") == "bass" and M.role_of("Kick loop") == "drums"
    assert M.role_of("Lead hook") == "lead" and M.role_of("zzz") == "other"


def test_small_group_only_count():
    rows = [dict(M.describe(n((0, 1, 36), (1, 1, 36), (2, 1, 36), (3, 1, 36)), 4.0), source="a", role="x", fp=str(i)) for i in range(5)]
    assert "note" in M.summarize(rows)


def test_als_patterns_loop_window():
    ev = lambda t: f'<MidiNoteEvent Time="{t}" Duration="0.25" Velocity="100" IsEnabled="true"/>'
    xml = (f'<Ableton><LiveSet><Tracks><MidiTrack Id="1"><Name><EffectiveName Value="Reese"/></Name><DeviceChain/>'
           f'<MidiClip><Loop><LoopStart Value="1"/><LoopEnd Value="5"/></Loop><Notes><KeyTracks><KeyTrack><Notes>{ev(0)}{ev(1)}{ev(4.5)}{ev(5)}</Notes>'
           f'<MidiKey Value="36"/></KeyTrack></KeyTracks></Notes></MidiClip></MidiTrack></Tracks></LiveSet></Ableton>')
    (name, notes, length), = M.als_patterns(ET.fromstring(xml))
    assert name == "Reese" and length == 4.0 and [x[0] for x in notes] == [0.0, 3.5]


def test_drums_have_no_pitch_metrics():
    d = M.describe(n((0, .25, 36), (1, .25, 38), (2, .25, 36), (3, .25, 42)), 4.0)
    out = M._finish(d, "drums")
    assert all(out[k] is None for k in M.PITCHED_KEYS) and out["density"] == d["density"]
    assert M._finish(d, "bass")["leap"] == d["leap"]


def test_source_key_skips_generic_containers():
    from pathlib import Path
    root = Path("X/20_Samples")
    assert M._source_key(root, Path("01_New/PackA/loops/a.mid")) == "20_Samples/PackA"
    assert M._source_key(root, Path("Packs/PackB/a.mid")) == "20_Samples/PackB"
    assert M._source_key(Path("X/40_MIDI"), Path("HNDNB/Bass/a.mid")) == "40_MIDI/HNDNB"
    assert M._source_key(root, Path("a.mid")) == "20_Samples"


def test_pack_name_does_not_decide_role():
    from pathlib import Path
    root = Path("X/20_Samples")
    rel = Path("01_New/KULTURE - Drum & Bass Production Suite/MIDI/Basslines/riff 1.mid")
    assert M.role_of(M.role_text(root, rel)) == "bass"
    rel2 = Path("01_New/Neuro Drum & Bass Pack/MIDI/Chords/Am.mid")
    assert M.role_of(M.role_text(root, rel2)) == "harmony"
    assert M.role_of("Drum & Bass kit") == "other"


def test_legato_is_share_of_notes_that_fill_the_gap():
    full = M.describe(n((0, 1, 36), (1, 1, 38), (2, 1, 36), (3, 1, 40), (4, .5, 36)), 8.0)
    stac = M.describe(n((0, .25, 36), (1, .25, 38), (2, .25, 36), (3, .25, 40), (4, .25, 36)), 8.0)
    assert full["legato"] == 1.0 and stac["legato"] == 0.0


def test_progression_and_songstarter_roles():
    assert M.role_of("Liquid Chord Progressions / Am7") == "harmony"
    assert M.role_of("Dance Floor Progressions / 01 Cmin") == "harmony"
    assert M.role_of("KULTURE Songstarter 03") == "songstarter"
    assert M.role_of("Songstarter 03 - Bass") == "bass"
