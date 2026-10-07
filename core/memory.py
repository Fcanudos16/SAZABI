"""Memória persistente: conversa e contexto (última empresa/pesquisa) sobrevivem a reinícios."""
from __future__ import annotations

from typing import List, Optional, Tuple

from database.database import Database
from database.repositories import ConversationRepository, SettingsRepository


class Memory:
    def __init__(self, db: Database, scope: str = ''):
        self.scope = scope
        self.settings = SettingsRepository(db)
        self.conversation = ConversationRepository(db)

    def log_turn(self, role: str, text: str) -> None:
        self.conversation.add(role, text)

    def recent_turns(self, limit: int = 20) -> List[Tuple[str, str]]:
        return self.conversation.recent(limit)

    def get_setting(self, key: str) -> Optional[str]:
        return self.settings.get(key)

    def set_setting(self, key: str, value: str) -> None:
        self.settings.set(key, value)

    def last_company_id(self) -> Optional[str]:
        return self.settings.get(self.scope + "last_company_id")

    def set_last_company(self, company_id: str) -> None:
        self.settings.set(self.scope + "last_company_id", company_id)

    def last_run_id(self) -> Optional[int]:
        value = self.settings.get(self.scope + "last_run_id")
        return int(value) if value else None

    def set_last_run(self, run_id: int) -> None:
        self.settings.set(self.scope + "last_run_id", str(run_id))
