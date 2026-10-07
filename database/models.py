"""Modelos de dados do SAZABI (dataclasses simples, sem ORM)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

STATUSES = ("NEW", "RESEARCHED", "INTERESTING", "SAVED", "CONTACTED", "CLIENT", "DISCARDED")

# Tipos iniciais de sinais. Novos tipos podem ser adicionados aqui e em signal_detector.RULES.
SIGNAL_TYPES = (
    "growth", "new_unit", "hiring", "manual_process", "digital_gap", "multiple_locations",
    "customer_service", "scheduling", "ecommerce", "automation", "operational_complexity",
)

CONFIDENCE_LABELS = {"low": "Baixa", "moderate": "Moderada", "high": "Alta"}
EVIDENCE_LEVELS = ("insuficiente", "fraco", "moderado", "forte")
EVIDENCE_RANK = {level: i for i, level in enumerate(EVIDENCE_LEVELS)}


@dataclass
class Observation:
    """Fato bruto observado em uma fonte pública (a base de todo sinal)."""
    text: str
    source_name: str
    url: Optional[str] = None
    retrieved_at: Optional[str] = None


@dataclass
class RawCompany:
    """Empresa como devolvida por uma fonte, antes de normalização."""
    name: str
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    website: Optional[str] = None
    segment: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    legal_name: Optional[str] = None
    description: Optional[str] = None
    estimated_size: Optional[str] = None
    units: Optional[int] = None
    services: List[str] = field(default_factory=list)
    social_profiles: Dict[str, str] = field(default_factory=dict)
    observations: List[Observation] = field(default_factory=list)
    source_name: Optional[str] = None


@dataclass
class SearchCriteria:
    segment: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    size: Optional[str] = None      # micro | pequena | média | grande
    need: Optional[str] = None
    silent: bool = False
    raw_query: str = ""

    def describe(self) -> List[str]:
        items = []
        if self.city:
            items.append(f"Região: {self.city}" + (f"/{self.state}" if self.state else ""))
        if self.segment:
            items.append(f"Segmento: {self.segment}")
        if self.size:
            items.append(f"Porte: {self.size.capitalize()} (estimado)")
        if self.need:
            items.append(f"Necessidade investigada: {self.need}")
        if self.silent:
            items.append("Modo: silencioso")
        return items


@dataclass
class Signal:
    type: str
    description: str                  # inferência
    evidence: str                     # fato observado
    source: str
    detected_at: str
    confidence: str                   # low | moderate | high
    company_id: Optional[str] = None
    source_url: Optional[str] = None
    id: Optional[int] = None


@dataclass
class Hypothesis:
    solution: str
    reasons: List[str]
    evidence_level: str               # insuficiente | fraco | moderado | forte
    created_at: str
    company_id: Optional[str] = None
    id: Optional[int] = None


@dataclass
class CompanyProfile:
    name: str
    id: Optional[str] = None
    legal_name: Optional[str] = None
    website: Optional[str] = None
    domain: Optional[str] = None
    segment: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    estimated_size: Optional[str] = None
    description: Optional[str] = None
    social_profiles: Dict[str, str] = field(default_factory=dict)
    services: List[str] = field(default_factory=list)
    units: Optional[int] = None
    status: str = "NEW"
    investigated: bool = False
    first_seen: Optional[str] = None
    last_researched: Optional[str] = None
    normalized_name: str = ""
    observations: List[Observation] = field(default_factory=list)   # "sources" da spec
    signals: List[Signal] = field(default_factory=list)
    hypotheses: List[Hypothesis] = field(default_factory=list)

    @property
    def location(self) -> str:
        if self.city and self.state:
            return f"{self.city}/{self.state}"
        return self.city or "Não identificado"


@dataclass
class ResearchRun:
    id: int
    query: str
    started_at: str
    segment: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    size: Optional[str] = None
    need: Optional[str] = None
    silent: bool = False
    finished_at: Optional[str] = None
    found: int = 0
    duplicates: int = 0
    new_count: int = 0
    known_count: int = 0
    ignored_count: int = 0
    investigated: int = 0
    with_data: int = 0
    signals_count: int = 0
    opportunities: int = 0
    status: str = 'running'
    error_message: str = ''
