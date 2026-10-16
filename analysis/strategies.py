"""Declarative strategies over the existing search and evidence pipeline."""
from copy import deepcopy
from dataclasses import asdict, replace
import re
from utils.normalization import normalize_text


def defaults():
    rows = [
        ('digital','Presença digital',['site','sistemas web','presença digital','e-commerce'],['site','digital','e-commerce'],['digital_gap','ecommerce']),
        ('manual','Possíveis processos manuais',['automação','sistemas internos'],['automação','manual','agendamento','pedidos'],['manual_process','scheduling','customer_service']),
        ('integration','Possibilidades de integração',['integrações'],['integração','ferramentas','canais'],['digital_tools']),
        ('custom','Sistemas personalizados',['sistemas web','sistemas internos','sistemas de gestão','dashboards','painéis','aplicativos','aplicações'],['sistema','gestão','aplicativo'],['multiple_locations','operational_complexity','manual_process','growth','new_unit','hiring']),
    ]
    return {key:dict(enabled=True,objective=objective,services=services,triggers=triggers,
                    segments=[],signals=signals,query_terms=[],excluded_terms=[],min_signals=1,
                    sources=['site público da empresa'],
                    evidence='Observação explícita com URL e data recente; necessidade permanece hipótese.',
                    limits='Não inferir necessidade pelo segmento, estética, ausência de resultado ou tecnologia presumida.')
            for key,objective,services,triggers,signals in rows}


SIGNALS={'digital_gap','ecommerce','manual_process','scheduling','customer_service','digital_tools',
         'multiple_locations','operational_complexity','growth','hiring','new_unit'}


def contains(text, values):
    text=normalize_text(text or '')
    return any(normalize_text(value) in text for value in values)


def applicable(strategy, services):
    return any(contains(service,strategy['services']) for service in services)


def segment_rule(profile, segment):
    return next((value for key,value in profile.get('segment_rules',{}).items()
                 if normalize_text(key)==normalize_text(segment or '')), {})


def plan(profile, criteria, query, explicit=None):
    criteria=replace(criteria)
    original=asdict(criteria)
    applied=[]
    if normalize_text(criteria.segment or '') in ('empresas','negocios','leads'):
        criteria.segment=None
    for field,key in [('segment','priority_segments'),('city','priority_locations'),('size','company_sizes')]:
        if not getattr(criteria,field) and profile[key]:
            # Unknown free-text segments must not be replaced by a priority.
            if field=='segment' and query.strip() and not re.fullmatch(r'(?:empresas|negocios|negócios|leads)(?:\s+em\s+.+)?',query.strip(),re.I):
                continue
            setattr(criteria,field,profile[key][0]);applied.append(f'{field}: {profile[key][0]}')
    rule=segment_rule(profile,criteria.segment)
    strategies=profile['strategies']
    chosen=explicit or rule.get('strategy')
    eligible={key:value for key,value in strategies.items() if value['enabled'] and applicable(value,profile['services'])
              and (not value['segments'] or contains(criteria.segment,value['segments']))}
    if explicit and explicit not in eligible:
        raise ValueError('Estratégia inexistente, desativada ou incompatível com serviços/segmento. Consulte /strategies.')
    if chosen not in eligible:
        chosen=next((key for key,value in eligible.items() if contains(query,value['triggers'])),None)
    if not chosen:
        chosen=next((key for key,value in eligible.items() if contains(' '.join(profile.get('automation_processes',[])),value['triggers'])),None)
    if not chosen:
        chosen='custom' if 'custom' in eligible else next(iter(eligible),None)
    strategy=deepcopy(eligible[chosen]) if chosen else None
    if strategy and not criteria.need and strategy['query_terms']:
        criteria.need=' '.join(strategy['query_terms']);applied.append('Termos da estratégia: '+criteria.need)
    return criteria,dict(strategy_id=chosen,strategy=strategy,segment_rule=deepcopy(rule),
        original=original,effective=asdict(criteria),applied=applied,profile=deepcopy(profile),
        limitation='Critérios orientam a busca; não comprovam características ou necessidades das empresas.')


def evidence_policy(profile, company, signals, context=None):
    """Filter actual observed signals; never manufacture a missing observation."""
    rule=segment_rule(profile,company.segment)
    strategies=profile.get('strategies',defaults())
    if context is not None:
        selected=[context['strategy']] if context.get('strategy') else []
    else:
        selected=[s for s in strategies.values() if s['enabled'] and applicable(s,profile['services'])
                  and (not s['segments'] or contains(company.segment,s['segments']))]
    qualified=[s for s in selected if len({signal.type for signal in signals if signal.type in s['signals']})>=s['min_signals']]
    allowed=set().union(*(set(s['signals']) for s in qualified)) if qualified else set()
    if rule.get('signals'): allowed &= set(rule['signals'])
    filtered=[s for s in signals if s.type in allowed]
    required=rule.get('min_signals',1)
    exclusions=profile.get('excluded_segments',[])
    excluded=contains(company.segment,exclusions)
    terms=profile.get('exclusion_terms',[])+rule.get('excluded_terms',[])
    terms+=sum((s['excluded_terms'] for s in selected),[])
    excluded |= contains(' '.join([company.name or '',company.segment or '',company.description or '']),terms)
    reasons=[]
    if excluded: reasons.append('Lead excluído pelos critérios comerciais configurados.');filtered=[]
    if len({s.type for s in filtered})<required:
        reasons.append(f'Estratégia exige {required} tipos de sinal observados; evidência insuficiente.');filtered=[]
    if selected and not qualified: reasons.append('O mínimo de sinais das estratégias selecionadas não foi atingido.')
    if not selected: reasons.append('Nenhuma estratégia ativa compatível com os serviços; pesquisa apenas exploratória.')
    return filtered,reasons
