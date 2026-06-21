

def test_every_workflow_receives_name(labeling_pipeline):
    """1. Every workflow receives a name"""
    workflows = labeling_pipeline.get_labeled_workflows()
    for wf in workflows:
        assert getattr(wf, "name", None) is not None
        assert isinstance(wf.name, str)


def test_every_workflow_receives_description(labeling_pipeline):
    """2. Every workflow receives a description"""
    workflows = labeling_pipeline.get_labeled_workflows()
    for wf in workflows:
        assert getattr(wf, "description", None) is not None
        assert isinstance(wf.description, str)


def test_empty_names_rejected(labeling_pipeline):
    """3. Empty names rejected"""
    workflows = labeling_pipeline.get_labeled_workflows()
    for wf in workflows:
        assert len(wf.name.strip()) > 0


def test_duplicate_workflow_ids_rejected(labeling_pipeline):
    """4. Duplicate workflow IDs rejected"""
    workflows = labeling_pipeline.get_labeled_workflows()
    ids = [wf.id for wf in workflows]
    assert len(ids) == len(set(ids))


def test_risk_classification_assigned(labeling_pipeline):
    """5. Risk classification assigned"""
    valid_risks = ["READ_ONLY", "CONFIG_CHANGE", "DESTRUCTIVE"]
    workflows = labeling_pipeline.get_labeled_workflows()
    for wf in workflows:
        assert getattr(wf, "risk_level", None) in valid_risks
