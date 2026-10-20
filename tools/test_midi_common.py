import xml.etree.ElementTree as ET

import als_stats as A
import midi_batch as B
import midi_common as C
import midi_stats as M
import stem_grid as S


def test_quant_variants_match_old_callers():
    xs = [1.0, 2.0, 3.0, 4.0]
    assert C.quant(xs) == {"n": 4, "q1": 1.75, "median": 2.5, "q3": 3.25} == M.quant(xs)
    assert A.quant([1.0, 2.0, 2.0 / 3]) == {"n": 3, "min": 2.0 / 3, "q1": 0.83, "median": 1.0, "q3": 1.5, "max": 2.0}


def test_gap_signature_hit_chars():
    assert C.gap_signature("x..+............") == B.gap_signature("x..+............") == "3-13"
    assert S.gap_signature("x..+............") == "16"


def test_clip_notes_window_disabled_and_missing_key():
    clip = ET.fromstring('<MidiClip><Notes><KeyTracks>'
                         '<KeyTrack><Notes><MidiNoteEvent Time="1.5" Duration="0.25" Velocity="90.5"/>'
                         '<MidiNoteEvent Time="0.5" Duration="1" Velocity="100" IsEnabled="false"/>'
                         '<MidiNoteEvent Time="5" Duration="1" Velocity="100"/></Notes><MidiKey Value="36"/></KeyTrack>'
                         '<KeyTrack><Notes><MidiNoteEvent Time="1" Duration="1" Velocity="100"/></Notes></KeyTrack>'
                         '</KeyTracks></Notes></MidiClip>')
    assert C.clip_notes(clip, 1.0, 5.0, A.val) == [(0.5, 0.25, 36, 90)]
