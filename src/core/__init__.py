"""
Dell MCP — Core Package
========================
Exports shared Pydantic models, configuration, and exceptions.
"""

from src.core.config import DEFAULT_CONFIG, ParserConfig
from src.core.exceptions import (
    ContractSerializationError,
    DellMCPBaseError,
    ParserError,
    SpecFileNotFoundError,
    SpecParseError,
    UnsupportedSpecVersionError,
)
from src.core.models import ContractA, EndpointContract, RequiredParameter

__all__ = [
    # Config
    "DEFAULT_CONFIG",
    "ParserConfig",
    # Exceptions
    "DellMCPBaseError",
    "ParserError",
    "SpecFileNotFoundError",
    "SpecParseError",
    "UnsupportedSpecVersionError",
    "ContractSerializationError",
    # Models
    "RequiredParameter",
    "EndpointContract",
    "ContractA",
]
