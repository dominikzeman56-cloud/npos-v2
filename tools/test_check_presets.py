import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import check_presets as cp  # noqa: E402
import preset_roles as pr  # noqa: E402


def write(p: Path, rows):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_clean_tree_passes(tmp_path):
    write(tmp_path / "index" / "a.jsonl", [{"id": "a1"}])
    write(tmp_path / "features" / "a.jsonl", [{"id": "a1", "features": {"x": 1, "y": None}}])
    write(tmp_path / "audio" / "a.jsonl", [{"id": "a1", "protocol": {"note": 28}, "audio": {"rms_db": -9.0, "window": "sustain", "silent": False}}])
    assert cp.check(tmp_path) == []


def test_detects_duplicates_unknown_ids_types_and_leaks(tmp_path):
    write(tmp_path / "index" / "a.jsonl", [{"id": "a1"}])
    write(tmp_path / "fxp" / "b.jsonl", [{"id": "a1", "note": "D:\\samples D&B\\x.wav"}])
    write(tmp_path / "features" / "a.jsonl", [{"id": "zz", "features": {"x": "text"}}])
    write(tmp_path / "audio" / "a.jsonl", [{"id": "a1", "audio": {}}])
    errs = " | ".join(cp.check(tmp_path))
    for needle in ("duplicitní id a1", "neznámé id zz", "není číslo", "bez protokolu", "lokální cesta"):
        assert needle in errs


def test_knn_separates_two_clear_clusters_and_skips_duplicates():
    rng = np.random.default_rng(0)
    X = np.vstack([rng.normal(0, 0.1, (10, 3)), rng.normal(5, 0.1, (10, 3))])
    labels = ["bass"] * 10 + ["tonal"] * 10
    pred = pr.knn(X, labels, k=3)
    assert [p for p, _ in pred] == labels
    # identická kopie se nepočítá jako soused (jinak by validace byla přehnaně dobrá)
    X2 = np.vstack([X, X[:1]])
    pred2 = pr.knn(X2, labels + [None], k=1)
    assert pred2[0][0] == "bass" and pred2[-1][0] == "bass"


def test_evaluate_reports_recall_precision_and_baseline():
    ev = pr.evaluate([("a", 1.0), ("a", 1.0), ("b", 1.0), ("a", 1.0)], ["a", "a", "b", "b"])
    assert ev["accuracy"] == 0.75 and ev["recall"] == {"a": 1.0, "b": 0.5} and ev["precision"]["a"] == round(2 / 3, 3)
    assert ev["majority_baseline"] == 0.5


def test_vector_transforms_and_missing():
    v = pr.vector({"centroid_hz": 1000.0, "side_minus_mid_db": -138.0, "window": "attack"})
    keys = [k for k, _ in pr.FEATURES]
    assert v[keys.index("centroid_hz")] == 3.0 and v[keys.index("side_minus_mid_db")] == -40.0
    assert v[keys.index("attack")] == 1.0 and v[keys.index("rms_db")] is None


def test_duplicate_sha_and_serum1_host_modulation_must_be_null(tmp_path):
    row = {"source_id": "s", "reader": "serum1_host", "cues": {"lfo_to_filter": 0, "silent_mod_osc": None}, "container": {"sha256": "abc"}}
    write(tmp_path / "fxp" / "s.jsonl", [{"id": "s1", **row}, {"id": "s2", **row}])
    write(tmp_path / "features" / "s.jsonl", [{"id": "s1", "reader": "serum1_host", "features": {"mod_lfo": 0, "mod_env": None}}])
    errs = " | ".join(cp.check(tmp_path))
    for needle in ("s2 má stejný sha256 jako s1", "cues.lfo_to_filter má být null", "s1.mod_lfo má být null"):
        assert needle in errs, needle
    assert "mod_env" not in errs
