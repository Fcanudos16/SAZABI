"""Interfaces de fontes. Novas fontes implementam CompanySource sem tocar no núcleo."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from database.models import CompanyProfile, Observation, RawCompany, SearchCriteria


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""


class SearchProvider(ABC):
    """Motor de busca genérico (Google, Bing...). Será usado pelas fontes reais."""

    @abstractmethod
    def search(self, query: str) -> List[SearchResult]:
        ...


class CompanySource(ABC):
    """Fonte de empresas e de observações públicas sobre elas."""

    name: str = "fonte"

    @abstractmethod
    def search(self, criteria: SearchCriteria) -> List[RawCompany]:
        """Lista empresas que atendem aos critérios."""

    @abstractmethod
    def fetch_observations(self, company: CompanyProfile) -> List[Observation]:
        """Fatos públicos observáveis sobre a empresa (cada um com fonte e URL)."""

    @abstractmethod
    def lookup(self, name: str) -> Optional[RawCompany]:
        """Localiza uma empresa pelo nome."""
