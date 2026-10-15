import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import import_sessions as imp  # noqa: E402

GOOD = {"date": "2026-10-15", "track_id": "test-track", "goal": "Zamknout sub", "done": ["a", "b"], "next": "drop B"}


def test_validate_accepts_schema_object_and_rejects_bad_ones():
    assert imp.validate(GOOD) == []
    assert "chybí goal" in imp.validate({"date": "2026-10-15", "track_id": "x"})
    assert "date není YYYY-MM-DD" in imp.validate({**GOOD, "date": "15.10.2026"})
    assert "done není pole řetězců" in imp.validate({**GOOD, "done": "a"})
    assert imp.validate("x") == ["není objekt"]


def test_import_writes_one_file_per_session_and_never_overwrites(tmp_path):
    src = tmp_path / "sessions.json"
    src.write_text(json.dumps([GOOD, GOOD]), encoding="utf-8")
    out = tmp_path / "out"
    assert imp.main([str(src), "--out", str(out)]) == 0
    names = sorted(p.name for p in out.glob("*.json"))
    assert names == ["2026-10-15-test-track-2.json", "2026-10-15-test-track.json"]
    assert json.loads((out / names[1]).read_text(encoding="utf-8"))["goal"] == "Zamknout sub"


def test_import_dry_run_and_invalid_entries(tmp_path):
    src = tmp_path / "s.json"
    src.write_text(json.dumps([GOOD, {"date": "x"}]), encoding="utf-8")
    out = tmp_path / "out"
    assert imp.main([str(src), "--out", str(out), "--dry-run"]) == 1
    assert not out.exists()
