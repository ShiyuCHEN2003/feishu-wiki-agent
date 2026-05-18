import time
import requests
from config import Config
from models import WikiNode

_BASE = "https://open.feishu.cn/open-apis"
_NO_PROXY = {"http": "", "https": "", "all": ""}  # always direct-connect to Feishu


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
            proxies=_NO_PROXY,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code", 0) != 0:
            raise RuntimeError(f"Feishu auth error: {data}")
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
            resp = requests.get(url, headers=self._headers(), params=params, proxies=_NO_PROXY)
            resp.raise_for_status()
            body = resp.json()
            if body.get("code", 0) != 0:
                raise RuntimeError(f"Feishu API error: {body}")
            data = body["data"]
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
                obj_token=item.get("obj_token", ""),
            )
            if node.has_child:
                child_items = self._list_nodes(parent_node_token=node.node_token)
                node.children = self._build_nodes(child_items)
            nodes.append(node)
        return nodes

    def get_wiki_tree(self) -> list[WikiNode]:
        root_items = self._list_nodes()
        return self._build_nodes(root_items)

    # Best-effort: returns "" on any network/API error so scans degrade gracefully.
    def get_doc_content(self, obj_token: str) -> str:
        if not obj_token:
            return ""
        url = f"{_BASE}/docx/v1/documents/{obj_token}/raw_content"
        try:
            resp = requests.get(url, headers=self._headers(), proxies=_NO_PROXY)
            resp.raise_for_status()
        except requests.exceptions.RequestException:
            return ""
        body = resp.json()
        if body.get("code", 0) != 0:
            return ""
        return body.get("data", {}).get("content", "")[:300]

    def fetch_content_for_tree(self, nodes: list[WikiNode]) -> None:
        for node in nodes:
            # Shortcuts may share obj_token with their origin; skip to avoid duplicate content.
            if node.obj_token and node.node_type == "origin":
                node.content = self.get_doc_content(node.obj_token)
            if node.children:
                self.fetch_content_for_tree(node.children)

    # ── write ─────────────────────────────────────────────────────────────

    def rename_node(self, node_token: str, new_title: str, obj_token: str = "") -> None:
        if obj_token:
            # Title lives in the page's first block; block_id == document_id (obj_token).
            url = f"{_BASE}/docx/v1/documents/{obj_token}/blocks/{obj_token}"
            resp = requests.patch(
                url, headers=self._headers(),
                params={"document_revision_id": -1},
                json={"update_text_elements": {"elements": [{"text_run": {"content": new_title}}]}},
                proxies=_NO_PROXY,
            )
        else:
            url = f"{_BASE}/wiki/v2/spaces/{self._config.wiki_space_id}/nodes/{node_token}"
            resp = requests.patch(url, headers=self._headers(), json={"title": new_title}, proxies=_NO_PROXY)
        if not resp.ok:
            raise RuntimeError(f"Feishu rename API {resp.status_code}: {resp.text}")
        body = resp.json()
        if body.get("code", 0) != 0:
            raise RuntimeError(f"Feishu API error on rename: {body}")

    def move_node(self, node_token: str, target_parent_token: str) -> None:
        url = f"{_BASE}/wiki/v2/spaces/{self._config.wiki_space_id}/nodes/{node_token}/move"
        resp = requests.post(
            url, headers=self._headers(), json={"target_parent_token": target_parent_token},
            proxies=_NO_PROXY,
        )
        if not resp.ok:
            raise RuntimeError(f"Feishu move API {resp.status_code}: {resp.text}")
        body = resp.json()
        if body.get("code", 0) != 0:
            raise RuntimeError(f"Feishu API error on move: {body}")

    def write_child_index(self, obj_token: str, children: list[dict]) -> None:
        """Insert a child-document index section at the top of the document body.

        children: list of {"title": str, "description": str, "node_token": str}
        """
        if not children:
            return
        domain = self._config.feishu_domain.rstrip("/")
        blocks = [
            {
                "block_type": 3,  # heading 1
                "heading1": {"elements": [{"text_run": {"content": "子文档目录"}}]},
            }
        ]
        for child in children:
            node_token = child.get("node_token", "")
            title = child["title"]
            description = child.get("description", "")

            # Build title element: hyperlink if domain configured, else plain text
            if domain and node_token:
                link_url = f"https://{domain}/wiki/{node_token}"
                title_element = {
                    "text_run": {
                        "content": title,
                        "text_element_style": {"link": {"url": link_url}, "bold": True},
                    }
                }
            else:
                title_element = {
                    "text_run": {"content": title, "text_element_style": {"bold": True}}
                }

            elements = [title_element]
            if description:
                elements.append({"text_run": {"content": f"  —  {description}"}})

            blocks.append({
                "block_type": 12,  # bullet list item
                "bullet": {"elements": elements},
            })

        url = f"{_BASE}/docx/v1/documents/{obj_token}/blocks/{obj_token}/children"
        resp = requests.post(
            url, headers=self._headers(),
            params={"document_revision_id": -1},
            json={"children": blocks, "index": 0},
            proxies=_NO_PROXY,
        )
        if not resp.ok:
            raise RuntimeError(f"Feishu write_child_index API {resp.status_code}: {resp.text}")
        body = resp.json()
        if body.get("code", 0) != 0:
            raise RuntimeError(f"Feishu API error on write_child_index: {body}")
