"""Strict Contract B schemas for discovered enterprise workflows and rollback state."""

from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Step(BaseModel):
    """
    Pydantic schema representing a single step in a workflow.
    """
    id: str = Field(description="Unique identifier for the step (e.g., step_1).")
    operation_id: str = Field(description="The underlying OpenAPI operation ID.")
    returned_state_variables: list[str] = Field(
        default_factory=list,
        description="Variables returned by this step to be passed as inputs to subsequent steps."
    )


class Workflow(BaseModel):
    """
    Pydantic schema representing a Dell MCP Workflow.
    
    This model includes metadata about the workflow execution parameters and 
    controls for the State-Aware Universal Rollback Architecture.
    """
    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Unique workflow identifier.")
    system_name: str = Field(description="System-friendly name of the workflow.")
    display_name: str = Field(description="Human-readable display name.")
    risk_level: Optional[str] = Field(None, description="Risk classification of the workflow steps.")
    cluster_size: Optional[int] = Field(None, description="Number of underlying API endpoints grouped in this workflow.")
    confidence: Optional[float] = Field(None, description="Clustering algorithm confidence score.")
    generated_description: Optional[str] = Field(None, description="AI-generated description explaining workflow actions.")
    approved: int = Field(default=0, description="Workflow approval status (0=pending, 1=approved, 2=rejected).")
    rejection_reason: Optional[str] = Field(None, description="Reason for rejection, if applicable.")
    community_id: Optional[str] = Field(None, description="Underlying community or cluster ID.")
    
    # AUDIT1.MD Fix: Multi-step orchestration variables and steps list
    steps: list[Step] = Field(default_factory=list, description="Ordered steps in this workflow.")
    returned_state_variables: list[str] = Field(
        default_factory=list,
        description="State variables returned/managed by this workflow's steps."
    )

    supports_rollback: bool = Field(
        default=False, 
        description="Whether this workflow supports state rollback or firmware reversion."
    )
    rollback_strategy: Literal["DUAL_BANK", "SCP_SNAPSHOT", "NONE"] = Field(
        default="NONE",
        description=(
            "The rollback strategy employed for this workflow. "
            "DUAL_BANK is for firmware (relying on Dell iDRAC hardware partitions), "
            "SCP_SNAPSHOT is for BIOS/Config changes, and NONE is for destructive "
            "actions (e.g., Factory Reset)."
        )
    )

    @field_validator("display_name", "system_name")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        """Validate string fields are non-empty."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank")
        return stripped
