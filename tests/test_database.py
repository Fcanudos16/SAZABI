import pytest

from database.database import Database
from database.models import CompanyProfile, Hypothesis, Observation, SearchCriteria, Signal
from database.repositories import (CompanyRepository, HypothesisRepository, IgnoredRepository,
                                   RunRepository, SettingsRepository, SignalRepository, SourceRepository)
from utils.timeutils import now_iso


@pytest.fixture
def db():
    return Database(":memory:")


def test_company_roundtrip_keeps_none_as_none(db):
    repo = CompanyRepository(db)
    cid = repo.add(CompanyProfile(name="Oficina Silva", city="São Paulo", units=2,
                                  social_profiles={"instagram": "x"}))
    got = repo.get(cid)
    assert got.name == "Oficina Silva" and got.units == 2 and got.social_profiles == {"instagram": "x"}
    assert got.website is None and got.phone is None and got.status == "NEW" and got.first_seen


def test_search_by_name_and_candidates(db):
    repo = CompanyRepository(db)
    repo.add(CompanyProfile(name="Oficina Silva LTDA", city="São Paulo", domain="silva.com.br", phone="(11) 4000-0003"))
    assert len(repo.search_by_name("oficina silva")) == 1
    assert len(repo.search_by_name("silva")) == 1
    assert repo.search_by_name("zzz") == []
    assert repo.candidates_for(CompanyProfile(name="X", city="Campinas", domain="silva.com.br"))
    assert repo.candidates_for(CompanyProfile(name="X", city="Campinas", phone="11 4000 0003"))
    assert not repo.candidates_for(CompanyProfile(name="X", city="Campinas", domain="outro.com"))


def test_status_changes_are_logged_and_validated(db):
    repo = CompanyRepository(db)
    cid = repo.add(CompanyProfile(name="A"))
    repo.set_status(cid, "SAVED")
    assert repo.get(cid).status == "SAVED"
    assert repo.list_changes(cid)[0][:3] == ("status", "NEW", "SAVED")
    with pytest.raises(ValueError):
        repo.set_status(cid, "INVALID")


def test_signals_hypotheses_sources_replace_and_cascade(db):
    companies = CompanyRepository(db)
    cid = companies.add(CompanyProfile(name="A"))
    SignalRepository(db).replace_for_company(cid, [Signal("scheduling", "d", "e", "s", now_iso(), "moderate")])
    HypothesisRepository(db).replace_for_company(cid, [Hypothesis("x", ["r"], "moderado", now_iso())])
    SourceRepository(db).replace_for_company(cid, [Observation("t", "src", "http://u")])
    assert len(SignalRepository(db).list_for_company(cid)) == 1
    assert HypothesisRepository(db).best_level_map([cid]) == {cid: "moderado"}
    SignalRepository(db).replace_for_company(cid, [])
    assert SignalRepository(db).list_for_company(cid) == []
    companies.delete(cid)
    assert SourceRepository(db).list_for_company(cid) == []
    assert HypothesisRepository(db).list_for_company(cid) == []


def test_runs_and_ignored_and_settings(db):
    runs = RunRepository(db)
    run = runs.create(SearchCriteria(city="Campinas", raw_query="q"))
    run.found = 5
    runs.finish(run)
    assert runs.last().found == 5 and runs.last().finished_at
    cid = CompanyRepository(db).add(CompanyProfile(name="A"))
    ign = IgnoredRepository(db)
    ign.add(cid)
    assert ign.is_ignored(cid)
    ign.remove(cid)
    assert not ign.is_ignored(cid)
    settings = SettingsRepository(db)
    assert settings.get("k", "d") == "d"
    settings.set("k", "v")
    assert settings.get("k") == "v"
