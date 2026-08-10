# neuroman/tools/coder.py
"""Coding-agent subprocess dispatcher (Claude Code / OpenCode) with streaming."""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
from typing import Optional

from rich.console import Console

from ..auth import ensure_claude_login, auth_status
from ..resilience import ErrorKind, NeuroError, get_breaker, retry_async

log = logging.getLogger("neuroman.tools.coder")


async def dispatch_to_coder(
    prompt: str,
    console: Console,
    agent_type: str = "claude",
    *,
    extra_context: str = "",
    ensure_auth: bool = True,
) -> int:
    """
    Spusti kodovaciho agenta v neinteraktivnim rezimu a streamuje vystup.
    Returns process exit code (or -1 on hard failure).
    """
    full_prompt = prompt
    if extra_context:
        full_prompt = (
            f"{prompt}\n\n---\nNeuroMan session context:\n{extra_context}\n"
        )

    if agent_type == "claude":
        if ensure_auth:
            try:
                status = await ensure_claude_login(interactive=True)
                console.print(
                    f"[dim]Claude auth: cli={status.claude_cli} "
                    f"key={status.anthropic_key_present} src={status.source}[/dim]"
                )
            except NeuroError as exc:
                console.print(f"[red]{exc.user_line()}[/red]")
                log.error("claude auth failed: %s", exc.detail)
                return -1
        command = ["claude", "-p", full_prompt]
        # Prefer API key from env if present (CLI picks it up)
        env = os.environ.copy()
    elif agent_type == "opencode":
        command = ["opencode-go", "run", full_prompt]
        env = os.environ.copy()
    else:
        console.print(f"[red]Neznamy coding agent: {agent_type}[/red]")
        return -1

    console.print(f"[dim]Spoustim: {' '.join(shlex.quote(c) for c in command[:3])} …[/dim]")
    breaker = get_breaker("claude" if agent_type == "claude" else "opencode")

    async def _run_once() -> int:
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        except FileNotFoundError as exc:
            raise NeuroError(
                message=f"Prikaz '{command[0]}' nenalezen v PATH.",
                kind=ErrorKind.AUTH if agent_type == "claude" else ErrorKind.DEPENDENCY_DOWN,
                source=agent_type,
                recoverable=False,
            ) from exc

        async def stream_output(stream: asyncio.StreamReader, prefix: str, color: str) -> None:
            while True:
                line = await stream.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                console.print(f"[{color}][{prefix}][/{color}] {text}")

        assert process.stdout and process.stderr
        await asyncio.gather(
            stream_output(process.stdout, "AGENT", "cyan"),
            stream_output(process.stderr, "ERROR", "red"),
        )
        rc = await process.wait()
        log.info("coder %s exit=%s", agent_type, rc)
        if rc != 0:
            raise NeuroError(
                message=f"Coding agent exit code {rc}.",
                kind=ErrorKind.DEPENDENCY_DOWN,
                source=agent_type,
                detail=f"rc={rc}",
            )
        return rc

    try:
        # single attempt for long-running agents (retry only auth/start failures)
        rc = await retry_async(
            _run_once,
            attempts=1,
            breaker=breaker,
            label=f"coder:{agent_type}",
        )
        console.print(f"[dim italic]Agent dokoncil ulohu (exit code: {rc})[/dim italic]")
        return rc
    except NeuroError as exc:
        console.print(f"[red]{exc.user_line()}[/red]")
        log.error("coder failed: %s | %s", exc, exc.detail)
        # fallback hint toward cline handoff
        st = auth_status()
        if not st.code_ready:
            console.print(
                "[yellow]Tip: nastav ANTHROPIC_API_KEY nebo spust `/login` v NeuroMan CLI.[/yellow]"
            )
        return -1
