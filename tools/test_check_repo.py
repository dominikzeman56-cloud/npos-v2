import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import check_repo  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "core" / "source.schema.json").read_text(encoding="utf-8"))


def test_repo_passes():
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "check_repo.py")],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr


def test_source_row_valid():
    errs = []
    row = {"id": "x-1", "kind": "track", "title": "T", "verified_by": "web", "verified_on": "2026-10-15"}
    check_repo.check_object(row, SCHEMA, "row", errs)
    assert errs == []


def test_source_row_rejects_unverified_and_unknown_fields():
    errs = []
    row = {"id": "Bad Id", "kind": "track", "title": "T", "verified_by": "guess", "extra": 1}
    check_repo.check_object(row, SCHEMA, "row", errs)
    joined = "\n".join(errs)
    assert "verified_on" in joined      # chybí povinné pole
    assert "guess" in joined            # neplatná hodnota verified_by
    assert "extra" in joined            # additionalProperties false
    assert "Bad Id" in joined           # vzor id


def test_frontmatter_parse():
    meta = check_repo.parse_frontmatter('---\nid: a\nsource_ids: [x, y]\ntitle: "P1: a"\n---\n\nbody')
    assert meta == {"id": "a", "source_ids": ["x", "y"], "title": "P1: a"}
    assert check_repo.parse_frontmatter("bez frontmatteru") is None
