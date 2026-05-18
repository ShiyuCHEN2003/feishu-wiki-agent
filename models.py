from dataclasses import dataclass, field


@dataclass
class WikiNode:
    node_token: str
    title: str
    node_type: str          # "origin" | "shortcut"
    parent_node_token: str
    has_child: bool
    obj_token: str = ""     # Feishu document token, used for content API
    content: str = ""       # body text excerpt, capped at 800 chars
    children: list["WikiNode"] = field(default_factory=list)


@dataclass
class Issue:
    id: str
    type: str               # "naming" | "structure" | "duplicate"
    severity: str           # "high" | "medium" | "low"
    suggestion: str
    reason: str
    node_token: str = ""                          # for naming / structure / index
    obj_token: str = ""                           # underlying doc token, for rename / index write
    current_title: str = ""                       # for naming / structure / index
    node_tokens: list[str] = field(default_factory=list)    # for duplicate
    current_titles: list[str] = field(default_factory=list) # for duplicate
    target_parent_token: str = ""                 # for structure moves
    child_index: list[dict] = field(default_factory=list)   # for index: [{title, description}]

    def __post_init__(self) -> None:
        if self.type == "duplicate":
            if not self.node_tokens:
                raise ValueError(f"Issue {self.id}: duplicate type requires node_tokens")
        elif self.type in ("naming", "structure", "index"):
            if not self.node_token:
                raise ValueError(f"Issue {self.id}: {self.type} type requires node_token")


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
