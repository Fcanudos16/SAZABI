# Entrega incremental do rework — 24/10/2026

> Registro da primeira entrega. A pesquisa, revisão e Git de escrita descritos
> abaixo como pendentes foram implementados na continuação:
> [relatório atualizado](REWORK_CONTINUATION.md). A LAYLA foi adiada pelo usuário.

## Resultado

O fluxo padrão agora é de agente pessoal local. Foram implementadas habilidades
integradas ao parser, registro, worker e terminal existentes, com SQLite real,
busca/hash/movimentação reais e execução real de processos autorizados.
O plano mestre completo **não está concluído**; limites estão discriminados abaixo.

## Fases e evidências

| Fase | Implementado e verificado | Limitação restante |
| --- | --- | --- |
| 0/1 | Auditoria anterior à edição; registro/UI pessoais; fallback comercial bloqueado; nenhuma fonte Tavily instanciada no modo pessoal; manutenção comercial automática desativada | Legado preservado para dependências e testes, não excluído |
| 2 | Contratos/registries existentes reutilizados, erros isolados, caminhos autorizados, histórico, confirmação por token com expiração | Execução de código aprovado não é sandbox |
| 3 | CRUD de tarefas, prioridade/data/categoria/projeto, pendentes/atrasadas, exportação; busca por filtros, duplicatas SHA-256, organização/mover com prévia, desfazer, backup | Listas/projetos são campos; sem interface dedicada; recuperação de lote parcialmente executado é manual pelo registro |
| 4 | Inventário, dependências, revisão sintática/eval/exec, Git de leitura, execução aprovada de testes | Revisão semântica, preparação de patches e escritas Git/remotas pendentes |
| 5 | Rotinas configuradas com argv/cwd, timeout/cancelamento, pesquisa local com arquivo/linha | Web técnica, síntese e comparação automatizadas pendentes |
| 6 | Terminal e bridge LAYLA preservados; contrato local coberto pela suíte | LAYLA real inacessível: porta loopback 5000 não respondeu e não há credencial de sessão configurada |
| 7 | Suíte, teste nativo real, captura inspecionada, README/guia atualizado | Multimonitor, outros níveis de DPI e overlay sobre apps externos não revalidados |

## Testes executados

- Antes das mudanças: `python run_tests.py` — **383 passed, 1 skipped,
  16 subtests passed**, 71,19 s.
- Primeira regressão da migração: 15 falhas, majoritariamente expectativas antigas
  de prospecção e uma falha real no resultado estruturado de recusa de credenciais.
  A recusa foi corrigida; testes de produção passaram a exigir funções pessoais.
  Testes dos componentes comerciais utilizam harness explícito, sem mocks novos
  substituindo implementações funcionais.
- Suíte após correções: `python run_tests.py` — **402 passed, 1 skipped,
  16 subtests passed**, 118,00 s.
- Após endurecimento adicional de caminhos e cancelamento:
  `python -m pytest tests/test_personal.py -q -p no:cacheprovider --basetemp data/personal-tests-final`
  — **27 passed**, 36,08 s. Inclui Git real em repositório temporário,
  script real com saída 3, cancelamento de processo real, persistência/reabertura,
  exportação, hash, confirmação/desfazer, prévia obsoleta, credenciais e backup.
- `python tests/native_personal_check.py` — **PASS** fora da sandbox: Tk real,
  sprites originais, terminal preto/verde, autocomplete, worker, tarefas,
  falha de permissão, geometria compacta e esconder terminal preservando mascote.
  A primeira execução restrita não carregou init.tcl; o arquivo existia e a
  execução autorizada fora da sandbox passou sem instalar/reparar Python.
- Captura `data/rework-terminal.png` inspecionada visualmente: sem barras brancas,
  botões pessoais e terminal contido. Captura apenas da janela de teste.
- `git diff --check` passou; avisos de conversão LF/CRLF do checkout, sem erro.
- Testes da LAYLA na suíte usam transporte HTTP contra servidor local de contrato.
  Não equivalem a autenticação ou delegação real para a instalação do usuário.

## Arquivos desta migração

Criados: `core/local_policy.py`, `database/personal.py`, `skills/personal.py`,
`tests/test_personal.py`, `tests/native_personal_check.py`,
`docs/REWORK_AUDIT.md`, `docs/PERSONAL_GUIDE.md`, `docs/REWORK_REPORT.md` e
`docs/LEGACY_COMMERCIAL_README.md` (cópia do README anterior).

Alterados: `core/agent.py`, `core/bootstrap.py`, `core/config.py`,
`core/commands/registry.py`, `core/worker.py`, `main.py`, `ui/terminal.py`,
`ui/companion.py`, `.env.example`, `README.md`, `tests/factories.py`,
`tests/test_desktop.py`, `tests/test_phase4.py`, `tests/test_phase5_quality.py`,
`tests/test_phase9_maintenance.py`, `tests/test_real_pipeline.py` e
`tests/test_slash_skills.py`.

Nenhum arquivo de usuário removido. Nenhuma dependência adicionada/removida,
nenhum segredo alterado ou exibido, nenhum commit/push realizado. Alterações
preexistentes em análise, pesquisa, comandos comerciais, SearchSkill, terminal,
docs e testes foram preservadas. O diff total do checkout inclui essas mudanças
anteriores e não deve ser atribuído integralmente a esta migração.

## Decisões e próxima etapa

Reutilizar interfaces e armazenamento, mantendo legado inacessível pelo registro
pessoal, evita apagar dados ou romper dependências desconhecidas. Os serviços
pessoais possuem tabelas próprias no mesmo banco porque lead_tasks exige empresa.
Confirmações são efêmeras; efeitos e resultados limitados ficam no SQLite.
Prévias não são tratadas como execução concluída pelo mascote.

Próximo incremento recomendado: revisão de código com propostas de patch e Git
de escrita com prévias verificáveis; depois um adaptador de pesquisa técnica
explicitamente escolhido e validado. A remoção física do legado deve seguir
uma separação adicional dos imports/serviços compartilhados e novos testes.
