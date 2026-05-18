import os
import pytest
from unittest.mock import patch
from config import load_config, Config

# Patch load_dotenv in all tests so a real .env file on disk doesn't interfere
_NO_DOTENV = patch("config.load_dotenv")


def test_load_config_success():
    env = {
        "FEISHU_APP_ID": "cli_test",
        "FEISHU_APP_SECRET": "secret123",
        "FEISHU_WIKI_SPACE_ID": "space456",
        "ANTHROPIC_API_KEY": "sk-ant-test",
    }
    with _NO_DOTENV, patch.dict(os.environ, env, clear=True):
        cfg = load_config()
    assert isinstance(cfg, Config)
    assert cfg.app_id == "cli_test"
    assert cfg.app_secret == "secret123"
    assert cfg.wiki_space_id == "space456"
    assert cfg.anthropic_api_key == "sk-ant-test"


def test_load_config_missing_raises():
    with _NO_DOTENV, patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="Missing required env vars"):
            load_config()


def test_load_config_partial_missing_raises():
    env = {"FEISHU_APP_ID": "cli_test"}
    with _NO_DOTENV, patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValueError, match="FEISHU_APP_SECRET"):
            load_config()


def test_load_config_with_archive_token():
    env = {
        "FEISHU_APP_ID": "cli_test",
        "FEISHU_APP_SECRET": "secret123",
        "FEISHU_WIKI_SPACE_ID": "space456",
        "ANTHROPIC_API_KEY": "sk-ant-test",
        "FEISHU_ARCHIVE_PARENT_TOKEN": "arch_tok_abc",
    }
    with _NO_DOTENV, patch.dict(os.environ, env, clear=True):
        cfg = load_config()
    assert cfg.archive_parent_token == "arch_tok_abc"


def test_load_config_archive_token_defaults_to_empty():
    env = {
        "FEISHU_APP_ID": "cli_test",
        "FEISHU_APP_SECRET": "secret123",
        "FEISHU_WIKI_SPACE_ID": "space456",
        "ANTHROPIC_API_KEY": "sk-ant-test",
    }
    with _NO_DOTENV, patch.dict(os.environ, env, clear=True):
        cfg = load_config()
    assert cfg.archive_parent_token == ""
