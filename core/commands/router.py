from core.commands.parser import parse
from core.commands.registry import default_registry
from skills.base import SkillResult

class CommandRouter:
    def __init__(self, skills, registry=None):
        self.skills, self.registry = skills, registry or default_registry()

    def execute(self, text, context):
        command = parse(text)
        definition = self.registry.get(command.name) if command else None
        if definition is None:
            return None  # Existing local commands and natural-language routing.
        if definition.skill:
            return self.skills.execute(definition.skill, command.arguments, context)
        if definition.action == 'open_ai':
            return SkillResult(True, 'layla', 'ready', 'Use /ai na interface desktop para abrir o terminal LAYLA.',
                               {'action': 'open_ai', 'draft': command.arguments})
        return SkillResult(False, '', 'failed', message='Comando indisponível.')
