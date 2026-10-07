"""Read-only desktop projection. All queries run on the agent's SQLite thread."""


def dashboard_snapshot(db):
    totals = db.query_one('''SELECT COUNT(*) AS found,
        COALESCE(SUM(investigated), 0) AS processed,
        COALESCE(SUM(status IN ('CONTACTED', 'CLIENT')), 0) AS contacted FROM companies''')
    qualified = db.query_one('''SELECT COUNT(DISTINCT c.id) AS total FROM companies c
        JOIN hypotheses h ON h.company_id=c.id WHERE c.status != 'DISCARDED'
        AND h.evidence_level IN ('moderado', 'forte')''')['total']
    runs = [dict(row) for row in db.query('''SELECT id, query, started_at, finished_at,
        found, investigated, opportunities, status, error_message FROM research_runs ORDER BY id DESC LIMIT 5''')]
    return {'found': totals['found'], 'processed': totals['processed'], 'qualified': qualified,
            'contacted': totals['contacted'], 'runs': runs,
            'searches': db.query_one('SELECT COUNT(*) AS total FROM research_runs')['total']}
