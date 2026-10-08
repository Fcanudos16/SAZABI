"""Conexão SQLite e schema."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    legal_name TEXT, website TEXT, domain TEXT, segment TEXT,
    city TEXT, city_key TEXT, state TEXT, country TEXT,
    address TEXT, phone TEXT, phone_key TEXT,
    estimated_size TEXT, description TEXT,
    social_profiles TEXT NOT NULL DEFAULT '{}',
    services TEXT NOT NULL DEFAULT '[]',
    units INTEGER,
    status TEXT NOT NULL DEFAULT 'NEW',
    investigated INTEGER NOT NULL DEFAULT 0,
    first_seen TEXT NOT NULL,
    last_researched TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain);
CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(normalized_name);
CREATE INDEX IF NOT EXISTS idx_companies_city ON companies(city_key);
CREATE INDEX IF NOT EXISTS idx_companies_phone ON companies(phone_key);
CREATE INDEX IF NOT EXISTS idx_companies_status ON companies(status);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    source_name TEXT NOT NULL, url TEXT, text TEXT NOT NULL, retrieved_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sources_company ON sources(company_id);

CREATE TABLE IF NOT EXISTS research_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT, segment TEXT, city TEXT, state TEXT, size TEXT, need TEXT,
    silent INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL, finished_at TEXT,
    found INTEGER NOT NULL DEFAULT 0, duplicates INTEGER NOT NULL DEFAULT 0,
    new_count INTEGER NOT NULL DEFAULT 0, known_count INTEGER NOT NULL DEFAULT 0,
    ignored_count INTEGER NOT NULL DEFAULT 0, investigated INTEGER NOT NULL DEFAULT 0,
    with_data INTEGER NOT NULL DEFAULT 0, signals_count INTEGER NOT NULL DEFAULT 0,
    opportunities INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_runs_started ON research_runs(started_at);

CREATE TABLE IF NOT EXISTS discovery_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    title TEXT NOT NULL, url TEXT NOT NULL, snippet TEXT NOT NULL,
    retrieved_at TEXT NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_discovery_run ON discovery_results(run_id);

CREATE TABLE IF NOT EXISTS run_companies (
    run_id INTEGER NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    is_new INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (run_id, company_id)
);

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    type TEXT NOT NULL, description TEXT NOT NULL, source TEXT, source_url TEXT,
    evidence TEXT, detected_at TEXT NOT NULL, confidence TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_signals_company ON signals(company_id);

CREATE TABLE IF NOT EXISTS hypotheses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    solution TEXT NOT NULL, reasons TEXT NOT NULL DEFAULT '[]',
    evidence_level TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hypotheses_company ON hypotheses(company_id);

CREATE TABLE IF NOT EXISTS saved_companies (
    company_id TEXT PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
    note TEXT, saved_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ignored_companies (
    company_id TEXT PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
    reason TEXT, ignored_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS company_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    field TEXT NOT NULL, old_value TEXT, new_value TEXT, changed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conversation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL, text TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT REFERENCES companies(id) ON DELETE SET NULL,
    kind TEXT NOT NULL, channel TEXT NOT NULL, message TEXT NOT NULL, sent_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY, value TEXT, updated_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: str = "data/sazabi.db"):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._transaction_depth = 0
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA busy_timeout = 5000")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.executescript(SCHEMA)
        columns = {row['name'] for row in self.conn.execute('PRAGMA table_info(research_runs)')}
        if 'status' not in columns:
            self.conn.execute("ALTER TABLE research_runs ADD COLUMN status TEXT NOT NULL DEFAULT 'legacy'")
        if 'error_message' not in columns:
            self.conn.execute("ALTER TABLE research_runs ADD COLUMN error_message TEXT NOT NULL DEFAULT ''")
        self.conn.commit()

    @contextmanager
    def transaction(self):
        """Nest safely without committing a caller's larger write operation."""
        name = 'sazabi_tx_' + str(self._transaction_depth)
        self.conn.execute('SAVEPOINT ' + name)
        self._transaction_depth += 1
        try:
            yield
        except BaseException:
            self.conn.execute('ROLLBACK TO SAVEPOINT ' + name)
            raise
        finally:
            self._transaction_depth -= 1
            self.conn.execute('RELEASE SAVEPOINT ' + name)

    def execute(self, sql: str, params: Iterable = ()) -> sqlite3.Cursor:
        with self.transaction():
            return self.conn.execute(sql, tuple(params))

    def query(self, sql: str, params: Iterable = ()) -> List[sqlite3.Row]:
        return self.conn.execute(sql, tuple(params)).fetchall()

    def query_one(self, sql: str, params: Iterable = ()) -> Optional[sqlite3.Row]:
        return self.conn.execute(sql, tuple(params)).fetchone()

    def close(self) -> None:
        self.conn.close()

    def backup(self, directory=None) -> str:
        from datetime import datetime, timezone
        root = Path(directory) if directory else Path(self.path).parent / 'backups'
        root.mkdir(parents=True, exist_ok=True)
        filename = root / (Path(self.path).stem + '_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f') + '.db')
        with sqlite3.connect(str(filename)) as target:
            self.conn.backup(target)
            if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Backup falhou na verificação de integridade')
        return str(filename)
