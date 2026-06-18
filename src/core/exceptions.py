"""
Dell MCP — Core Exception Hierarchy
====================================
Defines the full custom exception tree for the ingestion pipeline.

All exceptions are deterministic and surfaced with structured messages
so that callers (CLI, tests, future FastMCP error handlers) can distinguish
between configuration errors, malformed specs, and runtime I/O failures
without inspecting raw tracebacks.
"""

from __future__ import annotations


class DellMCPBaseError(Exception):
    """
    Root exception for the Dell MCP Workflow Proxy.

    All custom exceptions inherit from this class so that broad
    ``except DellMCPBaseError`` blocks can be used safely in CLI entry-points
    and test harnesses without accidentally swallowing unrelated errors.
    """


# ---------------------------------------------------------------------------
# Parser-specific exceptions
# ---------------------------------------------------------------------------


class ParserError(DellMCPBaseError):
    """
    Base class for all Phase 1 (OpenAPI ingestion) errors.

    Raised when the parser module encounters an unrecoverable problem during
    spec loading, structural validation, or Contract A serialisation.
    """


class SpecFileNotFoundError(ParserError):
    """
    Raised when the target OpenAPI spec file does not exist on disk.

    This is a distinct subclass (rather than re-raising ``FileNotFoundError``)
    so that consumers can check ``isinstance(exc, SpecFileNotFoundError)``
    and emit a user-friendly diagnostic without depending on OS-level messages.

    Args:
        path: The filesystem path that was not found.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"OpenAPI spec file not found: '{path}'")


class SpecParseError(ParserError):
    """
    Raised when the YAML/JSON spec cannot be parsed or is structurally invalid.

    Wraps underlying ``yaml.YAMLError``, ``json.JSONDecodeError``, or
    ``openapi-core`` validation exceptions so that callers receive a single,
    predictable exception type regardless of which library detected the fault.

    Args:
        path:   The file that triggered the error.
        reason: Human-readable description of why parsing failed.
    """

    def __init__(self, path: str, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"Failed to parse spec '{path}': {reason}")


class UnsupportedSpecVersionError(ParserError):
    """
    Raised when the spec declares an OpenAPI version other than 3.x.

    The pipeline is hardened for OpenAPI 3.0.x and 3.1.x only.
    Swagger 2.0 specs should be converted before ingestion.

    Args:
        version: The ``openapi`` field value found in the spec.
    """

    def __init__(self, version: str) -> None:
        self.version = version
        super().__init__(
            f"Unsupported OpenAPI version '{version}'. "
            "Only OpenAPI 3.x specs are supported."
        )


class ContractSerializationError(ParserError):
    """
    Raised when the Contract A Pydantic model cannot be serialised to JSON.

    This typically indicates a Pydantic validation failure caused by an
    unexpected data shape in the spec (e.g., a non-string operationId).

    Args:
        reason: Description of the serialisation failure.
    """

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Contract A serialisation failed: {reason}")
