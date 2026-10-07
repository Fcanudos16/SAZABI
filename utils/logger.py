"""Logging em arquivo com mascaramento de segredos."""
from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

_PATTERNS = [
    re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b"),                       # token de bot do Telegram
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\b\s*[=:]\s*\S+"),
]


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for pattern in _PATTERNS:
            msg = pattern.sub("[REDACTED]", msg)
        record.msg, record.args = msg, ()
        return True


def setup_logging(level: str = "INFO", log_file: str = "logs/sazabi.log", console: bool = False) -> logging.Logger:
    logger = logging.getLogger("sazabi")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handlers = []
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"))
    if console:
        handlers.append(logging.StreamHandler())
    for h in handlers:
        h.setFormatter(fmt)
        h.addFilter(RedactFilter())
        logger.addHandler(h)
    return logger
