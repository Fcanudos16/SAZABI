"""Integrated reliability regressions; isolated fixtures only."""
import threading
from unittest.mock import patch
from unittest.mock import Mock
from core.config import Config
from tests.factories import build_agent
from database.database import Database
from database.models import SearchCriteria, CompanyProfile
from database.repositories import RunRepository
from database.recovery import recover, research_lock, ResearchBusy
from database.leads import LeadRepository
from research.company_investigator import CompanyInvestigator
from utils.http_client import HttpClient
import pytest


@pytest.mark.parametrize('command',['/research clínicas em Campinas','procure clínicas em Campinas'])
def test_legacy_cancel_marks_run_and_next_request_works(agent,command):
    cancelled=threading.Event()
    original=agent.finder.find
    def find(criteria):
        result=original(criteria)
        cancelled.set()
        return result
    with patch.object(agent.finder,'find',side_effect=find):
        response=agent.handle(command,cancelled)
    assert 'cancelada' in response
    assert agent.last_skill_result.status=='cancelled'
    assert agent.runs.last().status=='cancelled' and agent.runs.last().finished_at
    assert agent.execution_context is None
    assert 'Pesquisa concluída' in agent.handle(command)


def test_cancelled_transport_callbacks_are_restored(agent):
    client=HttpClient();previous=client.checkpoint
    agent.finder.sources[0].client=client
    event=threading.Event();event.set()
    agent.handle('/research clínicas em Campinas',event)
    assert agent.last_skill_result.status=='cancelled'
    assert client.checkpoint is previous


def test_cancel_during_single_investigation_does_not_publish_new_evidence(agent):
    agent.handle('/investigate Oficina Silva')
    company=agent.companies.search_by_name('Oficina Silva')[0]
    before=agent.sources.list_for_company(company.id)
    original=agent.investigator.investigate
    cancelled=threading.Event()
    def investigate(*args,**kwargs):
        result=original(*args,**kwargs)
        cancelled.set()
        return result
    with patch.object(agent.investigator,'investigate',side_effect=investigate):
        agent.handle('/investigate '+company.id+' --refresh',cancelled)
    assert agent.last_skill_result.status=='cancelled'
    assert agent.sources.list_for_company(company.id)==before
    assert agent.companies.get(company.id).last_researched==company.last_researched


def test_search_skill_uses_its_configured_deadline_not_legacy_deadline(agent):
    from skills.base import SkillContext
    agent.execution_context=Mock()
    agent.skill_context=SkillContext(agent,timeout=600)
    try:
        agent.emit('SEARCH_PROCESSING')
        agent.execution_context.checkpoint.assert_not_called()
    finally:agent.execution_context=agent.skill_context=None


def test_restart_marks_orphan_run_without_deleting_data(tmp_path):
    config=Config(mock=True,database_path=str(tmp_path/'restart.db'))
    agent=build_agent(config)
    company=CompanyProfile(name='Fixture interrompida');agent.companies.add(company)
    run=agent.runs.create(SearchCriteria(raw_query='Fixture de interrupção'))
    agent.runs.add_company(run.id,company.id,True)
    agent.db.close()
    agent=build_agent(config)
    try:
        restored=agent.runs.last()
        assert restored.status=='interrupted' and restored.finished_at and 'interrompida' in restored.error_message
        assert restored.new_count==1 and agent.companies.get(company.id)
        assert 'interrupted' in agent.handle('/results')
    finally:agent.db.close()


def test_recovery_does_not_mark_live_other_instance_as_crashed(tmp_path):
    db=Database(str(tmp_path/'shared.db'));other=Database(db.path)
    run=RunRepository(db).create(SearchCriteria(raw_query='Fixture ativa'))
    try:
        with research_lock(db):
            recover(other)
            assert RunRepository(other).last().status=='running'
            with pytest.raises(ResearchBusy):
                with research_lock(other):pass
        recover(other)
        assert RunRepository(other).last().status=='interrupted'
        with research_lock(other):pass
    finally:db.close();other.close()


@pytest.mark.parametrize('stamp',['not-a-date','2999-01-01',None])
def test_invalid_future_cache_dates_do_not_crash_or_count_as_fresh(stamp):
    assert not CompanyInvestigator([]).is_fresh(CompanyProfile(name='Fixture',investigated=True,last_researched=stamp))


def test_lead_filters_use_latest_saved_qualification(agent):
    from tests.test_commercial import seed
    from analysis.commercial import CommercialService
    company=seed(agent)
    other=CompanyProfile(name='Fixture sem avaliação');agent.companies.add(other)
    CommercialService(agent.db,agent.config).qualify(company.id)
    rows=LeadRepository(agent.db).list(min_score=70,category='high',order='score')
    assert [r['id'] for r in rows]==[company.id]
    assert company.id in agent.handle('/leads min_score=70 categoria=high ordem=score')
    assert 'Dados inválidos' in agent.handle('/leads min_score=101')


def test_failed_worker_never_emits_response_ready():
    from core.worker import AgentWorker
    worker=AgentWorker(Config(database_path=':memory:'),progress=True)
    try:
        assert worker.events.get(timeout=5)[0]=='ready'
        assert worker.submit('/search clínicas em Campinas')
        seen=[]
        while True:
            kind,value=worker.events.get(timeout=5)
            seen.append((kind,value))
            if kind=='command_result':break
        assert value['status']=='failed'
        assert not any(k=='activity' and v['kind']=='RESPONSE_READY' for k,v in seen)
    finally:worker.close();worker.thread.join(5)
    assert not worker.thread.is_alive()
