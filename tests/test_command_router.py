import pytest

from core.command_router import parse_criteria, route


def test_natural_search_extracts_criteria():
    cmd = route("SAZABI, procure pequenas empresas de tecnologia em São Paulo.")
    assert cmd.name == "search"
    c = cmd.criteria
    assert (c.segment, c.size, c.city) == ("tecnologia", "pequena", "São Paulo")


def test_lowercase_city_and_state():
    c = route("procure oficinas em campinas/sp").criteria
    assert c.segment == "oficina" and c.city == "Campinas" and c.state == "SP"


def test_search_without_city_has_no_city():
    assert route("procure clínicas odontológicas").criteria.city is None


def test_silent_search():
    cmd = route("SAZABI, faça uma pesquisa silenciosa por pequenas empresas em Campinas.")
    assert cmd.name == "search" and cmd.criteria.silent and cmd.criteria.city == "Campinas"


def test_need_based_search():
    c = route("SAZABI, encontre empresas que possam precisar de automação em Campinas").criteria
    assert c.need == "automação" and c.city == "Campinas"


def test_slash_and_natural_investigate_are_equivalent():
    a, b = route("/investigate Oficina Silva"), route("SAZABI, investigue a Oficina Silva.")
    assert a.name == b.name == "investigate" and a.target == b.target == "Oficina Silva"


def test_refresh_variants():
    assert route("atualize a investigação da empresa Oficina Silva").refresh
    assert route("/investigate Oficina Silva --refresh").refresh
    cmd = route("pesquise novamente essa empresa")
    assert cmd.name == "investigate" and cmd.refresh and cmd.target is None


@pytest.mark.parametrize("text,name", [
    ("guarde essa empresa", "save"), ("ignore essa empresa", "ignore"), ("esqueça a empresa X", "forget"),
    ("o que você encontrou hoje?", "results"), ("me mostre as empresas encontradas ontem", "results"),
    ("quais empresas parecem interessantes?", "interesting"), ("o que eu pesquisei ontem?", "history"),
    ("/help", "help"), ("/status", "status"), ("sair", "exit"), ("blá blá", "unknown"), ("", "empty"),
])
def test_intents(text, name):
    assert route(text).name == name


def test_targets_and_periods():
    assert route("guarde essa empresa").target is None
    assert route("guarde a empresa Oficina Silva").target == "Oficina Silva"
    assert route("o que eu pesquisei ontem?").period == "yesterday"
    assert route("o que você encontrou hoje?").period == "today"


def test_pesquise_empresa_x_is_investigation_but_plural_is_search():
    assert route("pesquise a empresa Oficina Silva").name == "investigate"
    assert route("pesquise oficinas pequenas em Campinas").name == "search"


def test_parse_criteria_size_variants():
    assert parse_criteria("empresas de pequeno porte").size == "pequena"
    assert parse_criteria("empresas médias").size == "média"
