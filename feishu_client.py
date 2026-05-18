import time
import requests
from config import Config
from models import WikiNode

_BASE = "https://open.feishu.cn/open-apis"


class FeishuClient:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._token: str = ""
        self._token_expires_at: float = 0.0

    # ── auth ──────────────────────────────────────────────────────────────

    def _get_token(self) -> str:
        if time.time() < self._token_expires_at - 60:
            return self._token
        resp = requests.post(
            f"{_BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": self._config.app_id, "app_secret": self._config.app_secret},
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["tenant_access_token"]
        self._token_expires_at = time.time() + data["expire"]
        return self._token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._get_token()}"}

    # ── read ──────────────────────────────────────────────────────────────

    def _list_nodes(self, parent_node_token: str = "") -> list[dict]:
        url = f"{_BASE}/wiki/v2/spaces/{self._config.wiki_space_id}/nodes"
        params: dict = {"page_size": 50}
        if parent_node_token:
            params["parent_node_token"] = parent_node_token
        items: list[dict] = []
        while True:
            resp = requests.get(url, headers=self._headers(), params=params)
            resp.raise_for_status()
            data = resp.json()["data"]
            items.extend(data.get("items", []))
            if not data.get("has_more"):
                break
            params["page_token"] = data["page_token"]
        return items

    def _build_nodes(self, raw_items: list[dict]) -> list[WikiNode]:
        nodes = []
        for item in raw_items:
            node = WikiNode(
                node_token=item["node_token"],
                title=item["title"],
                node_type=item["node_type"],
                parent_node_token=item.get("parent_node_token", ""),
                has_child=item.get("has_child", False),
            )
            if node.has_child:
                child_items = self._list_nodes(parent_node_token=node.node_token)
                node.children = self._build_nodes(child_items)
            nodes.append(node)
        return nodes

    def get_wiki_tree(self) -> list[WikiNode]:
        root_items = self._list_nodes()
        return self._build_nodes(root_items)
