"""Fonte MOCK: empresas FICTÍCIAS para desenvolver e testar sem nenhuma API externa.

Nenhuma empresa, site, telefone ou endereço daqui é real.
"""
from __future__ import annotations

import copy
from typing import Dict, List, Optional

from database.models import CompanyProfile, Observation, RawCompany, SearchCriteria
from research.base import CompanySource
from utils.deduplication import is_same_company
from utils.normalization import company_domain, normalize_name, normalize_text

SITE, INSTA, DIR = "Site oficial (mock)", "Instagram público (mock)", "Diretório empresarial (mock)"


def _entry(name, city, segment, size, domain, phone, units, obs, instagram=None, address=None, state="SP"):
    return {
        "name": name, "city": city, "state": state, "segment": segment, "size": size,
        "domain": domain, "phone": phone, "units": units, "address": address,
        "instagram": instagram, "obs": obs,
    }


MOCK_DATA: List[Dict] = [
    # ---------------- São Paulo ----------------
    _entry("Clínica Alpha Odontologia", "São Paulo", "clínica odontológica", "pequena",
           "clinicaalpha.example", "(11) 4000-0001", 3, instagram="clinicaalpha",
           address="Rua Exemplo, 100 - Pinheiros", obs=[
               (SITE, "Site oficial lista 3 unidades: Pinheiros, Moema e Tatuapé."),
               (SITE, "Página de contato informa agendamento de consultas via WhatsApp."),
               (SITE, "Atendimento ao paciente divulgado via WhatsApp e telefone."),
               (SITE, "Site não apresenta agendamento online."),
               (SITE, "Equipe divulgada no site inclui mais de 12 dentistas."),
               (SITE, "Página 'Trabalhe conosco' lista vaga de recepcionista."),
           ]),
    _entry("Clinica Alpha", "São Paulo", "clínica odontológica", "pequena",
           "www.clinicaalpha.example", "11 4000-0001", None, instagram="clinicaalpha", obs=[
               (INSTA, "Perfil no Instagram divulga agendamento de consultas via WhatsApp."),
           ]),
    _entry("Clínica Sorriso Beta", "São Paulo", "clínica odontológica", "micro",
           "sorrisobeta.example", "(11) 4000-0002", 1, obs=[
               (SITE, "Site institucional apresenta apenas telefone e formulário de contato."),
               (SITE, "Agendamento de consultas somente por telefone."),
           ]),
    _entry("Oficina Silva", "São Paulo", "oficina mecânica", "pequena",
           "oficinasilva.example", "(11) 4000-0003", 2, instagram="oficinasilva", obs=[
               (INSTA, "Instagram da empresa divulga atendimento e orçamentos via WhatsApp."),
               (SITE, "Site lista duas unidades (Mooca e Santana)."),
               (SITE, "Serviços listados: mecânica geral, funilaria, elétrica e revisão."),
           ]),
    _entry("Oficina Silva Auto Center", "São Paulo", "oficina mecânica", "pequena",
           "oficinasilva.example", None, None, obs=[
               (INSTA, "Perfil no Instagram divulga agendamento de revisões via WhatsApp."),
           ]),
    _entry("Auto Mecânica Rápida Gama", "São Paulo", "oficina mecânica", "micro",
           None, "(11) 4000-0004", 1, instagram="mecanicagama", obs=[
               (DIR, "Empresa listada apenas em diretório e Instagram."),
           ]),
    _entry("Restaurante Beta", "São Paulo", "restaurante", "pequena",
           "restaurantebeta.example", "(11) 4000-0005", 1, instagram="restaurantebeta", obs=[
               (SITE, "Cardápio disponível apenas em PDF no site."),
               (SITE, "Reservas realizadas via WhatsApp, segundo a página de contato."),
               (INSTA, "Instagram anuncia inauguração de nova unidade."),
           ]),
    _entry("Academia Gamma Fit", "São Paulo", "academia", "média",
           "gammafit.example", "(11) 4000-0006", 1, instagram="gammafit", obs=[
               (SITE, "Matrícula realizada presencialmente, conforme o site."),
               (INSTA, "Perfil público divulga abertura de nova unidade em 2026."),
               (SITE, "Vaga de instrutor divulgada na página de contato."),
           ]),
    _entry("Startup Theta Tech", "São Paulo", "tecnologia (startup)", "micro",
           "thetatech.example", None, 1, obs=[
               (SITE, "Página de carreiras lista vaga para desenvolvedor."),
           ]),
    # ---------------- Campinas ----------------
    _entry("Clínica Vida Campinas", "Campinas", "clínica médica", "pequena",
           "clinicavida.example", "(19) 4000-0011", 1, obs=[
               (SITE, "Agendamento realizado por telefone e WhatsApp, segundo o site."),
           ]),
    _entry("Oficina Delta", "Campinas", "oficina mecânica", "micro",
           None, "(19) 4000-0012", 1, obs=[
               (DIR, "Presença pública encontrada apenas em diretório empresarial."),
           ]),
    _entry("Loja Casa Ômega", "Campinas", "loja de decoração", "pequena",
           "casaomega.example", "(19) 4000-0013", 1, instagram="casaomega", obs=[
               (SITE, "Loja física sem loja virtual identificada."),
               (INSTA, "Perfil divulga vendas pelo WhatsApp e Instagram."),
           ]),
    _entry("Salão Estilo Épsilon", "Campinas", "salão de beleza", "micro",
           None, "(19) 4000-0014", 1, instagram="estiloepsilon", obs=[
               (INSTA, "Agendamento feito via WhatsApp, segundo o perfil público."),
               (INSTA, "Equipe de 5 profissionais divulgada no Instagram."),
           ]),
    _entry("Escritório Contábil Zeta", "Campinas", "escritório contábil", "pequena",
           "contabilzeta.example", "(19) 4000-0015", 1, obs=[
               (SITE, "Site orienta o envio de documentos por e-mail e planilhas."),
           ]),
    _entry("Empresa Sigma", "Campinas", "serviços", None,
           None, "(19) 4000-0016", None, obs=[]),
]


