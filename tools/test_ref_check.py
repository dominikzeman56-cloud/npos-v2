import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import ref_check as rc  # noqa: E402


def _analysis(crest, sub, fund, cent, sub_side, fund_side):
    return {
        "dynamics": {"crest_factor_drop_db": crest},
        "bass": {
            "energy": {"sub_rel_db": sub, "fundament_rel_db": fund},
            "timbre": {"spectral_centroid_hz": cent},
            "stereo": {"sub_side_db": sub_side, "fundament_side_db": fund_side},
        },
    }


def test_metrics_from_analysis_derives_balance_and_tolerates_gaps():
    m = rc.metrics_from_analysis(_analysis(6.4, -2.8, -6.57, 4439.4, -42.04, -26.68))
    assert m["sub_minus_fund_db"] == pytest.approx(3.77)
    assert m["crest_db"] == 6.4 and m["centroid_hz"] == 4439.4
    empty = rc.metrics_from_analysis({})
    assert set(empty) == set(m) and all(v is None for v in empty.values())


@pytest.mark.parametrize("value,where,offset,nearest", [
    (5.0, "pod", -1.0, "a"),
    (6.0, "v", 0.0, "a"),      # hrana rozpětí je ještě uvnitř
    (7.1, "v", 0.0, "b"),
    (9.5, "nad", 1.5, "c"),
])
def test_position(value, where, offset, nearest):
    p = rc.position(value, {"a": 6.0, "b": 7.0, "c": 8.0})
    assert (p["where"], p["offset"], p["nearest"]) == (where, offset, nearest)
    assert (p["min"], p["max"], p["n"]) == (6.0, 8.0, 3)


def test_median_only_from_enough_references():
    few = rc.position(1.0, {"a": 1.0, "b": 2.0, "c": 3.0})
    enough = rc.position(1.0, {k: float(i) for i, k in enumerate("abcde")})
    assert few["median"] is None and enough["median"] == 2.0


def test_compare_skips_missing_values_and_gives_hint_only_outside():
    refs = {
        "x": rc.metrics_from_analysis(_analysis(6.0, -3.0, -7.0, 4500.0, -30.0, -25.0)),
        "y": rc.metrics_from_analysis(_analysis(8.0, -5.0, -6.0, 5500.0, -40.0, None)),
    }
    own = rc.metrics_from_analysis(_analysis(5.0, -4.0, -6.5, 6000.0, -20.0, -22.0))
    rows = {r["key"]: r for r in rc.compare(own, refs)}
    assert rows["crest_db"]["where"] == "pod" and rows["crest_db"]["hint"]
    assert rows["sub_rel_db"]["where"] == "v" and rows["sub_rel_db"]["hint"] == ""
    assert rows["centroid_hz"]["where"] == "nad" and rows["centroid_hz"]["offset"] == 500.0
    assert rows["sub_side_db"]["where"] == "nad"                       # širší sub než obě reference
    assert rows["fundament_side_db"]["n"] == 1                         # reference bez hodnoty se nepočítá
    own["crest_db"] = None
    assert {r["key"]: r for r in rc.compare(own, refs)}["crest_db"]["where"] == "bez dat"


def test_render_lists_outside_metrics_and_notes():
    refs = {"x": rc.metrics_from_analysis(_analysis(6.0, -3.0, -7.0, 4500.0, -30.0, -25.0))}
    own = rc.metrics_from_analysis(_analysis(4.0, -3.0, -7.0, 4500.0, -30.0, -25.0))
    text = rc.render(rc.compare(own, refs), 1, detail=True, notes=["sekce"])
    assert "pod o 2.00 dB" in text and "hustší" in text
    assert "Hodnoty po referencích" in text and "Pozor: sekce" in text
    assert "med." not in text                                           # jedna reference, žádný medián
    many = {k: rc.metrics_from_analysis(_analysis(6.0 + i, -3.0, -7.0, 4500.0, -30.0, -25.0)) for i, k in enumerate("abcde")}
    line = rc.render(rc.compare(own, many), 5).splitlines()[3]
    assert "(med. 8.00)" in line and "−4.00" in line                    # crest 4.0 proti mediánu 8.0


def test_load_references_excludes_own_work(tmp_path):
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "sources.jsonl").write_text(
        json.dumps({"id": "mine", "access": "own_work"}) + "\n" + json.dumps({"id": "pro", "access": "local_file"}) + "\n",
        encoding="utf-8")
    for tid, sid in (("my-track", "mine"), ("ref-track", "pro")):
        d = tmp_path / "data" / "tracks" / tid
        d.mkdir(parents=True)
        (d / "meta.json").write_text(json.dumps({"id": tid, "source_id": sid}), encoding="utf-8")
        (d / "analysis.json").write_text(json.dumps(_analysis(6.0, -3.0, -7.0, 4500.0, -30.0, -25.0)), encoding="utf-8")
    assert list(rc.load_references(tmp_path)) == ["ref-track"]
    with pytest.raises(SystemExit):
        rc.load_references(tmp_path, only=["my-track"])


def test_load_references_skips_stem_based_analyses(tmp_path):
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "sources.jsonl").write_text(json.dumps({"id": "pro", "access": "local_file"}) + "\n", encoding="utf-8")
    for tid, basis in (("mix-track", "full_mix"), ("stem-track", "stems")):
        d = tmp_path / "data" / "tracks" / tid
        d.mkdir(parents=True)
        (d / "meta.json").write_text(json.dumps({"id": tid, "source_id": "pro"}), encoding="utf-8")
        a = _analysis(6.0, -3.0, -7.0, 4500.0, -30.0, -25.0)
        a["method"] = {"basis": basis}
        (d / "analysis.json").write_text(json.dumps(a), encoding="utf-8")
    assert list(rc.load_references(tmp_path)) == ["mix-track"]
