"""Validated local commercial profile; no external calls and no invented capabilities."""
import json
import os
from pathlib import Path
import tempfile

LIST_FIELDS = ('services','technologies','accepted_projects','priority_segments','priority_locations',
               'company_sizes','excluded_projects','differentiators','automation_processes',
               'project_complexity','interesting_traits','excluded_segments','exclusion_terms')
WEIGHTS = {'service_fit':25,'evidence':25,'digital_features':10,'segment':10,'customer_profile':10,
           'information_quality':15,'public_contact':5}
DEFAULT_PATH = Path(__file__).resolve().parents[1] / 'commercial_profile.json'


def validate(profile):
    if not isinstance(profile,dict): raise ValueError('Perfil comercial inválido.')
    from analysis.strategies import defaults, SIGNALS
    for field in LIST_FIELDS[8:]: profile.setdefault(field,[])
    profile.setdefault('strategies',defaults())
    profile.setdefault('segment_rules',{})
    if set(profile) != set(LIST_FIELDS) | {'weights','thresholds','fresh_days','strategies','segment_rules'}:
        raise ValueError('Campos do perfil comercial inválidos ou ausentes.')
    for field in LIST_FIELDS:
        values=profile[field]
        if field=='services' and values is None: continue
        if not isinstance(values,list) or len(values)>50 or any(not isinstance(v,str) or not v.strip() or len(v)>200 or any(ord(c)<32 for c in v) for v in values):
            raise ValueError('Lista inválida no perfil: '+field)
    weights=profile['weights']
    if not isinstance(weights,dict) or set(weights)!=set(WEIGHTS) or any(type(v) is not int or not 0<=v<=100 for v in weights.values()) or sum(weights.values())!=100:
        raise ValueError('Os pesos inteiros precisam somar 100.')
    limits=profile['thresholds']
    if not isinstance(limits,dict) or set(limits)!={'moderate','high'} or any(type(v) is not int for v in limits.values()) or not 1<=limits['moderate']<limits['high']<=100:
        raise ValueError('Limites inválidos: 1 <= moderate < high <= 100.')
    if type(profile['fresh_days']) is not int or not 1<=profile['fresh_days']<=3650:
        raise ValueError('fresh_days deve estar entre 1 e 3650.')
    strategies=profile['strategies']
    if not isinstance(strategies,dict) or len(strategies)>30: raise ValueError('Estratégias inválidas.')
    import re
    required=set(next(iter(defaults().values())))
    for key,value in strategies.items():
        if not re.fullmatch('[a-z][a-z0-9_]{0,39}',key) or not isinstance(value,dict) or set(value)!=required:
            raise ValueError('Estratégia inválida: '+key)
        if type(value['enabled']) is not bool: raise ValueError('enabled deve ser booleano.')
        for field in ('objective','evidence','limits'):
            if not isinstance(value[field],str) or not value[field].strip() or len(value[field])>1000: raise ValueError('Descrição inválida.')
        for field in ('services','triggers','segments','signals','query_terms','excluded_terms','sources'):
            items=value[field]
            if not isinstance(items,list) or len(items)>50 or any(not isinstance(v,str) or not v.strip() or len(v)>200 or any(ord(c)<32 for c in v) for v in items): raise ValueError('Lista inválida: '+field)
        if not set(value['signals'])<=SIGNALS or not value['sources'] or not value['services']: raise ValueError('Sinais/fontes/serviços inválidos.')
        if set(value['sources'])-{'site público da empresa','descoberta Tavily'}: raise ValueError('Fonte não integrada. Use site público da empresa ou descoberta Tavily.')
        if type(value['min_signals']) is not int or not 1<=value['min_signals']<=10: raise ValueError('min_signals: 1 a 10.')
    rules=profile['segment_rules']
    if not isinstance(rules,dict) or len(rules)>50: raise ValueError('Regras por segmento inválidas.')
    for key,value in rules.items():
        if not key.strip() or len(key)>200 or not isinstance(value,dict) or set(value)-{'strategy','signals','excluded_terms','min_signals'}: raise ValueError('Regra de segmento inválida.')
        if 'strategy' in value and value['strategy'] not in strategies: raise ValueError('Estratégia desconhecida na regra.')
        for field in ('signals','excluded_terms'):
            if field in value and (not isinstance(value[field],list) or any(not isinstance(v,str) or not v.strip() or len(v)>200 for v in value[field])): raise ValueError('Lista inválida na regra.')
        if not set(value.get('signals',[]))<=SIGNALS: raise ValueError('Sinal desconhecido.')
        if type(value.get('min_signals',1)) is not int or not 1<=value.get('min_signals',1)<=10: raise ValueError('min_signals inválido.')
    return profile


def load(config):
    try:
        path=Path(config.commercial_profile_path)
        if path.stat().st_size>100_000: raise ValueError
        profile=validate(json.loads(path.read_text(encoding='utf-8-sig')))
    except (OSError,ValueError,TypeError):
        raise ValueError('Perfil comercial indisponível ou inválido. Revise commercial_profile.json; nenhum perfil foi inventado.') from None
    if profile['services'] is None:
        profile['services']=list(config.services)
    return validate(profile)


def update(config, field, values):
    if field not in LIST_FIELDS+('weights','thresholds','fresh_days','strategies','segment_rules'): raise ValueError('Campo editável desconhecido.')
    path=Path(config.commercial_profile_path)
    try: raw=json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError,ValueError): raise ValueError('Não foi possível ler o perfil comercial.') from None
    raw[field]=values
    validate(raw)
    if len(json.dumps(raw,ensure_ascii=False,indent=2).encode('utf-8'))>99_000:
        raise ValueError('Perfil excede o limite de tamanho.')
    descriptor,temporary=tempfile.mkstemp(prefix='.commercial-',dir=path.parent)
    try:
        with os.fdopen(descriptor,'w',encoding='utf-8') as output:
            json.dump(raw,output,ensure_ascii=False,indent=2);output.write('\n');output.flush();os.fsync(output.fileno())
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)
    return load(config)
