"""Bounded local maintenance, only while the desktop session is running."""
from collections import Counter
from datetime import date, timedelta
import json
import logging
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit
from utils.timeutils import now_iso,utcnow,parse_iso

log=logging.getLogger('sazabi.maintenance')
DEFAULTS=dict(auto_backup=True,backup_hours=24,retention=10,notifications=True,
              due_alerts=False,due_days=1,auto_refresh=False,refresh_minutes=60,stale_days=14)


class Maintenance:
    def __init__(self,agent,alert=None):
        self.agent=agent;self.db=agent.db;self.alert_sink=alert or (lambda message:None)

    def get(self,key,default=None):
        value=self.agent.memory.get_setting('ops.'+key)
        return json.loads(value) if value is not None else default

    def put(self,key,value): self.agent.memory.set_setting('ops.'+key,json.dumps(value,ensure_ascii=False))

    def options(self):
        options=DEFAULTS|self.get('config',{})
        if set(options)!=set(DEFAULTS): raise ValueError('Configuração operacional inválida.')
        for key in ('auto_backup','notifications','due_alerts','auto_refresh'):
            if type(options[key]) is not bool: raise ValueError('Opção booleana inválida: '+key)
        for key,low,high in [('backup_hours',1,720),('retention',1,100),('due_days',0,30),('refresh_minutes',30,10080),('stale_days',1,3650)]:
            if type(options[key]) is not int or not low<=options[key]<=high: raise ValueError(f'{key}: {low} a {high}.')
        return options

    def configure(self,key,value):
        if key not in DEFAULTS: raise ValueError('Opção desconhecida.')
        old=self.get('config',{})
        candidate=old|{key:value}
        # Validate before persisting, including types (bool is not an integer).
        getter=self.get
        self.get=lambda name,default=None:candidate if name=='config' else getter(name,default)
        try:self.options()
        finally:self.get=getter
        self.put('config',candidate)

    def journal(self,kind,status,detail=''):
        from utils.logger import redact
        record=dict(at=now_iso(),kind=kind,status=status,detail=redact(detail))
        log.info('operation=%s status=%s %s',kind,status,record['detail'])
        try:self.put('journal',(self.get('journal',[])+[record])[-100:])
        except sqlite3.Error:log.error('Falha ao gravar histórico operacional; consulte o log local.')

    def alert(self,key,message):
        if not self.options()['notifications']:return False
        seen=self.get('alerts',[])
        if key in seen:return False
        self.put('alerts',(seen+[key])[-500:])
        self.alert_sink(message)
        return True

    def backups(self):
        if self.db.path==':memory:':return []
        path=Path(self.db.path)
        return sorted((p for p in (path.parent/'backups').glob(path.stem+'_*.db') if p.is_file() and not p.is_symlink()),key=lambda p:p.name,reverse=True)

    def backup(self):
        self.put('backup_attempt',now_iso())
        try:
            result=self.db.backup()
            self.put('backup_success',dict(at=now_iso(),file=Path(result).name))
            self.journal('backup','completed',Path(result).name)
            # Only this database's completed backups; never pending files or rescue copies.
            try:
                for old in self.backups()[self.options()['retention']:]:old.unlink()
            except OSError:
                self.journal('retention','failed','Backup válido; algumas cópias antigas não puderam ser removidas.')
            return result
        except (OSError,sqlite3.Error,RuntimeError):
            self.journal('backup','failed','Backup não concluído; cópias anteriores preservadas.')
            self.alert('backup-failed:'+date.today().isoformat(),'Backup falhou. Consulte /health e verifique espaço e permissões.')
            raise

    def integrity(self):
        ok=self.db.query_one('PRAGMA integrity_check')[0]=='ok' and not self.db.query('PRAGMA foreign_key_check')
        record=dict(at=now_iso(),ok=ok)
        self.put('integrity',record);self.journal('integrity','completed' if ok else 'failed')
        return record

    def health(self):
        options=self.options()
        counts=Counter();durations=[];failures=Counter()
        for row in self.db.query('SELECT status,started_at,finished_at,error_message FROM research_runs'):
            counts[row['status']]+=1
            if row['status'] in ('completed','partial') and row['finished_at']:
                try:
                    seconds=(parse_iso(row['finished_at'])-parse_iso(row['started_at'])).total_seconds()
                    if seconds>=0:durations.append(seconds)
                except (TypeError,ValueError):pass
        # Domain only: diagnostic output does not expose queries, names or URLs with tokens.
        for row in self.db.query("SELECT url,reason FROM discovery_results WHERE status='pending'"):
            if any(word in row['reason'].lower() for word in ('falha','recus','robots','limite','timeout','excedeu')):
                try:failures[urlsplit(row['url']).hostname or 'fonte desconhecida']+=1
                except ValueError:failures['URL inválida']+=1
        cutoff=(utcnow()-timedelta(days=options['stale_days'])).isoformat()
        stale=self.db.query_one('SELECT COUNT(*) n FROM companies WHERE archived=0 AND (last_researched IS NULL OR last_researched<?)',(cutoff,))['n']
        config=self.agent.config
        return dict(research=dict(counts),mean_completed_seconds=round(sum(durations)/len(durations),2) if durations else None,
                    duration_sample=len(durations),source_failures=dict(failures.most_common(10)),
                    last_backup=self.get('backup_success'),last_integrity=self.get('integrity'),
                    pending_tasks=self.db.query_one('SELECT COUNT(*) n FROM lead_tasks t JOIN companies c ON c.id=t.company_id WHERE t.completed=0 AND c.archived=0')['n'],
                    stale_leads=stale,integrations={name:('configurada; conexão não verificada neste diagnóstico' if value else 'não configurada')
                    for name,value in [('Tavily',config.search_api_key),('Groq',config.groq_api_key),('LAYLA',config.layla_url)]},
                    maintenance=options,recent_operations=self.get('journal',[])[-10:])

    def due(self,stamp,seconds):
        try:return not stamp or (utcnow()-parse_iso(stamp)).total_seconds()>=seconds
        except (TypeError,ValueError):return True

    def tick(self,cancelled=None,allow_refresh=True):
        """Called serially by the existing worker; no daemon or external scheduler."""
        if cancelled and cancelled.is_set():return
        options=self.options()
        if options['auto_backup'] and self.db.path!=':memory:' and self.due(self.get('backup_attempt'),options['backup_hours']*3600):
            self.backup()
        if cancelled and cancelled.is_set():return
        if options['due_alerts']:
            until=(date.today()+timedelta(days=options['due_days'])).isoformat()
            count=0
            for row in self.db.query('SELECT t.id,t.due_date FROM lead_tasks t JOIN companies c ON c.id=t.company_id WHERE t.completed=0 AND c.archived=0 AND t.due_date<=? ORDER BY t.due_date LIMIT 100',(until,)):
                if self.alert(f"task:{row['id']}:{row['due_date']}",f"Tarefa #{row['id']} com prazo {row['due_date']}. Consulte /tasks."):count+=1
                if count>=3:break
        if allow_refresh and options['auto_refresh'] and not self.agent._pending and self.due(self.get('refresh_tick'),options['refresh_minutes']*60):
            self.put('refresh_tick',now_iso())
            self.refresh_one(options,cancelled)

    def refresh_one(self,options,cancelled):
        cutoff=(utcnow()-timedelta(days=options['stale_days'])).isoformat()
        for row in self.db.query("SELECT id,last_researched FROM companies WHERE archived=0 AND commercial_status NOT IN ('discarded','converted') AND website IS NOT NULL AND (last_researched IS NULL OR last_researched<?) ORDER BY last_researched,id",(cutoff,)):
            key='refresh:'+row['id'];record=self.get(key,{})
            if record.get('failures',0)>=3:continue
            if record.get('next_attempt') and parse_iso(record['next_attempt'])>utcnow():continue
            record.update(last_attempt=now_iso(),status='running');self.put(key,record)
            old={(r['url'],r['text']) for r in self.db.query('SELECT url,text FROM sources WHERE company_id=?',(row['id'],))}
            sink=self.agent.event_sink
            previous_result=self.agent.last_skill_result
            context_keys=[self.agent.memory.scope+key for key in ('last_company_id','last_run_id')]
            previous_context={key:self.agent.memory.settings.get(key) for key in context_keys}
            try:
                self.agent.event_sink=None
                self.agent.handle('/investigate '+row['id']+' --refresh',cancelled=cancelled)
                current=self.db.query_one('SELECT last_researched FROM companies WHERE id=?',(row['id'],))['last_researched']
                success=bool(current and current!=row['last_researched'])
                if success:
                    new={(r['url'],r['text']) for r in self.db.query('SELECT url,text FROM sources WHERE company_id=?',(row['id'],))}
                    record.update(status='partial' if self.agent.investigator.errors or not new else 'completed',last_success=current,failures=0,unconfirmed_observations=len(old-new))
                elif cancelled and cancelled.is_set():record.update(status='cancelled',failures=record.get('failures',0))
                else:record.update(status='failed',failures=record.get('failures',0)+1)
            except Exception:
                record.update(status='failed',failures=record.get('failures',0)+1)
                log.exception('Falha na atualização periódica de lead_id=%s',row['id'])
            finally:
                self.agent.event_sink=sink
                self.agent.last_skill_result=previous_result
                for context_key,value in previous_context.items():self.agent.memory.settings.set(context_key,value)
            record['next_attempt']=(utcnow()+timedelta(minutes=options['refresh_minutes']*2**min(record['failures'],3))).isoformat()
            self.put(key,record);self.journal('refresh',record['status'],'lead_id='+row['id'])
            if record['failures']>=3:self.alert('refresh-blocked:'+row['id'],'Atualização suspensa após três falhas. Consulte /maintenance refresh-status ID.')
            break

    def recover(self):
        for row in self.db.query("SELECT key,value FROM settings WHERE key LIKE 'ops.refresh:%'"):
            record=json.loads(row['value'])
            if record.get('status')=='running':
                record.update(status='unknown',failures=3)
                self.agent.memory.set_setting(row['key'],json.dumps(record))
                self.journal('refresh','unknown','Atualização interrompida; revisão manual antes de repetir.')
