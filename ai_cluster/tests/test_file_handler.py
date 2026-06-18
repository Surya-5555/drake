import json
from pathlib import Path

import pytest

from ai_cluster.utils.file_handler import FileHandler


def test_file_handler_reads_json(tmp_path: Path) -> None:
    path = tmp_path / "contract_a.json"
    path.write_text(json.dumps([{"operationId": "getPower"}]), encoding="utf-8")

    payload = FileHandler().read_json(path)

    assert payload == [{"operationId": "getPower"}]


def test_file_handler_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{broken", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid JSON"):
        FileHandler().read_json(path)

