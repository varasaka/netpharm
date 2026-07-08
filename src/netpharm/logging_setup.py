"""Structured logging.

Every step produces logs (a design requirement). We attach one console handler
and one rotating file handler under outputs/logs/, so a full run leaves an
auditable trail on disk in addition to the SQLite step records.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False


def setup_logging(output_dir: str | Path = "outputs", level: int = logging.INFO) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_dir = Path(output_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)-22s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger("netpharm")
    root.setLevel(level)
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    fileh = RotatingFileHandler(
        log_dir / "pipeline.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    fileh.setFormatter(fmt)
    root.addHandler(fileh)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Namespaced logger, e.g. get_logger('agent.ppi')."""
    return logging.getLogger(f"netpharm.{name}")
