import pytest
import time


@pytest.mark.parametrize("endpoint_count", [50, 200, 500])
def test_discovery_scalability(
    workflow_pipeline, mock_endpoints_generator, endpoint_count
):
    """
    Run: 50, 200, 500 endpoints
    Verify: Discovery completes, memory stable, no crashes
    """
    endpoints = mock_endpoints_generator(endpoint_count)

    start_time = time.time()
    # Assuming workflow_pipeline takes a list of endpoints or a graph directly
    workflows = workflow_pipeline.discover_from_endpoints(endpoints)
    end_time = time.time()

    duration = end_time - start_time

    # Discovery completes
    assert workflows is not None
    assert len(workflows) > 0
    assert len(workflows) <= endpoint_count

    # Simple arbitrary sanity check for execution time (e.g. under 10 seconds for 500 endpoints)
    assert duration < 10.0
