"""Funções de data/hora. Todo timestamp é guardado em UTC (ISO 8601)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return utcnow().isoformat(timespec="seconds")


def parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def fmt_date(value: Optional[str]) -> str:
    """ISO UTC -> dd/mm/aaaa no fuso local."""
    if not value:
        return "Não identificado"
    return parse_iso(value).astimezone().strftime("%d/%m/%Y")


def hours_since(value: str) -> float:
    return (utcnow() - parse_iso(value)).total_seconds() / 3600


def day_bounds(label: str, now: Optional[datetime] = None) -> Tuple[str, str]:
    """Limites (UTC, ISO) do dia local. label: 'today' ou 'yesterday'."""
    local_now = (now or utcnow()).astimezone()
    start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    if label == "yesterday":
        start -= timedelta(days=1)
    end = start + timedelta(days=1)
    to_utc = lambda d: d.astimezone(timezone.utc).isoformat(timespec="seconds")
    return to_utc(start), to_utc(end)
