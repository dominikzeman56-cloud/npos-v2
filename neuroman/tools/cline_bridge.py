# neuroman/tools/cline_bridge.py
"""Async handoff writer: NeuroMan -> context.md for Cline (VS Code)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import aiofiles
from rich.console import Console

log = logging.getLogger("neuroman.tools.cline_bridge")

CONTEXT_FILE = Path(__file__).resolve().parent.parent.parent / "context.md"


async def dispatch_to_cline(
    prompt: str,
    console: Console,
    extra_context: str = "",
    *,
    session_id: str = "",
) -> Path:
    """
    Zapise strukturovany kontext do context.md v rootu repa (async I/O).
    Cline pokracuje ve VS Code — zadne rucni copy-paste.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    sid_line = f"\n_session: `{session_id}`_\n" if session_id else "\n"

    body = f"""# NeuroMan -> Cline handoff

_Vygenerovano: {timestamp}_{sid_line}
## Pozadavek

{prompt}
"""
    if extra_context:
        body += f"\n## Session context\n\n```\n{extra_context}\n```\n"

    body += (
        "\n## Instrukce pro Cline\n\n"
        "- Implementuj pozadavek primo v repozitari.\n"
        "- Drz se existujicich konvencni a struktury projektu.\n"
        "- Po dokonceni shrn zmeny.\n"
    )

    CONTEXT_FILE.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(CONTEXT_FILE, "w", encoding="utf-8") as fh:
        await fh.write(body)

    log.info("cline handoff written -> %s", CONTEXT_FILE)
    console.print(
        f"[green]Kontext zapsan do[/green] [bold]{CONTEXT_FILE}[/bold]\n"
        "[dim]Otevri context.md ve VS Code a pokracuj s Cline.[/dim]"
    )
    return CONTEXT_FILE
