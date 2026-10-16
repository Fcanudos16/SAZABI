"""Background agent execution, independent of the desktop rendering layer."""
import logging
from queue import Queue, Empty
from contextlib import ExitStack
from types import SimpleNamespace
from threading import Thread, Event, Lock
from dataclasses import dataclass, field

from core.bootstrap import build_agent
from notifications.notifier import NullNotifier


@dataclass
class ConnectRequest:
    key: str = field(repr=False)


@dataclass
class GroqRequest:
    action: str
    model: str = ''


@dataclass
class CommandRequest:
    text: str
    cancelled: Event = field(default_factory=Event)


class AgentWorker:
    """Creates, uses and closes SQLite on its owning worker thread."""
    def __init__(self, config, factory=build_agent, snapshots=False, progress=False):
        self._submission_lock = Lock()
        self._active_request = None
        self._closed = False
        self._maintenance_cancel=Event()
        self.progress = progress
        self.snapshots = snapshots
        self.commands, self.events = Queue(), Queue()
        self.thread = Thread(target=self._run, args=(config, factory), daemon=False)
        self.thread.start()

    def _run(self, config, factory):
        agent = None
        stack=ExitStack()
        try:
            from database.recovery import research_lock
            stack.enter_context(research_lock(SimpleNamespace(path=config.database_path),suffix='.session.lock'))
            agent = factory(config, notifier=NullNotifier())
            from core.maintenance import Maintenance
            maintenance=Maintenance(agent,lambda message:self.events.put(('maintenance_alert',message)))
            maintenance.recover()
            logging.getLogger('sazabi.desktop').info('Sessão desktop iniciada')
            if self.progress:
                agent.event_sink = lambda kind, data: self.events.put(('activity', dict(kind=kind, **data)))
            if not config.mock:
                try:maintenance.tick(self._maintenance_cancel,allow_refresh=False)
                except Exception:
                    logging.getLogger('sazabi.desktop').exception('Manutenção inicial falhou; aplicação permanece disponível')
            self.events.put(('ready', 'Pronto para pesquisar.' if config.mock or config.search_api_key
                             else 'Configure SEARCH_API_KEY no .env e reinicie. Histórico local disponível.'))
            self._snapshot(agent)
            while True:
                try:command = self.commands.get(timeout=30)
                except Empty:
                    with self._submission_lock:
                        if self._closed:break
                        if self._active_request is not None or not self.commands.empty():continue
                        self._maintenance_cancel.clear()
                    if not config.mock:
                        try:maintenance.tick(self._maintenance_cancel)
                        except Exception:
                            logging.getLogger('sazabi.desktop').exception('Falha na manutenção da sessão')
                    continue
                if command is None:
                    break
                if isinstance(command, GroqRequest):
                    try:
                        from analysis.ai_provider import list_models
                        from core.connection import configure_groq
                        if command.action == 'list':
                            self.events.put(('groq_models', list_models(agent.config.groq_api_key)))
                        else:
                            configure_groq(agent, command.model)
                            self.events.put(('groq_ready', 'IA Groq ativada: ' + command.model if command.model else 'IA Groq desativada.'))
                    except (ValueError, OSError) as error:
                        self.events.put(('groq_error', str(error) if isinstance(error, ValueError) else 'Não foi possível salvar a configuração local.'))
                    except Exception:
                        self.events.put(('groq_error', 'Falha ao configurar Groq. Tente novamente.'))
                    continue
                if isinstance(command, ConnectRequest):
                    from core.connection import connect
                    from utils.http_client import FetchError
                    try:
                        connect(agent, command.key)
                        self.events.put(('connected', 'Tavily conectada. /search e /research usam créditos da conta.'))
                    except (FetchError, ValueError) as error:
                        self.events.put(('connection_error', str(error)))
                    except OSError:
                        self.events.put(('connection_error', 'Não foi possível salvar o .env. Confira a permissão da pasta.'))
                    except Exception:
                        self.events.put(('connection_error', 'Falha ao conectar. Confira a rede e tente novamente.'))
                    finally:
                        command.key = ''
                    continue
                try:
                    if self.progress:
                        self.events.put(('activity', {'kind': 'COMMAND_STARTED'}))
                    request = command if isinstance(command, CommandRequest) else None
                    reply = agent.handle(request.text if request else command,
                                         cancelled=request.cancelled if request else None)
                    if self.progress and not (agent.last_skill_result and not agent.last_skill_result.success):
                        self.events.put(('activity', {'kind': 'RESPONSE_READY'}))
                    if request:
                        with self._submission_lock:
                            if self._active_request is request:
                                self._active_request = None
                    if self.progress and agent.last_skill_result is not None:
                        try:agent.last_skill_result.data['notify']=maintenance.options()['notifications']
                        except ValueError:pass
                        self.events.put(('command_result', agent.last_skill_result.to_dict()))
                    else:
                        self.events.put(('reply', reply))
                    self._snapshot(agent)
                except Exception:
                    logging.getLogger('sazabi.desktop').exception('Falha no comando desktop')
                    if self.progress:
                        self.events.put(('activity', {'kind': 'TASK_ERROR', 'message': 'Não consegui concluir o pedido.'}))
                    self.events.put(('reply', 'Falha ao processar o comando. Consulte o log.'))
                finally:
                    if isinstance(command, CommandRequest):
                        with self._submission_lock:
                            if self._active_request is command:
                                self._active_request = None
        except Exception:
            logging.getLogger('sazabi.desktop').exception('Falha ao iniciar desktop')
            self.events.put(('error', 'Não foi possível iniciar. Confira a configuração e o log.'))
        finally:
            try:
                if agent is not None:
                    agent.db.close()
            except Exception:
                logging.getLogger('sazabi.desktop').exception('Falha ao fechar banco da sessão')
            finally:
                stack.close()
                logging.getLogger('sazabi.desktop').info('Sessão desktop encerrada; nenhuma tarefa continua após closed')
                self.events.put(('closed', ''))

    def _snapshot(self, agent):
        if self.snapshots:
            try:
                from core.dashboard import dashboard_snapshot
                self.events.put(('snapshot', dashboard_snapshot(agent.db)))
            except Exception:
                logging.getLogger('sazabi.desktop').exception('Falha ao atualizar painel')
                self.events.put(('dashboard_error', 'Não foi possível atualizar as métricas locais.'))

    def submit(self, text):
        from core.commands.parser import parse
        command = parse(text)
        with self._submission_lock:
            if self._closed or self._active_request is not None or not self.thread.is_alive():
                return False
            self._maintenance_cancel.set()
            self._active_request = CommandRequest(text)
            if self.progress and command and command.name == 'search':
                self.events.put(('activity', {'kind': 'SKILL_STATE', 'skill': 'search', 'status': 'queued'}))
            self.commands.put(self._active_request)
            return True

    def cancel(self):
        with self._submission_lock:
            self._maintenance_cancel.set()
            if self._active_request:
                self._active_request.cancelled.set()

    def close(self):
        with self._submission_lock:
            if self._closed:
                return
            self._closed = True
        self.cancel()
        self._maintenance_cancel.set()
        self.commands.put(None)
