import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import rebuild_preset_indexes as rb  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
READING = {
    "oscillators": [
        {"slot": 0, "enabled": True, "unison_voices": 4, "params": {"kParamDetune": 0.3}, "kind_params": {"kParamWarpMenu": "kPD_OSC"}},
        {"slot": 1, "enabled": True, "unison_voices": 1, "params": {}, "kind_params": {}},
        {"slot": 3, "enabled": True, "params": {}},
    ],
    "voice_filters": [{"slot": 0, "params": {"kParamFreq": 0.5, "kParamReso": 20}}],
    "fx": [{"module": "FXDistortion"}, {"module": "FXDistortion"}, {"module": "FXComp"}, {"module": "FXNeznamy"}],
    "modulation": [{"source": "LFO 1", "dest_module": "VoiceFilter"}, {"source": "Macro 1", "dest_module": "WTOsc"}],
    "lfos": [{"index": 0, "curve": {"x": [0, 0.5, 1], "y": [1, 0, 1]}}, {"index": 1}],
    "envs": [{"index": 0}], "macros": [], "voice": {"kParamMonoToggle": 1},
}


def test_features_are_numbers_and_flags_only():
    f = rb.features(READING)
    assert f["osc_on"] == 2 and f["unison_max"] == 4 and f["unison_sum"] == 5
    assert f["warp_slots"] == 1 and f["noise_on"] == 1 and f["sub_on"] == 0
    assert f["fx_count"] == 4 and f["fx_distortion"] == 2 and f["fx_comp"] == 1 and f["fx_other"] == 1
    assert f["mod_lfo"] == 1 and f["mod_macro"] == 1 and f["mod_to_filter"] == 1 and f["mod_to_osc"] == 1
    assert f["lfo_curves"] == 1 and f["lfo_points"] == 3 and f["mono"] == 1
    assert all(v is None or isinstance(v, (int, float)) for v in f.values())


def test_features_survive_an_empty_reading():
    f = rb.features({})
    assert f["osc_on"] == 0 and f["fx_count"] == 0 and f["filter_freq"] is None


def test_committed_feature_vectors_cover_the_committed_indexes():
    idx = {}
    for p in (REPO / "data" / "presets" / "index").glob("*.jsonl"):
        idx[p.stem] = [json.loads(line)["id"] for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    for sid, ids in idx.items():
        fp = REPO / "data" / "presets" / "features" / f"{sid}.jsonl"
        assert fp.exists(), f"chybí vektory pro {sid}"
        rows = [json.loads(line) for line in fp.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert [r["id"] for r in rows] == ids
        assert all(r["confidence"] == "hypothesis" and isinstance(r["features"], dict) for r in rows)
