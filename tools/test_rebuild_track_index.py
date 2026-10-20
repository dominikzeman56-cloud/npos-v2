import json

import rebuild_track_index as R


def test_row_flattens_analysis():
    meta = {"id": "t1", "title": "T", "artist": "A", "bpm": 174, "key": "F minor", "source_id": "s1"}
    an = {"analyzed": "2026-10-01", "method": {"basis": "full_mix", "stems": ["bass"]},
          "structure": {"sections": [{"name": "intro"}, {"name": "drop"}]},
          "dynamics": {"crest_factor_drop_db": 8.1},
          "bass": {"type": "reese", "energy": {"profile": "mid", "sub_rel_db": -3.0},
                   "modulation": {"primary_hz": 5.8, "grid_match": "1/8", "confidence": "hypothesis"}}}
    r = R.row(meta, an)
    assert r["sections"] == ["intro", "drop"] and r["stems"] is True and r["bass_type"] == "reese"
    assert r["bass_mod_hz"] == 5.8 and r["sub_rel_db"] == -3.0 and r["centroid_hz"] is None and r["loudness_strategy"] == ""
    assert R.row({"id": "x"}, {})["sections"] == []


def test_main_skips_own_work_and_tracks_without_analysis(tmp_path, monkeypatch):
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "sources.jsonl").write_text(
        json.dumps({"id": "pro", "access": "purchased"}) + "\n" + json.dumps({"id": "mine", "access": "own_work"}) + "\n", encoding="utf-8")
    for tid, sid, with_an in (("a", "pro", True), ("b", "mine", True), ("c", "pro", False)):
        d = tmp_path / "data" / "tracks" / tid
        d.mkdir(parents=True)
        (d / "meta.json").write_text(json.dumps({"id": tid, "source_id": sid}), encoding="utf-8")
        if with_an:
            (d / "analysis.json").write_text("{}", encoding="utf-8")
    (tmp_path / "data" / "corpus").mkdir()
    monkeypatch.setattr(R, "ROOT", tmp_path)
    assert R.main() == 0
    rows = [json.loads(x) for x in (tmp_path / "data" / "corpus" / "tracks.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["id"] for r in rows] == ["a"]
