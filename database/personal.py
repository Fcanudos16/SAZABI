"""Personal data in the existing SQLite connection; legacy data is untouched."""
import json
from utils.timeutils import now_iso
from utils.logger import redact

SCHEMA = '''
CREATE TABLE IF NOT EXISTS personal_tasks (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, priority TEXT NOT NULL DEFAULT 'normal',
 due TEXT, category TEXT NOT NULL DEFAULT '', project TEXT NOT NULL DEFAULT '',
 completed INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS personal_operations (
 id INTEGER PRIMARY KEY, command TEXT NOT NULL, status TEXT NOT NULL,
 result TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
'''


class PersonalStore:
    def __init__(self, db):
        self.db = db
        db.conn.executescript(SCHEMA)
        db.execute("UPDATE personal_operations SET status='failed', result='Sessão interrompida; verifique os efeitos antes de repetir.', updated_at=? WHERE status IN ('running','planned')", (now_iso(),))

    def start(self, command):
        stamp = now_iso()
        return self.db.execute('INSERT INTO personal_operations(command,status,created_at,updated_at) VALUES (?, ?, ?, ?)',
                               (command, 'running', stamp, stamp)).lastrowid

    def finish(self, identity, status, message):
        self.db.execute('UPDATE personal_operations SET status=?,result=?,updated_at=? WHERE id=?',
                        (status, redact(message)[:12000], now_iso(), identity))

    def history(self):
        return [dict(row) for row in self.db.query('SELECT * FROM personal_operations ORDER BY id DESC LIMIT 30')]

    def tasks(self, mode='all'):
        condition = {'all': '1', 'pending': 'completed=0', 'overdue': "completed=0 AND due < date('now','localtime')"}.get(mode)
        if condition is None:
            raise ValueError('Use /task list all|pending|overdue.')
        return [dict(row) for row in self.db.query('SELECT * FROM personal_tasks WHERE '+condition+' ORDER BY id DESC')]
