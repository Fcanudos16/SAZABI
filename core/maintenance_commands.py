"""Explicit local maintenance commands; restoration happens with the app closed."""
import json
from pathlib import Path
import sqlite3
from core.maintenance import Maintenance
from skills.base import SkillResult

COMMANDS={'health':'Saúde operacional, sem expor credenciais','backup':'Criar backup SQLite validado',
          'backups':'Listar cópias locais e instruções de restauração','integrity':'Verificar integridade do SQLite',
          'maintenance':'Ver opções; set opção JSON; refresh-status ID; reset-refresh ID',
          'diagnostics':'Diagnóstico sanitizado no terminal (sem consultas ou dados de leads)'}


def execute(agent,name,args):
    service=Maintenance(agent)
    try:
        if name in ('health','diagnostics'):
            if args:raise ValueError('Use /'+name+' sem argumentos.')
            message=json.dumps(service.health(),ensure_ascii=False,indent=2)
            message+='\nConfiguração não comprova conectividade. LAYLA/Groq/Tavily são verificados nas operações explícitas existentes.'
        elif name=='backup':
            if args:raise ValueError('Use /backup sem argumentos.')
            message='Backup validado: '+service.backup()
        elif name=='backups':
            if args:raise ValueError('Use /backups sem argumentos.')
            message='Backups locais:\n'+'\n'.join(str(p) for p in service.backups())
            message+='\nPara restaurar: feche o SAZABI e execute scripts/restore_backup.py --db CAMINHO_DO_BANCO --backup COPIA_ESCOLHIDA. O utilitário pede confirmação e preserva uma cópia anterior em rescue.'
        elif name=='integrity':
            if args:raise ValueError('Use /integrity sem argumentos.')
            result=service.integrity()
            return SkillResult(result['ok'],'maintenance','completed' if result['ok'] else 'failed',json.dumps(result))
        else:
            if args:
                action,key,*rest=args.split(None,2)
                if action=='set' and rest:service.configure(key,json.loads(rest[0]))
                elif action in ('refresh-status','reset-refresh') and not rest:
                    from database.leads import LeadRepository
                    identity=LeadRepository(agent.db).resolve(key)['id']
                    if action=='reset-refresh':service.put('refresh:'+identity,dict(status='manual_reset',failures=0))
                    return SkillResult(True,'maintenance','completed',json.dumps(service.get('refresh:'+identity,{}),ensure_ascii=False,indent=2))
                else:raise ValueError('Use /maintenance set opção valor JSON; refresh-status ID; reset-refresh ID.')
            message=json.dumps(service.options(),ensure_ascii=False,indent=2)+'\nAutomação somente no desktop aberto e ocioso. Atualização opcional: até um lead por intervalo; três falhas suspendem novas tentativas.'
        return SkillResult(True,'maintenance','completed',message)
    except (OSError,sqlite3.Error,ValueError,RuntimeError,IndexError) as error:
        return SkillResult(False,'maintenance','failed',str(error) if isinstance(error,ValueError) else 'Operação local não concluída. Confira /health, permissões, espaço e logs; dados anteriores não foram deliberadamente apagados.')
