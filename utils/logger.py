"""Logging em arquivo com mascaramento de segredos."""
from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

_PATTERNS = [
    re.compile(r'''(?i)["']?(?:[a-z0-9]+_)*(?:api[_-]?key|token|secret|password|authorization)["']?\s*[:=]\s*["'][^"']*["']'''),
    re.compile(r"(?i)\b(?:[a-z0-9]+_)+(?:api[_-]?key|token|secret|password)\s*[=:]\s*\S+"),
    re.compile(r"\bgsk_[A-Za-z0-9_-]+\b"),
    re.compile(r"(?i)(?:https?://)[^\s/@]+:[^\s/@]+@[^\s]+"),
    re.compile(r"(?i)[?&](?:key|api_key|token|secret|password)=[^&\s]+"),
    re.compile(r"\btvly-[A-Za-z0-9_-]+\b"),
    re.compile(r"(?i)\bBearer\s+[^\s'\"]+"),
    re.compile(r"(?i)\b(?:LAYLA_SESSION_COOKIE|session)\s*[=:]\s*[^\s;]+"),
    re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b"),                       # token de bot do Telegram
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\b\s*[=:]\s*\S+"),
]


def redact(text):
    for pattern in _PATTERNS:
        text = pattern.sub('[REDACTED]', text)
    return text


class RedactingFormatter(logging.Formatter):
    def format(self, record):
        # Exceptions and stack traces are added AFTER filters run.
        return redact(super().format(record))


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = redact(record.getMessage())
        record.msg, record.args = msg, ()
        return True


def setup_logging(level: str = "INFO", log_file: str = "logs/sazabi.log", console: bool = False) -> logging.Logger:
    logger = logging.getLogger("sazabi")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    fmt = RedactingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
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
