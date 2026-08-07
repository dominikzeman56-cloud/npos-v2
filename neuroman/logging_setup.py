# neuroman/logging_setup.py
"""Central logging: rotating file + quiet console diagnostics."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_DIR = Path(__file__).resolve().parent / "data" / "logs"
_CONFIGURED = False


def setup_logging(*, level: int = logging.INFO, console: bool = False) -> Path:
    """
    Idempotent logger bootstrap.
    Writes neuroman.log under Neuroman/data/logs/.
    Console handler is optional (rich CLI owns user-facing output).
    """
    global _CONFIGURED
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = _LOG_DIR / "neuroman.log"

    if _CONFIGURED:
        return log_path

    root = logging.getLogger("neuroman")
    root.setLevel(level)
    root.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = RotatingFileHandler(
        log_path,
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    fh.setLevel(level)
    root.addHandler(fh)

    if console:
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        ch.setLevel(logging.WARNING)
        root.addHandler(ch)

    # quiet noisy libs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)

    _CONFIGURED = True
    root.info("logging initialized -> %s", log_path)
    return log_path
