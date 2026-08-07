# neuroman/tools/knowledge.py
"""Keyword search over the NPOS vault (.md files) for grounding MUSIC/GENERAL answers."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

log = logging.getLogger("neuroman.tools.knowledge")

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_VAULT_DIRS = [
    "Knowledge",
    "Framework",
    "Producer-Knowledge",
    "Case-Studies",
    "Presets",
    "Session-Management",
    "Troubleshooting",
]

_STOPWORDS = {
    "jak", "co", "je", "na", "se", "do", "za", "pro", "ale", "nebo", "the",
    "a", "an", "of", "to", "in", "for", "with", "and", "or", "is", "at",
    "mi", "mu", "mou", "muj", "tve", "jeho", "jeji", "jsem", "jsi", "jsou",
}


@dataclass
class KnowledgeHit:
    path: str
    title: str
    score: int
    snippet: str


def _tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9\-]{3,}", text.lower())
    return [w for w in words if w not in _STOPWORDS]


def _iter_md_files() -> list[str]:
    files: list[str] = []
    for rel_dir in _VAULT_DIRS:
        abs_dir = os.path.join(_PROJECT_ROOT, rel_dir)
        if not os.path.isdir(abs_dir):
            continue
        for root, _dirs, names in os.walk(abs_dir):
            for name in names:
                if name.lower().endswith(".md"):
                    files.append(os.path.join(root, name))
    return files


def search_vault(query: str, limit: int = 4, snippet_chars: int = 600) -> list[KnowledgeHit]:
    """Score every .md file in the vault against query tokens; return top hits with a snippet."""
    terms = _tokenize(query)
    if not terms:
        return []

    hits: list[KnowledgeHit] = []
    for path in _iter_md_files():
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError as exc:
            log.warning("knowledge: cannot read %s: %s", path, exc)
            continue

        lower = content.lower()
        score = sum(lower.count(t) for t in terms)
        if score == 0:
            continue

        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else os.path.basename(path)

        # snippet centred on the first matching term
        idx = -1
        for t in terms:
            idx = lower.find(t)
            if idx != -1:
                break
        if idx == -1:
            idx = 0
        start = max(0, idx - 120)
        snippet = content[start : start + snippet_chars].strip()

        hits.append(KnowledgeHit(path=path, title=title, score=score, snippet=snippet))

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:limit]


def format_context_block(hits: list[KnowledgeHit]) -> str:
    """Render hits as a compact context block to inject into an LLM system prompt."""
    if not hits:
        return ""
    parts = ["Relevantni znalosti z NPOS vaultu (pouzij je pred obecnymi znalostmi, pokud sedi):"]
    for h in hits:
        rel = os.path.relpath(h.path, _PROJECT_ROOT)
        parts.append(f"\n--- {h.title} ({rel}) ---\n{h.snippet}")
    return "\n".join(parts)
