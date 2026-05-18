import re
from datetime import datetime, timezone, timedelta
from enum import Enum
from models import Issue, LogEntry
from feishu_client import FeishuClient
from analyzer import Analyzer
from logger import Logger

_TZ = timezone(timedelta(hours=8))


class State(Enum):
    IDLE = "idle"
    SCAN = "scan"
    ANALYZE = "analyze"
    REPORT = "report"
    CONFIRM = "confirm"
    EXECUTE = "execute"
    LOG = "log"


def _extract_new_title(suggestion: str) -> str:
    """Pull the recommended title from a suggestion string like '重命名为 [技术文档]...'."""
    m = re.search(r"重命名为\s*(.+?)(?:，|$)", suggestion)
    if m:
        return m.group(1).strip()
    return suggestion


class WorkflowEngine:
    def __init__(
        self,
        feishu_client: FeishuClient,
        analyzer: Analyzer,
        logger: Logger,
        archive_parent_token: str = "",
    ) -> None:
        self._feishu = feishu_client
        self._analyzer = analyzer
        self._logger = logger
        self._archive_parent_token = archive_parent_token
        self.state = State.IDLE
        self.pending_issues: list[Issue] = []
        self.current_index: int = 0
        self.last_scan_node_count: int = 0

    # ── public API ────────────────────────────────────────────────────────

    def start_scan(self) -> None:
        self.state = State.SCAN
        tree = self._feishu.get_wiki_tree()
        self.last_scan_node_count = self._count_nodes(tree)
        self.state = State.ANALYZE
        issues = self._analyzer.analyze(tree)
        self.state = State.REPORT
        if not issues:
            self.state = State.IDLE
            return
        self.pending_issues = issues
        self.current_index = 0
        self.state = State.CONFIRM

    def current_issue(self) -> Issue | None:
        if self.state != State.CONFIRM or self.current_index >= len(self.pending_issues):
            return None
        return self.pending_issues[self.current_index]

    def confirm_current(self) -> None:
        issue = self.current_issue()
        if issue is None:
            return
        self.state = State.EXECUTE
        self._execute(issue)
        self.state = State.LOG
        self._log(issue)
        self._advance()

    def skip_current(self) -> None:
        self._advance()

    def cancel_all(self) -> None:
        self.pending_issues = []
        self.current_index = 0
        self.state = State.IDLE

    # ── private ───────────────────────────────────────────────────────────

    def _advance(self) -> None:
        self.current_index += 1
        if self.current_index >= len(self.pending_issues):
            self.pending_issues = []
            self.current_index = 0
            self.state = State.IDLE
        else:
            self.state = State.CONFIRM

    def _execute(self, issue: Issue) -> None:
        if issue.type == "naming":
            new_title = _extract_new_title(issue.suggestion)
            self._feishu.rename_node(node_token=issue.node_token, new_title=new_title)
        elif issue.type == "duplicate" and len(issue.node_tokens) > 1:
            if not self._archive_parent_token:
                return  # archive token not configured — skip silently
            for token in issue.node_tokens[1:]:
                self._feishu.move_node(
                    node_token=token, target_parent_token=self._archive_parent_token
                )
        elif issue.type == "structure" and issue.node_token:
            new_title = _extract_new_title(issue.suggestion)
            if new_title != issue.current_title:
                self._feishu.rename_node(node_token=issue.node_token, new_title=new_title)

    def _log(self, issue: Issue) -> None:
        now = datetime.now(_TZ).isoformat()
        if issue.type in ("naming", "structure"):
            entry = LogEntry(
                timestamp=now, action="rename",
                node_token=issue.node_token,
                from_value=issue.current_title,
                to_value=_extract_new_title(issue.suggestion),
                operator="system", confirmed_by="user", issue_id=issue.id,
            )
        else:
            entry = LogEntry(
                timestamp=now, action="move",
                node_token=",".join(issue.node_tokens[1:]),
                from_value=",".join(issue.current_titles[1:]),
                to_value=self._archive_parent_token,
                operator="system", confirmed_by="user", issue_id=issue.id,
            )
        self._logger.record(entry)

    @staticmethod
    def _count_nodes(nodes) -> int:
        count = len(nodes)
        for n in nodes:
            count += WorkflowEngine._count_nodes(n.children)
        return count
