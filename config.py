import os
from dataclasses import dataclass
from dotenv import load_dotenv

_REQUIRED_KEYS = [
    "FEISHU_APP_ID",
    "FEISHU_APP_SECRET",
    "FEISHU_WIKI_SPACE_ID",
    "ANTHROPIC_API_KEY",
]


@dataclass
class Config:
    app_id: str
    app_secret: str
    wiki_space_id: str
    anthropic_api_key: str
    archive_parent_token: str = ""   # optional: node_token of _归档 folder
    categories: dict = None          # optional: {name: node_token} for topic categories
    feishu_domain: str = ""          # optional: e.g. yourcompany.feishu.cn, for constructing wiki links


def _parse_categories(raw: str) -> dict:
    """Parse 'name1:token1,name2:token2' into {name: token}."""
    if not raw:
        return {}
    result = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if ":" in pair:
            name, token = pair.split(":", 1)
            result[name.strip()] = token.strip()
    return result


def load_config() -> Config:
    load_dotenv()
    missing = [k for k in _REQUIRED_KEYS if not os.getenv(k)]
    if missing:
        raise ValueError(f"Missing required env vars: {', '.join(missing)}")
    return Config(
        app_id=os.environ["FEISHU_APP_ID"],
        app_secret=os.environ["FEISHU_APP_SECRET"],
        wiki_space_id=os.environ["FEISHU_WIKI_SPACE_ID"],
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        archive_parent_token=os.getenv("FEISHU_ARCHIVE_PARENT_TOKEN", ""),
        categories=_parse_categories(os.getenv("FEISHU_CATEGORIES", "")),
        feishu_domain=os.getenv("FEISHU_DOMAIN", ""),
    )
