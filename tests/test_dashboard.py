from core.dashboard import dashboard_snapshot
from database.database import Database
from database.models import CompanyProfile, Hypothesis
from database.repositories import CompanyRepository, HypothesisRepository
from utils.timeutils import now_iso


def test_dashboard_empty_is_zero_not_demo_data():
    db = Database(':memory:')
    try:
        assert dashboard_snapshot(db) == dict(found=0, processed=0, qualified=0, contacted=0, runs=[], searches=0)
    finally:
        db.close()


def test_dashboard_distinguishes_qualified_processed_and_contacted():
    db = Database(':memory:')
    try:
        companies = CompanyRepository(db)
        a = companies.add(CompanyProfile('A', investigated=True))
        b = companies.add(CompanyProfile('B', investigated=True))
        companies.add(CompanyProfile('C', status='CONTACTED'))
        hypotheses = HypothesisRepository(db)
        hypotheses.replace_for_company(a, [Hypothesis('x', [], 'moderado', now_iso()),
                                           Hypothesis('y', [], 'forte', now_iso())])
        hypotheses.replace_for_company(b, [Hypothesis('x', [], 'forte', now_iso())])
        companies.set_status(b, 'DISCARDED')
        result = dashboard_snapshot(db)
        assert result['found'] == 3 and result['processed'] == 2
        assert result['qualified'] == 1 and result['contacted'] == 1
    finally:
        db.close()
