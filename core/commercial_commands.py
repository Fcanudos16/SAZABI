"""Commercial intelligence in the existing slash terminal, without automatic outreach."""
import json
import sqlite3
from analysis.commercial import CommercialService, ai_prompt
from analysis.commercial_profile import load, update
from analysis.qualification import LABELS
from database.leads import LeadRepository
from skills.base import SkillResult

COMMANDS={'profile':'Ver perfil; set campo item;item para editar',
          'qualify':'Qualificar ID [--refresh] localmente',
          'evaluations':'Histórico de avaliações: ID [número]',
          'draft':'Prévia de abordagem: ID email|message|call',
          'draft-save':'Salvar o último rascunho revisado, sem enviar',
          'drafts':'Consultar rascunhos salvos: ID',
          'qualify-ai':'Preparar resumo para LAYLA: ID [summary|compare|questions|draft]'}


def render(result):
    lines=[f"Avaliação #{result['id']} · {result['company']['name']} · {result['evaluated_at']}",
           f"Qualificação: {result['score']}/100 — {LABELS[result['category']]} (não é probabilidade de venda)",
           'Critérios:']
    lines.extend(f"{f['criterion']}: {f['points']}/{f['maximum']} — {f['reason']}" for f in result['factors'])
    lines.extend(f"Ajuste {a['points']}: {a['reason']}" for a in result['adjustments'])
    lines.extend('Fator contrário: '+n for n in result['negative_factors'])
    lines.append('Fatos relatados pelas fontes (não são necessidades confirmadas):')
    lines.extend(f"[{f['id']}] {f['text']} | {f['url'] or 'sem URL'} | {f['checked_at'] or 'sem data'} | {'utilizada' if f['eligible'] else 'não pontua'}" for f in result['facts'])
    for r in result['recommendations']:
        lines.append(f"Hipótese: {r['solution']} · serviços: {', '.join(r['services'])} · fontes {r['evidence_ids']}\nMotivo: {'; '.join(r['motivation'])}\n{r['hypothesis']} {r['question']}\nPróxima ação: {r['next_action']}")
    lines.extend('Lacuna: '+g for g in result['gaps'])
    lines.extend(['Próxima ação: '+result['next_action'],'Recalcular: /qualify '+result['company']['id']+' --refresh'])
    return '\n'.join(lines)


class CommercialCommands:
    def __init__(self,agent):
        self.agent=agent
        self.service=CommercialService(agent.db,agent.config)

    def execute(self,name,args):
        try: return self._execute(name,args)
        except (ValueError,IndexError) as exc:
            return SkillResult(False,'commercial','failed',str(exc) or 'Argumentos inválidos. /'+name+' — '+COMMANDS[name])
        except (sqlite3.Error,OSError):
            return SkillResult(False,'commercial','failed','Não foi possível ler/gravar os dados locais. Confira acesso e espaço; tente novamente.')

    def _execute(self,name,args):
        message=''; data={}
        if name=='draft': self.agent._commercial_draft=None
        if name=='profile':
            if args:
                action,field,values=args.split(None,2)
                if action!='set': raise ValueError('Use /profile set campo item;item. - limpa a lista.')
                update(self.agent.config,field,[] if values=='-' else [s.strip() for s in values.split(';')])
            message='Perfil comercial local:\n'+json.dumps(load(self.agent.config),ensure_ascii=False,indent=2)+'\nPesos e limites: edite commercial_profile.json. Avaliações anteriores são preservadas.'
        elif name=='draft-save':
            if args: raise ValueError('Use /draft-save sem argumentos.')
            draft=getattr(self.agent,'_commercial_draft',None)
            if not draft: raise ValueError('Gere e revise primeiro: /draft ID email|message|call.')
            self.service.save_draft(draft)
            self.agent._commercial_draft=None
            message='Rascunho salvo localmente. Nenhuma mensagem enviada.'
        else:
            parts=args.split()
            row=LeadRepository(self.agent.db).resolve(parts[0])
            identity=row['id']
            if name=='qualify':
                if len(parts)>2 or len(parts)==2 and parts[1]!='--refresh': raise ValueError('Use /qualify ID [--refresh].')
                message=render(self.service.qualify(identity,refresh=len(parts)==2))
            elif name=='evaluations':
                if len(parts)>2: raise ValueError('Use /evaluations ID [número].')
                history=self.service.history(identity)
                if len(parts)==2:
                    selected=next((r for r in history if str(r['id'])==parts[1]),None)
                    if not selected: raise ValueError('Avaliação não encontrada para este lead.')
                    message=render(selected)
                else:
                    message='Histórico imutável de avaliações:\n'+'\n'.join(f"#{r['id']} | {r['evaluated_at']} | {r['score']}/100 | {LABELS[r['category']]}" for r in history)
                    message+='\nDetalhes: /evaluations ID número. Perfil e fontes originais também constam da exportação JSON.'
            elif name=='draft':
                self.agent._commercial_draft=None
                if len(parts)!=2: raise ValueError('Use /draft ID email|message|call.')
                draft=self.service.draft(identity,parts[1]); self.agent._commercial_draft=draft
                message=draft['body']+'\n\nSalvar após revisão: /draft-save. A prévia ainda não foi salva.'
            elif name=='drafts':
                if len(parts)!=1: raise ValueError('Use /drafts ID.')
                drafts=self.agent.db.query('SELECT * FROM commercial_drafts WHERE company_id=? ORDER BY id DESC',(identity,))
                message='Rascunhos locais (nenhum envio automático):\n'+'\n\n'.join(f"#{r['id']} | {r['format']} | {r['created_at']}\n{r['body']}" for r in drafts)
            elif name=='qualify-ai':
                if len(parts)>2: raise ValueError('Use /qualify-ai ID [summary|compare|questions|draft].')
                result=self.service.qualify(identity)
                prompt=ai_prompt(result,parts[1] if len(parts)==2 else 'summary')
                message='Revise o resumo no terminal LAYLA antes de clicar Enviar. A LAYLA pode utilizar serviços pagos. A resposta não altera a pontuação nem é salva como fato.\n\n'+prompt
                data={'action':'open_ai','draft':prompt}
        return SkillResult(True,'commercial','completed',message,data)
