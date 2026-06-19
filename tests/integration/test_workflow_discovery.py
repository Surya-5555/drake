import pytest

def test_workflow_discovery_completes(workflow_pipeline):
    """1. Workflow discovery completes"""
    workflows = workflow_pipeline.discover()
    assert workflows is not None

def test_every_endpoint_belongs_to_workflow(workflow_pipeline, parsed_endpoints):
    """2. Every endpoint belongs to at least one workflow"""
    workflows = workflow_pipeline.get_workflows()
    mapped_endpoints = set()
    for wf in workflows:
        for ep in wf.endpoints:
            mapped_endpoints.add(ep.operation_id)
            
    endpoint_ids = set(ep.operation_id for ep in parsed_endpoints)
    assert endpoint_ids.issubset(mapped_endpoints)

def test_no_orphan_endpoints(workflow_pipeline, parsed_endpoints):
    """3. No orphan endpoints exist"""
    workflows = workflow_pipeline.get_workflows()
    mapped_endpoints = set()
    for wf in workflows:
        for ep in wf.endpoints:
            mapped_endpoints.add(ep.operation_id)
            
    for ep in parsed_endpoints:
        assert ep.operation_id in mapped_endpoints

def test_workflow_count_greater_than_zero(workflow_pipeline):
    """4. Workflow count > 0"""
    workflows = workflow_pipeline.get_workflows()
    assert len(workflows) > 0

def test_workflow_count_less_than_endpoints(workflow_pipeline, parsed_endpoints):
    """5. Workflow count < endpoint count"""
    workflows = workflow_pipeline.get_workflows()
    assert len(workflows) < len(parsed_endpoints)

def test_coverage_100_percent(workflow_pipeline, parsed_endpoints):
    """6. Coverage = 100%"""
    workflows = workflow_pipeline.get_workflows()
    mapped_endpoints = set()
    for wf in workflows:
        for ep in wf.endpoints:
            mapped_endpoints.add(ep.operation_id)
    
    coverage = len(mapped_endpoints) / len(parsed_endpoints)
    assert coverage == 1.0
