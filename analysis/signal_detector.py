"""Detecção determinística de sinais (regras sobre observações). Sem IA.

Cada regra liga um padrão (aplicado ao texto sem acentos/minúsculo) a um tipo de
sinal. O FATO é a observação; a INFERÊNCIA é a descrição do sinal.
Para adicionar um sinal novo: inclua o tipo em database/models.py e uma SignalRule aqui.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence

from database.models import CompanyProfile, Observation, Signal
from utils.normalization import normalize_text
from utils.timeutils import now_iso

NUM_WORDS = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5,
             "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10}
_NUM = r"(?P<n>\d+|" + "|".join(NUM_WORDS) + r")"


@dataclass(frozen=True)
class SignalRule:
    type: str
    pattern: str
    description: str
    confidence: str
    min_count: int = 0          # se > 0, o grupo 'n' do padrão precisa ser >= min_count


RULES: Sequence[SignalRule] = (
    SignalRule('manual_process', r'\b(?:precisamos|necessitamos|buscamos)\s+(?:de\s+)?(?:um[a]?\s+)?(?:automatizar|automacao)',
               'Necessidade de software ou automação declarada; validar escopo', 'high'),
    SignalRule('operational_complexity', r'\b(?:precisamos|necessitamos|buscamos)\s+(?:de\s+)?(?:um[a]?\s+)?(?:sistema|software)',
               'Necessidade de sistema declarada; validar finalidade e escopo', 'high'),
    SignalRule('digital_tools', r'(?:integrar|integracao|integracoes).{0,40}(?:sistemas|plataformas|ferramentas)',
               'Integração mencionada publicamente; contratação externa não confirmada', 'moderate'),
    SignalRule("multiple_locations", _NUM + r"\s+(?:unidades|filiais|lojas|sedes)\b",
               "Possível operação em múltiplas unidades", "high", min_count=2),
    SignalRule("operational_complexity",
               _NUM + r"\s+(?:dentistas|profissionais|especialistas|mecanicos|instrutores|funcionarios|colaboradores)\b",
               "Equipe grande, o que pode indicar operação mais complexa", "moderate", min_count=4),
    SignalRule("scheduling",
               r"agend\w*.{0,40}(?:whatsapp|telefone)|(?:whatsapp|telefone).{0,40}agend\w*|reserva\w*.{0,30}whatsapp",
               "Agendamento via WhatsApp/telefone; trabalho manual não confirmado", "moderate"),
    SignalRule("customer_service",
               r"atendimento.{0,40}whatsapp|whatsapp.{0,40}atendimento|orcamento\w*.{0,30}whatsapp|vendas?\s+(?:pelo|via|por)\s+whatsapp",
               "Atendimento aparentemente realizado via WhatsApp", "moderate"),
    SignalRule("hiring", r"\bvagas?\s+(?:abertas|disponiveis|para)\b|estamos contratando",
               "Empresa divulga vagas (possível necessidade operacional)", "low"),
    SignalRule("new_unit", r"(?:em breve|abriremos|inauguraremos).{0,40}(?:unidade|loja)|abertura de (?:uma )?nova unidade",
               "Possível expansão com nova unidade", "moderate"),
    SignalRule("growth", r"estamos (?:em expansao|crescendo|ampliando)|plano de expansao",
               "Possível fase de crescimento", "moderate"),
    SignalRule("manual_process",
               r"planilhas?|\bpapel\b|preenchimento manual|presencialmente|documentos por e-?mail|controle manual",
               "Possível processo manual", "moderate"),
    SignalRule("digital_gap",
               r"nao (?:possui|tem|apresenta|oferece|ha) (?:site|agendamento online|sistema de agendamento)"
               r"|site nao identificado|\bsem site\b|apenas (?:em )?(?:pdf|diretorio\w*)",
               "Possível lacuna de presença ou serviços digitais", "low"),
    SignalRule("ecommerce",
               r"sem loja virtual|nao possui loja virtual|loja virtual nao identificada",
               "Possível ausência de canal de e-commerce", "moderate"),
)


def _to_int(value: str) -> int:
    return int(value) if value.isdigit() else NUM_WORDS.get(value, 0)


def existing_online_channels(observations):
    found = set()
    for observation in observations:
        text = normalize_text(observation.text)
        for kind, pattern in (
            ('scheduling', r'(?:\b(?:oferece|possui|tem|acesse|use)\s+(?:nosso\s+)?|^sistema de\s+)agendamento online'),
            ('ecommerce', r'\b(?:oferece|possui|tem|acesse|use)\s+(?:nossa\s+)?loja virtual')):
            if any(not re.search(r'\b(?:nao|sem)\b[^.!?;]*$',text[max(0,m.start()-30):m.start()])
                   for m in re.finditer(pattern,text)):
                found.add(kind)
    return found


class SignalDetector:
    def __init__(self, rules: Sequence[SignalRule] = RULES):
        self.rules = rules

    def detect(self, profile: CompanyProfile, observations: Sequence[Observation]) -> List[Signal]:
        now = now_iso()
        signals: List[Signal] = []
        seen = set()
        for obs in observations:
            text = normalize_text(obs.text)
            for rule in self.rules:
                m = re.search(rule.pattern, text)
                if not m:
                    continue
                if rule.type not in ('digital_gap', 'ecommerce'):
                    prefix = text[max(0, m.start() - 55):m.start()]
                    if re.search(r'\b(?:nao|sem|deixou de|deixamos de)\b[^.!?;]*$', prefix):
                        continue
                if rule.min_count and _to_int(m.group("n")) < rule.min_count:
                    continue
                key = (rule.type, text)
                if key in seen:
                    continue
                seen.add(key)
                signals.append(Signal(company_id=profile.id, type=rule.type, description=rule.description,
                                      evidence=obs.text, source=obs.source_name, source_url=obs.url,
                                      detected_at=now, confidence=rule.confidence))
        have = {s.type for s in signals}
        if "multiple_locations" not in have and profile.units and profile.units >= 2:
            signals.append(Signal(company_id=profile.id, type="multiple_locations",
                                  description="Possível operação em múltiplas unidades",
                                  evidence=f"Número de unidades informado no cadastro: {profile.units}",
                                  source="Cadastro da empresa", detected_at=now, confidence="moderate"))
        if "digital_gap" not in have and not profile.website:
            signals.append(Signal(company_id=profile.id, type="digital_gap",
                                  description="Possível lacuna de presença digital",
                                  evidence="Site oficial não identificado nas fontes consultadas",
                                  source="Fontes consultadas", detected_at=now, confidence="low"))
        existing = existing_online_channels(observations)
        for obs in observations:
            text=normalize_text(obs.text)
            tools=[name for name in ('whatsapp','shopify','woocommerce','salesforce','hubspot','bling','tiny','omie')
                   if re.search(r'\b'+name+r'\b',text)]
            if len(tools)>=2 and re.search(r'\b(?:usamos|utilizamos|atendemos|vendemos|pedidos|atendimento)\b',text) and not re.search(r'\b(?:nao|sem)\b',text):
                signals.append(Signal(company_id=profile.id,type='digital_tools',description='Ferramentas/canais citados: '+', '.join(tools)+'; integração atual desconhecida',evidence=obs.text,source=obs.source_name,source_url=obs.url,detected_at=now,confidence='low'))
        return [signal for signal in signals if signal.type not in existing]
