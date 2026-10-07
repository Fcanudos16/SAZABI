"""Cálculo do nível de evidência de uma hipótese."""
from __future__ import annotations

from typing import Iterable

from database.models import EVIDENCE_RANK, Signal

CONFIDENCE_WEIGHT = {"low": 1, "moderate": 2, "high": 3}


def score(signals: Iterable[Signal]) -> int:
    return sum(CONFIDENCE_WEIGHT.get(s.confidence, 1) for s in signals)


def evidence_level(signals: Iterable[Signal]) -> str:
    """insuficiente (sem sinais) | fraco | moderado | forte.

    'forte' é propositalmente raro: exige vários sinais independentes e
    mesmo assim continua sendo uma hipótese baseada em informação pública.
    """
    signals = list(signals)
    if not signals:
        return "insuficiente"
    total, kinds = score(signals), len({s.type for s in signals})
    if total >= 9 and kinds >= 4:
        return "forte"
    if total >= 3:
        return "moderado"
    return "fraco"


def level_label(level: str) -> str:
    return level.capitalize()


def rank(level: str) -> int:
    return EVIDENCE_RANK.get(level, 0)
