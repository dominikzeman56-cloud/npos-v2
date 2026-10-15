import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
pytest.importorskip("cbor2")
pytest.importorskip("zstandard")
import index_presets as ip  # noqa: E402
from test_analyze_preset import make_blob  # noqa: E402

WARP_BASS = {
    "Oscillator0": {"plainParams": {}, "WTOsc0": {"plainParams": {"kParamWarpMenu": "kPD_OSC"}}},
    "Oscillator1": {"plainParams": {"kParamEnable": 1.0, "kParamVolume": 0.0, "kParamFine": -60.0},
                    "WTOsc1": {"plainParams": {"kParamTablePos": 14.0}}},
}
UNISON_BASS = {"Oscillator0": {"plainParams": {"kParamUnison": 5.0}, "WTOsc0": {"plainParams": {"kParamTablePos": 1.0}}}}


def test_index_proposals_and_local_dump(tmp_path):
    root = tmp_path / "pack" / "Proj A"
    root.mkdir(parents=True)
    (root / "Reese.SerumPreset").write_bytes(make_blob(WARP_BASS, {"presetName": "Reese", "product": "Serum2"}))
    (root / "Other Reese.SerumPreset").write_bytes(make_blob(UNISON_BASS, {"presetName": "Wide Reese", "product": "Serum2"}))
    (root / "Pad.SerumPreset").write_bytes(make_blob(UNISON_BASS, {"presetName": "Soft Pad", "product": "Serum2"}))
    dump = tmp_path / "_local"
    rows, bad = ip.index(tmp_path / "pack", "s-1", dump)
    by = {r["name"]: r for r in rows}
    assert not bad and len(rows) == 3
    assert by["Reese"]["archetype"] == "osc-warp-body" and by["Reese"]["cues"]["silent_mod_osc"] == 1
    assert by["Wide Reese"]["archetype"] == "detuned-unison-reese"
    assert by["Soft Pad"]["function"] == "pad" and by["Soft Pad"]["archetype"] == "unclassified"
    assert all(r["confidence"] == "hypothesis" and "reading" not in r for r in rows)  # index bez parametrů
    assert sorted(p.stem for p in dump.glob("*.json")) == sorted(r["id"] for r in rows)
    assert "reading" in json.loads((dump / f"{by['Reese']['id']}.json").read_text(encoding="utf-8"))
