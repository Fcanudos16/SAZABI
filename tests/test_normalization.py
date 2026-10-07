from utils.normalization import (company_domain, normalize_domain, normalize_name, normalize_phone,
                                 normalize_text, title_case_pt)


def test_normalize_text_removes_accents_and_case():
    assert normalize_text("  Clínica   SÃO Paulo ") == "clinica sao paulo"


def test_normalize_name_strips_legal_suffix_only_at_end():
    assert normalize_name("Oficina Silva LTDA.") == "oficina silva"
    assert normalize_name("Me Ajuda Consultoria ME") == "me ajuda consultoria"


def test_domain_normalization():
    assert normalize_domain("https://www.OficinaSilva.com.br/contato") == "oficinasilva.com.br"
    assert normalize_domain("oficinasilva.com.br") == "oficinasilva.com.br"
    assert normalize_domain("sem-ponto") is None
    assert normalize_domain(None) is None


def test_social_networks_are_not_company_domains():
    assert company_domain("https://instagram.com/oficinasilva") is None
    assert company_domain("https://l.instagram.com/x") is None
    assert company_domain("https://oficinasilva.com.br") == "oficinasilva.com.br"


def test_phone_normalization():
    assert normalize_phone("(11) 4000-0001") == "1140000001"
    assert normalize_phone("+55 11 94000-0001") == "11940000001"
    assert normalize_phone("123") is None


def test_title_case_pt_keeps_prepositions_lower():
    assert title_case_pt("são josé dos campos") == "São José dos Campos"
