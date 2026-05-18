import time
import pytest
from unittest.mock import patch, MagicMock
from config import Config
from feishu_client import FeishuClient
from models import WikiNode

FAKE_CONFIG = Config(
    app_id="cli_test",
    app_secret="secret123",
    wiki_space_id="space456",
    anthropic_api_key="sk-ant-test",
)


def _token_response(token="t-token123", expire=7200):
    m = MagicMock()
    m.json.return_value = {"tenant_access_token": token, "expire": expire}
    m.raise_for_status = MagicMock()
    return m


def _nodes_response(items, has_more=False, page_token=None):
    m = MagicMock()
    body = {"code": 0, "data": {"items": items, "has_more": has_more}}
    if page_token:
        body["data"]["page_token"] = page_token
    m.json.return_value = body
    m.raise_for_status = MagicMock()
    return m


def test_get_token_calls_feishu(mocker):
    mock_post = mocker.patch("requests.post", return_value=_token_response())
    client = FeishuClient(FAKE_CONFIG)
    token = client._get_token()
    assert token == "t-token123"
    mock_post.assert_called_once()
    call_json = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
    assert call_json["app_id"] == "cli_test"


def test_get_token_cached(mocker):
    mock_post = mocker.patch("requests.post", return_value=_token_response())
    client = FeishuClient(FAKE_CONFIG)
    client._get_token()
    client._get_token()
    assert mock_post.call_count == 1  # only fetched once


def test_get_token_refreshes_when_expired(mocker):
    mock_post = mocker.patch("requests.post", return_value=_token_response(expire=0))
    client = FeishuClient(FAKE_CONFIG)
    client._get_token()
    client._get_token()
    assert mock_post.call_count == 2  # expired, re-fetched


def test_get_wiki_tree_single_page(mocker):
    mocker.patch("requests.post", return_value=_token_response())
    items = [
        {"node_token": "n1", "title": "SLAM部署文档", "node_type": "doc",
         "parent_node_token": "", "has_child": False},
        {"node_token": "n2", "title": "数据预处理", "node_type": "folder",
         "parent_node_token": "", "has_child": True},
    ]
    child_items = [
        {"node_token": "n3", "title": "子文档", "node_type": "doc",
         "parent_node_token": "n2", "has_child": False},
    ]
    mocker.patch(
        "requests.get",
        side_effect=[
            _nodes_response(items),
            _nodes_response(child_items),
        ],
    )
    client = FeishuClient(FAKE_CONFIG)
    tree = client.get_wiki_tree()
    assert len(tree) == 2
    assert tree[0].node_token == "n1"
    assert tree[0].title == "SLAM部署文档"
    folder = tree[1]
    assert len(folder.children) == 1
    assert folder.children[0].node_token == "n3"


def test_get_wiki_tree_handles_pagination(mocker):
    mocker.patch("requests.post", return_value=_token_response())
    page1 = [{"node_token": f"n{i}", "title": f"Doc{i}", "node_type": "doc",
               "parent_node_token": "", "has_child": False} for i in range(3)]
    page2 = [{"node_token": f"n{i}", "title": f"Doc{i}", "node_type": "doc",
               "parent_node_token": "", "has_child": False} for i in range(3, 5)]
    mocker.patch(
        "requests.get",
        side_effect=[
            _nodes_response(page1, has_more=True, page_token="pt_abc"),
            _nodes_response(page2, has_more=False),
        ],
    )
    client = FeishuClient(FAKE_CONFIG)
    tree = client.get_wiki_tree()
    assert len(tree) == 5


def _ok_response():
    m = MagicMock()
    m.json.return_value = {"code": 0}
    m.raise_for_status = MagicMock()
    return m


def test_rename_node_calls_patch(mocker):
    mocker.patch("requests.post", return_value=_token_response())
    mock_patch = mocker.patch("requests.patch", return_value=_ok_response())
    client = FeishuClient(FAKE_CONFIG)
    client.rename_node(node_token="n1", new_title="[技术文档][2026-05] 新标题")
    mock_patch.assert_called_once()
    url = mock_patch.call_args[0][0]
    assert "n1" in url
    body = mock_patch.call_args.kwargs.get("json") or mock_patch.call_args[1].get("json")
    assert body["title"] == "[技术文档][2026-05] 新标题"


def test_move_node_calls_post(mocker):
    mocker.patch("requests.post", side_effect=[
        _token_response(),
        _ok_response(),
    ])
    client = FeishuClient(FAKE_CONFIG)
    client.move_node(node_token="n1", target_parent_token="folder_abc")
    # No assertion needed beyond "it didn't raise"


def test_feishu_client_has_no_delete_method():
    client = FeishuClient(FAKE_CONFIG)
    assert not hasattr(client, "delete_node"), "delete_node must not exist"
    assert not hasattr(client, "delete"), "delete must not exist"
