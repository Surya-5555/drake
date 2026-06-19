import pytest
import httpx

@pytest.mark.anyio
async def test_mock_api_health(mock_api_client: httpx.AsyncClient) -> None:
    """
    Test that the Prism mock server is running and returning the exact mock payload for /redfish/v1.
    """
    try:
        response = await mock_api_client.get("/redfish/v1")
        assert response.status_code == 200
        data = response.json()
        assert data.get("@odata.id") == "/redfish/v1"
    except httpx.ConnectError:
        pytest.fail("Failed to connect to the Stoplight Prism mock server. Ensure it is running via docker-compose.")

@pytest.mark.anyio
async def test_mock_api_systems(mock_api_client: httpx.AsyncClient) -> None:
    """
    Test a dynamic path parameter endpoint against the mock server.
    """
    response = await mock_api_client.get(
        "/redfish/v1/Systems/1234",
        auth=("root", "calvin")
    )
    assert response.status_code == 200
