"""Transforma sinais em HIPÓTESES de oportunidade, filtradas pelos serviços da software house.

Nunca afirma que a empresa 'precisa' de algo: gera hipóteses com nível de evidência.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, List, Sequence, Tuple

from analysis.evidence_manager import evidence_level, rank
from database.models import CompanyProfile, Hypothesis, Signal
from utils.normalization import normalize_text
from utils.timeutils import now_iso


@dataclass(frozen=True)
class HypothesisRule:
    solution: str
    service_keywords: Tuple[str, ...]      # a software house precisa oferecer algum destes
    primary: FrozenSet[str]                # sinais que disparam a hipótese
    supporting: FrozenSet[str]             # sinais que reforçam


def _r(solution, services, primary, supporting=()):
    return HypothesisRule(solution, tuple(services), frozenset(primary), frozenset(supporting))


RULES: Sequence[HypothesisRule] = (
    _r("sistema de agendamento online", ("sistemas web", "aplicativos", "automação"),
       {"scheduling"}, {"customer_service", "operational_complexity", "digital_gap", "manual_process", "hiring"}),
    _r("automação de atendimento (WhatsApp)", ("automação", "inteligência artificial", "integrações"),
       {"customer_service"}, {"scheduling", "manual_process", "operational_complexity"}),
    _r("sistema de gestão centralizado", ("sistemas de gestão", "sistemas internos", "dashboards"),
       {"multiple_locations", "operational_complexity"},
       {"growth", "new_unit", "hiring", "manual_process", "multiple_locations", "operational_complexity"}),
    _r("automação de processos internos", ("automação", "sistemas internos", "integrações"),
       {"manual_process"}, {"growth", "new_unit", "hiring", "operational_complexity"}),
    _r("site / presença digital", ("sistemas web", "e-commerce"),
       {"digital_gap"}, {"customer_service", "ecommerce"}),
    _r("e-commerce / loja virtual", ("e-commerce",),
       {"ecommerce"}, {"customer_service", "digital_gap"}),
)


class OpportunityAnalyzer:
    def __init__(self, services: Sequence[str]):
        self.services = [normalize_text(s) for s in services]

    def _offers(self, rule: HypothesisRule) -> bool:
        return any(kw_n in s or s in kw_n
                   for kw in rule.service_keywords for kw_n in [normalize_text(kw)] for s in self.services)

    def analyze(self, profile: CompanyProfile, signals: Sequence[Signal]) -> List[Hypothesis]:
        signals = [s for s in signals if s.source_url and s.evidence and s.source]
        now = now_iso()
        hypotheses: List[Hypothesis] = []
        for rule in RULES:
            if not self._offers(rule):
                continue
            involved = [s for s in signals if s.type in rule.primary | rule.supporting]
            if not any(s.type in rule.primary for s in involved):
                continue
            reasons = []
            for s in involved:
                line = f"{s.description} (fato: {s.evidence})"
                if line not in reasons:
                    reasons.append(line)
            hypotheses.append(Hypothesis(company_id=profile.id, solution=rule.solution, reasons=reasons,
                                         evidence_level=evidence_level(involved), created_at=now))
        return sorted(hypotheses, key=lambda h: -rank(h.evidence_level))
