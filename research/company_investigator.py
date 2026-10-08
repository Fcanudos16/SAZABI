"""Coleta de observações públicas sobre uma empresa, com cache."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional, Sequence

from database.models import CompanyProfile, Observation
from research.base import CompanySource
from utils.timeutils import hours_since, now_iso

log = logging.getLogger("sazabi.investigator")


@dataclass
class InvestigationResult:
    observations: List[Observation]
    from_cache: bool
    failed: bool = False


class CompanyInvestigator:
    def __init__(self, sources: Sequence[CompanySource], cache_ttl_hours: float = 24):
        self.sources = list(sources)
        self.cache_ttl_hours = cache_ttl_hours
        self.errors: List[str] = []

    def is_fresh(self, profile: CompanyProfile) -> bool:
        return bool(profile.investigated and profile.last_researched
                    and hours_since(profile.last_researched) < self.cache_ttl_hours)

    def investigate(self, profile: CompanyProfile, refresh: bool = False,
                    stored: Optional[List[Observation]] = None) -> InvestigationResult:
        if not refresh and self.is_fresh(profile):
            log.info("Cache usado para %s", profile.name)
            return InvestigationResult(list(stored or []), True)
        if not self.sources:
            self.errors.append('Nenhuma fonte configurada; investigação não atualizada.')
            return InvestigationResult(list(stored or []), bool(stored), failed=True)
        collected = [] if profile.investigated else list(profile.observations)
        current_errors = []
        for source in self.sources:
            try:
                if refresh and hasattr(source, 'pages'):
                    source.pages.clear()
                collected.extend(source.fetch_observations(profile))
            except Exception as error:
                from utils.http_client import FetchError
                detail = str(error) if isinstance(error, FetchError) else 'Coleta indisponível.'
                log.warning('Fonte %s: %s', source.name, detail)
                current_errors.append(source.name + ': ' + detail)
        self.errors.extend(current_errors)
        now, seen, observations = now_iso(), set(), []
        if current_errors:
            return InvestigationResult(list(stored or []), bool(stored), failed=True)
        for o in collected:
            if (o.text, o.url) in seen:
                continue
            seen.add((o.text, o.url))
            o.retrieved_at = o.retrieved_at or now
            observations.append(o)
        return InvestigationResult(observations, False)