def _social(entry: Dict) -> Dict[str, str]:
    profiles: Dict[str, str] = {}
    if entry["instagram"]:
        profiles["instagram"] = f"https://instagram.example/{entry['instagram']}"
        profiles["whatsapp"] = "https://wa.example/" + entry["instagram"]
    return profiles


def _raw(entry: Dict) -> RawCompany:
    website = f"https://{entry['domain']}" if entry["domain"] else None
    return RawCompany(
        name=entry["name"], city=entry["city"], state=entry["state"], country="Brasil",
        website=website, segment=entry["segment"], address=entry["address"], phone=entry["phone"],
        estimated_size=entry["size"], units=entry["units"], social_profiles=_social(entry),
        source_name="mock")


class MockSource(CompanySource):
    name = "mock"

    def __init__(self, data: Optional[List[Dict]] = None):
        self.data = data if data is not None else MOCK_DATA

    def search(self, criteria: SearchCriteria) -> List[RawCompany]:
        results = []
        for entry in self.data:
            if criteria.city and normalize_text(criteria.city) != normalize_text(entry["city"]):
                continue
            if criteria.segment and normalize_text(criteria.segment) not in normalize_text(entry["segment"]):
                continue
            if criteria.size and entry["size"] and normalize_text(criteria.size) != normalize_text(entry["size"]):
                continue
            results.append(_raw(entry))
        return copy.deepcopy(results)

    def fetch_observations(self, company: CompanyProfile) -> List[Observation]:
        observations: List[Observation] = []
        for entry in self.data:
            if not is_same_company(company, _raw(entry)):
                continue
            domain = company_domain(entry["domain"])
            urls = {
                SITE: f"https://{domain}/" if domain else None,
                INSTA: _social(entry).get("instagram"),
                DIR: "https://diretorio.example/empresas",
            }
            for source, text in entry["obs"]:
                observations.append(Observation(text=text, source_name=source, url=urls.get(source)))
        return observations

    def lookup(self, name: str) -> Optional[RawCompany]:
        key = normalize_name(name)
        if not key:
            return None
        exact = [e for e in self.data if normalize_name(e["name"]) == key]
        partial = [e for e in self.data if key in normalize_name(e["name"])]
        matches = exact or partial
        return copy.deepcopy(_raw(matches[0])) if matches else None
