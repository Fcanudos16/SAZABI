# Auditoria do rework — 24/10/2026

## Estado observado antes das alterações

- Entradas: `main.py`, `desktop.py`, `iniciar_sazabi.cmd` e `.pyw`.
- Desktop nativo Tkinter: `ui/companion.py`, terminal compacto, tema compartilhado,
  sprites originais em assets, Win32 em `ui/native.py`, countdown e monitor locais.
- Dois roteadores: parser slash/registro em `core/commands` e roteamento comercial
  natural em `core/command_router.py`; `SazabiAgent._handle` faz fallback para este.
- `skills/registry.py` já oferece execução isolada e `SkillResult`. SearchSkill é
  comercial; `/research` também cai no pipeline comercial.
- Banco SQLite único, migrations, transações, backup e recuperação existentes.
  Tarefas antigas pertencem a leads: não servem como tarefas pessoais independentes.
- Worker possui cancelamento, eventos e execução fora da thread Tk. A manutenção
  periódica pode atualizar leads: precisa ser desligada no fluxo pessoal.
- LAYLA já tem bridge local, sessão, CSRF, limites, validação e terminal separado.
  Contrato observado: `/`, `/api/configuracoes`, `/enviar`, `/novo_chat`.
  Nenhum endpoint novo será presumido; disponibilidade real ainda não verificada.
- Configurações em `.env`; não foi exibido seu conteúdo. Tavily/Groq opcionais.
- Dependências declaradas: psutil e pytest. Nenhum venv encontrado na raiz;
  Python disponível é 3.14 e há `.test-deps` local reutilizado por run_tests.py.
- Há alterações preexistentes em análise, agente, comandos, pesquisa e terminal,
  além de docs e testes não rastreados. Devem ser preservadas; sem reset/limpeza.

## Referência e riscos

Comandos executados: `git status --short`, inventário `rg --files`, leitura dos
módulos acima e `python run_tests.py` (em execução ao escrever esta auditoria).
Não há AGENTS.md encontrado no inventário acessível. Testes de serviços externos
não comprovam disponibilidade sem execução real. Não instalar pacotes globais.

Reaproveitar tema, mascote, terminal, worker, SQLite, parser, registro, bridge,
backup e testes de componentes. Isolar código comercial fora do registro pessoal,
sem apagar banco nem módulos enquanto testes/dependências ainda os utilizarem.
Riscos: fallback natural acionar prospecção, manutenção automática residual,
expectativas antigas de testes, caminhos Windows, junctions e processos arbitrários.

## Migração adaptada

1. Registro pessoal e interceptação explícita antes do fallback comercial; atualizar
   botões, ajuda e mensagens iniciais. Desativar manutenção comercial automática.
2. Habilidades sobre contratos existentes, política de raízes autorizadas,
   histórico operacional no mesmo SQLite e confirmações vinculadas a prévias.
3. Tarefas pessoais e arquivos com buscas limitadas, hashes e planos reversíveis.
4. Inspeção local, Git somente leitura e testes com aprovação contextual.
5. Rotinas explicitamente configuradas; pesquisa local referenciada. Web opcional
   deve reportar indisponibilidade enquanto não houver adaptador técnico validado.
6. Preservar contrato LAYLA e validar testes existentes, sem execução de respostas.
7. Testes específicos do novo comportamento, regressões dos componentes preservados,
   smoke Tk real, README e relatório com limitações e resultados reais.
