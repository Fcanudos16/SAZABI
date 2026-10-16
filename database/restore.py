"""Offline restore using SQLite backup, a live-session lock and a rescue copy."""
from contextlib import closing
from pathlib import Path
import sqlite3
import logging
import time
from types import SimpleNamespace
from database.recovery import research_lock


def validate_backup(path):
    path=Path(path).resolve(strict=True)
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as conn:
        conn.execute('PRAGMA trusted_schema=OFF')
        if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or conn.execute('PRAGMA foreign_key_check').fetchone():
            raise ValueError('Backup inválido: integridade ou referências.')
        tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'companies','research_runs','sources','settings','lead_events','schema_migrations'}<=tables:
            raise ValueError('O arquivo não é um backup SAZABI compatível.')
        version=conn.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0]
        if not isinstance(version,int) or not 1<=version<=4:raise ValueError('Versão de backup incompatível.')
        return dict(version=version,companies=conn.execute('SELECT COUNT(*) FROM companies').fetchone()[0])


def restore_backup(target,backup,confirmed=False):
    if not confirmed:raise ValueError('Restauração exige confirmação explícita.')
    target=Path(target).resolve();backup=Path(backup).resolve(strict=True)
    if target==backup:raise ValueError('Destino e backup não podem ser o mesmo arquivo.')
    validate_backup(backup)
    target.parent.mkdir(parents=True,exist_ok=True)
    with research_lock(SimpleNamespace(path=str(target)),suffix='.session.lock'),research_lock(SimpleNamespace(path=str(target))):
        logging.getLogger('sazabi.recovery').info('Restauração confirmada: backup=%s',backup.name)
        rescue=None
        if target.exists():
            # No schema changes to the old database before preserving it.
            from database.database import Database
            source=Database.__new__(Database);source.path=str(target)
            source.conn=sqlite3.connect(target.as_uri()+'?mode=ro',uri=True)
            try:rescue=source.backup(target.parent/'rescue')
            finally:source.conn.close()
        with closing(sqlite3.connect(backup.as_uri()+'?mode=ro',uri=True)) as source,closing(sqlite3.connect(str(target),timeout=5)) as destination:
            deadline=time.monotonic()+30
            def progress(status,remaining,total):
                if time.monotonic()>deadline:raise TimeoutError('Restauração excedeu 30 segundos; consulte a cópia rescue.')
            source.backup(destination,pages=128,progress=progress,sleep=.1)
        validate_backup(target)
        logging.getLogger('sazabi.recovery').info('Restauração validada; cópia anterior preservada=%s',bool(rescue))
        return rescue
