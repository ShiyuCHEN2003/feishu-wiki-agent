import os
import pytest
from unittest.mock import patch
from config import load_config, Config


def test_load_config_success():
    env = {
        "FEISHU_APP_ID": "cli_test",
        "FEISHU_APP_SECRET": "secret123",
        "FEISHU_WIKI_SPACE_ID": "space456",
        "ANTHROPIC_API_KEY": "sk-ant-test",
    }
    with patch.dict(os.environ, env, clear=True):
        cfg = load_config()
    assert isinstance(cfg, Config)
    assert cfg.app_id == "cli_test"
    assert cfg.app_secret == "secret123"
    assert cfg.wiki_space_id == "space456"
    assert cfg.anthropic_api_key == "sk-ant-test"


def test_load_config_missing_raises():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="Missing required env vars"):
            load_config()


def test_load_config_partial_missing_raises():
    env = {"FEISHU_APP_ID": "cli_test"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValueError, match="FEISHU_APP_SECRET"):
            load_config()
