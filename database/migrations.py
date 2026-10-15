"""Additive, versioned migrations for the existing local SQLite database."""
from utils.timeutils import now_iso


def migrate(db):
    db.conn.execute('CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)')
    db.conn.commit()
    version = db.conn.execute('SELECT COALESCE(MAX(version), 0) FROM schema_migrations').fetchone()[0]
    if version > 1:
        raise RuntimeError('Banco criado por uma versão mais recente do SAZABI.')
    if version == 1:
        return
    # A verified SQLite backup includes WAL; never copy an open database file.
    if db.path != ':memory:' and any(db.query_one('SELECT COUNT(*) AS n FROM '+table)['n'] for table in ('companies','research_runs','settings','conversation_history')):
        db.backup()
    with db.transaction():
        db.conn.execute('UPDATE schema_migrations SET version=version WHERE 0')
        if db.conn.execute('SELECT 1 FROM schema_migrations WHERE version=1').fetchone():
            return
        db.conn.execute("ALTER TABLE companies ADD COLUMN commercial_status TEXT NOT NULL DEFAULT 'new' CHECK(commercial_status IN ('new','qualified','contact_pending','contacted','negotiating','converted','discarded'))")
        db.conn.execute("ALTER TABLE companies ADD COLUMN notes TEXT NOT NULL DEFAULT ''")
        db.conn.execute('ALTER TABLE companies ADD COLUMN archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1))')
        db.conn.execute("UPDATE companies SET commercial_status=CASE status WHEN 'CONTACTED' THEN 'contacted' WHEN 'CLIENT' THEN 'converted' WHEN 'DISCARDED' THEN 'discarded' WHEN 'INTERESTING' THEN 'qualified' ELSE 'new' END")
        db.conn.execute("UPDATE companies SET notes=COALESCE((SELECT note FROM saved_companies WHERE company_id=companies.id),'')")
        db.conn.execute('CREATE INDEX idx_companies_commercial ON companies(commercial_status,archived)')
        db.conn.execute('CREATE TABLE lead_events (id INTEGER PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE, kind TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL)')
        db.conn.execute('CREATE INDEX idx_lead_events_company ON lead_events(company_id,id)')
        db.conn.execute('CREATE TABLE duplicate_candidates (company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE, other_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE, reason TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(company_id,other_id), CHECK(company_id < other_id))')
        db.conn.execute('CREATE TABLE source_history (id INTEGER PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE, source_name TEXT NOT NULL, url TEXT, text TEXT NOT NULL, retrieved_at TEXT NOT NULL)')
        db.conn.execute('CREATE INDEX idx_source_history_company ON source_history(company_id)')
        db.conn.execute('INSERT INTO source_history(company_id,source_name,url,text,retrieved_at) SELECT company_id,source_name,url,text,retrieved_at FROM sources')
        db.conn.execute("INSERT INTO lead_events(company_id,kind,detail,created_at) SELECT id,'migrated','Cadastro existente preservado; estágio: ' || commercial_status,? FROM companies", (now_iso(),))
        db.conn.execute("CREATE TRIGGER lead_created AFTER INSERT ON companies BEGIN INSERT INTO lead_events(company_id,kind,detail,created_at) VALUES(NEW.id,'identified','Lead identificado',NEW.first_seen); END")
        db.conn.execute('INSERT INTO schema_migrations VALUES (1,?)', (now_iso(),))
