from analysis.evidence_manager import evidence_level
from analysis.opportunity_analyzer import OpportunityAnalyzer
from analysis.signal_detector import SignalDetector
from core.config import DEFAULT_SERVICES
from database.models import CompanyProfile, Observation, Signal
from utils.timeutils import now_iso


def obs(text):
    return Observation(text=text, source_name="Site oficial", url="https://x.example/")


def detect(texts, **profile_kwargs):
    profile = CompanyProfile(name="X", id="1", website="https://x.example", **profile_kwargs)
    return SignalDetector().detect(profile, [obs(t) for t in texts])


def types(signals):
    return {s.type for s in signals}


def test_detects_basic_signals_with_fact_and_source():
    signals = detect(["Agendamento de consultas via WhatsApp.", "Site lista duas unidades."])
    assert types(signals) == {"scheduling", "multiple_locations"}
    s = next(s for s in signals if s.type == "scheduling")
    assert s.evidence == "Agendamento de consultas via WhatsApp." and s.source == "Site oficial" and s.source_url


def test_number_thresholds():
    assert "multiple_locations" not in types(detect(["Possui uma unidade no centro."]))
    assert "operational_complexity" not in types(detect(["Equipe de 2 profissionais."]))
    assert "operational_complexity" in types(detect(["Equipe de 5 profissionais."]))


def test_no_observations_means_no_invented_signals():
    assert detect([]) == []


def test_missing_website_is_flagged_only_as_not_identified():
    profile = CompanyProfile(name="X", id="1")
    signals = SignalDetector().detect(profile, [])
    assert types(signals) == {"digital_gap"}
    assert "não identificado" in signals[0].evidence.lower()


def test_units_field_creates_signal_when_text_does_not():
    assert "multiple_locations" in types(detect([], units=3))


def test_duplicated_observation_does_not_duplicate_signal():
    assert len(detect(["Atendimento via WhatsApp.", "Atendimento via WhatsApp."])) == 1


def sig(t, c="moderate"):
    return Signal(t, "d", "e", "s", now_iso(), c, source_url='https://x.example/')


def test_evidence_levels():
    assert evidence_level([]) == "insuficiente"
    assert evidence_level([sig("hiring", "low")]) == "fraco"
    assert evidence_level([sig("scheduling"), sig("customer_service")]) == "moderado"
    many = [sig("scheduling"), sig("customer_service"), sig("manual_process"), sig("hiring", "high"), sig("growth")]
    assert evidence_level(many) == "forte"


def test_hypothesis_requires_primary_signal_and_uses_cautious_wording():
    analyzer = OpportunityAnalyzer(DEFAULT_SERVICES)
    profile = CompanyProfile(name="X", id="1")
    assert analyzer.analyze(profile, [sig("hiring", "low")]) == []         # só sinal de apoio
    hyps = analyzer.analyze(profile, [sig("scheduling"), sig("customer_service")])
    assert hyps[0].solution == "sistema de agendamento online" and hyps[0].evidence_level == "moderado"
    assert all("precisa" not in h.solution for h in hyps)


def test_hypotheses_respect_configured_services():
    profile = CompanyProfile(name="X", id="1")
    assert OpportunityAnalyzer(["consultoria"]).analyze(profile, [sig("scheduling")]) == []
    only_ecom = OpportunityAnalyzer(["e-commerce"]).analyze(profile, [sig("ecommerce"), sig("scheduling")])
    assert [h.solution for h in only_ecom] == ["e-commerce / loja virtual"]
