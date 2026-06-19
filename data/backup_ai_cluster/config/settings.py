"""Runtime settings for the local AI Workflow Discovery Engine."""

from __future__ import annotations

import os
from pathlib import Path


class Settings:
    """Purpose: Centralize runtime configuration.

    Responsibilities:
        Read environment-backed settings and expose typed defaults.
    Inputs:
        Environment variables such as OLLAMA_MODEL and OUTPUT_PATH.
    Outputs:
        Immutable-style class attributes consumed by services.
    """

    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "phi3:mini")
    OLLAMA_TIMEOUT: float = float(os.getenv("OLLAMA_TIMEOUT", "120"))
    OLLAMA_MAX_RETRIES: int = int(os.getenv("OLLAMA_MAX_RETRIES", "2"))
    OUTPUT_PATH: Path = Path(
        os.getenv("OUTPUT_PATH", "ai_cluster/output/workflow_mapping.json")
    )
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
