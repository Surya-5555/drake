from functools import cached_property
from src.cli.services import (
    ClusterCLIService,
    GovernanceCLIService,
    CompatibilityCLIService,
    RuntimeCLIService,
    AnsibleCLIService,
    SystemCLIService,
    DiagnosticsCLIService,
    AuditCLIService,
)


class CLIContainer:
    """Central Dependency Injection container utilizing lazy cached property resolution."""

    @cached_property
    def cluster_service(self) -> ClusterCLIService:
        return ClusterCLIService()

    @cached_property
    def governance_service(self) -> GovernanceCLIService:
        return GovernanceCLIService()

    @cached_property
    def compatibility_service(self) -> CompatibilityCLIService:
        return CompatibilityCLIService()

    @cached_property
    def runtime_service(self) -> RuntimeCLIService:
        return RuntimeCLIService()

    @cached_property
    def ansible_service(self) -> AnsibleCLIService:
        return AnsibleCLIService()

    @cached_property
    def system_service(self) -> SystemCLIService:
        return SystemCLIService()

    @cached_property
    def diagnostics_service(self) -> DiagnosticsCLIService:
        return DiagnosticsCLIService()

    @cached_property
    def audit_service(self) -> AuditCLIService:
        return AuditCLIService()
