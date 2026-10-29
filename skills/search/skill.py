"""Search orchestration adapter. Existing research services remain authoritative."""
import json
import re
from pathlib import Path
from skills.base import SkillResult, ExecutionStopped
from core.command_router import parse_criteria

class SearchSkill:
    name = 'search'
    description = 'Pesquisa e prospecção comercial'
    version = '1.0.0'
    commands = ('/search',)
    specification = Path(__file__).with_name('SKILL.md')

    def __init__(self, config_path=None):
        self.state = 'idle'
        self.config_error = False
        self.allow_tavily = False
        try:
            settings = json.loads(Path(config_path or Path(__file__).with_name('config.json')).read_text(encoding='utf-8-sig'))
            self.allow_tavily = settings.get('allow_tavily', False)
            if type(self.allow_tavily) is not bool:
                raise ValueError
            self.enabled = settings['enabled']
            self.timeout = settings['timeout_seconds']
            if type(self.enabled) is not bool or type(self.timeout) not in (int, float) or not 5 <= self.timeout <= 600:
                raise ValueError
        except (OSError, ValueError, KeyError, TypeError):
            self.enabled, self.timeout, self.config_error = True, 180, True

    def execute(self, query, context):
        agent = context.agent
        original_query=query
        from analysis.commercial_profile import load
        from analysis.strategies import plan
        explicit=re.search(r'(?:^|\s)(?:estratégia|estrategia|strategy)=([a-z0-9_]+)(?=\s|$)',query)
        selected=explicit.group(1) if explicit else None
        if explicit: query=(query[:explicit.start()]+' '+query[explicit.end():]).strip()
        criteria = context.criteria or parse_criteria(query)
        try:
            criteria,search_plan=plan(load(agent.config),criteria,query,selected)
        except ValueError as error:
            return SkillResult(False,self.name,'failed',message=str(error))
        if not criteria.city:
            criteria.city = agent.memory.get_setting('region') or agent.config.default_region
        if not criteria.city and not self.config_error:
            agent._pending = dict(type='region', criteria=criteria,
                                  skill_name=self.name, skill_query=original_query)
            self.state = 'idle'
            return SkillResult(False, self.name, 'needs_input', message='Qual região devo pesquisar?')
        # Paid Tavily access requires explicit opt-in; validate discovery and enrichment.
        from research.web_source import WebSource, TavilySearch
        sources = agent.finder.sources + agent.investigator.sources
        allowed = bool(agent.finder.sources) and all(
            getattr(source, 'search_skill_cost_policy', None) == 'zero_cost'
            or (self.allow_tavily and isinstance(source, WebSource)
                and isinstance(source.provider, TavilySearch) and bool(source.provider.key))
            or (agent.config.mock and getattr(source, 'search_skill_cost_policy', None) == 'test_fixture')
            for source in sources)
        if self.config_error or not self.specification.is_file() or not allowed:
            self.state = 'failed'
            message = ('Pesquisa não iniciada. Search Skill ainda não configurada. '
                       'Configure SEARCH_API_KEY no .env e reinicie; Tavily usa créditos e exige '
                       'allow_tavily=true em skills/search/config.json. '
                       'Fontes desconhecidas ou configuração inválida também impedem a pesquisa. '
                       'Nenhuma consulta foi enviada e nenhum resultado foi fabricado.')
            context.state('failed')
            agent.emit('TASK_ERROR', message=message)
            return SkillResult(False, self.name, 'unconfigured', message=message, error='Pesquisa não iniciada.')
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
        from dataclasses import asdict
        search_plan['effective']=asdict(criteria)
        criteria.strategy_context=search_plan
        agent.search_strategy_context=search_plan
        try:
            previous = agent.runs.last()
            context.checkpoint()
            message = agent._cmd_search(criteria)
            label=search_plan['strategy']['objective'] if search_plan['strategy'] else 'Exploratória — nenhuma estratégia compatível ativa'
            message='Estratégia: '+label+'\n'+('Critérios do perfil: '+', '.join(search_plan['applied'])+'\n' if search_plan['applied'] else '')+search_plan['limitation']+'\n\n'+message
            run = agent.runs.last()
            if run is None or (previous and run.id == previous.id):
                if agent._pending and agent._pending.get('type') == 'region':
                    agent._pending.update(skill_name=self.name, skill_query=query)
                    self.state = 'idle'
                    context.state('idle')
                    return SkillResult(False, self.name, 'needs_input', message=message)
                self.state='failed'
                context.state('failed')
                return SkillResult(False,self.name,'failed',message=message)
            companies = agent.companies.get_many(agent.runs.company_ids(run.id))
            from analysis.search_brief import qualification_gaps, matches_need
            cards, pending = [], []
            states = getattr(agent, 'search_analysis_states', {})
            for company in companies:
                gaps = qualification_gaps(company, criteria)
                evaluation=agent.db.query_one('SELECT result_json FROM lead_evaluations WHERE company_id=? ORDER BY id DESC LIMIT 1',(company.id,))
                saved=json.loads(evaluation['result_json']) if evaluation else {}
                gaps += [reason for reason in saved.get('negative_factors',[]) if reason.startswith('Lead excluído')]
                brief=saved.get('search_brief')
                if gaps or states.get(company.id) == 'failed' or not brief or saved.get('strategy_context') != search_plan:
                    pending.append(dict(id=company.id, name=company.name, url=company.website,
                        reason='; '.join(gaps) or 'Análise indisponível nesta pesquisa; dados anteriores preservados.'))
                    continue
                if not matches_need(criteria.need, brief):
                    pending.append(dict(id=company.id,name=company.name,url=company.website,
                        reason='Necessidade solicitada ainda não sustentada por evidências.'))
                    continue
                cards.append(brief)
            cards.sort(key=lambda c: (-c['score'], c['name']))
            diagnostics = message
            message = ('Pesquisa parcial — confira as limitações.' if run.status == 'partial' else
                       'Pesquisa não concluída.' if run.status == 'failed' else 'Pesquisa concluída.')
            message += f'\n{len(cards)} empresas qualificadas; {len(pending)} empresas pendentes de validação.'
            message += '\nEstratégia: ' + label
            if not cards: message += '\nNenhuma empresa qualificada para apresentação comercial nesta pesquisa.'
            if agent.config.mock: message += '\nModo mock: empresas e fontes fictícias.'
            for card in cards:
                message += f"\n\n{card['name']}\n{card['summary']}\n{card['situation']}\nPrioridade {card['priority']}: {card['score']}/100 · Evidência {card['evidence_quality']}\nDetalhes: /lead {card['company_id']}"
            data = dict(run_id=run.id, strategy=search_plan, opportunities=cards,
                        pending_companies=pending, discovery=agent.finder.hits, diagnostics=diagnostics,
                        headline=message.split('\n\n')[0],
                        companies=[dict(id=p.id, name=p.name, segment=p.segment,
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
            import logging
            logging.getLogger('sazabi.search').exception('Falha na execução da Search Skill')
            self.state = 'failed'
            context.state('failed')
            agent.emit('TASK_ERROR', message='Search Skill não conseguiu concluir a pesquisa.')
            return SkillResult(False, self.name, 'failed', message='Não foi possível concluir a pesquisa. Tente novamente.', error='Falha de execução.')
        finally:
            for client, callback in callbacks:
                client.checkpoint = callback
            agent.skill_context = None
            agent.search_strategy_context = None
