"""Explainable local qualification. Sources are claims, never verified business needs."""
from datetime import timedelta
import ipaddress
import re
from urllib.parse import urlsplit
from analysis.signal_detector import SignalDetector
from analysis.opportunity_analyzer import OpportunityAnalyzer, RULES
from utils.normalization import normalize_text
from utils.timeutils import utcnow, parse_iso

VERSION = 'commercial-1'
LABELS = {'high':'Alta', 'moderate':'Moderada', 'low':'Baixa', 'insufficient':'Dados insuficientes'}


def public_url(value):
    try:
        parsed=urlsplit(value or '')
        host=(parsed.hostname or '').lower().rstrip('.')
        if parsed.scheme not in ('http','https') or parsed.username or parsed.password or not host or '.' not in host: return False
        if host.endswith(('.local','.localhost')) or host=='localhost': return False
        try: return ipaddress.ip_address(host).is_global
        except ValueError: return True
    except ValueError: return False


def matches(value, options):
    value=normalize_text(value or '')
    return any(normalize_text(option) in value for option in options) if value else False


def evaluate(company, observations, profile, now=None):
    now=now or utcnow()
    facts, usable, seen, gaps = [], [], set(), []
    for obs in observations:
        key=(obs.url,normalize_text(obs.text))
        if key in seen: continue
        seen.add(key)
        try: date=parse_iso(obs.retrieved_at) if obs.retrieved_at else None
        except (ValueError,TypeError,OverflowError): date=None
        fresh=bool(date and now-timedelta(days=profile['fresh_days'])<=date<=now)
        eligible=bool(public_url(obs.url) and obs.text.strip() and obs.source_name and fresh)
        facts.append({'id':len(facts)+1,'text':obs.text,'url':obs.url,'source':obs.source_name,
                      'checked_at':obs.retrieved_at,'eligible':eligible})
        if eligible: usable.append(obs)
    if len(usable)<len(facts): gaps.append('Há fontes sem URL pública, sem data válida ou antigas; não pontuam.')
    if not usable: gaps.append('Faltam observações públicas recentes com URL e data.')
    if not profile['services']: gaps.append('Configure serviços realmente oferecidos pela software house.')
    signals=[s for s in SignalDetector().detect(company,usable) if s.source_url]
    # A failed lookup is a gap in our knowledge, not a missing business feature.
    signals=[s for s in signals if not (s.type in ('digital_gap','ecommerce') and
             re.search(r'(?:site|loja virtual) nao identificad',normalize_text(s.evidence)))]
    # Existing online channels contradict a claim that that channel is absent.
    text=' '.join(normalize_text(o.text) for o in usable)
    contrary=[]
    for pattern,types,label in [
        (r'\b(?:oferece|possui|tem|acesse|use)\s+(?:nosso\s+)?agendamento online',{'scheduling'},'Fonte indica agendamento online existente.'),
        (r'\b(?:oferece|possui|tem|acesse|use)\s+(?:nossa\s+)?loja virtual',{'ecommerce'},'Fonte indica loja virtual existente.')]:
        positive=any(not re.search(r'\b(?:nao|sem)\b[^.!?;]*$',text[max(0,m.start()-30):m.start()]) for m in re.finditer(pattern,text))
        if positive:
            contrary.append(label)
            signals=[s for s in signals if s.type not in types and not (s.type=='digital_gap' and ('agendamento' in normalize_text(s.evidence) or 'loja virtual' in normalize_text(s.evidence)))]
    hypotheses=OpportunityAnalyzer(profile['services']).analyze(company,signals)
    recommendations=[]
    relevant=set()
    for hypothesis in hypotheses:
        rule=next(r for r in RULES if r.solution==hypothesis.solution)
        offered=[service for service in profile['services'] if any(matches(service,[kw]) or matches(kw,[service]) for kw in rule.service_keywords)]
        scope=' '.join([rule.solution]+offered)
        if matches(scope,profile['excluded_projects']):
            contrary.append('Projeto excluído pelo perfil: '+rule.solution); continue
        if profile['accepted_projects'] and not matches(scope,profile['accepted_projects']):
            contrary.append('Projeto fora dos tipos aceitos: '+rule.solution); continue
        involved=[s for s in signals if s.type in rule.primary|rule.supporting]
        relevant.update(s.type for s in involved)
        refs=[f['id'] for f in facts if f['eligible'] and any(s.source_url==f['url'] and s.evidence==f['text'] for s in involved)]
        recommendations.append({'solution':rule.solution,'services':offered,'evidence_ids':refs,
            'motivation':list(dict.fromkeys(s.description for s in involved)),
            'next_action':'Confirmar o processo atual e a pertinência desta solução antes de propor projeto.',
            'hypothesis':'Pode haver aderência; necessidade e interesse não confirmados.',
            'question':'Como esse processo funciona hoje e existe alguma dificuldade que valha resolver?'})
    factors=[]
    def factor(key,ratio,reason):
        factors.append({'criterion':key,'points':int(profile['weights'][key]*ratio),
                        'maximum':profile['weights'][key],'reason':reason})
    factor('service_fit',bool(recommendations),'Compatibilidade entre serviços configurados e hipóteses sustentadas por fontes.' if recommendations else 'Nenhuma hipótese compatível sustentada.')
    factor('evidence',min(len(relevant)/3,1),'Tipos distintos de sinal relevantes: '+(', '.join(sorted(relevant)) or 'nenhum')+'. Repetição não aumenta pontos.')
    factor('digital_features',bool(relevant & {'digital_gap','ecommerce','manual_process'}),'Só lacunas/processos explicitamente descritos na fonte; ausência de cadastro não é falha digital.')
    factor('segment',matches(company.segment,profile['priority_segments']),'Comparação com segmento do cadastro e prioridades configuradas; não confirma necessidade.')
    fit=(int(matches(company.location,profile['priority_locations']))+int(matches(company.estimated_size,profile['company_sizes'])))/2
    factor('customer_profile',fit,'Localidade e porte cadastrado comparados às preferências; porte pode ser estimado.')
    factor('information_quality',bool(usable),'Existência de fonte pública com data recente; não garante veracidade nem atividade atual.')
    phone=re.sub(r'\D','',company.phone or '')
    contact=bool(len(phone)>=8 and any(phone in re.sub(r'\D','',o.text) for o in usable))
    factor('public_contact',contact,'Telefone cadastrado encontrado em observação pública recente.' if contact else 'Contato comercial público não confirmado nas observações.')
    for field in ('segment','city','estimated_size'):
        if not getattr(company,field): gaps.append('Dado não informado: '+field)
    gaps.append('Orçamento, urgência, interesse, poder de decisão e necessidade ainda precisam ser validados.')
    if profile['technologies']:
        gaps.append('Validar requisitos técnicos frente às tecnologias configuradas; nenhuma stack do lead foi presumida.')
    score=sum(f['points'] for f in factors)
    cap=100; reason=''
    insufficient=not usable or not profile['services']
    if insufficient or not recommendations:
        cap=profile['thresholds']['moderate']-1; reason='Sem evidência suficiente ou oportunidade compatível, não classificar como moderada/alta.'
    elif len(relevant)<2:
        cap=profile['thresholds']['high']-1; reason='Alta exige ao menos dois tipos distintos de sinal relevante.'
    adjustments=[]
    if score>cap: adjustments.append({'points':cap-score,'reason':reason}); score=cap
    category='insufficient' if insufficient else 'high' if score>=profile['thresholds']['high'] else 'moderate' if score>=profile['thresholds']['moderate'] else 'low'
    action='Validar as hipóteses e revisar um rascunho antes de qualquer contato.' if recommendations and not insufficient else 'Complementar fontes públicas e conferir o perfil antes de abordar.'
    return {'engine_version':VERSION,'company':{'id':company.id,'name':company.name,'segment':company.segment,'location':company.location},
            'score':score,'category':category,'factors':factors,'adjustments':adjustments,'negative_factors':contrary,
            'facts':facts,'recommendations':recommendations,'gaps':gaps,'next_action':action,'profile':profile}
