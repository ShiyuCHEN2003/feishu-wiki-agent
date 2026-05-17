import json
import os
import pytest
from models import LogEntry
from logger import Logger


@pytest.fixture
def tmp_logger(tmp_path):
    log_file = tmp_path / "operations.json"
    return Logger(log_path=str(log_file))


def _make_entry(issue_id="issue_001", action="rename") -> LogEntry:
    return LogEntry(
        timestamp="2026-05-17T14:32:00+08:00",
        action=action,
        node_token="abc123",
        from_value="旧文档名",
        to_value="[技术文档][2026-05] 新文档名",
        operator="system",
        confirmed_by="user",
        issue_id=issue_id,
    )


def test_record_creates_file(tmp_logger, tmp_path):
    tmp_logger.record(_make_entry())
    log_file = tmp_path / "operations.json"
    assert log_file.exists()


def test_record_appends_valid_json(tmp_logger, tmp_path):
    tmp_logger.record(_make_entry("issue_001"))
    tmp_logger.record(_make_entry("issue_002"))
    log_file = tmp_path / "operations.json"
    lines = log_file.read_text().strip().splitlines()
    assert len(lines) == 2
    for line in lines:
        data = json.loads(line)
        assert "timestamp" in data
        assert "from" in data  # LogEntry.to_dict() maps from_value → "from"
        assert "to" in data


def test_read_recent_returns_latest_n(tmp_logger):
    for i in range(5):
        tmp_logger.record(_make_entry(f"issue_{i:03d}"))
    recent = tmp_logger.read_recent(n=3)
    assert len(recent) == 3
    assert recent[0]["issue_id"] == "issue_004"  # most recent first


def test_read_recent_empty_file_returns_empty(tmp_logger):
    assert tmp_logger.read_recent() == []
