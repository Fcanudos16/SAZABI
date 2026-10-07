from database.models import CompanyProfile
from research.company_finder import merge_profiles
from utils.deduplication import deduplicate, find_existing, is_same_company


def co(name, city="São Paulo", domain=None, phone=None, address=None):
    return CompanyProfile(name=name, city=city, domain=domain, phone=phone, address=address)


def test_same_domain_is_same_company():
    assert is_same_company(co("Oficina Silva", domain="oficinasilva.com.br"),
                           co("Oficina Silva Auto Center", domain="oficinasilva.com.br"))


def test_same_phone_is_same_company_even_with_different_name_and_format():
    assert is_same_company(co("Alpha", phone="(11) 4000-0001"), co("Clínica Alfa", phone="11 4000 0001"))


def test_name_subset_in_same_city_is_same_company():
    assert is_same_company(co("Oficina Silva"), co("Oficina Silva Auto Center"))


def test_different_city_is_not_same_company_by_name():
    assert not is_same_company(co("Oficina Silva", city="São Paulo"), co("Oficina Silva", city="Campinas"))


def test_different_businesses_with_same_surname_are_kept_apart():
    assert not is_same_company(co("Oficina Silva"), co("Restaurante Silva"))


def test_single_word_names_do_not_match_by_subset():
    assert not is_same_company(co("Alpha"), co("Alpha Odontologia Premium"))


def test_deduplicate_merges_missing_fields():
    a, b = co("Oficina Silva", domain="x.com.br"), co("Oficina Silva Auto Center", domain="x.com.br", phone="11 4000 0003")
    unique, dups = deduplicate([a, b], merge_profiles)
    assert dups == 1 and len(unique) == 1
    assert unique[0].phone == "11 4000 0003" and unique[0].name == "Oficina Silva"


def test_find_existing():
    known = [co("Clínica Beta", domain="beta.com.br")]
    assert find_existing(co("Beta Clínica", domain="beta.com.br"), known) is known[0]
    assert find_existing(co("Outra", domain="outra.com.br"), known) is None
