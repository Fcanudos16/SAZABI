from skills.base import SkillResult

class SkillRegistry:
    def __init__(self):
        self.skills = {}

    def register(self, skill, replace=False):
        if skill.name in self.skills and not replace:
            raise ValueError('Skill já registrada.')
        self.skills[skill.name] = skill

    def get(self, name):
        return self.skills.get(name)

    def available(self, name):
        skill = self.get(name)
        return bool(skill and skill.enabled)

    def execute(self, name, query, context):
        skill = self.get(name)
        if not skill or not skill.enabled:
            return SkillResult(False, name, 'unavailable', error='Skill inexistente ou desativada.',
                               message='Skill indisponível. Verifique a configuração do backend.')
        try:
            result = skill.execute(query, context)
            if not isinstance(result, SkillResult):
                raise TypeError
            return result
        except Exception:
            return SkillResult(False, name, 'failed', message='A Skill não conseguiu concluir a operação.', error='Falha de execução.')
