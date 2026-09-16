import os
import pytest
from app.config import Config


def test_config_missing_required_raises():
    """Verify that empty environment raises ValueError listing missing keys."""
    # Clear all TPMC env vars
    clean_env = {
        "API_ID": "",
        "API_HASH": "",
        "BOT_TOKEN": "",
        "CHANNEL_ID": "",
        "TELEGRAM_SESSION": "",
        "AUTHORIZED_USER_ID": "",
    }
    for k in clean_env:
        os.environ.pop(k, None)

    with pytest.raises(ValueError) as excinfo:
        Config.load_from_env(env_path="non_existent_empty.env")

    msg = str(excinfo.value)
    assert "API_ID is required" in msg
    assert "API_HASH is required" in msg
    assert "BOT_TOKEN is required" in msg
    assert "CHANNEL_ID is required" in msg
    assert "TELEGRAM_SESSION is required" in msg
    assert "AUTHORIZED_USER_ID is required" in msg


def test_config_placeholder_rejection(monkeypatch):
    """Verify that placeholder strings are rejected with descriptive error."""
    monkeypatch.setenv("API_ID", "1234567")
    monkeypatch.setenv("API_HASH", "abcdef0123456789abcdef0123456789")
    monkeypatch.setenv("BOT_TOKEN", "your_bot_token_here")
    monkeypatch.setenv("CHANNEL_ID", "your_channel_id_here")
    monkeypatch.setenv("TELEGRAM_SESSION", "your_session_string_here")
    monkeypatch.setenv("AUTHORIZED_USER_ID", "your_user_id_here")

    with pytest.raises(ValueError) as excinfo:
        Config.load_from_env()

    msg = str(excinfo.value)
    assert "invalid placeholder" in msg


def test_config_valid_loading(monkeypatch):
    """Verify that correctly populated environment variables parse successfully."""
    monkeypatch.setenv("API_ID", "987654")
    monkeypatch.setenv("API_HASH", "validhash1234567890abcdef12345678")
    monkeypatch.setenv("BOT_TOKEN", "999999999:AAFakeTokenForTestingOnly_12345678")
    monkeypatch.setenv("CHANNEL_ID", "-1001999888777")
    monkeypatch.setenv("TELEGRAM_SESSION", "1BVtsOFakeValidTelethonSessionString...")
    monkeypatch.setenv("AUTHORIZED_USER_ID", "1122334455")
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    cfg = Config.load_from_env()
    assert cfg.api_id == 987654
    assert cfg.api_hash == "validhash1234567890abcdef12345678"
    assert cfg.bot_token == "999999999:AAFakeTokenForTestingOnly_12345678"
    assert cfg.channel_id == -1001999888777
    assert cfg.telegram_session == "1BVtsOFakeValidTelethonSessionString..."
    assert cfg.authorized_user_id == 1122334455
    assert cfg.port == 9000
    assert cfg.host == "0.0.0.0"
    assert cfg.log_level == "DEBUG"
    assert cfg.max_concurrent_jobs == 1
    assert cfg.max_download_batch == 25
    assert cfg.max_search_results == 50
    assert cfg.flood_wait_max == 300


def test_config_channel_id_auto_heal(monkeypatch):
    """Verify that positive channel IDs are automatically normalized to negative -100..."""
    monkeypatch.setenv("API_ID", "987654")
    monkeypatch.setenv("API_HASH", "validhash1234567890abcdef12345678")
    monkeypatch.setenv("BOT_TOKEN", "999999999:AAFakeTokenForTestingOnly_12345678")
    monkeypatch.setenv("TELEGRAM_SESSION", "1BVtsOFakeValidTelethonSessionString...")
    monkeypatch.setenv("AUTHORIZED_USER_ID", "1122334455")

    # Case 1: user entered 1004316652121 without minus
    monkeypatch.setenv("CHANNEL_ID", "1004316652121")
    cfg1 = Config.load_from_env()
    assert cfg1.channel_id == -1004316652121

    # Case 2: user entered 4316652121 without -100
    monkeypatch.setenv("CHANNEL_ID", "4316652121")
    cfg2 = Config.load_from_env()
    assert cfg2.channel_id == -1004316652121

    # Case 3: user entered standard -1004316652121
    monkeypatch.setenv("CHANNEL_ID", "-1004316652121")
    cfg3 = Config.load_from_env()
    assert cfg3.channel_id == -1004316652121
