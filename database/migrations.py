"""Additive versioned migrations on the existing database."""
from utils.timeutils import now_iso


def migrate(db):
    db.conn.execute('CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)')
    db.conn.commit()
    version=db.conn.execute('SELECT COALESCE(MAX(version),0) FROM schema_migrations').fetchone()[0]
    if version>4: raise RuntimeError('Banco criado por uma versão mais recente do SAZABI.')
    if version==4: return
    if db.path!=':memory:' and any(db.query_one('SELECT COUNT(*) AS n FROM '+table)['n'] for table in ('companies','research_runs','settings','conversation_history')):
        db.backup()
    # Rebuild the existing CHECK constraint with foreign keys disabled only for
    # this transaction; child records remain intact and are checked before commit.
    db.conn.execute('PRAGMA foreign_keys=OFF')
    try:
        with db.transaction():
            db.conn.execute('UPDATE schema_migrations SET version=version WHERE 0')
            version=db.conn.execute('SELECT COALESCE(MAX(version),0) FROM schema_migrations').fetchone()[0]
            if version<1: _v1(db)
            if version<2: _v2(db)
            if version<3: _v3(db)
            if version<4: _v4(db)
            if db.conn.execute('PRAGMA foreign_key_check').fetchone():
                raise RuntimeError('Migração cancelada: referência inválida no banco.')
    finally:
        db.conn.execute('PRAGMA foreign_keys=ON')


def _v1(db):
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


def _v4(db):
    db.conn.execute("ALTER TABLE research_runs ADD COLUMN strategy_json TEXT NOT NULL DEFAULT '{}'")
    db.conn.execute('INSERT INTO schema_migrations VALUES(4,?)',(now_iso(),))


def _v2(db):
    db.conn.execute('CREATE TABLE lead_evaluations (id INTEGER PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE, input_hash TEXT NOT NULL, engine_version TEXT NOT NULL, score INTEGER NOT NULL CHECK(score BETWEEN 0 AND 100), category TEXT NOT NULL, result_json TEXT NOT NULL, evaluated_at TEXT NOT NULL)')
    db.conn.execute('CREATE INDEX idx_evaluations_company ON lead_evaluations(company_id,id)')
    db.conn.execute("CREATE TABLE commercial_drafts (id INTEGER PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE, evaluation_id INTEGER NOT NULL REFERENCES lead_evaluations(id) ON DELETE CASCADE, format TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(company_id,evaluation_id,format,body))")
    db.conn.execute('INSERT INTO schema_migrations VALUES(2,?)',(now_iso(),))


def _v3(db):
    sql = db.query_one("SELECT sql FROM sqlite_master WHERE type='table' AND name='companies'")['sql']
    objects = [r['sql'] for r in db.query("SELECT sql FROM sqlite_master WHERE tbl_name='companies' AND type IN ('index','trigger') AND sql IS NOT NULL")]
    sql = sql.replace('CREATE TABLE companies', 'CREATE TABLE companies_v3', 1)
    sql = sql.replace("'new','qualified'", "'new','verifying','qualified'")
    db.conn.execute(sql)
    db.conn.execute('INSERT INTO companies_v3 SELECT * FROM companies')
    db.conn.execute('DROP TABLE companies')
    db.conn.execute('ALTER TABLE companies_v3 RENAME TO companies')
    for statement in objects:
        db.conn.execute(statement)
    db.conn.execute("ALTER TABLE companies ADD COLUMN manual_fields TEXT NOT NULL DEFAULT '{}'")
    # Carry forward explicit field edits from the existing commercial history.
    import json
    verified = {}
    for event in db.query("SELECT company_id,detail,created_at FROM lead_events WHERE kind='edit' ORDER BY id"):
        try:
            edit=json.loads(event['detail'])
            field=edit['field']
            if field not in {'phone','segment','city','address','description'}: continue
            verified.setdefault(event['company_id'],{})[field]={'value':edit['after'],'verified_at':event['created_at'],'origin':'user'}
        except (ValueError,KeyError,TypeError):
            continue
    for identity,fields in verified.items():
        current=db.query_one('SELECT * FROM companies WHERE id=?',(identity,))
        fields={key:value for key,value in fields.items() if current[key]==value['value']}
        db.conn.execute('UPDATE companies SET manual_fields=? WHERE id=?',(json.dumps(fields,ensure_ascii=False),identity))
    db.conn.execute('''CREATE TABLE lead_tasks (
        id INTEGER PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
        title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', due_date TEXT NOT NULL,
        completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0,1)),
        created_at TEXT NOT NULL, completed_at TEXT, updated_at TEXT NOT NULL)''')
    db.conn.execute('CREATE INDEX idx_tasks_company ON lead_tasks(company_id,completed,due_date)')
    db.conn.execute('CREATE INDEX idx_tasks_due ON lead_tasks(completed,due_date)')
    db.conn.execute('INSERT INTO schema_migrations VALUES(3,?)',(now_iso(),))
