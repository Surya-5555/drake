import pytest
import os
from fastapi.testclient import TestClient
from src.proxy.api import app
from unittest.mock import patch, AsyncMock, MagicMock

client = TestClient(app)


@patch("src.proxy.api.sync_workflow_mappings_async")
@patch("src.proxy.api.aiosqlite.connect")
def test_runtime_reload(mock_db_connect, mock_sync_mappings):
    # Setup API key
    valid_key = os.getenv("DELL_MCP_API_KEY", "default_dev_key")

    # Save original reload callback to avoid test pollution
    original_callback = getattr(app.state, "mcp_reload", None)

    # Mock the reload callback
    mock_reload_callback = AsyncMock()
    app.state.mcp_reload = mock_reload_callback

    class MockAioSqliteCursor:
        def __init__(self, result=None):
            self.result = result or {"hash": "SOME_PREVIOUS_HASH"}

        def __await__(self):
            async def _await():
                return self
            return _await().__await__()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def fetchone(self):
            return self.result

        async def fetchall(self):
            return [self.result]

    try:
        # Create mock db connection and context manager
        mock_db = AsyncMock()
        mock_db.execute = MagicMock(return_value=MockAioSqliteCursor())
        mock_db.commit = AsyncMock()
        mock_db_connect.return_value.__aenter__.return_value = mock_db

        response = client.post("/api/v1/mcp/reload", headers={"X-API-Key": valid_key})

        assert response.status_code == 200
        assert response.json() == {"status": "reloaded"}

        # Verify the reload callback was triggered
        mock_reload_callback.assert_called_once()

        # Verify the mappings sync was called
        mock_sync_mappings.assert_called_once()
    finally:
        if original_callback is not None:
            app.state.mcp_reload = original_callback
        else:
            if hasattr(app.state, "mcp_reload"):
                delattr(app.state, "mcp_reload")
