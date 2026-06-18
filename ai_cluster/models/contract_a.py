"""Strict models for Person 2's Contract A endpoint inventory."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


class ApiEndpoint(BaseModel):
    """Purpose: Represent one OpenAPI operation from Contract A.

    Responsibilities:
        Validate operation identity, HTTP method, path, and required parameters.
    Inputs:
        JSON object containing operationId, method, url, and required_params.
    Outputs:
        A normalized endpoint model for workflow clustering.
    """

    model_config = ConfigDict(extra="forbid")

    operationId: str = Field(min_length=1)
    method: HttpMethod
    url: str = Field(min_length=1)
    required_params: list[str] = Field(default_factory=list)

    @field_validator("operationId", "url")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        """Validate that string fields are not blank after trimming."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank")
        return stripped

    @field_validator("required_params")
    @classmethod
    def validate_required_params(cls, values: list[str]) -> list[str]:
        """Validate required parameters are unique, non-empty strings."""
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            stripped = value.strip()
            if not stripped:
                raise ValueError("required_params must not contain blank values")
            if stripped in seen:
                raise ValueError(f"duplicate required parameter: {stripped}")
            seen.add(stripped)
            normalized.append(stripped)
        return normalized

