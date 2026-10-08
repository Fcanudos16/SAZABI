"""Background agent execution, independent of the desktop rendering layer."""
import logging
from queue import Queue
from threading import Thread
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


class AgentWorker:
    """Creates, uses and closes SQLite on its owning worker thread."""
    def __init__(self, config, factory=build_agent, snapshots=False, progress=False):
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
                    reply = agent.handle(command)
                    if self.progress:
                        self.events.put(('activity', {'kind': 'RESPONSE_READY'}))
                    self.events.put(('reply', reply))
                    self._snapshot(agent)
                except Exception:
                    logging.getLogger('sazabi.desktop').exception('Falha no comando desktop')
                    if self.progress:
                        self.events.put(('activity', {'kind': 'TASK_ERROR', 'message': 'Não consegui concluir o pedido.'}))
                    self.events.put(('reply', 'Falha ao processar o comando. Consulte o log.'))
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

    def close(self):
        self.commands.put(None)


