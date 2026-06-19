"""Strict Contract B schemas for discovered enterprise workflows."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

SNAKE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")


class LLMNamingResponse(BaseModel):
    """Purpose: Represent structured LLM naming response.
    
    Responsibilities:
        Capture display_name and generated_description.
    """
    model_config = ConfigDict(extra="forbid")
    
    display_name: str = Field(min_length=1)
    generated_description: str = Field(min_length=1)

    @field_validator("display_name", "generated_description")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        """Validate string fields are non-empty."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank")
        return stripped


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

    workflows: list[LLMNamingResponse] = Field(min_length=1)
