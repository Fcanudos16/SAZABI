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


def build_agent(config: Config, notifier: Optional[Notifier] = None,
                sources: Optional[Sequence[CompanySource]] = None) -> SazabiAgent:
    if sources is None:
        sources = []
        if config.legacy_commercial and not config.mock and config.search_api_key:
            from research.web_source import TavilySearch, WebSource
            sources = [WebSource(TavilySearch(config.search_api_key, config.search_limit))]
    db=Database(config.database_path)
    try:
        from database.recovery import recover
        recover(db)
        return SazabiAgent(
            config=config, db=db, finder=CompanyFinder(sources),
            investigator=CompanyInvestigator(sources, config.cache_ttl_hours), detector=SignalDetector(),
            analyzer=OpportunityAnalyzer(config.services), notifier=notifier or ConsoleNotifier())
    except BaseException:
        db.close()
        raise
