import pytest
from unittest.mock import MagicMock
from models import WikiNode, Issue, LogEntry
from workflow import WorkflowEngine, State


def _make_naming_issue(token="n1", title="旧文档名") -> Issue:
    return Issue(
        id="issue_001", type="naming", severity="medium",
        suggestion="重命名为 [技术文档][2026-05] 新文档名",
        reason="缺少类型标签", node_token=token, current_title=title,
    )


def _make_duplicate_issue() -> Issue:
    return Issue(
        id="issue_002", type="duplicate", severity="high",
        suggestion="保留最新版，其余移入_归档",
        reason="主题重叠",
        node_tokens=["n1", "n2"],
        current_titles=["文档A", "文档B"],
    )


@pytest.fixture
def engine():
    feishu = MagicMock()
    analyzer = MagicMock()
    logger = MagicMock()
    return WorkflowEngine(feishu_client=feishu, analyzer=analyzer, logger=logger)


def test_initial_state_is_idle(engine):
    assert engine.state == State.IDLE


def test_scan_transitions_to_analyze(engine):
    engine._feishu.get_wiki_tree.return_value = [WikiNode("n1", "Doc", "doc", "", False)]
    engine._analyzer.analyze.return_value = []
    engine.start_scan()
    assert engine.state == State.IDLE  # no issues → back to IDLE


def test_scan_with_issues_reaches_confirm(engine):
    engine._feishu.get_wiki_tree.return_value = [WikiNode("n1", "旧文档名", "doc", "", False)]
    engine._analyzer.analyze.return_value = [_make_naming_issue()]
    engine.start_scan()
    assert engine.state == State.CONFIRM
    assert len(engine.pending_issues) == 1


def test_confirm_yes_calls_rename(engine):
    engine._feishu.get_wiki_tree.return_value = [WikiNode("n1", "旧文档名", "doc", "", False)]
    engine._analyzer.analyze.return_value = [_make_naming_issue()]
    engine.start_scan()
    assert engine.state == State.CONFIRM
    engine.confirm_current()  # user says 确认
    engine._feishu.rename_node.assert_called_once_with(
        node_token="n1", new_title="[技术文档][2026-05] 新文档名"
    )
    engine._logger.record.assert_called_once()


def test_confirm_skip_does_not_call_write(engine):
    engine._feishu.get_wiki_tree.return_value = [WikiNode("n1", "旧文档名", "doc", "", False)]
    engine._analyzer.analyze.return_value = [_make_naming_issue()]
    engine.start_scan()
    engine.skip_current()
    engine._feishu.rename_node.assert_not_called()
    engine._feishu.move_node.assert_not_called()


def test_cancel_all_returns_to_idle(engine):
    engine._feishu.get_wiki_tree.return_value = [WikiNode("n1", "旧文档名", "doc", "", False)]
    engine._analyzer.analyze.return_value = [_make_naming_issue(), _make_naming_issue("n2", "文档B")]
    engine.start_scan()
    engine.cancel_all()
    assert engine.state == State.IDLE
    assert engine.pending_issues == []


def test_all_issues_confirmed_returns_to_idle(engine):
    engine._feishu.get_wiki_tree.return_value = [WikiNode("n1", "旧", "doc", "", False)]
    engine._analyzer.analyze.return_value = [_make_naming_issue()]
    engine.start_scan()
    engine.confirm_current()
    assert engine.state == State.IDLE


def test_duplicate_issue_confirm_calls_move(engine):
    # Override engine with archive token configured
    feishu = MagicMock()
    analyzer = MagicMock()
    logger = MagicMock()
    engine_with_archive = WorkflowEngine(
        feishu_client=feishu, analyzer=analyzer, logger=logger,
        archive_parent_token="archive_folder_token",
    )
    feishu.get_wiki_tree.return_value = [
        WikiNode("n1", "文档A", "doc", "", False),
        WikiNode("n2", "文档B", "doc", "", False),
    ]
    analyzer.analyze.return_value = [_make_duplicate_issue()]
    engine_with_archive.start_scan()
    engine_with_archive.confirm_current()
    feishu.move_node.assert_called()
