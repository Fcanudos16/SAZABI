"""Recompute metrics from the frozen real sample and explicit human-readable review.

No network or credentials. Labels refer to the captured sites, not independent
legal verification. Keep review decisions separate from automatic extraction.
"""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/phase5'
OUTPUT = ROOT / 'reports/phase5'

# Zero-based discovery index: name, location decision, evidence/reason.
REVIEW = {
    1: ('Policlínica São Paulo', 'outside', 'Endereço publicado em Beja, Portugal.'),
    2: ('Clínica São Paulo', 'outside', 'Endereço publicado em Mogi das Cruzes/SP.'),
    3: ('Clínica Dentária São Paulo', 'outside', 'Dois endereços publicados em Lisboa, Portugal.'),
    6: ('Centro Médico Doutor São Paulo', 'local', 'O site se apresenta como Doutor SP e declara atendimento à comunidade da Zona Leste de São Paulo; não é validação cadastral.'),
    7: ('Clínica da Cidade — Tatuapé', 'local', 'MedicalClinic/LocalBusiness declara São Paulo/SP; Organization genérica se refere à matriz em Campinas. A unidade é o alvo.'),
    8: ('Centro Médico Cirúrgico São Paulo', 'outside', 'Endereço publicado em Nova Iguaçu/RJ; a página apresenta problemas de codificação.'),
    9: ('Clínica São Francisco', 'local', 'Identidade no rodapé e endereços publicados em Pari/Tucuruvi, São Paulo; agendamento online já anunciado.'),
    10: ('Exame (publicador)', 'editorial', 'NewsArticle/NewsMediaOrganization. Artigo sobre outra empresa; o jornal não é uma oficina.'),
    12: ('Riveros Serviços Automotivos', 'local', 'AutoRepair declara São Paulo/SP. A página anuncia sistema de agendamento online, telefone e WhatsApp.'),
    13: ('Auto Mecânica do Vale', 'local', 'Nome e endereço publicados na Zona Oeste — São Paulo — SP; og:site_name longo prejudica extração.'),
    15: ('Stradale', 'local', 'Identidade do site e três endereços publicados em São Paulo/SP; múltiplas unidades não provam uma dor de gestão.'),
    17: ('High Torque', 'uncertain', 'Identidade própria observada; lista distritos/SP, mas o material capturado não explicita o município para essas unidades.'),
    20: ('Petlove / Petsupermarket', 'local', 'Corporation declara razão social e o site publica endereços de lojas em São Paulo/SP. Nenhuma necessidade comercial confirmada.'),
    22: ('Breeds Pet Shop', 'uncertain', 'Identidade própria e comércio online observados; lojas físicas em SP não distinguem estado de município.'),
    24: ('Pet Life', 'uncertain', 'Três unidades e ruas publicadas; município não explícito. Não inferir cidade apenas por nomes de bairros.'),
    25: ('Cobasi', 'uncertain', 'Schema declara São Paulo, Brasil, enquanto rodapé legal informa Barueri/SP. Matriz, unidade e cadastro legal precisam ser distinguidos.'),
    27: ('Bem Locão', 'local', 'Nome publicado no site; og:locality São Paulo, og:region SP e endereço General Ataliba Leonel, 1111. Falta identidade estruturada aceita pelo extrator.'),
}


def main():
    digest = hashlib.sha256((DATA/'capture.json').read_bytes()).hexdigest()
    if digest != '71afc22e5411d784f0d9ce13877c405d83bb97cbefcd2bbcc743b1942fc5ecd0':
        raise ValueError('A revisão por índice se aplica somente à captura original; revise a nova amostra.')
    capture = json.loads((DATA / 'capture.json').read_text(encoding='utf-8'))
    before = json.loads((DATA / 'baseline.json').read_text(encoding='utf-8'))
    after = json.loads((DATA / 'after-final.json').read_text(encoding='utf-8'))
    rows = []
    for segment, query in zip(('clínicas', 'oficinas', 'pet shops'), capture['queries']):
        for hit in query['hits']:
            index = len(rows)
            page = capture['pages'].get(hit['url'], {})
            name, decision, reason = REVIEW.get(index, ('Não confirmada', 'unavailable', page.get('error', 'Sem página capturada')))
            rows.append(dict(index=index, segment=segment, title=hit['title'], url=hit['url'],
                             checked_at=page.get('checked_at', query['checked_at']),
                             identity=name, decision=decision, reason=reason,
                             usable_source='page' in page,
                             identity_self_declared=decision not in ('unavailable', 'editorial'),
                             commercial_need_verified=False))
    decisions = Counter(row['decision'] for row in rows)
    total = len(rows)
    def metric(n, d=total):
        return {'numerator': n, 'denominator': d, 'percent': round(100*n/d, 2) if d else None}
    metrics = {
        'scope': 'Frozen real sample; manual review of captured self-declarations, not legal verification',
        'capture_started_at': capture['started_at'],
        'capture_sha256': digest,
        'results': total,
        'usable_pages': metric(sum(r['usable_source'] for r in rows)),
        'self_identified_businesses': metric(sum(r['identity_self_declared'] for r in rows)),
        'local_candidates_manual': metric(decisions['local']),
        'insufficient': metric(decisions['unavailable'] + decisions['uncertain']),
        'discarded': metric(decisions['outside'] + decisions['editorial']),
        'decisions': dict(decisions),
        'unique_discovery_urls': len({r['url'] for r in rows}),
        'duplicate_urls': metric(total-len({r['url'] for r in rows})),
        'automatic_companies_before': len(before['companies']),
        'automatic_companies_after': len(after['companies']),
        'companies_with_hypotheses': metric(sum(bool(c['qualification']['recommendations']) for c in after['companies']), len(after['companies'])),
        'commercial_need_verified': 0,
        'initial_live_seconds': [r['seconds'] for r in before['runs']],
        'initial_live_mean_seconds': sum(r['seconds'] for r in before['runs']) / len(before['runs']),
        'baseline_statuses': [r['skill_status'] for r in before['runs']],
        'corrected_statuses': [r['skill_status'] for r in after['runs'][:3]],
        'repeat_query': {k: after['runs'][-1]['run'][k] for k in ('found','new_count','known_count','duplicates')},
        'persistence': after['counts_after_reopen'],
        'source_errors': dict(Counter(capture['pages'][r['url']]['error'] for r in rows if not r['usable_source'])),
    }
    assert after['counts_after_reopen'] == after['counts_before_close']
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT/'review.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    (OUTPUT/'metrics.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
