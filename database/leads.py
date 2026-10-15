"""Commercial operations on companies: one database, no separate lead copy."""
import csv
import io
import json
import os
from pathlib import Path
import tempfile
import uuid
from analysis.scoring import opportunity_score
from database.repositories import SignalRepository, HypothesisRepository
from utils.normalization import normalize_name, normalize_city, normalize_phone
from utils.timeutils import now_iso

STAGES = {'new': 'Novo lead', 'qualified': 'Qualificado', 'contact_pending': 'Contato pendente',
          'contacted': 'Contatado', 'negotiating': 'Em negociação', 'converted': 'Convertido', 'discarded': 'Descartado'}
EDITABLE = {'phone', 'segment', 'city', 'address', 'description'}
ACTIONS = {'response': 'Resposta recebida', 'next': 'Próxima ação', 'note': 'Observação'}


class LeadRepository:
    def __init__(self, db):
        self.db = db

    def resolve(self, identity):
        rows = self.db.query('SELECT * FROM companies WHERE id=? OR id LIKE ?', (identity, identity + '%'))
        if len(rows) != 1 or not identity or any(c not in '0123456789abcdef' for c in identity):
            raise ValueError('ID ausente, ambíguo ou inválido. Consulte /leads e use o ID completo.')
        return dict(rows[0])

    def event(self, identity, kind, detail):
        self.db.execute('INSERT INTO lead_events(company_id,kind,detail,created_at) VALUES(?,?,?,?)',
                        (identity, kind, detail, now_iso()))

    def events(self, identity):
        return [dict(r) for r in self.db.query('SELECT kind,detail,created_at FROM lead_events WHERE company_id=? ORDER BY id', (identity,))]

    def list(self, query='', stage=None, city=None, segment=None, archived=False, saved=False, offset=0,
             min_score=None, category=None, order='name'):
        if min_score is not None and (type(min_score) is not int or not 0<=min_score<=100): raise ValueError('min_score: 0 a 100.')
        if category is not None and category not in ('high','moderate','low','insufficient'): raise ValueError('Categoria inválida.')
        if order not in ('name','score'): raise ValueError('Ordem inválida.')
        clauses, args = ['archived=?'], [int(archived)]
        if stage:
            if stage not in STAGES: raise ValueError('Estágio inválido: ' + ', '.join(STAGES))
            clauses.append('commercial_status=?'); args.append(stage)
        if query:
            clauses.append('instr(normalized_name,?) > 0'); args.append(normalize_name(query))
        if city:
            clauses.append('city_key=?'); args.append(normalize_city(city))
        if saved: clauses.append('id IN (SELECT company_id FROM saved_companies)')
        rows = [dict(r) for r in self.db.query('SELECT companies.*, '
            '(SELECT score FROM lead_evaluations e WHERE e.company_id=companies.id ORDER BY e.id DESC LIMIT 1) AS qualification_score, '
            '(SELECT category FROM lead_evaluations e WHERE e.company_id=companies.id ORDER BY e.id DESC LIMIT 1) AS qualification_category '
            'FROM companies WHERE ' + ' AND '.join(clauses) + ' ORDER BY name,id', args)]
        if segment: rows = [r for r in rows if normalize_name(segment) in normalize_name(r['segment'])]
        if min_score is not None: rows=[r for r in rows if r['qualification_score'] is not None and r['qualification_score']>=min_score]
        if category: rows=[r for r in rows if r['qualification_category']==category]
        if order=='score': rows.sort(key=lambda r: (-(r['qualification_score'] if r['qualification_score'] is not None else -1),r['name'],r['id']))
        return rows[offset:offset+50]

    def stage(self, identity, value):
        row = self.resolve(identity)
        if value not in STAGES: raise ValueError('Estágios: ' + ', '.join(STAGES))
        if row['commercial_status'] == value: return
        with self.db.transaction():
            self.db.execute('UPDATE companies SET commercial_status=?,updated_at=? WHERE id=?', (value,now_iso(),row['id']))
            legacy={'contacted':'CONTACTED','converted':'CLIENT','discarded':'DISCARDED'}.get(value)
            if legacy:
                self.db.execute('UPDATE companies SET status=? WHERE id=?', (legacy,row['id']))
            elif row['status'] in ('CONTACTED','CLIENT','DISCARDED'):
                self.db.execute("UPDATE companies SET status=? WHERE id=?", ('RESEARCHED' if row['investigated'] else 'NEW',row['id']))
            self.event(row['id'], 'stage', row['commercial_status'] + ' → ' + value)
            # Discard is also respected by the existing research pipeline.
            if value == 'discarded':
                self.db.execute('INSERT OR REPLACE INTO ignored_companies VALUES(?,?,?)', (row['id'],'Descartado pelo usuário',now_iso()))
            elif row['commercial_status'] == 'discarded':
                self.db.execute('DELETE FROM ignored_companies WHERE company_id=?', (row['id'],))
                self.db.execute("UPDATE companies SET status='RESEARCHED' WHERE id=? AND status='DISCARDED'", (row['id'],))

    def edit(self, identity, field, value):
        if field not in EDITABLE | {'notes'}: raise ValueError('Campos editáveis: ' + ', '.join(sorted(EDITABLE | {'notes'})))
        if not isinstance(value,str) or len(value)>2000 or '\x00' in value: raise ValueError('Valor inválido; máximo de 2.000 caracteres.')
        row = self.resolve(identity)
        if row[field] == value: return
        with self.db.transaction():
            self.db.execute(f'UPDATE companies SET {field}=?,updated_at=? WHERE id=?', (value,now_iso(),row['id']))
            if field in ('city','phone'):
                key, normalized = ('city_key',normalize_city(value)) if field=='city' else ('phone_key',normalize_phone(value))
                self.db.execute(f'UPDATE companies SET {key}=? WHERE id=?', (normalized,row['id']))
            self.event(row['id'], 'edit', json.dumps({'field':field,'before':row[field],'after':value},ensure_ascii=False))

    def archive(self, identity, archived=True):
        row=self.resolve(identity)
        if bool(row['archived']) == archived: return
        with self.db.transaction():
            self.db.execute('UPDATE companies SET archived=?,updated_at=? WHERE id=?', (int(archived),now_iso(),row['id']))
            self.event(row['id'], 'archived' if archived else 'restored', 'Arquivado' if archived else 'Restaurado')

    def duplicates(self, identity):
        return [dict(r) for r in self.db.query('SELECT company_id,other_id,reason FROM duplicate_candidates WHERE company_id=? OR other_id=?', (identity,identity))]

    def flag_possible_duplicates(self, profile):
        from utils.deduplication import possible_duplicate
        from database.repositories import _to_profile
        # Conservative review only; never merges fuzzy candidates here.
        for row in self.db.query('SELECT * FROM companies WHERE id!=? AND (city_key IS ? OR normalized_name=?)',
                                 (profile.id,normalize_city(profile.city),normalize_name(profile.name))):
            other=_to_profile(row)
            if possible_duplicate(profile,other):
                a,b=sorted((profile.id,other.id))
                self.db.execute('INSERT OR IGNORE INTO duplicate_candidates VALUES(?,?,?,?)', (a,b,'Nome semelhante; identidade não confirmada',now_iso()))

    def detail(self, identity):
        row=self.resolve(identity)
        # Explicit export allowlist: configuration and conversation tables never enter.
        data={k:row[k] for k in ('id','name','normalized_name','website','domain','segment','city','state','address','phone','description','commercial_status','notes','archived','first_seen','updated_at','last_researched')}
        data['social_profiles']=json.loads(row['social_profiles'] or '{}')
        data['legacy_signal_score']=opportunity_score(SignalRepository(self.db).list_for_company(row['id']))
        from analysis.commercial import CommercialService
        data['evaluations']=[CommercialService.unpack(r) for r in self.db.query('SELECT * FROM lead_evaluations WHERE company_id=? ORDER BY id DESC',(row['id'],))]
        data['score']=data['evaluations'][0]['score'] if data['evaluations'] else None
        data['drafts']=[dict(r) for r in self.db.query('SELECT id,evaluation_id,format,body,created_at FROM commercial_drafts WHERE company_id=? ORDER BY id',(row['id'],))]
        data['opportunities']=[{'solution':h.solution,'reasons':h.reasons,'evidence_level':h.evidence_level} for h in HypothesisRepository(self.db).list_for_company(row['id'])]
        data['sources']=[dict(r) for r in self.db.query('SELECT source_name,url,text,retrieved_at FROM source_history WHERE company_id=? ORDER BY id', (row['id'],))]
        data['research_runs']=[dict(r) for r in self.db.query('SELECT r.id,r.query,r.started_at,r.finished_at,r.status,r.error_message FROM research_runs r JOIN run_companies rc ON rc.run_id=r.id WHERE rc.company_id=? ORDER BY r.id', (row['id'],))]
        data['events']=self.events(row['id'])
        data['possible_duplicates']=self.duplicates(row['id'])
        return data

    def export(self, format, identities, directory):
        if format not in ('csv','json'): raise ValueError('Formato: csv ou json.')
        if not identities: raise ValueError('Selecione os IDs para exportar; não há seleção implícita de todos.')
        ids=list(dict.fromkeys(self.resolve(i)['id'] for i in identities))
        rows=[self.detail(i) for i in ids]
        if format=='json': text=json.dumps(rows,ensure_ascii=False,indent=2)
        else:
            stream=io.StringIO(newline='')
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
            writer.writeheader()
            for row in rows:
                cooked={}
                for key,value in row.items():
                    value=json.dumps(value,ensure_ascii=False) if isinstance(value,(dict,list)) else '' if value is None else str(value)
                    # Prevent spreadsheet formula execution, including leading spaces.
                    cooked[key]="'"+value if value.lstrip().startswith(('=','+','-','@')) else value
                writer.writerow(cooked)
            text=stream.getvalue()
        root=Path(directory); root.mkdir(parents=True,exist_ok=True)
        target=root/('leads_'+uuid.uuid4().hex+'.'+format)
        fd,temporary=tempfile.mkstemp(prefix='.export-',dir=root)
        try:
            with os.fdopen(fd,'w',encoding='utf-8-sig' if format=='csv' else 'utf-8',newline='') as output:
                output.write(text); output.flush(); os.fsync(output.fileno())
            os.replace(temporary,target)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)
        return target
