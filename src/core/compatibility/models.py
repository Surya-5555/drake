from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

# ===========================================================================
# Compatibility and Risk Enums
# ===========================================================================


class CompatibilityStatus(str, Enum):
    ALLOW = "ALLOW"
    WARN = "WARN"
    BLOCK = "BLOCK"


class CompatibilityDomain(str, Enum):
    BIOS = "BIOS"
    FIRMWARE = "FIRMWARE"
    HARDWARE = "HARDWARE"
    POWER = "POWER"
    STORAGE = "STORAGE"
    GOVERNANCE = "GOVERNANCE"
    TELEMETRY = "TELEMETRY"


class RiskLevel(str, Enum):
    READ_ONLY = "READ_ONLY"
    CONFIG_CHANGE = "CONFIG_CHANGE"
    DESTRUCTIVE = "DESTRUCTIVE"


# ===========================================================================
# Target Metadata and Capabilities Schemas
# ===========================================================================


class DeviceFacts(BaseModel):
    """
    Schema representing physical server configurations parsed at runtime.
    """

    target_ip: str = Field(description="Target server management IP address.")
    device_model: str = Field(
        description="System hardware model (e.g. PowerEdge R750)."
    )
    bios_version: str = Field(description="System BIOS version (e.g. 2.12.2).")
    lifecycle_controller_version: Optional[str] = Field(
        default=None, description="iDRAC Lifecycle Controller version."
    )
    firmware_inventory: Dict[str, str] = Field(
        default_factory=dict,
        description="Key-value mapping of component firmware versions (e.g. iDRAC9, StorageController).",
    )
    last_scanned: Optional[datetime] = Field(
        default=None, description="Timestamp of when facts were retrieved."
    )
    is_live: bool = Field(
        default=True, description="Whether the facts were fetched live or from cache."
    )


class RiskProfile(BaseModel):
    id: str
    profile_name: str
    base_risk_level: RiskLevel
    method_adjustments: Dict[str, int] = Field(default_factory=dict)
    order_coefficient: float = 1.0
    max_risk_score: int = 100


class CapabilityInfo(BaseModel):
    """
    Schema representing dynamic capability mapping for an operation ID.
    """

    operation_id: str
    capability_name: str
    compatibility_domain: CompatibilityDomain
    default_risk_level: RiskLevel
    parameters_schema: Dict[str, Any] = Field(default_factory=dict)
    risk_profile_id: Optional[str] = None
    is_manual_override: int = 0
    discovery_confidence: float = 1.0


# ===========================================================================
# Polymorphic Rules Schemas
# ===========================================================================


class BaseRuleConfig(BaseModel):
    """Base empty schema for rule configs."""

    pass


class HardwareRuleConfig(BaseRuleConfig):
    supported_models: List[str] = Field(
        description="List of supported PowerEdge hardware models."
    )


class FirmwareRuleConfig(BaseRuleConfig):
    target_component: str = Field(
        description="Target component identifier (e.g. iDRAC9, NIC)."
    )
    min_version: str = Field(description="Minimum supported firmware version.")
    max_version: Optional[str] = Field(
        default=None, description="Optional upper boundary limit version."
    )


class BIOSRuleConfig(BaseRuleConfig):
    device_model: str = Field(description="Hardware model name matching target.")
    min_bios_version: str = Field(description="Minimum supported BIOS version.")


class DependencyRuleConfig(BaseRuleConfig):
    prerequisite_operation_id: str = Field(description="Prerequisite endpoint step.")
    target_operation_id: str = Field(description="Operation requiring prerequisite.")


class WorkflowSafetyRuleConfig(BaseRuleConfig):
    forbidden_combinations: List[str] = Field(
        description="List of operation IDs that cannot execute in same sequence."
    )


# ===========================================================================
# Compliance and Validation Output Reports
# ===========================================================================


class CompatibilityFinding(BaseModel):
    """
    A single compatibility message generated during rules validation.
    """

    title: str = Field(description="Finding title description.")
    severity: Literal["low", "medium", "high", "critical"] = Field(
        description="Assessed issue severity."
    )
    message: str = Field(description="Detailed diagnostic findings explanation.")
    suggested_action: str = Field(
        description="Suggested remediation step for human operators."
    )


class CompatibilityViolation(BaseModel):
    """
    A structural rule validation failure that could block execution.
    """

    rule_id: str
    field_checked: str
    expected_value: str
    actual_value: str
    remediation_step: str


class CompatibilityReport(BaseModel):
    """
    Aggregated compliance evaluation report containing scores, heatmaps, and verdicts.
    """

    id: str = Field(description="Unique report ID.")
    workflow_id: str = Field(description="Evaluated workflow ID.")
    target_ip: str = Field(description="Target device IP validated against.")
    status: CompatibilityStatus = Field(description="Overall execution decision.")
    compatibility_score: int = Field(
        ge=0, le=100, description="Structural and version validation score."
    )
    risk_score: int = Field(
        ge=0, le=100, description="Workflows execution severity risk score."
    )
    blast_radius: str = Field(
        description="Containment boundary level: NODE, CHASSIS, RACK, CLUSTER."
    )
    confidence_score: int = Field(
        ge=0, le=100, description="Freshness and catalog completeness rating."
    )
    findings: List[CompatibilityFinding] = Field(default_factory=list)
    violations: List[CompatibilityViolation] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BaseExplainabilityReport(BaseModel):
    workflow_id: str
    workflow_display_name: str
    compatibility_score: int
    overall_risk_level: str
    confidence_level: int
    blast_radius: str
    unsupported_models: List[str] = Field(default_factory=list)
    remediation_actions: List[str] = Field(default_factory=list)
    risk_heatmap_data: Dict[str, Any] = Field(default_factory=dict)


class GovernanceExplainabilityReport(BaseExplainabilityReport):
    dependency_graph_mermaid: str
