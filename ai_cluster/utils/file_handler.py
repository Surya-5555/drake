"""JSON file IO helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class FileHandler:
    """Purpose: Read and write JSON files.

    Responsibilities:
        Encapsulate filesystem JSON access and consistent error handling.
    Inputs:
        Paths to Contract A and Contract B JSON files.
    Outputs:
        Python JSON-compatible objects or persisted JSON files.
    """

    def read_json(self, path: Path) -> Any:
        """Read and parse a JSON file from disk."""
        try:
            with path.open("r", encoding="utf-8") as file:
                return json.load(file)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"JSON file not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    def write_json(self, path: Path, payload: dict[str, Any]) -> None:
        """Write a JSON-compatible payload to disk with stable formatting."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2)
            file.write("\n")
