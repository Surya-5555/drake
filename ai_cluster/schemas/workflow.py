"""Strict Contract B schemas for discovered enterprise workflows."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

SNAKE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")


class Workflow(BaseModel):
    """Purpose: Represent one business workflow in Contract B.

    Responsibilities:
        Store workflow name, shared parameters, API membership, and optional
        explainability metadata.
    Inputs:
        Structured LLM output or validated workflow JSON.
    Outputs:
        A strict workflow object suitable for downstream MCP generation.
    """

    model_config = ConfigDict(extra="forbid")

    workflow_name: str = Field(min_length=1)
    required_params: list[str] = Field(default_factory=list)
    underlying_api_calls: list[str] = Field(min_length=1)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    reasoning: list[str] | None = None

    @field_validator("workflow_name")
    @classmethod
    def validate_workflow_name(cls, value: str) -> str:
        """Validate workflow names are non-empty snake_case identifiers."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("workflow_name must not be blank")
        if not SNAKE_CASE_PATTERN.fullmatch(stripped):
            raise ValueError("workflow_name must be snake_case")
        return stripped

    @field_validator("required_params", "underlying_api_calls")
    @classmethod
    def validate_string_list(cls, values: list[str]) -> list[str]:
        """Validate list fields contain unique, non-empty strings."""
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            stripped = value.strip()
            if not stripped:
                raise ValueError("list fields must not contain blank values")
            if stripped in seen:
                raise ValueError(f"duplicate list value: {stripped}")
            seen.add(stripped)
            normalized.append(stripped)
        return normalized

    @field_validator("reasoning")
    @classmethod
    def validate_reasoning(cls, values: list[str] | None) -> list[str] | None:
        """Validate optional reasoning contains meaningful entries."""
        if values is None:
            return None
        normalized: list[str] = []
        for value in values:
            stripped = value.strip()
            if not stripped:
                raise ValueError("reasoning must not contain blank values")
            normalized.append(stripped)
        return normalized


class WorkflowMapping(BaseModel):
    """Purpose: Represent the full Contract B output.

    Responsibilities:
        Validate the top-level workflows collection.
    Inputs:
        JSON object containing a workflows array.
    Outputs:
        A Contract B model ready for JSON serialization and downstream use.
    """

    model_config = ConfigDict(extra="forbid")

    workflows: list[Workflow] = Field(min_length=1)
