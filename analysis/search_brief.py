"""Commercial presentation derived from the existing immutable evaluation, without AI calls."""
import re
from urllib.parse import urlsplit
from utils.normalization import normalize_text

SOLUTIONS = {
    'automação de processos internos': ('Automação de processos', 'Automatizar a etapa manual descrita, começando por uma tarefa e validando o resultado com a equipe.'),
    'possível integração entre ferramentas observadas': ('Integração entre plataformas', 'Avaliar a troca de dados entre as ferramentas citadas antes de propor uma integração.'),
    'sistema de agendamento online': ('Sistema personalizado', 'Organizar horários e solicitações de agendamento em um fluxo adequado ao atendimento existente.'),
    'automação de atendimento (WhatsApp)': ('Automação de processos', 'Avaliar uma automação pontual para organizar solicitações de atendimento, mantendo revisão humana.'),
    'sistema de gestão centralizado': ('Sistema personalizado', 'Diagnosticar quais informações precisam ser organizadas entre as operações antes de definir um sistema.'),
    'site / presença digital': ('Desenvolvimento de site', 'Organizar as informações e os canais públicos da empresa em um site.'),
    'e-commerce / loja virtual': ('Sistema personalizado', 'Avaliar um catálogo com pedidos online adequado à operação descrita.'),
}


def host(url):
    return (urlsplit(url or '').hostname or '').removeprefix('www.')


def qualification_gaps(company, criteria):
    gaps = []
    for field, actual in [('city', company.city), ('state', company.state),
                          ('segment', company.segment), ('size', company.estimated_size)]:
        requested = normalize_text(getattr(criteria, field, None))
        value = normalize_text(actual)
        if requested and (not value or (requested not in value if field == 'segment' else requested != value)):
            gaps.append(f'{field}: critério solicitado não confirmado ({getattr(criteria, field)}).')
    if not company.name or not company.website:
        gaps.append('Identidade/site oficial ainda não confirmado.')
    return gaps


def matches_need(need, brief):
    if not need: return True
    text=normalize_text(' '.join(e['text'] for e in brief['evidence'])+' '+brief['solution'])
    patterns={'automacao': r'automa|controle manual|preenchimento manual',
              'processos manuais': r'controle manual|preenchimento manual|(?:usamos|utilizamos|controlamos).{0,50}planilhas',
              'software/sistemas': r'software|sistema'}
    normalized=normalize_text(need)
    return bool(re.search(patterns.get(normalized,re.escape(normalized)),text))


