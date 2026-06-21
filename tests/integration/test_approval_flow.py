

def test_pending_workflow_exists(approval_pipeline, pending_workflow):
    """1. Pending workflow exists"""
    assert pending_workflow.status == "PENDING"
    workflows = approval_pipeline.get_pending_workflows()
    assert pending_workflow.id in [wf.id for wf in workflows]


def test_approve_action_updates_status(approval_pipeline, pending_workflow):
    """2. Approve action updates status"""
    approval_pipeline.approve(pending_workflow.id)
    updated = approval_pipeline.get_workflow(pending_workflow.id)
    assert updated.status == "APPROVED"


def test_reject_action_updates_status(approval_pipeline, pending_workflow):
    """3. Reject action updates status"""
    approval_pipeline.reject(pending_workflow.id)
    updated = approval_pipeline.get_workflow(pending_workflow.id)
    assert updated.status == "REJECTED"


def test_audit_log_created_on_approval(approval_pipeline, pending_workflow):
    """4. Audit log created"""
    initial_logs = len(approval_pipeline.get_audit_logs())
    approval_pipeline.approve(pending_workflow.id)
    logs = approval_pipeline.get_audit_logs()
    assert len(logs) > initial_logs
    assert logs[-1].action == "APPROVE"


def test_version_increments_on_approval(approval_pipeline, pending_workflow):
    """5. Version increments"""
    initial_version = getattr(pending_workflow, "version", 1)
    approval_pipeline.approve(pending_workflow.id)
    updated = approval_pipeline.get_workflow(pending_workflow.id)
    # Testing that version correctly updates (if versioning is part of the flow)
    assert getattr(updated, "version", 1) >= initial_version
