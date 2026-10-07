from datetime import timedelta

from tests.factories import build_agent
from core.config import Config
from database.models import SearchCriteria
from research.base import CompanySource
from utils.timeutils import now_iso, utcnow


def test_full_search_flow_dedupes_investigates_and_persists(agent):
    reply = agent.handle("SAZABI, procure clínicas em São Paulo.")
    assert "Pesquisa concluída" in reply
    assert "3 encontradas" in reply and "1 duplicada removida" in reply and "2 novas" in reply
    assert "Clínica Alpha Odontologia" in reply
    assert agent.companies.count() == 2                      # duplicata não foi gravada
    alpha = agent.companies.search_by_name("Clínica Alpha")[0]
    assert alpha.status == "RESEARCHED" and alpha.investigated
    assert agent.signals.list_for_company(alpha.id) and agent.hypotheses.list_for_company(alpha.id)
    assert agent.runs.last().found == 3


def test_second_search_recognises_known_companies_and_uses_cache(agent):
    agent.handle("procure clínicas em São Paulo")
    before = agent.signals.total()
    reply = agent.handle("procure clínicas em São Paulo")
    assert "0 novas" in reply and "2 já conhecidas" in reply
    assert agent.signals.total() == before and agent.companies.count() == 2


def test_missing_region_is_asked_once_then_search_runs(agent):
    assert agent.handle("procure oficinas") == "Qual região devo pesquisar?"
    reply = agent.handle("Campinas")
    assert "Pesquisa concluída" in reply and "Região: Campinas" in reply


def test_default_region_is_used_without_asking(agent):
    agent.handle("/set region Campinas")
    reply = agent.handle("procure oficinas")
    assert "Região: Campinas" in reply and "Oficina Delta" in reply


def test_ignored_company_is_not_presented_again(agent):
    agent.handle("procure clínicas em São Paulo")
    assert "ignorar" in agent.handle("ignore Clínica Sorriso Beta").lower()
    reply = agent.handle("procure clínicas em São Paulo")
    assert "1 ignorada" in reply and "Sorriso Beta" not in reply


def test_investigate_unknown_company_via_lookup_has_sources_and_disclaimer(agent):
    reply = agent.handle("SAZABI, investigue a Oficina Silva.")
    assert "Empresa: Oficina Silva" in reply
    assert "Fato observado:" in reply and "Fonte:" in reply and "Possível interpretação" in reply
    assert "Existe uma possível oportunidade para" in reply and "hipóteses baseadas em informações públicas" in reply
    assert "Fontes consultadas" in reply


def test_unknown_company_is_not_invented(agent):
    reply = agent.handle("investigue a Empresa Inexistente XYZ")
    assert "Não identifiquei" in reply and agent.companies.count() == 0


def test_company_without_data_never_invents_fields(agent):
    reply = agent.handle("investigue Empresa Sigma")
    assert "Telefone: (19) 4000-0016" in reply and "Unidades identificadas: Não identificado" in reply
    assert "Porte: Não identificado" in reply and "Site: Não identificado" in reply
    assert "Site oficial não identificado nas fontes consultadas" in reply
    assert "Nenhuma hipótese com evidência suficiente" in reply and "Fontes consultadas:" not in reply


def test_signal_without_enough_hypothesis_is_stated_plainly(agent):
    reply = agent.handle("investigue Startup Theta Tech")
    assert "Nenhuma hipótese com evidência suficiente" in reply


def test_cache_and_refresh(agent):
    agent.handle("investigue Oficina Silva")
    assert "cache" in agent.handle("investigue Oficina Silva").lower()
    assert "cache" not in agent.handle("atualize a investigação da empresa Oficina Silva").lower()


def test_save_uses_last_company_context(agent):
    agent.handle("investigue Oficina Silva")
    assert "salva" in agent.handle("guarde essa empresa").lower()
    assert agent.companies.search_by_name("Oficina Silva")[0].status == "SAVED"
    assert "SALVA" in agent.handle("/company Oficina Silva")


def test_forget_requires_confirmation(agent):
    agent.handle("investigue Oficina Silva")
    assert "Confirma" in agent.handle("/forget Oficina Silva")
    assert "nada foi apagado" in agent.handle("não")
    assert agent.companies.count() == 1
    agent.handle("/forget Oficina Silva")
    assert "apagados" in agent.handle("sim")
    assert agent.companies.count() == 0


def test_results_history_and_interesting(agent):
    agent.handle("procure clínicas em São Paulo")
    assert "Clínica Alpha Odontologia" in agent.handle("o que você encontrou hoje?")
    assert "Clínica Alpha Odontologia" in agent.handle("quais empresas parecem interessantes?")
    history = agent.handle("o que eu pesquisei hoje?")
    assert "Encontradas: 3" in history and "Duplicadas: 1" in history
    assert "Não encontrei pesquisas" in agent.handle("o que eu pesquisei ontem?")


def test_yesterday_runs_are_found_by_period(agent):
    run = agent.runs.create(SearchCriteria(city="X", raw_query="pesquisa antiga"),
                            started_at=(utcnow() - timedelta(days=1)).isoformat(timespec="seconds"))
    agent.runs.finish(run)
    assert "pesquisa antiga" in agent.handle("o que eu pesquisei ontem?")
    assert "pesquisa antiga" not in agent.handle("o que eu pesquisei hoje?")


def test_notifications_silent_vs_normal(agent, notifier):
    agent.handle("faça uma pesquisa silenciosa por clínicas em São Paulo")
    assert len(notifier.messages) == 1 and "resumo" in notifier.messages[0]
    notifier.messages.clear()
    agent.handle("procure oficinas em São Paulo")
    assert len(notifier.messages) >= 2 and "resumo" in notifier.messages[-1]
    assert agent.notifications.count() >= 3


def test_failing_source_is_reported_not_fatal(notifier):
    class Broken(CompanySource):
        name = "quebrada"

        def search(self, criteria):
            raise RuntimeError("fora do ar")

        def fetch_observations(self, company):
            return []

        def lookup(self, name):
            return None

    agent = build_agent(Config(database_path=":memory:"), notifier=notifier, sources=[Broken()])
    reply = agent.handle("procure clínicas em São Paulo")
    assert "Pesquisa não concluída" in reply and "quebrada" in reply


def test_no_sources_configured_is_honest(notifier):
    agent = build_agent(Config(database_path=":memory:"), notifier=notifier)
    assert "Pesquisa não iniciada" in agent.handle("procure clínicas em São Paulo")
    assert notifier.messages == []


def test_unknown_input_and_internal_errors_do_not_crash(agent, monkeypatch):
    assert "Não entendi" in agent.handle("xyzzy")
    monkeypatch.setattr(agent.finder, "find", lambda c: (_ for _ in ()).throw(RuntimeError("boom")))
    assert "erro interno" in agent.handle("procure clínicas em São Paulo")


def test_memory_persists_conversation_and_context(agent):
    agent.handle("investigue Oficina Silva")
    assert agent.memory.last_company_id() == agent.companies.search_by_name("Oficina Silva")[0].id
    assert agent.memory.recent_turns(2)[0] == ("user", "investigue Oficina Silva")
