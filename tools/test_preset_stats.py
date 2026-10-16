import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import preset_stats as ps  # noqa: E402


def write(p: Path, rows):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_cliffs_delta_extremes_and_ties():
    a, b = np.array([5.0, 6, 7]), np.array([1.0, 2, 3])
    assert ps.cliffs_delta(a, b) == 1.0 and ps.cliffs_delta(b, a) == -1.0
    assert ps.cliffs_delta(np.array([1.0, 1]), np.array([1.0, 1])) == 0.0


def test_small_group_gets_count_only():
    rows = [{"features": {"x": float(i)}} for i in range(9)]
    g = ps.group_stats(rows, ["x"], lambda r, k: r["features"].get(k))
    assert g["n"] == 9 and "features" not in g and "n < 10" in g["note"]


def test_null_values_do_not_count_towards_n():
    rows = [{"features": {"x": float(i) if i < 12 else None}} for i in range(30)]
    g = ps.group_stats(rows, ["x"], lambda r, k: r["features"].get(k))
    assert g["features"]["x"]["n"] == 12


def rows_two_roles(pack_a="p1", pack_b="p2"):
    rng = np.random.default_rng(0)
    out = []
    for i in range(40):
        out.append({"id": f"a{i}", "role": "bass", "source_id": pack_a, "features": {"fx": float(rng.normal(8, 1)), "flat": 1.0}})
        out.append({"id": f"b{i}", "role": "lead", "source_id": pack_b, "features": {"fx": float(rng.normal(2, 1)), "flat": 1.0}})
    return out


def test_contrast_finds_separating_feature_and_ignores_constant():
    c = ps.contrast(rows_two_roles(), "bass", ["fx", "flat"], lambda r, k: r["features"].get(k))
    keys = [f["key"] for f in c["features"]]
    assert keys == ["fx"] and c["features"][0]["delta"] > 0.9 and c["features"][0]["median_role"] > c["features"][0]["median_rest"]
    assert "warning" in c  # role je celá z jednoho packu


def test_contrast_needs_ten_in_both_groups():
    rows = rows_two_roles()[:30]
    rows = [r for r in rows if r["role"] == "lead"] + [r for r in rows if r["role"] == "bass"][:3]
    c = ps.contrast(rows, "bass", ["fx"], lambda r, k: r["features"].get(k))
    assert c["features"] == []


def test_build_keeps_readers_apart_and_writes_markdown(tmp_path):
    idx = [{"id": f"s2-{i}", "source_id": "pk", "role": "bass"} for i in range(12)]
    fx = [{"id": f"s1-{i}", "source_id": "q", "role": "bass", "reader": "serum1_host"} for i in range(12)]
    write(tmp_path / "index" / "pk.jsonl", idx)
    write(tmp_path / "fxp" / "q.jsonl", fx)
    write(tmp_path / "features" / "pk.jsonl", [{"id": r["id"], "features": {"osc_on": 2.0}} for r in idx])
    write(tmp_path / "features" / "q.jsonl", [{"id": r["id"], "reader": "serum1_host", "features": {"osc_on": 1.0}} for r in fx])
    st = ps.build(tmp_path, tmp_path / "none.jsonl")
    assert st["readers"]["s2"]["roles"]["bass"]["params"]["features"]["osc_on"]["median"] == 2.0
    assert st["readers"]["serum1_host"]["roles"]["bass"]["params"]["features"]["osc_on"]["median"] == 1.0
    md = ps.markdown(st)
    assert "Serum 1" in md and "Serum 2" in md and "hypothesis" in md
