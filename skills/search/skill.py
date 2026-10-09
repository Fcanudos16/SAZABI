"""Search orchestration adapter. Existing research services remain authoritative."""
import json
from pathlib import Path
from skills.base import SkillResult, ExecutionStopped
from core.command_router import parse_criteria

class SearchSkill:
    name = 'search'
    description = 'Pesquisa e prospecção comercial'
    version = '1.0.0'
    commands = ('/search',)

    def __init__(self, config_path=None):
        self.state = 'idle'
        self.config_error = False
        try:
            settings = json.loads(Path(config_path or Path(__file__).with_name('config.json')).read_text(encoding='utf-8-sig'))
            self.enabled = settings['enabled']
            self.timeout = settings['timeout_seconds']
            if type(self.enabled) is not bool or type(self.timeout) not in (int, float) or not 5 <= self.timeout <= 600:
                raise ValueError
        except (OSError, ValueError, KeyError, TypeError):
            self.enabled, self.timeout, self.config_error = True, 180, True

    def execute(self, query, context):
        agent = context.agent
        if self.config_error or not agent.finder.sources:
            self.state = 'failed'
            message = 'Pesquisa não iniciada. Search Skill ainda não configurada. Abra Configuração e conecte a Tavily para habilitar a pesquisa real.'
            context.state('failed')
            agent.emit('TASK_ERROR', message=message)
            return SkillResult(False, self.name, 'unconfigured', message=message, error='Pesquisa não iniciada.')
        if not query.strip():
            self.state = 'idle'
            return SkillResult(False, self.name, 'needs_input', message='Digite /search seguido do que deseja pesquisar e da região.')
        context.timeout = self.timeout
        agent.skill_context = context
        from utils.http_client import HttpClient
        clients = {}
        for source in agent.finder.sources + agent.investigator.sources:
            for client in (getattr(source, 'client', None), getattr(getattr(source, 'provider', None), 'client', None)):
                if isinstance(client, HttpClient):
                    clients[id(client)] = client
        callbacks = [(client, client.checkpoint) for client in clients.values()]
        for client, _ in callbacks:
            client.checkpoint = context.checkpoint
        self.state = 'running'
        context.state('running')
        try:
            previous = agent.runs.last()
            context.checkpoint()
            message = agent._cmd_search(context.criteria or parse_criteria(query))
            run = agent.runs.last()
            if run is None or (previous and run.id == previous.id):
                if agent._pending and agent._pending.get('type') == 'region':
                    agent._pending.update(skill_name=self.name, skill_query=query)
                self.state = 'idle'
                context.state('idle')
                return SkillResult(False, self.name, 'needs_input', message=message)
            companies = agent.companies.get_many(agent.runs.company_ids(run.id))
            data = dict(run_id=run.id, companies=[dict(id=p.id, name=p.name, segment=p.segment,
                location=p.location, website=p.website) for p in companies])
            status = run.status
            self.state = status
            context.state('failed' if status == 'failed' else 'completed')
            return SkillResult(status in ('completed', 'partial'), self.name, status, message, data,
                               run.error_message if status in ('failed', 'partial') else '')
        except ExecutionStopped as error:
            self.state = error.status
            context.state(error.status)
            message = 'Pesquisa cancelada.' if error.status == 'cancelled' else 'Tempo limite da pesquisa atingido. Resultados anteriores foram preservados.'
            agent.emit('TASK_ERROR', message=message)
            return SkillResult(False, self.name, error.status, message=message, error=message)
        except Exception:
            self.state = 'failed'
            context.state('failed')
            agent.emit('TASK_ERROR', message='Search Skill não conseguiu concluir a pesquisa.')
            return SkillResult(False, self.name, 'failed', message='Não foi possível concluir a pesquisa. Tente novamente.', error='Falha de execução.')
        finally:
            for client, callback in callbacks:
                client.checkpoint = callback
            agent.skill_context = None
