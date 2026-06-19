"""Logging setup for the AI Workflow Discovery Engine."""

from __future__ import annotations

import logging

from ai_cluster.config.settings import settings


def configure_logging() -> None:
    """Configure process-wide logging with the configured log level."""
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="[%(levelname)s] %(message)s",
    )


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger for a module or class."""
    configure_logging()
    return logging.getLogger(name)
