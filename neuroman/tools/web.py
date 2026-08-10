# neuroman/tools/web.py
"""GENERAL intent fallback via OmniRoute."""

from __future__ import annotations

import logging

from rich.console import Console

from ..resilience import NeuroError
from .knowledge import format_context_block, search_vault

log = logging.getLogger("neuroman.tools.web")


async def handle_web_query(prompt: str, router, console: Console, *, context: str = "") -> str:
    """Fallback pro obecne dotazy (kategorie GENERAL). Vraci text odpovedi."""
    system = "Jsi NeuroMan asistent. Odpovidej strucne a vecne."
    vault_hits = search_vault(prompt)
    if vault_hits:
        console.print(f"[dim]Vault: {len(vault_hits)} relevantnich .md souboru[/dim]")
        system += "\n\n" + format_context_block(vault_hits)
    if context:
        system += f"\n\nSession context:\n{context}"
    try:
        with console.status("[cyan]Hledam odpoved.[/cyan]"):
            response = await router.generate_completion(prompt, system_message=system)
        console.print(f"\n[bold magenta]NeuroMan:[/bold magenta]\n{response}\n")
        return response
    except NeuroError as exc:
        log.error("web query failed: %s", exc.detail or exc)
        console.print(f"[red]{exc.user_line()}[/red]")
        return ""
