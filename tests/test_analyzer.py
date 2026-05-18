import pytest
from unittest.mock import MagicMock, patch
from models import WikiNode, Issue
from analyzer import Analyzer, _flatten

FAKE_API_KEY = "sk-ant-test"

def _make_tree() -> list[WikiNode]:
    return [
        WikiNode("n1", "slam_deploy_lisi", "doc", "", False),
        WikiNode("n2", "SLAM部署文档", "doc", "", False),
        WikiNode("n3", "部署流程整理", "doc", "", False),
        WikiNode("n4", "[技术文档][2026-03] 模型量化指南（王五）", "doc", "", False),
    ]


def _mock_claude_response(issues_payload: list[dict]):
    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.input = {"issues": issues_payload}

    message = MagicMock()
    message.content = [tool_use_block]
    return message


def test_analyze_returns_issue_list(mocker):
    issues_payload = [
        {
            "id": "issue_001",
            "type": "duplicate",
            "severity": "high",
            "suggestion": "保留最新版，其余移入_归档",
            "reason": "三份文档主题重叠",
            "node_token": "",
            "current_title": "",
            "node_tokens": ["n1", "n2", "n3"],
            "current_titles": ["slam_deploy_lisi", "SLAM部署文档", "部署流程整理"],
        }
    ]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_claude_response(issues_payload)
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    analyzer = Analyzer(api_key=FAKE_API_KEY)
    issues = analyzer.analyze(_make_tree())

    assert len(issues) == 1
    assert isinstance(issues[0], Issue)
    assert issues[0].type == "duplicate"
    assert issues[0].severity == "high"
    assert issues[0].node_tokens == ["n1", "n2", "n3"]


def test_analyze_returns_empty_for_clean_wiki(mocker):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_claude_response([])
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    analyzer = Analyzer(api_key=FAKE_API_KEY)
    issues = analyzer.analyze([WikiNode("n4", "[技术文档][2026-03] 整洁文档（张三）", "doc", "", False)])
    assert issues == []


def test_analyze_passes_tree_as_json_to_claude(mocker):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_claude_response([])
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    analyzer = Analyzer(api_key=FAKE_API_KEY)
    tree = _make_tree()
    analyzer.analyze(tree)

    call_kwargs = mock_client.messages.create.call_args.kwargs
    user_content = call_kwargs["messages"][0]["content"]
    assert "slam_deploy_lisi" in str(user_content)
    assert "SLAM部署文档" in str(user_content)


def test_flatten_includes_content_when_present():
    node = WikiNode(
        node_token="tok1", title="Doc", node_type="origin",
        parent_node_token="", has_child=False, content="摘要内容"
    )
    result = _flatten([node])
    assert result[0]["content"] == "摘要内容"


def test_flatten_omits_content_when_empty():
    node = WikiNode(
        node_token="tok1", title="Doc", node_type="origin",
        parent_node_token="", has_child=False
    )
    result = _flatten([node])
    assert "content" not in result[0]
