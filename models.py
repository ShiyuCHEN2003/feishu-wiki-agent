from dataclasses import dataclass, field


@dataclass
class WikiNode:
    node_token: str
    title: str
    node_type: str          # "doc" | "folder" | "wiki"
    parent_node_token: str
    has_child: bool
    children: list["WikiNode"] = field(default_factory=list)


@dataclass
class Issue:
    id: str
    type: str               # "naming" | "structure" | "duplicate"
    severity: str           # "high" | "medium" | "low"
    suggestion: str
    reason: str
    node_token: str = ""                          # for naming / structure
    current_title: str = ""                       # for naming / structure
    node_tokens: list[str] = field(default_factory=list)    # for duplicate
    current_titles: list[str] = field(default_factory=list) # for duplicate


@dataclass
class LogEntry:
    timestamp: str
    action: str             # "rename" | "move"
    node_token: str
    from_value: str         # old title (rename) or old parent token (move)
    to_value: str           # new title (rename) or new parent token (move)
    operator: str
    confirmed_by: str
    issue_id: str

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "action": self.action,
            "node_token": self.node_token,
            "from": self.from_value,
            "to": self.to_value,
            "operator": self.operator,
            "confirmed_by": self.confirmed_by,
            "issue_id": self.issue_id,
        }
