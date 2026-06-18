"""
Dell MCP — Core Configuration
================================
Centralised, strongly-typed settings for the entire ingestion pipeline.

Design rationale
----------------
All magic constants (file names, directory paths, encoding settings) live here
so that:

1. Tests can monkey-patch ``ParserConfig`` without touching production modules.
2. Future environment-variable overrides (via ``pydantic-settings``) can be
   dropped in without changing call-sites.
3. Code reviews have a single authoritative location for "what are the
   defaults?" questions.

Usage::

    from src.core.config import ParserConfig

    cfg = ParserConfig()
    print(cfg.output_dir)          # PosixPath('data/output')
    print(cfg.contract_a_filename) # 'contract_a.json'
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class ParserConfig(BaseModel):
    """
    Immutable configuration bag for the Phase 1 OpenAPI ingestion pipeline.

    All paths are relative to the project root so that the parser can be
    invoked from any working directory via ``python -m src.parser.openapi_parser``.

    Attributes:
        project_root:        Absolute path to the repository root.  Derived
                             automatically from this file's location.
        raw_specs_dir:       Directory where raw OpenAPI YAML/JSON files are
                             stored.  Created automatically if absent.
        output_dir:          Destination directory for all generated artefacts
                             (Contract A JSON, future workflow mappings).
        contract_a_filename: Basename of the serialised Contract A JSON file.
        file_encoding:       Encoding used for all file I/O. ``utf-8`` is
                             mandated to handle Unicode characters in Dell spec
                             descriptions (even though those descriptions are
                             stripped, the loader must read them first).
        json_indent:         Pretty-print indentation level for Contract A.
                             Set to 2 for human-readable diffs in version
                             control.  Set to ``None`` for compact output.
    """

    model_config = {"frozen": True}  # Pydantic v2: make instances immutable

    # ------------------------------------------------------------------ paths
    project_root: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent,
        description="Absolute project root — derived from this config file's location.",
    )

    raw_specs_dir: Path = Field(
        default=Path("data/raw_specs"),
        description="Drop-zone for raw Dell OpenAPI YAML/JSON specification files.",
    )

    output_dir: Path = Field(
        default=Path("data/output"),
        description="Output directory for Contract A JSON and other generated artefacts.",
    )

    contract_a_filename: str = Field(
        default="contract_a.json",
        description="Filename for the stripped, flat Contract A endpoint registry.",
    )

    # --------------------------------------------------------------- encoding
    file_encoding: str = Field(
        default="utf-8",
        description="Encoding for all file read/write operations.",
    )

    json_indent: int = Field(
        default=2,
        ge=0,
        description="JSON pretty-print indentation spaces. Use 0 for compact output.",
    )

    # --------------------------------------------------------- computed paths
    @property
    def contract_a_path(self) -> Path:
        """Full path to the Contract A output file."""
        return self.project_root / self.output_dir / self.contract_a_filename

    @property
    def abs_raw_specs_dir(self) -> Path:
        """Absolute path to the raw specs drop-zone."""
        return self.project_root / self.raw_specs_dir

    @property
    def abs_output_dir(self) -> Path:
        """Absolute path to the output directory."""
        return self.project_root / self.output_dir


# Module-level singleton — import and use directly in most cases.
DEFAULT_CONFIG = ParserConfig()
