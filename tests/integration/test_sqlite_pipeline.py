import pytest

def test_workflow_persists_to_database(db_pipeline, sample_workflow):
    """1. Workflow persists to database"""
    db_pipeline.save_workflow(sample_workflow)
    stored = db_pipeline.get_workflow(sample_workflow.id)
    assert stored is not None
    assert stored.id == sample_workflow.id

def test_approval_status_stored(db_pipeline, sample_workflow):
    """2. Approval status stored"""
    sample_workflow.approved = 1
    db_pipeline.save_workflow(sample_workflow)
    stored = db_pipeline.get_workflow(sample_workflow.id)
    assert stored.approved == 1

def test_risk_level_stored(db_pipeline, sample_workflow):
    """3. Risk level stored"""
    sample_workflow.risk_level = "DESTRUCTIVE"
    db_pipeline.save_workflow(sample_workflow)
    stored = db_pipeline.get_workflow(sample_workflow.id)
    assert stored.risk_level == "DESTRUCTIVE"

def test_version_stored(db_pipeline, sample_workflow):
    """4. Version stored"""
    sample_workflow.version = "1.0.0"
    db_pipeline.save_workflow(sample_workflow)
    stored = db_pipeline.get_workflow(sample_workflow.id)
    assert getattr(stored, 'version', None) == "1.0.0"

def test_audit_log_generated(db_pipeline, sample_workflow):
    """5. Audit log generated"""
    initial_logs = len(db_pipeline.get_audit_logs())
    db_pipeline.log_action("SAVE", sample_workflow.id)
    logs = db_pipeline.get_audit_logs()
    assert len(logs) == initial_logs + 1
    assert logs[-1].action == "SAVE"
    assert logs[-1].workflow_id == sample_workflow.id

def test_workflow_retrieval_works(db_pipeline, sample_workflow):
    """6. Workflow retrieval works"""
    db_pipeline.save_workflow(sample_workflow)
    retrieved = db_pipeline.get_workflow(sample_workflow.id)
    assert retrieved.name == sample_workflow.name
    assert retrieved.endpoints == sample_workflow.endpoints
