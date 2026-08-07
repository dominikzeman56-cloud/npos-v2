# neuroman/auth.py
"""Secure Claude Code / Anthropic credential bootstrap (no secrets in repo)."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .resilience import ErrorKind, NeuroError

log = logging.getLogger("neuroman.auth")

# Optional local env file (gitignored). Never commit secrets.
_ENV_CANDIDATES = (
    Path(__file__).resolve().parent / ".env",
    Path(__file__).resolve().parent.parent / ".env",
)


@dataclass(frozen=True)
class AuthStatus:
    claude_cli: bool
    anthropic_key_present: bool
    source: str  # env | env_file | missing
    detail: str = ""

    @property
    def code_ready(self) -> bool:
        """CODE branch can run autonomously if CLI exists OR API key is set."""
        return self.claude_cli or self.anthropic_key_present


def _load_dotenv_if_present() -> Optional[Path]:
    """Minimal KEY=VALUE loader (no third-party dotenv dependency)."""
    for path in _ENV_CANDIDATES:
        if not path.is_file():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                # do not overwrite already-exported env
                if key and key not in os.environ:
                    os.environ[key] = val
            log.info("loaded env file %s", path)
            return path
        except OSError as exc:
            log.warning("env file read failed %s: %s", path, exc)
    return None


def ensure_env_loaded() -> None:
    _load_dotenv_if_present()


def claude_cli_path() -> Optional[str]:
    return shutil.which("claude")


def anthropic_api_key() -> Optional[str]:
    ensure_env_loaded()
    key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
    if key and key.strip():
        return key.strip()
    return None


def auth_status() -> AuthStatus:
    ensure_env_loaded()
    cli = claude_cli_path() is not None
    key = anthropic_api_key()
    if key:
        src = "env"
        # detect if came from file roughly
        for p in _ENV_CANDIDATES:
            if p.is_file() and "ANTHROPIC_API_KEY" in p.read_text(encoding="utf-8", errors="ignore"):
                src = "env_file"
                break
        return AuthStatus(claude_cli=cli, anthropic_key_present=True, source=src)
    if cli:
        return AuthStatus(
            claude_cli=True,
            anthropic_key_present=False,
            source="cli",
            detail="Claude CLI found; will use CLI session credentials",
        )
    return AuthStatus(
        claude_cli=False,
        anthropic_key_present=False,
        source="missing",
        detail="Set ANTHROPIC_API_KEY or run `claude login`",
    )


async def ensure_claude_login(*, interactive: bool = True) -> AuthStatus:
    """
    Ensure CODE branch can operate.
    - If API key present: ready immediately.
    - Else if `claude` CLI present: optionally run `claude login` / status probe.
    - Else: raise NeuroError AUTH.
    """
    status = auth_status()
    if status.code_ready and status.anthropic_key_present:
        log.info("claude auth: API key present (%s)", status.source)
        return status

    cli = claude_cli_path()
    if not cli:
        raise NeuroError(
            message="Claude Code neni pripraveny (chybi CLI i ANTHROPIC_API_KEY).",
            kind=ErrorKind.AUTH,
            source="claude",
            recoverable=False,
            detail=status.detail,
        )

    # Probe non-interactive: `claude -p` with tiny prompt may still need login.
    # Prefer `claude auth status` if available; fall back to version check.
    probe_cmds = [
        [cli, "auth", "status"],
        [cli, "--version"],
    ]
    logged_in = False
    for cmd in probe_cmds:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20.0)
            out = (stdout or b"").decode("utf-8", errors="replace") + (stderr or b"").decode(
                "utf-8", errors="replace"
            )
            log.debug("claude probe %s -> rc=%s out=%s", cmd, proc.returncode, out[:300])
            if proc.returncode == 0:
                logged_in = True
                break
            if "not logged" in out.lower() or "login" in out.lower():
                logged_in = False
                break
        except (FileNotFoundError, asyncio.TimeoutError, OSError) as exc:
            log.warning("claude probe failed: %s", exc)

    if logged_in or status.claude_cli:
        # CLI present; user may already have session cookies from prior login
        if not interactive:
            return auth_status()

    if interactive and not (logged_in or anthropic_api_key()):
        log.info("launching interactive claude login")
        try:
            proc = await asyncio.create_subprocess_exec(cli, "login")
            rc = await proc.wait()
            if rc != 0:
                raise NeuroError(
                    message="Claude login selhal nebo byl zrusen.",
                    kind=ErrorKind.AUTH,
                    source="claude",
                    recoverable=True,
                    detail=f"exit={rc}",
                )
        except FileNotFoundError as exc:
            raise NeuroError(
                message="Prikaz 'claude' nenalezen v PATH.",
                kind=ErrorKind.AUTH,
                source="claude",
                recoverable=False,
            ) from exc

    final = auth_status()
    if not final.code_ready:
        raise NeuroError(
            message="Claude auth stale nekompletni.",
            kind=ErrorKind.AUTH,
            source="claude",
            recoverable=True,
            detail=final.detail,
        )
    return final


def redact_secret(value: str, keep: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= keep * 2:
        return "***"
    return value[:keep] + "…" + value[-keep:]
