"""Validated local commercial profile; no external calls and no invented capabilities."""
import json
import os
from pathlib import Path
import tempfile

LIST_FIELDS = ('services','technologies','accepted_projects','priority_segments','priority_locations',
               'company_sizes','excluded_projects','differentiators')
WEIGHTS = {'service_fit':25,'evidence':25,'digital_features':10,'segment':10,'customer_profile':10,
           'information_quality':15,'public_contact':5}
DEFAULT_PATH = Path(__file__).resolve().parents[1] / 'commercial_profile.json'


def validate(profile):
    if not isinstance(profile,dict): raise ValueError('Perfil comercial inválido.')
    if set(profile) != set(LIST_FIELDS) | {'weights','thresholds','fresh_days'}:
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
    if field not in LIST_FIELDS: raise ValueError('Campo editável: '+', '.join(LIST_FIELDS))
    path=Path(config.commercial_profile_path)
    try: raw=json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError,ValueError): raise ValueError('Não foi possível ler o perfil comercial.') from None
    raw[field]=values
    validate(raw)
    descriptor,temporary=tempfile.mkstemp(prefix='.commercial-',dir=path.parent)
    try:
        with os.fdopen(descriptor,'w',encoding='utf-8') as output:
            json.dump(raw,output,ensure_ascii=False,indent=2);output.write('\n');output.flush();os.fsync(output.fileno())
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)
    return load(config)
