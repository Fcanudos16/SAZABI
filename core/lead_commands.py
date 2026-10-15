"""Small terminal operations backed by the existing company records."""
import shlex
import sqlite3
from pathlib import Path
from database.leads import LeadRepository, STAGES, ACTIONS
from skills.base import SkillResult

COMMANDS = {
    'leads': 'Listar e filtrar leads locais', 'lead': 'Detalhes e histórico de um ID',
    'stage': 'Alterar estágio: ID estágio', 'note': 'Editar observações: ID texto',
    'edit': 'Editar dado público: ID campo valor', 'action': 'Registrar ação: ID response|next|note texto',
    'archive': 'Arquivar ID com confirmação', 'restore': 'Restaurar ID arquivado',
    'export': 'Exportar csv|json ID,ID (seleção explícita)',
}


class LeadCommands:
    def __init__(self, agent):
        self.agent=agent
        self.leads=LeadRepository(agent.db)

    def execute(self, name, arguments):
        try:
            message, status=self._execute(name,arguments)
            return SkillResult(True,'leads',status,message)
        except (ValueError,IndexError):
            return SkillResult(False,'leads','failed', 'Dados inválidos. ' + self.usage(name))
        except sqlite3.Error:
            return SkillResult(False,'leads','failed','Não foi possível acessar ou gravar o banco local. Ele pode estar bloqueado ou sem espaço. Nenhuma operação incompleta foi confirmada; tente novamente.')
        except OSError:
            return SkillResult(False,'leads','failed','Não foi possível gravar a exportação. Confira espaço e permissão da pasta; tente novamente.')

    def usage(self,name):
        return {'leads':'Use /leads [texto] [status=new] [cidade="São Paulo"] [segmento=clínica] [min_score=70] [categoria=high] [ordem=score] [salvos] [arquivados] [pagina=1].',
                'lead':'Use /lead ID (ID único exibido em /leads).',
                'stage':'Use /stage ID ' + '|'.join(STAGES),
                'note':'Use /note ID texto; use - para limpar.',
                'edit':'Use /edit ID phone|segment|city|address|description valor; - limpa.',
                'action':'Use /action ID response|next|note texto.',
                'archive':'Use /archive ID e confirme sim/não.', 'restore':'Use /restore ID.',
                'export':'Use /export csv|json ID,ID. Exporta somente os IDs informados.'}[name]

    def _execute(self,name,args):
        if name=='leads':
            options,terms={},[]
            for part in shlex.split(args):
                if part in ('salvos','arquivados'): options['saved' if part=='salvos' else 'archived']=True
                elif '=' in part:
                    key,value=part.split('=',1)
                    if key=='pagina':
                        if not value.isdigit() or int(value)<1: raise ValueError
                        options['offset']=(int(value)-1)*50
                    elif key=='min_score': options['min_score']=int(value)
                    elif key=='categoria': options['category']=value
                    elif key=='ordem': options['order']=value
                    elif key in ('status','cidade','segmento'):
                        options[{'status':'stage','cidade':'city','segmento':'segment'}[key]]=value
                    else: raise ValueError
                else: terms.append(part)
            rows=self.leads.list(query=' '.join(terms),**options)
            lines=['Leads locais — até 50 por página; use pagina=2 para continuar.']
            for row in rows:
                duplicates=self.leads.duplicates(row['id'])
                lines.append(f"{row['id']} | {row['name']} | {STAGES[row['commercial_status']]} | {row['city'] or 'Localidade não informada'}" + (' | possível duplicação: revisar /lead' if duplicates else ''))
                if row['qualification_score'] is not None:
                    from analysis.qualification import LABELS
                    lines.append(f"  Última avaliação salva: {row['qualification_score']}/100 — {LABELS[row['qualification_category']]}; /qualify ID revalida.")
            if not rows: lines.append('Nenhum lead corresponde aos filtros.')
            lines.append('Detalhes: /lead ID · Estágio: /stage ID estágio · Notas: /note ID texto\nSalvar: /save ID · Arquivar: /archive ID · Exportar: /export csv|json ID,ID')
            return '\n'.join(lines),'completed'
        if name=='export':
            parts=args.split()
            if len(parts)!=2: raise ValueError
            directory=Path(self.agent.db.path).resolve().parent/'exports' if self.agent.db.path!=':memory:' else Path(__file__).resolve().parents[1]/'data'/'exports'
            path=self.leads.export(parts[0],parts[1].split(','),directory)
            return 'Exportação local concluída: '+str(path),'completed'
        parts=args.split(None,1)
        row=self.leads.resolve(parts[0])
        identity=row['id']
        rest=parts[1] if len(parts)>1 else ''
        if name=='lead':
            if rest: raise ValueError
            data=self.leads.detail(identity)
            lines=[f"Lead: {row['name']}\nID: {identity}\nEstágio: {STAGES[row['commercial_status']]} · Arquivado: {'sim' if row['archived'] else 'não'}"]
            for field,label in [('website','Site'),('segment','Segmento'),('city','Cidade'),('phone','Contato comercial'),('address','Endereço'),('description','Descrição'),('notes','Observações'),('first_seen','Criado'),('updated_at','Atualizado'),('last_researched','Última verificação')]:
                lines.append(label+': '+str(row[field] or 'Não informado'))
            if data['evaluations']:
                from analysis.qualification import LABELS
                last=data['evaluations'][0]
                lines.append(f"Última avaliação salva: {last['score']}/100 — {LABELS[last['category']]} · {last['evaluated_at']}")
            lines.append('Qualificar/revalidar: /qualify '+identity+' · Histórico: /evaluations '+identity+' · Rascunho: /draft '+identity+' email')
            lines.extend('Hipótese: '+h['solution']+' — '+h['evidence_level'] for h in data['opportunities'])
            lines.append('Fontes (últimas 20; exportação contém o histórico completo):')
            lines.extend(f"{s['retrieved_at']} | {s['source_name']} | {s['url'] or 'URL não informada'} | {s['text']}" for s in data['sources'][-20:])
            lines.append('Pesquisas: '+', '.join(f"#{r['id']} ({r['status']})" for r in data['research_runs']))
            lines.append('Histórico comercial (últimas 20 ações):')
            lines.extend(f"{e['created_at']} | {e['kind']} | {e['detail']}" for e in data['events'][-20:])
            lines.extend('Possível duplicação — revisar, sem fusão automática: '+d['company_id']+' / '+d['other_id'] for d in data['possible_duplicates'])
            return '\n'.join(lines),'completed'
        if name=='archive':
            if rest: raise ValueError
            self.agent._pending=dict(type='archive',company_id=identity,name=row['name'])
            return f"Arquivar {row['name']}? Histórico será preservado. Confirma? (sim/não)",'needs_confirmation'
        if name=='restore':
            if rest: raise ValueError
            self.leads.archive(identity,False)
        elif name=='stage': self.leads.stage(identity,rest)
        elif name=='note':
            if not rest: raise ValueError
            self.leads.edit(identity,'notes','' if rest=='-' else rest)
        elif name=='edit':
            field,value=rest.split(None,1)
            self.leads.edit(identity,field,'' if value=='-' else value)
        elif name=='action':
            kind,text=rest.split(None,1)
            if kind not in ACTIONS or not text.strip(): raise ValueError
            self.leads.event(identity,kind,text)
        return 'Lead atualizado: '+row['name']+'. Consulte /lead '+identity,'completed'
