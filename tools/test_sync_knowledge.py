"""sync_knowledge.py při importu hned čte vault a zapisuje knowledge/, proto se testují jen jeho čisté funkce,
vytažené z kódu bez spuštění skriptu."""
import ast
import json
import re
from pathlib import Path

SRC = Path(__file__).with_name("sync_knowledge.py").read_text(encoding="utf-8")


def _funcs(*names):
    tree = ast.parse(SRC)
    mod = ast.Module([n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names], type_ignores=[])
    ns = {"re": re, "json": json}
    exec(compile(mod, "sync_knowledge.py", "exec"), ns)
    return ns


F = _funcs("unlink", "fm", "sections")


def test_unlink_wikilinks():
    assert F["unlink"]("viz [[20 Basa|basa]] a [[40 Mix a master#2. Tři výstupy]]") == "viz basa a 40 Mix a master, kap. 2. Tři výstupy"
    assert F["unlink"]("[[Producenti/Joe_Ford]]") == "Joe Ford"


def test_frontmatter_quotes_and_lists():
    out = F["fm"]({"id": "p1", "title": "P1 · Rozhodování: proč", "source_ids": ["a", "b"], "skip": None})
    assert out == '---\nid: p1\ntitle: "P1 · Rozhodování: proč"\nsource_ids: [a, b]\n---\n'


def test_sections_split_at_hr_and_higher_heading():
    text = "### P1 · A\nprvní\n---\nmimo\n### P2 · B\ndruhá\n## Další\nmimo"
    assert F["sections"](text, 3) == [("P1 · A", "první"), ("P2 · B", "druhá")]
