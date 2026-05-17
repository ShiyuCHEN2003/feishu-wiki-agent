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
    )
