"""Small terminal operations backed by the existing company records."""
import shlex
import json
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
    'overview': 'Visão geral comercial e próximas ações',
    'tasks': 'Listar tarefas: [ID|vencidas|todas]',
    'task': 'Criar tarefa: ID AAAA-MM-DD título | descrição opcional',
    'taskdone': 'Concluir tarefa: número', 'taskreopen': 'Reabrir tarefa: número',
    'taskedit': 'Corrigir tarefa: número AAAA-MM-DD título | descrição',
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
        if name in ('overview','tasks','task','taskdone','taskreopen','taskedit'):
            return 'Use /'+name+' — '+COMMANDS[name]+'. Datas no calendário local; vencida somente após o dia previsto.'
        return {'leads':'Use /leads [texto] [status=new] [cidade="São Paulo"] [segmento=clínica] [min_score=20] [max_score=70] [categoria=high] [desde=2026-01-01] [ate=2026-12-31] [vencidas] [insuficientes] [ordem=name|score|discovered|updated|next] [salvos] [arquivados] [pagina=1].',
                'lead':'Use /lead ID (ID único exibido em /leads).',
                'stage':'Use /stage ID ' + '|'.join(STAGES)+' [motivo opcional]',
                'note':'Use /note ID texto; use - para limpar.',
                'edit':'Use /edit ID phone|segment|city|address|description valor; - limpa.',
                'action':'Use /action ID response|next|note texto para histórico. Para próxima ação com prazo: /task ID AAAA-MM-DD título.',
                'archive':'Use /archive ID e confirme sim/não.', 'restore':'Use /restore ID.',
                'export':'Use /export csv|json ID,ID. Exporta somente os IDs informados.'}[name]

    def _execute(self,name,args):
        if name=='overview':
            if args.strip(): raise ValueError
            data=self.leads.overview()
            lines=[f"VISÃO GERAL · {data['total']} leads não arquivados (não significa clientes)"]
            lines.extend(f'{STAGES[key]}: {count}' for key,count in data['stages'].items())
            lines.append(f"Tarefas vencidas: {data['overdue']}")
            lines.append('Próximas ações:')
            lines.extend(self.task_lines(data['upcoming']))
            lines.append('Prioridade por última avaliação salva (revisar evidências):')
            lines.extend(f"{r['id']} | {r['name']} | {r['qualification_score']}/100 | {STAGES[r['commercial_status']]}" for r in data['priority'])
            lines.append('Leads: /leads · Pendências: /tasks vencidas · Detalhes: /lead ID')
            return '\n'.join(lines),'completed'
        if name=='tasks':
            option=args.strip()
            rows=self.leads.tasks(identity=option if option not in ('','todas','vencidas') else None,
                                  include_completed=option=='todas',overdue=option=='vencidas')
            return '\n'.join(['Tarefas comerciais (datas locais):']+self.task_lines(rows)+['Criar: /task ID AAAA-MM-DD título | descrição · Concluir: /taskdone número · Reabrir: /taskreopen número']),'completed'
        if name in ('taskdone','taskreopen'):
            number=int(args.strip())
            if not 0<number<2**63: raise ValueError
            self.leads.change_task(number,completed=name=='taskdone')
            return 'Tarefa atualizada.\n'+self._execute('overview','')[0],'completed'
        if name in ('task','taskedit'):
            identity,due,title=args.split(None,2)
            title,_,description=title.partition('|')
            if name=='task': number=self.leads.create_task(identity,title.strip(),due,description.strip())
            else:
                number=int(identity)
                if not 0<number<2**63: raise ValueError
                self.leads.change_task(number,title=title.strip(),due_date=due,description=description.strip())
            return f'Tarefa #{number} salva.\n'+self._execute('overview','')[0],'completed'
        if name=='leads':
            options,terms={},[]
            for part in shlex.split(args):
                if part in ('salvos','arquivados','vencidas','insuficientes'):
                    options[{'salvos':'saved','arquivados':'archived','vencidas':'overdue','insuficientes':'insufficient'}[part]]=True
                elif '=' in part:
                    key,value=part.split('=',1)
                    if key=='pagina':
                        if not value.isdigit() or int(value)<1: raise ValueError
                        options['offset']=(int(value)-1)*50
                    elif key in ('min_score','max_score'): options[key]=int(value)
                    elif key in ('desde','ate'): options['discovered_from' if key=='desde' else 'discovered_to']=value
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
                lines.append(f"  {row['segment'] or 'Segmento desconhecido'} | {row['website'] or 'Site desconhecido'} | Verificação: {row['last_researched'] or 'Não realizada'}")
                lines.append(f"  Próxima ação: {row['next_action'] or 'Não definida'} | Prazo: {row['next_date'] or 'Não definido'}")
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
                if last.get('search_brief'):
                    from analysis.search_brief import detail_text
                    lines += ['Análise comercial do /search', detail_text(last['search_brief'])]
                lines.append(f"Última avaliação salva: {last['score']}/100 — {LABELS[last['category']]} · {last['evaluated_at']}")
            lines.append('Qualificar/revalidar: /qualify '+identity+' · Justificativa e histórico: /evaluations '+identity)
            if data['evaluations']:
                lines.append('Justificativa da pontuação:')
                lines.extend(f"{f['criterion']}: {f['points']}/{f['maximum']} — {f['reason']}" for f in data['evaluations'][0]['factors'])
            lines.append('Campos verificados/editados pelo usuário (fontes originais preservadas abaixo):')
            lines.extend(f"{field}: {value['value']} · {value['verified_at']}" for field,value in data['manual_fields'].items())
            lines.append('Tarefas e acompanhamento:')
            lines.extend(self.task_lines(data['tasks']))
            lines.extend(f"Tarefa #{t['id']} criada em {t['created_at']} · Concluída em {t['completed_at'] or 'Não concluída'}" for t in data['tasks'])
            lines.extend('Hipótese: '+h['solution']+' — '+h['evidence_level'] for h in data['opportunities'])
            lines.append('Fontes (últimas 20; exportação contém o histórico completo):')
            lines.extend(f"{s['retrieved_at']} | {s['source_name']} | {s['url'] or 'URL não informada'} | {s['text']}" for s in data['sources'][-20:])
            lines.append('Pesquisas: '+', '.join(f"#{r['id']} ({r['status']})" for r in data['research_runs']))
            lines.append('Histórico comercial (últimas 20 ações):')
            lines.extend(self.event_line(e) for e in data['events'][-20:])
            lines.extend('Possível duplicação — revisar, sem fusão automática: '+d['company_id']+' / '+d['other_id'] for d in data['possible_duplicates'])
            return '\n'.join(lines),'completed'
        if name=='archive':
            if rest: raise ValueError
            self.agent._pending=dict(type='archive',company_id=identity,name=row['name'])
            return f"Arquivar {row['name']}? Histórico será preservado. Confirma? (sim/não)",'needs_confirmation'
        if name=='restore':
            if rest: raise ValueError
            self.leads.archive(identity,False)
        elif name=='stage':
            value,_,reason=rest.partition(' ')
            self.leads.stage(identity,value,reason.strip())
        elif name=='note':
            if not rest: raise ValueError
            self.leads.edit(identity,'notes','' if rest=='-' else rest)
        elif name=='edit':
            field,value=rest.split(None,1)
            self.leads.edit(identity,field,'' if value=='-' else value)
        elif name=='action':
            kind,text=rest.split(None,1)
            if kind not in ACTIONS or not text.strip(): raise ValueError
            self.leads.validate_text(text)
            self.leads.event(identity,kind,text)
        return 'Lead atualizado: '+row['name']+'. Consulte /lead '+identity+'\n'+self._execute('overview','')[0],'completed'

    @staticmethod
    def event_line(event):
        detail=event['detail']
        if event['kind'] in ('task_edited','task_completed','task_reopened','edit'):
            try:
                value=json.loads(detail)
                if event['kind']=='edit':
                    detail=f"Campo manual: {value['field']} · {str(value['before'])[:120]} → {str(value['after'])[:120]}"
                else:
                    after=value['after']
                    detail=f"Tarefa #{value['id']} · {after['title']} · Prazo: {after['due_date']}"
            except (ValueError,KeyError,TypeError): pass
        return f"{event['created_at']} | {event['kind']} | {detail}"

    @staticmethod
    def task_lines(rows):
        from datetime import date
        return [f"#{t['id']} | {t['company_name']} | {t['due_date']} | " +
                ('Concluída' if t['completed'] else 'VENCIDA' if t['due_date']<date.today().isoformat() else 'Pendente')+
                f" | {t['title']}"+(' — '+t['description'] if t['description'] else '') for t in rows] or ['Nenhuma tarefa.']
