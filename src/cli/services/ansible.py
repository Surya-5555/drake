from typing import Any, Dict
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.cli.exceptions import DellCLIError
from src.core.database import async_session, Workflow
from src.core.compatibility.ansible_enricher import AnsiblePlaybookEnricher
from .bridge import AsyncServiceBridge


class AnsibleCLIService:
    """Adapter for playbook generation and task transformations."""

    def get_playbook(self, workflow_id: str) -> Dict[str, Any]:
        async def _async_get_playbook() -> Dict[str, Any]:
            async with async_session() as session:
                result = await session.execute(
                    select(Workflow)
                    .where(Workflow.id == workflow_id)
                    .options(selectinload(Workflow.steps))
                )
                wf = result.scalar_one_or_none()
                if not wf:
                    raise DellCLIError(
                        title="Ansible Export Failed",
                        cause=f"Workflow '{workflow_id}' not found.",
                        impact="Configuration tasks cannot be compiled.",
                        action="Check spelling of workflow ID.",
                    )
                steps = wf.steps

            tasks = AnsiblePlaybookEnricher.enrich_playbook_tasks(steps)
            playbook = [
                {
                    "name": f"Dell MCP Workflow Playbook: {wf.display_name}",
                    "hosts": "idrac_servers",
                    "gather_facts": False,
                    "vars": {
                        "idrac_ip": "192.168.1.100",
                        "idrac_user": "root",
                        "idrac_password": "calvin",
                    },
                    "tasks": tasks,
                }
            ]
            import yaml

            return {"yaml_content": yaml.dump(playbook, sort_keys=False)}

        return AsyncServiceBridge.run(_async_get_playbook())  # type: ignore[no-any-return]
