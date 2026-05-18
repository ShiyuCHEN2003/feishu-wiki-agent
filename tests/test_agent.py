import pytest
from unittest.mock import MagicMock, patch
from models import Issue


def test_parse_intent_scan():
    from agent import parse_intent
    assert parse_intent("扫描") == "scan"
    assert parse_intent("scan") == "scan"
    assert parse_intent("SCAN") == "scan"


def test_parse_intent_log():
    from agent import parse_intent
    assert parse_intent("查看日志") == "log"
    assert parse_intent("日志") == "log"


def test_parse_intent_help():
    from agent import parse_intent
    assert parse_intent("help") == "help"
    assert parse_intent("帮助") == "help"


def test_parse_intent_confirm():
    from agent import parse_intent
    assert parse_intent("确认") == "confirm"
    assert parse_intent("同意") == "confirm"


def test_parse_intent_skip():
    from agent import parse_intent
    assert parse_intent("跳过") == "skip"


def test_parse_intent_cancel():
    from agent import parse_intent
    assert parse_intent("取消全部") == "cancel"
    assert parse_intent("取消") == "cancel"


def test_format_issue_naming():
    from agent import format_issue
    issue = Issue(
        id="issue_001", type="naming", severity="medium",
        suggestion="重命名为 [技术文档][2026-05] SLAM部署指南（李四）",
        reason="缺少类型标签", node_token="n1", current_title="slam_deploy_lisi",
    )
    output = format_issue(issue, index=1, total=5)
    assert "1/5" in output
    assert "slam_deploy_lisi" in output
    assert "重命名" in output
    assert "缺少类型标签" in output


def test_format_issue_duplicate():
    from agent import format_issue
    issue = Issue(
        id="issue_002", type="duplicate", severity="high",
        suggestion="保留最新版，其余移入_归档",
        reason="主题重叠",
        node_tokens=["n1", "n2", "n3"],
        current_titles=["SLAM部署文档", "slam_deploy_lisi", "部署流程整理"],
    )
    output = format_issue(issue, index=2, total=5)
    assert "SLAM部署文档" in output
    assert "slam_deploy_lisi" in output
    assert "主题重叠" in output
