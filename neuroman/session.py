# neuroman/session.py
"""Persistent session memory across sequential NeuroMan turns."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger("neuroman.session")

# Default store: Neuroman/data/sessions/<id>.json
_DATA_DIR = Path(__file__).resolve().parent / "data" / "sessions"

# Patterns for lightweight entity extraction (no LLM required)
_TEMPO_RE = re.compile(
    r"(?i)\b(?:tempo|bpm)\b\s*[:=]?\s*(\d{2,3}(?:\.\d+)?)"
    r"|\b(\d{2,3}(?:\.\d+)?)\s*(?:bpm)\b"
)
_KEY_RE = re.compile(
    r"(?i)\b(?:key|tonina|tonalita)\b\s*[:=]?\s*([A-G](?:#|b)?\s*(?:maj|min|major|minor|m)?)"
)
_TIME_SIG_RE = re.compile(r"(?i)\b(?:time\s*sig(?:nature)?|takt)\b\s*[:=]?\s*(\d{1,2}\s*/\s*\d{1,2})")


@dataclass
class Turn:
    role: str  # user | assistant | system | tool
    content: str
    intent: str = ""
    ts: float = field(default_factory=time.time)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionMemory:
    """
    In-memory + disk-backed conversation/context store.
    Survives process restarts when save() is called.
    """

    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    turns: list[Turn] = field(default_factory=list)
    # Structured facts extracted / set across turns
    facts: dict[str, Any] = field(default_factory=dict)
    # Last successful tool outcomes (e.g. ableton state snapshot keys)
    tool_state: dict[str, Any] = field(default_factory=dict)
    max_turns: int = 80

    # --- mutation ---------------------------------------------------------

    def add_user(self, text: str, intent: str = "") -> None:
        self.turns.append(Turn(role="user", content=text, intent=intent))
        self._extract_facts(text)
        self._trim()
        self.touch()

    def add_assistant(self, text: str, intent: str = "", **meta: Any) -> None:
        self.turns.append(Turn(role="assistant", content=text, intent=intent, meta=meta))
        self._trim()
        self.touch()

    def add_system(self, text: str) -> None:
        self.turns.append(Turn(role="system", content=text))
        self._trim()
        self.touch()

    def set_fact(self, key: str, value: Any) -> None:
        self.facts[key] = value
        self.touch()
        log.debug("fact set %s=%r", key, value)

    def get_fact(self, key: str, default: Any = None) -> Any:
        return self.facts.get(key, default)

    def merge_tool_state(self, patch: dict[str, Any]) -> None:
        self.tool_state.update(patch)
        self.touch()

    def touch(self) -> None:
        self.updated_at = time.time()

    def _trim(self) -> None:
        if len(self.turns) > self.max_turns:
            # keep first system notes + recent tail
            head = [t for t in self.turns[:3] if t.role == "system"]
            tail = self.turns[-(self.max_turns - len(head)) :]
            self.turns = head + tail

    def _extract_facts(self, text: str) -> None:
        m = _TEMPO_RE.search(text)
        if m:
            raw = m.group(1) or m.group(2)
            try:
                self.facts["tempo_bpm"] = float(raw)
            except ValueError:
                pass
        m = _KEY_RE.search(text)
        if m:
            self.facts["key"] = m.group(1).strip()
        m = _TIME_SIG_RE.search(text)
        if m:
            self.facts["time_signature"] = re.sub(r"\s+", "", m.group(1))

    # --- context projection -----------------------------------------------

    def context_block(self, *, max_chars: int = 3500) -> str:
        """
        Compact context string for LLM system prompts / coding handoffs.
        Includes structured facts + recent dialogue.
        """
        parts: list[str] = [f"session_id={self.session_id}"]
        if self.facts:
            facts_lines = ", ".join(f"{k}={v}" for k, v in sorted(self.facts.items()))
            parts.append(f"facts: {facts_lines}")
        if self.tool_state:
            # keep tool_state short
            ts = json.dumps(self.tool_state, ensure_ascii=False)[:800]
            parts.append(f"tool_state: {ts}")

        dialogue: list[str] = []
        for t in self.turns[-12:]:
            prefix = t.role.upper()
            intent = f"/{t.intent}" if t.intent else ""
            dialogue.append(f"{prefix}{intent}: {t.content}")
        blob = "\n".join(parts + ["---", *dialogue])
        if len(blob) > max_chars:
            blob = blob[-max_chars:]
        return blob

    def last_user_prompt(self) -> str:
        for t in reversed(self.turns):
            if t.role == "user":
                return t.content
        return ""

    # --- persistence ------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "max_turns": self.max_turns,
            "facts": self.facts,
            "tool_state": self.tool_state,
            "turns": [asdict(t) for t in self.turns],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionMemory":
        turns = [Turn(**t) for t in data.get("turns", [])]
        return cls(
            session_id=data.get("session_id", uuid.uuid4().hex[:12]),
            created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())),
            max_turns=int(data.get("max_turns", 80)),
            facts=dict(data.get("facts") or {}),
            tool_state=dict(data.get("tool_state") or {}),
            turns=turns,
        )

    def save(self, directory: Optional[Path] = None) -> Path:
        directory = directory or _DATA_DIR
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.session_id}.json"
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        log.debug("session saved %s", path)
        return path

    @classmethod
    def load(cls, session_id: str, directory: Optional[Path] = None) -> "SessionMemory":
        directory = directory or _DATA_DIR
        path = directory / f"{session_id}.json"
        if not path.is_file():
            raise FileNotFoundError(f"session not found: {session_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    @classmethod
    def load_or_create(
        cls,
        session_id: Optional[str] = None,
        directory: Optional[Path] = None,
    ) -> "SessionMemory":
        directory = directory or _DATA_DIR
        if session_id:
            try:
                return cls.load(session_id, directory)
            except (FileNotFoundError, json.JSONDecodeError) as exc:
                log.warning("session load failed (%s), creating new", exc)
        mem = cls(session_id=session_id or uuid.uuid4().hex[:12])
        mem.add_system("NeuroMan session started.")
        return mem

    @classmethod
    def latest(cls, directory: Optional[Path] = None) -> Optional["SessionMemory"]:
        directory = directory or _DATA_DIR
        if not directory.is_dir():
            return None
        files = sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            return None
        try:
            return cls.from_dict(json.loads(files[0].read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("latest session corrupt: %s", exc)
            return None
