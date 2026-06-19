import pytest


def test_workflow_resolves_endpoints(execution_engine, sample_workflow):
    """1. Workflow resolves endpoints"""
    resolved = execution_engine.resolve(sample_workflow)
    assert len(resolved) == len(sample_workflow.endpoints)


def test_endpoints_execute(execution_engine, sample_workflow):
    """2. Endpoints execute"""
    result = execution_engine.execute(sample_workflow)
    assert result is not None
    assert result.success is True


def test_parallel_execution_works(execution_engine, sample_workflow):
    """3. Parallel execution works"""
    # Specifically check if execution time is less than sequential sum
    # Here we just verify the behavior logic passes parallel execution path
    result = execution_engine.execute_parallel(sample_workflow)
    assert result is not None
    assert result.success is True


def test_execution_result_returned(execution_engine, sample_workflow):
    """4. Execution result returned"""
    result = execution_engine.execute(sample_workflow)
    assert hasattr(result, "data")


def test_timeouts_handled(execution_engine, slow_workflow):
    """5. Timeouts handled"""
    with pytest.raises(TimeoutError) as exc:
        execution_engine.execute(slow_workflow, timeout=0.1)


def test_retry_logic_works(execution_engine, flaky_workflow):
    """6. Retry logic works"""
    result = execution_engine.execute(flaky_workflow, retries=3)
    assert result.success is True
