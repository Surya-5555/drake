"""
Dell MCP — Core Pydantic Models (Contract A Schemas)
=====================================================

WHY THIS STRIPPING PROCESS IS MANDATORY
----------------------------------------
The Dell iDRAC 9 Redfish API OpenAPI specification (v7.xx) is a **2.9 MB YAML
file spanning 64,000+ lines**.  A naive pass-through to an LLM would consume
an estimated **700,000+ tokens** — far exceeding the context windows of every
commercially deployed model (GPT-4: 128K, Claude 3: 200K, Gemini 1.5: 1M but
at prohibitive cost).

Even in models with "infinite" context (e.g., Gemini 1.5 Pro 1M), feeding the
raw spec degrades reasoning quality through a phenomenon called *lost in the
middle*: the model's attention mechanism struggles to surface relevant signal
buried deep in a sea of noise.

The noise removed by this parser includes:

- **``description`` fields**: Verbose human prose (sometimes multi-paragraph
  HTML-embedded strings) that accounts for ~40% of total byte weight.
- **``example`` / ``examples`` fields**: Inline JSON payloads that can be
  hundreds of lines long per endpoint (see the ``OAuth2Service`` example in
  ``/redfish/v1/AccountService`` — 30+ lines of JWT key material).
- **``x-longDescription`` / ``x-*`` extension fields**: DMTF-specific metadata
  with no runtime or routing value.
- **``summary`` fields**: Redundant single-line versions of descriptions.
- **``responses`` bodies**: Full schema references for 200/202/204/default
  responses are irrelevant for route dispatch (we only care about inputs).
- **``tags``**: Grouping hints for Swagger UI; useless post-clustering.

After stripping, Contract A targets **< 50,000 tokens** for 500+ endpoints —
a **≥ 86% token reduction** that is a hard security and correctness requirement
for the LLM clustering stage (Phase 2).

Pydantic v2 is used throughout for:
- Runtime type validation (catches malformed specs early)
- JSON serialisation with ``model.model_dump_json()``
- IDE autocompletion and static analysis support via ``mypy``
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Parameter model
# ---------------------------------------------------------------------------


class RequiredParameter(BaseModel):
    """
    A single required input parameter for an API endpoint.

    Only parameters explicitly marked ``required: true`` in the OpenAPI spec
    are captured.  Optional parameters are deliberately omitted — the LLM
    clustering engine (Phase 2) needs to know *what must be supplied* to
    call an endpoint, not every possible knob.

    Attributes:
        name:      The parameter name as declared in the spec (e.g.,
                   ``"ManagerAccountId"``, ``"$expand"``).
        location:  Where the parameter appears in the HTTP request.
                   One of: ``"path"``, ``"query"``, ``"header"``,
                   ``"cookie"``, or ``"body"`` (synthesised for required
                   ``requestBody`` entries).
        param_type: The JSON Schema primitive type of the parameter value.
                    Defaults to ``"string"`` when no ``schema.type`` is
                    declared (common in polymorphic Redfish params).
    """

    name: str = Field(description="Parameter name as declared in the OpenAPI spec.")
    location: Literal["path", "query", "header", "cookie", "body"] = Field(
        description="Where the parameter appears in the HTTP request."
    )
    param_type: str = Field(
        default="string",
        description=(
            "JSON Schema primitive type (string, integer, boolean, object, array). "
            "Defaults to 'string' for untyped parameters."
        ),
    )


# ---------------------------------------------------------------------------
# Endpoint contract model
# ---------------------------------------------------------------------------


class EndpointContract(BaseModel):
    """
    The stripped, minimal representation of a single OpenAPI operation.

    This is the atomic unit of **Contract A**.  Each instance maps exactly to
    one ``{HTTP_METHOD} {path}`` pair in the source spec.

    The four retained fields are the **minimum viable routing signature**:
    they are sufficient for the AI clustering engine to group related
    endpoints into high-level workflows without knowing response payloads,
    authentication schemes, or human-readable documentation.

    Attributes:
        operation_id:        The ``operationId`` field from the spec.  Dell
                             iDRAC follows the convention
                             ``"METHOD_/path/segment"`` (e.g.,
                             ``"GET_/redfish/v1/Systems/{ComputerSystemId}"``).
                             This field is unique across the entire spec and
                             serves as the primary key in workflow mappings.
        http_method:         The HTTP verb in upper-case.  Constrained to the
                             seven methods supported by OpenAPI 3.x.
        url:                 The path template exactly as declared in the spec,
                             including path parameter placeholders (e.g.,
                             ``"/redfish/v1/Chassis/{ChassisId}/Power"``).
        required_parameters: List of required inputs.  Path parameters are
                             *always* required by definition (OpenAPI 3.x §4.8.12).
                             Query/header/cookie params are included only when
                             ``required: true`` is explicit.  A synthesised
                             ``"body"`` entry is added when
                             ``requestBody.required: true``.
    """

    operation_id: str = Field(
        description=(
            "Unique operation identifier from the OpenAPI spec. "
            "Used as the primary key in workflow_mapping.json."
        )
    )
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"] = Field(
        description="HTTP verb in upper-case."
    )
    url: str = Field(
        description=(
            "URL path template with placeholders, e.g. "
            "'/redfish/v1/Systems/{ComputerSystemId}'."
        )
    )
    required_params: list[RequiredParameter] = Field(
        default_factory=list,
        description=(
            "Required inputs only. Optional parameters are excluded to "
            "minimise token footprint in Phase 2 clustering."
        ),
    )
    tags: list[str] = Field(
        default_factory=list, description="OpenAPI tags for graph grouping."
    )
    summary: str = Field(
        default="", description="Endpoint summary for graph embeddings."
    )
    description: str = Field(
        default="", description="Endpoint description for graph embeddings."
    )
    request_schema: dict | None = Field(
        default=None, description="Request schema for graph similarity."
    )
    response_schema: dict | None = Field(
        default=None, description="Response schema for graph similarity."
    )


# ---------------------------------------------------------------------------
# Top-level Contract A model
# ---------------------------------------------------------------------------


class ContractA(BaseModel):
    """
    The complete Phase 1 output artefact — the stripped endpoint registry.

    Contract A is a *flat* JSON document (no nesting deeper than
    ``EndpointContract.required_parameters``) that can be:

    1. Fed directly to the Phase 2 AI clustering engine as a compact prompt.
    2. Diffed in version control to track spec changes between Dell firmware
       releases without reviewing 2.9 MB of raw YAML.
    3. Validated programmatically by downstream consumers via Pydantic's
       ``model_validate_json()`` without importing the full parser.

    Attributes:
        spec_title:       The ``info.title`` from the source spec.
        spec_version:     The ``info.version`` from the source spec
                          (e.g., ``"7.00.00.00"``).
        openapi_version:  The ``openapi`` field (e.g., ``"3.0.1"``).
        parsed_at:        UTC timestamp of when the parser ran.  Used for
                          audit trails and cache invalidation.
        source_file:      Basename of the input spec file.
        total_endpoints:  Total number of ``EndpointContract`` records.
                          Must equal ``len(endpoints)``.
        endpoints:        The complete list of stripped endpoint contracts,
                          sorted by ``url`` then ``http_method`` for
                          deterministic diffs.
    """

    spec_title: str = Field(description="info.title from the source OpenAPI spec.")
    spec_version: str = Field(description="info.version from the source OpenAPI spec.")
    openapi_version: str = Field(
        description="OpenAPI specification version declared in the spec file."
    )
    parsed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of parser execution.",
    )
    source_file: str = Field(description="Basename of the input spec file.")
    total_endpoints: int = Field(
        description="Total number of endpoint contracts. Must equal len(endpoints)."
    )
    endpoints: list[EndpointContract] = Field(
        description=(
            "Stripped endpoint contracts sorted by (url, method) for "
            "deterministic diffs."
        )
    )
