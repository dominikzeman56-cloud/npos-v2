import gzip
import xml.etree.ElementTree as ET

import als_stats as A


def band(on, mode, freq):
    return f'<ParameterA><IsOn><Manual Value="{on}"/></IsOn><Mode><Manual Value="{mode}"/></Mode><Freq><Manual Value="{freq}"/></Freq></ParameterA>'


def track(tag, name, devices="", gid="-1", idx="1"):
    return (f'<{tag} Id="{idx}"><Name><EffectiveName Value="{name}"/></Name><TrackGroupId Value="{gid}"/>'
            f'<DeviceChain><DeviceChain><Devices>{devices}</Devices></DeviceChain></DeviceChain></{tag}>')


def doc(tracks, main=""):
    return ET.fromstring(
        f'<Ableton><LiveSet><Tracks>{tracks}</Tracks><MainTrack><DeviceChain><Mixer><Tempo><Manual Value="174"/></Tempo></Mixer>'
        f'<DeviceChain><Devices>{main}</Devices></DeviceChain></DeviceChain></MainTrack>'
        f'<Locators><Locators><Locator><Name Value="A"/></Locator></Locators></Locators></LiveSet></Ableton>')


def test_counts_and_groups():
    t = track("GroupTrack", "G", idx="5") + track("MidiTrack", "m", gid="5", idx="6") + track("ReturnTrack", "A", idx="7")
    r = A.analyze(doc(t))
    assert (r["tracks"], r["groups"], r["returns"], r["group_depth"], r["locators"], r["tempo"]) == (2, 1, 1, 1, 1, 174.0)


def test_utility_trim_counts_only_below_threshold():
    sg = lambda g: f'<StereoGain><Gain><Manual Value="{g}"/></Gain></StereoGain>'
    r = A.analyze(doc(track("AudioTrack", "x", sg(1.0) + sg(0.5) + sg(0.95))))
    assert r["utility_trims"] == 1  # 0.5 = -6 dB; 0.95 = -0.4 dB se nepočítá


def test_kick_highpass_detected_only_on_kick_track():
    eq = lambda b: f'<Eq8><Bands.0>{b}</Bands.0></Eq8>'
    hp = band("true", 1, 100)
    r = A.analyze(doc(track("AudioTrack", "Kick A", eq(hp)) + track("AudioTrack", "Pad", eq(hp), idx="2")))
    assert (r["kick_tracks"], r["kick_highpass"]) == (1, 1)
    low = A.analyze(doc(track("AudioTrack", "kick", eq(band("true", 1, 25)))))
    off = A.analyze(doc(track("AudioTrack", "kick", eq(band("false", 1, 100)))))
    shelf = A.analyze(doc(track("AudioTrack", "kick", eq(band("true", 2, 100)))))
    assert low["kick_highpass"] == off["kick_highpass"] == shelf["kick_highpass"] == 0


def test_kick_name_not_matched_inside_words():
    assert A.analyze(doc(track("AudioTrack", "Kickstart bus")))["kick_tracks"] == 0
    assert A.analyze(doc(track("AudioTrack", "bd 1")))["kick_tracks"] == 1


def test_small_group_gets_only_count():
    assert A.summarize([{"tracks": 3}] * 5) == {"n_projects": 5, "note": "méně než 10 projektů: jen počet"}


def test_roundtrip_gzip_and_no_paths(tmp_path):
    p = tmp_path / "Secret Course Name.als"
    p.write_bytes(gzip.compress(ET.tostring(doc(track("MidiTrack", "m")))))
    out = tmp_path / "o.json"
    assert A.main(["--roots", str(tmp_path), "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "Secret" not in text and str(tmp_path) not in text
