from src.core.models import EndpointContract
from ai_cluster.prompts.workflow_prompt import WorkflowPromptBuilder


def test_prompt_contains_enterprise_architect_instructions() -> None:
    endpoints = [
        EndpointContract(
            operation_id="getThermal",
            method="GET",
            url="/redfish/v1/Thermal",
            required_params=[],
        )
    ]

    prompt = WorkflowPromptBuilder().build(endpoints)

    assert "You are a Dell Enterprise Infrastructure Architect" in prompt
    assert "Do not group solely by path similarity" in prompt
    assert "Return only JSON matching the supplied schema" in prompt
    assert "getThermal" in prompt
