import pytest
import sqlite3
from src.core.database import DB_FILE, init_db_sync, save_workflows, save_endpoints
import asyncio
from unittest.mock import patch, MagicMock


@pytest.fixture
def setup_db():
    init_db_sync()
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM workflows")
        conn.execute("DELETE FROM endpoint_steps")
        conn.execute("DELETE FROM endpoints")
        conn.commit()
    yield
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM workflows")
        conn.execute("DELETE FROM endpoint_steps")
        conn.execute("DELETE FROM endpoints")
        conn.commit()


def test_endpoint_steps_generation(setup_db):
    # Insert dummy endpoint
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "INSERT INTO endpoints (operation_id, method, url, required_params, community_id) VALUES (?, ?, ?, ?, ?)",
            ("op1", "GET", "/Systems/{id}", '["id"]', "comm_1"),
        )
        conn.execute(
            "INSERT INTO endpoints (operation_id, method, url, required_params, community_id) VALUES (?, ?, ?, ?, ?)",
            ("op2", "POST", "/Systems/{id}/Reset", '["id", "type"]', "comm_1"),
        )
        conn.commit()

    # Save workflow
    wf_list = [
        {
            "id": "wf_1",
            "workflow_name": "Reset System",
            "risk_level": "High",
            "cluster_size": 2,
            "confidence": 0.9,
            "generated_description": "Resets the system",
            "community_id": "comm_1",
        }
    ]

    save_workflows(wf_list)

    # Check endpoint steps
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        steps = conn.execute(
            "SELECT * FROM endpoint_steps WHERE workflow_id = 'wf_1' ORDER BY step_order"
        ).fetchall()

    assert len(steps) == 2
    assert steps[0]["operation_id"] == "op1"
    assert steps[0]["method"] == "GET"
    assert steps[0]["url"] == "/Systems/{id}"

    assert steps[1]["operation_id"] == "op2"
    assert steps[1]["method"] == "POST"
    assert steps[1]["url"] == "/Systems/{id}/Reset"
