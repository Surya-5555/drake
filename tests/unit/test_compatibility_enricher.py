from src.core.compatibility.ansible_enricher import AnsiblePlaybookEnricher


# Mock step helpers
class MockStepObj:
    def __init__(self, url, method, op_id):
        self.url = url
        self.method = method
        self.operation_id = op_id


def test_enricher_get_val_branches():
    enricher = AnsiblePlaybookEnricher()

    # 1. Dict success
    d_ok = {"url": "/test"}
    assert (
        enricher.enrich_playbook_tasks([d_ok])[0]["ansible.builtin.uri"]["url"]
        == "https://{{ idrac_ip }}/test"
    )

    # 2. Dict KeyError -> falls back to getattr -> returns default
    d_key_err = {"method": "GET"}  # url key is missing, so it raises KeyError inside []
    res = enricher.enrich_playbook_tasks([d_key_err])
    assert (
        res[0]["ansible.builtin.uri"]["url"] == "https://{{ idrac_ip }}"
    )  # defaults to empty string

    # 3. TypeError (e.g. integer or list index lookup on dict)
    # Inside get_val: obj["url"] raises TypeError if obj is a list
    list_obj = ["/test"]
    res = enricher.enrich_playbook_tasks([list_obj])
    assert (
        res[0]["ansible.builtin.uri"]["url"] == "https://{{ idrac_ip }}"
    )  # defaults to empty string

    # 4. Attribute fallback success (object lookup)
    obj_ok = MockStepObj("/test_obj", "POST", "op1")
    res_obj = enricher.enrich_playbook_tasks([obj_ok])
    assert res_obj[0]["ansible.builtin.uri"]["url"] == "https://{{ idrac_ip }}/test_obj"
    assert res_obj[0]["ansible.builtin.uri"]["method"] == "POST"

    # 5. AttributeError fallback (object without attribute)
    class MockNoAttr:
        pass

    obj_no_attr = MockNoAttr()
    res_no_attr = enricher.enrich_playbook_tasks([obj_no_attr])
    assert res_no_attr[0]["ansible.builtin.uri"]["url"] == "https://{{ idrac_ip }}"

    # 6. AttributeError raised dynamically via property access
    class MockBadAttr:
        @property
        def url(self):
            raise AttributeError("Simulated property error")

    obj_bad = MockBadAttr()
    res_bad = enricher.enrich_playbook_tasks([obj_bad])
    assert res_bad[0]["ansible.builtin.uri"]["url"] == "https://{{ idrac_ip }}"


def test_enricher_no_enrichment_needed():
    # Scenario: No firmware update requested
    steps = [
        {"url": "/redfish/v1/Systems/1", "method": "GET"},
        {"url": "/redfish/v1/Chassis/1", "method": "GET"},
    ]
    tasks = AnsiblePlaybookEnricher.enrich_playbook_tasks(steps)
    # Should map tasks directly without adding prerequisite steps
    assert len(tasks) == 2
    assert tasks[0]["name"] == "Step 1 - GET /redfish/v1/Systems/1"
    assert tasks[0]["register"] == "step_1_result"


def test_enricher_enrichment_bios_already_present():
    # Scenario: Has firmware update but BIOS update is ALREADY present
    steps = [
        {
            "url": "/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
            "method": "POST",
            "operation_id": "SimpleUpdate",
        },
        {"url": "/redfish/v1/Systems/1", "method": "PATCH"},  # BIOS update
    ]
    tasks = AnsiblePlaybookEnricher.enrich_playbook_tasks(steps)
    # Should map tasks directly without duplicate prerequisites
    assert len(tasks) == 2
    assert (
        tasks[0]["name"]
        == "Step 1 - POST /redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate"
    )
    assert tasks[0]["ansible.builtin.uri"]["body_format"] == "json"

    # Scenario: BIOS_UPDATE in op_id is also recognized as bios update
    steps_op = [
        {
            "url": "/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
            "method": "POST",
            "operation_id": "SimpleUpdate",
        },
        {"url": "/redfish/v1/SomeUrl", "method": "POST", "operation_id": "BIOS_UPDATE"},
    ]
    tasks_op = AnsiblePlaybookEnricher.enrich_playbook_tasks(steps_op)
    assert len(tasks_op) == 2


def test_enricher_injects_prerequisites():
    # Scenario: Has firmware update but NO BIOS update present
    steps = [
        {
            "url": "/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
            "method": "POST",
            "operation_id": "SimpleUpdate",
        },
        {"url": "/redfish/v1/Chassis/1", "method": "GET", "operation_id": "GetChassis"},
    ]
    tasks = AnsiblePlaybookEnricher.enrich_playbook_tasks(steps)

    # 4 prerequisites + 2 original steps = 6 tasks
    assert len(tasks) == 6

    # Verify prerequisites
    assert tasks[0]["name"] == "Prerequisite Step 1 - Update System BIOS to 2.12.0"
    assert (
        tasks[1]["name"] == "Prerequisite Step 2 - Reboot System for BIOS Installation"
    )
    assert (
        tasks[2]["name"]
        == "Prerequisite Step 3 - Wait for iDRAC to become responsive after reboot"
    )
    assert (
        tasks[3]["name"] == "Prerequisite Step 4 - Verify System BIOS Version >= 2.12.0"
    )

    # Verify offset original tasks
    assert (
        tasks[4]["name"]
        == "Step 5 - POST /redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate"
    )
    assert tasks[5]["name"] == "Step 6 - GET /redfish/v1/Chassis/1"

    # Verify original task register names are offset
    assert tasks[4]["register"] == "step_5_result"
    assert tasks[5]["register"] == "step_6_result"
