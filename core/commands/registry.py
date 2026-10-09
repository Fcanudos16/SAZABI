from dataclasses import dataclass

@dataclass(frozen=True)
class CommandDefinition:
    name: str
    description: str
    skill: str = ''
    action: str = ''

class CommandRegistry:
    def __init__(self):
        self.commands = {}

    def register(self, command):
        if command.name in self.commands:
            raise ValueError('Comando já registrado.')
        self.commands[command.name] = command

    def get(self, name):
        return self.commands.get(name)

    def suggestions(self, prefix):
        return [c for c in self.commands.values() if ('/' + c.name).startswith(prefix.lower())]


def default_registry():
    registry = CommandRegistry()
    registry.register(CommandDefinition('search', 'Pesquisa e prospecção comercial', skill='search'))
    registry.register(CommandDefinition('ai', 'Abrir Terminal de IA conectado à LAYLA', action='open_ai'))
    return registry
