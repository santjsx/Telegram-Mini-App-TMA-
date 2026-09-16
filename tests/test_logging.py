import io
import logging
from app.logging_config import setup_logging, SecretRedactingFilter


def test_secret_redacting_filter():
    secrets = ["secret_bot_token_12345", "secret_hash_abcdef"]
    filt = SecretRedactingFilter(secrets)

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Connecting with token secret_bot_token_12345 and secret_hash_abcdef",
        args=(),
        exc_info=None,
    )
    filt.filter(record)
    assert "secret_bot_token_12345" not in record.msg
    assert "secret_hash_abcdef" not in record.msg
    assert "***REDACTED***" in record.msg
