import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import check_repo as cr  # noqa: E402


def make(tmp_path, items, heads="## 3.6 DROP 2 — jak ho dělat jiný `[K]`\n"):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "30 Aranž.md").write_text("# 30 Aranž\n" + heads, encoding="utf-8")
    f = tmp_path / "next-step.json"
    f.write_text(json.dumps({"phases": [{"id": "aranz", "title": "Aranž"}], "items": items}), encoding="utf-8")
    return f, vault


ITEM = {"id": "a", "phase": "aranz", "situation": "s", "steps": ["x"], "sources": ["LS"], "confidence": "estimated",
        "vault": "30 Aranž", "anchor": "3.6 DROP 2 — jak ho dělat jiný [K]"}


def test_valid_item_and_backtick_anchor(tmp_path):
    f, v = make(tmp_path, [ITEM])
    assert cr.check_next_step(f, v) == []


def test_broken_anchor_unknown_then_phase_and_confidence(tmp_path):
    bad = dict(ITEM, id="b", anchor="neexistuje", then=["zzz"], phase="nope", confidence="jisté")
    f, v = make(tmp_path, [ITEM, bad])
    errs = " | ".join(cr.check_next_step(f, v))
    assert "kotva" in errs and "then" in errs and "neznámá fáze" in errs and "confidence" in errs