def build_brief(company, result):
    """No extra collection; duplicate claims never multiply evidence strength."""
    recommendations = result['recommendations']
    # Prefer a small automation over a broad management system for the same process.
    rec = next((r for r in recommendations if r['solution'] == 'automação de processos internos'),
               recommendations[0] if recommendations else None)
    evidence, seen = [], set()
    for fact in result['facts']:
        if not rec or fact['id'] not in rec['evidence_ids'] or not fact['eligible']:
            continue
        text = normalize_text(fact['text'])
        if text in seen:
            continue
        seen.add(text)
        official = bool(host(company.website) and host(company.website) == host(fact['url']))
        hiring = bool(re.search(r'\bvaga|contratando|contratacao', text))
        negated = bool(re.search(r'\b(?:nao|sem|deixamos de|deixou de)\b', text))
        direct = official and not hiring and not negated and bool(re.search(
            r'\b(?:precisamos|necessitamos|buscamos)\s+(?:de\s+)?(?:um[a]?\s+)?(?:sistema|automatizar|integrar|software|automacao)|'
            r'\b(?:enfrentamos|temos)\s+(?:dificuldades|problemas)\s+(?:para|com).{0,35}(?:sistemas|integracao|controle manual|automatizar)', text))
        concrete = not negated and bool(re.search(r'controle manual|preenchimento manual|(?:usamos|utilizamos|controlamos).{0,50}planilhas|integrac\w*.{0,30}sistemas', text))
        strength = 'Direta' if direct else 'Indireta' if concrete or hiring else 'Fraca'
        evidence.append(dict(fact, strength=strength, origin='Site da empresa' if official else fact['source'],
                             published_at=None, reliability='Fonte primária; declaração não auditada' if official else 'Origem externa; requer confirmação',
                             limitation='Vaga não é pedido de contratação de fornecedores.' if hiring else
                             'A declaração não comprova orçamento ou intenção de contratar.' if direct else
                             'O sinal não confirma necessidade nem inexistência de sistemas internos.'))
    rank = {'Direta': 3, 'Indireta': 2, 'Fraca': 1}
    evidence.sort(key=lambda f: -rank[f['strength']])
    evidence = evidence[:3]
    quality = evidence[0]['strength'] if evidence else 'Insuficiente'
    situation = {'Direta': 'Necessidade identificada', 'Indireta': 'Oportunidade provável'}.get(quality, 'Hipótese de prospecção')
    solution = rec['solution'] if rec and evidence else ''
    category, practical = SOLUTIONS.get(solution, ('Consultoria técnica ou diagnóstico', 'Reunir informações públicas antes de propor uma solução.'))
    summary = (f'{company.name} relata uma necessidade relacionada a {solution}; o escopo precisa ser validado.' if quality == 'Direta' else
               f'{company.name} pode se beneficiar de {solution}; é preciso confirmar o processo atual.' if solution else
               'A necessidade específica não pôde ser determinada com as informações disponíveis.')
    phone = re.sub(r'\D', '', company.phone or '')
    contact = len(phone) >= 8 and any(f['eligible'] and phone in re.sub(r'\D', '', f['text']) for f in result['facts'])
    values = {'Direta': (35, 25, 10), 'Indireta': (20, 18, 6), 'Fraca': (8, 8, 2), 'Insuficiente': (0, 0, 0)}[quality]
    factors = [dict(criterion=key, points=points, maximum=maximum, reason=reason) for key, points, maximum, reason in [
        ('Força das evidências', values[0], 35, quality + '; repetição de fontes não soma pontos.'),
        ('Clareza da oportunidade', values[1], 25, solution or 'Necessidade específica não determinada.'),
        ('Compatibilidade com a equipe', 20 if solution else 0, 20, ', '.join(rec['services']) if solution else 'Sem solução compatível sustentada.'),
        ('Relevância comercial', values[2], 10, 'Validar escopo, orçamento e interesse; não são conhecidos.'),
        ('Facilidade de validação', 10 if contact else 0, 10, 'Telefone publicado na fonte.' if contact else 'Canal comercial não confirmado.')]]
    raw = sum(f['points'] for f in factors)
    score = min(raw, 44) if quality in ('Fraca', 'Insuficiente') else raw
    priority = 'Alta' if score >= 75 else 'Média' if score >= 45 else 'Baixa'
    explanation = ('Necessidade documentada e solução compatível; validar escopo e interesse.' if priority == 'Alta' else
                   'Sinais relevantes; confirmar a necessidade antes de investir mais tempo.' if priority == 'Média' else
                   'Poucas evidências de uma necessidade específica; complementar a investigação.')
    outreach = ''
    if solution and quality in ('Direta', 'Indireta'):
        outreach = (f'Olá, equipe da {company.name}! Na página pública de vocês encontramos esta informação: '
                    f'“{evidence[0]["text"][:260]}”. Trabalhamos com {", ".join(rec["services"])}. '
                    f'Uma possibilidade a avaliar é {solution}. Como esse processo funciona hoje e há alguma dificuldade que valha conversar?')
    return dict(company_id=company.id, name=company.name, website=company.website, summary=summary,
                need=summary, situation=situation, evidence_quality=quality, evidence=evidence,
                signals=[dict(s, interpretation=s['description'], solution=solution,
                              evidence_ids=[e['id'] for e in evidence if e['url']==s['url'] and e['text']==s['evidence']])
                         for s in result.get('commercial_signals', [])
                         if any(e['url']==s['url'] and e['text']==s['evidence'] for e in evidence)],
                solution=solution, solution_category=category, help=practical,
                score=score, priority=priority, factors=factors, adjustment=score-raw,
                priority_reason=explanation, outreach=outreach,
                investigation_state='analyzed' if evidence else 'insufficient',
                checked_at=company.last_researched, limitations=result['gaps']+result['negative_factors'])


def detail_text(brief):
    lines = ['O que essa empresa pode precisar', brief['need'], 'Como nossa software house pode ajudar', brief['help'],
             'Por que essa oportunidade foi identificada']
    lines += [s['interpretation'] for s in brief['signals']] or ['Não foram encontrados sinais concretos suficientes.']
    lines += ['Sinais e evidências encontrados']
    for e in brief['evidence']:
        lines += [e['text'], f"{e['strength']} · {e['origin']} · {e['reliability']}",
                  f"Consulta: {e['checked_at']} · publicação: {e['published_at'] or 'não informada'}", e['url'], e['limitation']]
    lines += ['Solução sugerida', brief.get('solution_category','') + ': ' + (brief['solution'] or 'Ainda não determinada.'), 'Justificativa da prioridade', brief['priority_reason']]
    lines += [f"{f['criterion']}: {f['points']}/{f['maximum']} — {f['reason']}" for f in brief['factors']]
    if brief['adjustment']: lines += [f"Proteção por evidência fraca: {brief['adjustment']} pontos."]
    lines += ['Pontuação organizacional; não é probabilidade de contratação.', 'Como iniciar o contato',
              brief['outreach'] or 'Ainda faltam elementos para personalizar o contato.', 'Limitações'] + brief['limitations']
    return '\n'.join(lines)
