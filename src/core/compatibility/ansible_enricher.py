import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class AnsiblePlaybookEnricher:
    """
    Enriches exported Ansible Playbooks with prerequisite updates, system reboots, and status checks.
    """
    @staticmethod
    def enrich_playbook_tasks(steps: List[Any]) -> List[Dict[str, Any]]:
        """
        Scan workflow steps and enrich the playbook configuration tasks if target firmware updates are requested.
        """
        def get_val(obj, key, default=None):
            try:
                return obj[key]
            except (KeyError, TypeError, IndexError):
                try:
                    return getattr(obj, key, default)
                except AttributeError:
                    return default

        has_firmware_update = False
        has_bios_update = False

        for step in steps:
            url = get_val(step, "url", "") or ""
            op_id = get_val(step, "operation_id", "") or get_val(step, "operationId", "") or ""
            method = get_val(step, "method", "") or ""

            if "UpdateService.SimpleUpdate" in url or "SimpleUpdate" in op_id or "UpdateService.Install" in url:
                has_firmware_update = True
            if "Systems" in url and method.upper() in ("PATCH", "POST"):
                has_bios_update = True
            if "BIOS_UPDATE" in op_id:
                has_bios_update = True

        if not has_firmware_update or has_bios_update:
            # Map standard tasks directly without changes
            mapped_tasks = []
            for idx, step in enumerate(steps):
                url_str = get_val(step, "url", "")
                method_str = get_val(step, "method", "").upper()
                task_data = {
                    "name": f"Step {idx + 1} - {method_str} {url_str}",
                    "ansible.builtin.uri": {
                        "url": f"https://{{{{ idrac_ip }}}}{url_str}",
                        "method": method_str,
                        "user": "{{ idrac_user }}",
                        "password": "{{ idrac_password }}",
                        "force_basic_auth": True,
                        "validate_certs": False,
                        "status_code": [200, 201, 202, 204],
                    }
                }
                if method_str in ["POST", "PATCH", "PUT"]:
                    task_data["ansible.builtin.uri"]["body_format"] = "json"
                    task_data["ansible.builtin.uri"]["body"] = {
                        "Target": "Example"
                    }
                task_data["register"] = f"step_{idx + 1}_result"
                mapped_tasks.append(task_data)
            return mapped_tasks

        # Inject BIOS prerequisite updates, reboot, and verify steps
        enriched_tasks = []
        
        # 1. Add BIOS Update step
        bios_update_task = {
            "name": "Prerequisite Step 1 - Update System BIOS to 2.12.0",
            "ansible.builtin.uri": {
                "url": "https://{{ idrac_ip }}/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
                "method": "POST",
                "user": "{{ idrac_user }}",
                "password": "{{ idrac_password }}",
                "force_basic_auth": True,
                "validate_certs": False,
                "status_code": [200, 202],
                "body_format": "json",
                "body": {
                    "ImageURI": "http://downloads.dell.com/FOLDER123/BIOS_2.12.0.exe",
                    "TransferProtocol": "HTTP",
                    "Targets": ["/redfish/v1/Systems/System.Embedded.1"]
                }
            },
            "register": "bios_update_result"
        }
        
        # 2. Add Reboot System task
        reboot_task = {
            "name": "Prerequisite Step 2 - Reboot System for BIOS Installation",
            "ansible.builtin.uri": {
                "url": "https://{{ idrac_ip }}/redfish/v1/Systems/System.Embedded.1/Actions/ComputerSystem.Reset",
                "method": "POST",
                "user": "{{ idrac_user }}",
                "password": "{{ idrac_password }}",
                "force_basic_auth": True,
                "validate_certs": False,
                "status_code": [200, 204],
                "body_format": "json",
                "body": {
                    "ResetType": "GracefulRestart"
                }
            },
            "register": "reboot_result"
        }

        # 3. Add Pause / Wait for connection task
        wait_task = {
            "name": "Prerequisite Step 3 - Wait for iDRAC to become responsive after reboot",
            "ansible.builtin.wait_for": {
                "host": "{{ idrac_ip }}",
                "port": 443,
                "delay": 30,
                "timeout": 300
            }
        }

        # 4. Verify BIOS Update task
        verify_task = {
            "name": "Prerequisite Step 4 - Verify System BIOS Version >= 2.12.0",
            "ansible.builtin.uri": {
                "url": "https://{{ idrac_ip }}/redfish/v1/Systems/System.Embedded.1",
                "method": "GET",
                "user": "{{ idrac_user }}",
                "password": "{{ idrac_password }}",
                "force_basic_auth": True,
                "validate_certs": False,
                "status_code": [200]
            },
            "register": "verify_bios_result",
            "failed_when": "verify_bios_result.json.BiosVersion is version('2.12.0', '<')"
        }

        enriched_tasks.extend([bios_update_task, reboot_task, wait_task, verify_task])

        # Now append the original tasks (with offset indices)
        for idx, step in enumerate(steps):
            url_str = get_val(step, "url", "")
            method_str = get_val(step, "method", "").upper()
            task_data = {
                "name": f"Step {idx + 5} - {method_str} {url_str}",
                "ansible.builtin.uri": {
                    "url": f"https://{{{{ idrac_ip }}}}{url_str}",
                    "method": method_str,
                    "user": "{{ idrac_user }}",
                    "password": "{{ idrac_password }}",
                    "force_basic_auth": True,
                    "validate_certs": False,
                    "status_code": [200, 201, 202, 204],
                }
            }
            if method_str in ["POST", "PATCH", "PUT"]:
                task_data["ansible.builtin.uri"]["body_format"] = "json"
                task_data["ansible.builtin.uri"]["body"] = {
                    "Target": "Example"
                }
            task_data["register"] = f"step_{idx + 5}_result"
            enriched_tasks.append(task_data)

        return enriched_tasks
