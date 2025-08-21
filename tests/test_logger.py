import json
import logging

from app.telemetry.logger import JsonFormatter, get_logger


def test_json_formatter():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    data = json.loads(output)
    assert data["level"] == "INFO"
    assert data["msg"] == "Test message"
    assert data["logger"] == "test"


def test_get_logger():
    logger = get_logger("test_app")
    assert logger.name == "test_app"
    assert logger.level == logging.INFO
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0].formatter, JsonFormatter)
