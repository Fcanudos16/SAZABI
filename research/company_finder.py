"""Descoberta de empresas e normalização inicial (RawCompany -> CompanyProfile)."""
from __future__ import annotations

import logging
from typing import List, Optional, Sequence

from database.models import CompanyProfile, RawCompany, SearchCriteria
from research.base import CompanySource
from utils.normalization import company_domain, normalize_name

log = logging.getLogger("sazabi.finder")


def build_profile(raw: RawCompany) -> CompanyProfile:
    """Normalização: nada é inventado; o que a fonte não trouxe fica None."""
    return CompanyProfile(
        name=raw.name.strip(), normalized_name=normalize_name(raw.name), legal_name=raw.legal_name,
        website=raw.website, domain=company_domain(raw.website), segment=raw.segment, city=raw.city,
        state=raw.state, country=raw.country, address=raw.address, phone=raw.phone,
        estimated_size=raw.estimated_size, description=raw.description,
        social_profiles=dict(raw.social_profiles), services=list(raw.services), units=raw.units,
        observations=list(raw.observations))


def merge_profiles(a: CompanyProfile, b: CompanyProfile) -> CompanyProfile:
    """Preenche em `a` o que estiver vazio usando `b` (a vence em caso de conflito)."""
    for attr in ("legal_name", "website", "domain", "segment", "city", "state", "country", "address",
                 "phone", "estimated_size", "description"):
        if not getattr(a, attr) and getattr(b, attr):
            setattr(a, attr, getattr(b, attr))
    if b.units and (not a.units or b.units > a.units):
        a.units = b.units
    for k, v in b.social_profiles.items():
        a.social_profiles.setdefault(k, v)
    for s in b.services:
        if s not in a.services:
            a.services.append(s)
    seen = {(o.text, o.url) for o in a.observations}
    for o in b.observations:
        if (o.text, o.url) not in seen:
            a.observations.append(o)
    return a


class CompanyFinder:
    def __init__(self, sources: Sequence[CompanySource]):
        self.sources = list(sources)
        self.errors: List[str] = []
        self.hits = []

    def find(self, criteria: SearchCriteria) -> List[RawCompany]:
        self.errors = []
        self.hits = []
        if not self.sources:
            log.warning("Nenhuma fonte configurada")
            return []
        results: List[RawCompany] = []
        for source in self.sources:
            try:
                found = source.search(criteria)
                log.info("%d empresas encontradas em %s", len(found), source.name)
                results.extend(found)
                self.hits.extend(getattr(source, 'last_hits', []))
            except Exception as error:
                from skills.base import ExecutionStopped
                if isinstance(error, ExecutionStopped):
                    raise
                from utils.http_client import FetchError
                detail = str(error) if isinstance(error, FetchError) else 'Falha ao consultar a fonte.'
                log.warning('Fonte %s: %s', source.name, detail)
                self.errors.append(source.name + ': ' + detail)
        return results

    def lookup(self, name: str) -> Optional[RawCompany]:
        self.errors = []
        for source in self.sources:
            try:
                raw = source.lookup(name)
                if raw:
                    return raw
            except Exception as error:
                from skills.base import ExecutionStopped
                if isinstance(error, ExecutionStopped):
                    raise
                from utils.http_client import FetchError
                self.errors.append(str(error) if isinstance(error, FetchError) else 'Falha ao consultar a fonte.')
        return None
