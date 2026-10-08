"""Configuração via .env (+ variáveis de ambiente) e services.yaml. Sem dependências externas."""
from __future__ import annotations

import os
import math
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_SERVICES = ["sistemas web", "aplicativos mobile", "automação", "sistemas internos",
                    "integrações", "dashboards", "e-commerce", "inteligência artificial",
                    "sistemas de gestão"]
DEFAULT_DB = "data/sazabi.db"
MOCK_DB = "data/sazabi_mock.db"


@dataclass
class Config:
    env_file: str = '.env'
    env: str = "development"
    database_path: str = DEFAULT_DB
    mock: bool = False
    cache_ttl_hours: float = 24.0
    log_level: str = "INFO"
    log_file: str = "logs/sazabi.log"
    default_region: Optional[str] = None
    services: List[str] = field(default_factory=lambda: list(DEFAULT_SERVICES))
    search_api_key: str = field(default='', repr=False)
    search_limit: int = 5
    telegram_token: str = field(default='', repr=False)
    telegram_allowed_ids: tuple = ()
    ai_provider: str = 'none'
    ollama_model: str = ''
    session_scope: str = ''


def read_env_file(path: str) -> Dict[str, str]:
    values: Dict[str, str] = {}
    p = Path(path)
    if not p.is_file():
        return values
    for line in p.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def read_services(path: str) -> List[str]:
    """Lê a lista `services:` de um YAML simples (sem precisar de PyYAML)."""
    p = Path(path)
    if not p.is_file():
        return list(DEFAULT_SERVICES)
    items: List[str] = []
    in_block = False
    for line in p.read_text(encoding="utf-8-sig").splitlines():
        line = line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if re.match(r"^services\s*:", line.strip()):
            in_block = True
        elif in_block:
            m = re.match(r"^\s*-\s*(.+?)\s*$", line)
            if m:
                items.append(m.group(1).strip("\"'"))
    return items or list(DEFAULT_SERVICES)


def load_config(env_file: str = ".env", services_file: str = "services.yaml",
                mock: bool = False, db_path: Optional[str] = None) -> Config:
    file_values = read_env_file(env_file)

    def get(key: str, default: Optional[str] = None) -> Optional[str]:
        return os.environ.get(key) or file_values.get(key) or default

    database = db_path or get("DATABASE_PATH", DEFAULT_DB)
    if mock and database == DEFAULT_DB:
        database = MOCK_DB          # dados fictícios nunca se misturam com o banco real
    try:
        ttl = float(get("CACHE_TTL_HOURS", "24"))
    except ValueError:
        ttl = 24.0
    if not math.isfinite(ttl) or ttl < 0:
        ttl = 24.0
    try:
        allowed_ids = tuple(int(x.strip()) for x in get('TELEGRAM_ALLOWED_USER_IDS', '').split(',') if x.strip())
        if any(uid <= 0 for uid in allowed_ids):
            raise ValueError
    except ValueError:
        # Fail closed for Telegram, but do not disable the unrelated desktop UI.
        allowed_ids = ()
        logging.getLogger('sazabi.config').warning('Lista de usuários Telegram inválida; acesso Telegram desabilitado.')
    try:
        search_limit = min(20, max(1, int(get('SEARCH_LIMIT', '5'))))
    except ValueError:
        search_limit = 5
    return Config(env_file=str(Path(env_file).resolve()), env=get("SAZABI_ENV", "development"), database_path=database, mock=mock,
                  cache_ttl_hours=ttl, log_level=get("LOG_LEVEL", "INFO"),
                  log_file=get("LOG_FILE", "logs/sazabi.log"), default_region=get("DEFAULT_REGION"),
                  services=read_services(services_file),
                  search_api_key=get('SEARCH_API_KEY', ''),
                  search_limit=search_limit,
                  telegram_token=get('TELEGRAM_BOT_TOKEN', ''),
                  telegram_allowed_ids=allowed_ids,
                  ai_provider=get('AI_PROVIDER', 'none'), ollama_model=get('OLLAMA_MODEL', ''))
