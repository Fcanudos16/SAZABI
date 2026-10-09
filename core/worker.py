"""Background agent execution, independent of the desktop rendering layer."""
import logging
from queue import Queue
from threading import Thread, Event, Lock
from dataclasses import dataclass, field

from core.bootstrap import build_agent
from notifications.notifier import NullNotifier


@dataclass
class ConnectRequest:
    key: str = field(repr=False)


@dataclass
class OllamaRequest:
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
        self.progress = progress
        self.snapshots = snapshots
        self.commands, self.events = Queue(), Queue()
        self.thread = Thread(target=self._run, args=(config, factory), daemon=False)
        self.thread.start()

    def _run(self, config, factory):
        agent = None
        try:
            agent = factory(config, notifier=NullNotifier())
            if self.progress:
                agent.event_sink = lambda kind, data: self.events.put(('activity', dict(kind=kind, **data)))
            if not config.mock and config.database_path != ':memory:':
                agent.db.backup()
            self.events.put(('ready', 'Pronto para pesquisar.' if config.mock or config.search_api_key
                             else 'Abra Configuração para conectar a Tavily. Histórico local disponível.'))
            self._snapshot(agent)
            while True:
                command = self.commands.get()
                if command is None:
                    break
                if isinstance(command, OllamaRequest):
                    try:
                        from analysis.ai_provider import list_models
                        from core.connection import configure_ollama
                        if command.action == 'list':
                            self.events.put(('ollama_models', list_models()))
                        else:
                            configure_ollama(agent, command.model)
                            self.events.put(('ollama_ready', 'IA local ativada: ' + command.model if command.model else 'IA local desativada.'))
                    except (ValueError, OSError) as error:
                        self.events.put(('ollama_error', str(error) if isinstance(error, ValueError) else 'Não foi possível salvar a configuração local.'))
                    except Exception:
                        self.events.put(('ollama_error', 'Falha ao configurar Ollama. Tente novamente.'))
                    continue
                if isinstance(command, ConnectRequest):
                    from core.connection import connect
                    from utils.http_client import FetchError
                    try:
                        connect(agent, command.key)
                        self.events.put(('connected', 'Tavily conectada. Chave salva. Você já pode pesquisar.'))
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
                    if self.progress:
                        self.events.put(('activity', {'kind': 'RESPONSE_READY'}))
                    if request:
                        with self._submission_lock:
                            if self._active_request is request:
                                self._active_request = None
                    if self.progress and agent.last_skill_result is not None:
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
            if agent is not None:
                agent.db.close()
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
            self._active_request = CommandRequest(text)
            if self.progress and command and command.name == 'search':
                self.events.put(('activity', {'kind': 'SKILL_STATE', 'skill': 'search', 'status': 'queued'}))
            self.commands.put(self._active_request)
            return True

    def cancel(self):
        with self._submission_lock:
            if self._active_request:
                self._active_request.cancelled.set()

    def close(self):
        with self._submission_lock:
            if self._closed:
                return
            self._closed = True
        self.cancel()
        self.commands.put(None)
