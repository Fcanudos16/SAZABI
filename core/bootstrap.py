"""Montagem das peças do SAZABI (usado pelo main.py e pelos testes)."""
from __future__ import annotations

from typing import Optional, Sequence

from analysis.opportunity_analyzer import OpportunityAnalyzer
from analysis.signal_detector import SignalDetector
from core.agent import SazabiAgent
from core.config import Config
from database.database import Database
from notifications.notifier import ConsoleNotifier, Notifier
from research.base import CompanySource
from research.company_finder import CompanyFinder
from research.company_investigator import CompanyInvestigator
from research.mock_source import MockSource


def build_agent(config: Config, notifier: Optional[Notifier] = None,
                sources: Optional[Sequence[CompanySource]] = None) -> SazabiAgent:
    if sources is None:
        sources = [MockSource()] if config.mock else []
        if not config.mock and config.search_api_key:
            from research.web_source import BraveSearch, WebSource
            sources = [WebSource(BraveSearch(config.search_api_key, config.search_limit))]
    return SazabiAgent(
        config=config, db=Database(config.database_path), finder=CompanyFinder(sources),
        investigator=CompanyInvestigator(sources, config.cache_ttl_hours), detector=SignalDetector(),
        analyzer=OpportunityAnalyzer(config.services), notifier=notifier or ConsoleNotifier())
