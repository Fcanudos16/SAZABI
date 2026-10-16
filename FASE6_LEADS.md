# Fase 6 — gestão e acompanhamento de leads

Implementação integrada ao cadastro de empresas e ao terminal nativo do SAZABI. Reinicie o aplicativo para carregar os comandos e aplicar a migração. A mascote, os assets e o countdown foram preservados.

## Acesso diário

No terminal, clique em **Visão geral**, **Leads** ou **Tarefas**. Os comandos também aparecem no autocomplete de `/` e na ajuda. A interface continua compacta, com rolagem para listas e detalhes.

1. Execute `/search oficinas em São Paulo, capital`.
2. Abra `/leads` e copie o ID da empresa. `/lead ID` mostra fontes, pesquisas, avaliações, histórico comercial, notas e tarefas.
3. Use `/stage ID verifying Conferir localização e dados da fonte` para iniciar a verificação.
4. Defina `/task ID 2026-10-20 Confirmar se a empresa continua ativa | Consultar o site oficial`.
5. Consulte `/tasks vencidas` ou `/overview` diariamente.

`ID` é um marcador: substitua pelo ID exibido em `/leads`. O número de uma tarefa aparece como `#1`, por exemplo; para concluir, use `/taskdone 1`.

## Estados comerciais

| Valor usado em `/stage` | Estado |
|---|---|
| `new` | Novo lead |
| `verifying` | Em verificação |
| `qualified` | Qualificado |
| `contact_pending` | Contato pendente |
| `contacted` | Contatado |
| `negotiating` | Em negociação |
| `converted` | Convertido |
| `discarded` | Descartado |

Exemplo: `/stage ID contacted Contato realizado manualmente por telefone`.

Todas as mudanças são manuais e registram data, transição e motivo opcional. A passagem para `contacted` registra um acontecimento de contato manual declarado pelo usuário. Abrir os detalhes, qualificar, pesquisar novamente ou criar/concluir uma tarefa não altera automaticamente o estágio. Repetir o mesmo estágio não duplica o histórico. É possível corrigir uma escolha alterando o estágio novamente; as transições anteriores ficam preservadas.

## Tarefas

| Comando | Uso |
|---|---|
| `/task ID AAAA-MM-DD título` | Criar tarefa |
| `/task ID AAAA-MM-DD título \| descrição` | Criar com descrição |
| `/tasks` | Pendentes dos leads não arquivados |
| `/tasks vencidas` | Pendentes cujo dia previsto já passou |
| `/tasks todas` | Pendentes e concluídas dos leads não arquivados |
| `/tasks ID` | Pendentes de uma empresa específica |
| `/taskdone 1` | Concluir a tarefa 1 |
| `/taskreopen 1` | Reabrir a tarefa 1 |
| `/taskedit 1 AAAA-MM-DD título \| descrição` | Corrigir título, prazo e descrição |

Datas são dias do calendário local da máquina, sem horário. Uma tarefa prevista para hoje ainda não está vencida. Criação, edição, conclusão e reabertura têm histórico. A data de conclusão é limpa ao reabrir; o evento da conclusão anterior permanece. Omitir a descrição em `/taskedit` limpa essa descrição. Não há exclusão silenciosa de tarefas.

A próxima ação é a tarefa pendente com o prazo mais próximo. Assim, concluir ou reagendar uma tarefa atualiza a próxima ação automaticamente. Os antigos registros `/action ID next texto` continuam no histórico como intenções sem prazo; não são convertidos em tarefas com datas inventadas. Use `/task` para acompanhamento com prazo.

## Lista, filtros e ordenação

Cada lead exibe nome, segmento, cidade disponível, site, estágio, última verificação, avaliação salva quando existente e próxima ação/prazo. Ausência de avaliação não equivale a nota zero. A lista usa os registros reais do SQLite e pagina em grupos de 50.

```text
/leads status=verifying
/leads segmento=oficina min_score=30 max_score=70 ordem=score
/leads desde=2026-10-01 ate=2026-10-31 ordem=discovered
/leads vencidas ordem=next
/leads insuficientes
/leads ordem=updated
/leads salvos pagina=2
```

Filtros podem ser combinados. `insuficientes` inclui leads sem avaliação e aqueles cuja última categoria salva é `insufficient`. Datas de descoberta são inclusivas e interpretadas no calendário local. Ordenações: `name` alfabética; `score` maior primeiro; `discovered` descoberta mais recente; `updated` atualização mais recente; `next` prazo mais próximo, sem tarefa ao final. Arquivados são consultados separadamente com `arquivados`.

`/overview` mostra totais por estágio, tarefas vencidas, as dez próximas ações e até cinco prioridades pela última nota salva. Exclui arquivados; prioridades excluem convertidos e descartados. “Total de leads” é quantidade de cadastros, e “convertidos” depende exclusivamente da declaração manual do usuário. Nota não é probabilidade de venda. Após alterações comerciais, o terminal apresenta os indicadores recalculados.

## Fontes, edição e histórico

- `/note ID texto` edita as anotações do usuário; `/note ID -` limpa, preservando a alteração no histórico.
- `/edit ID phone|segment|city|address|description valor` registra uma correção manual. `-` limpa o campo. Informar o mesmo valor permite registrar a verificação manual.
- Os campos manuais aparecem nos detalhes com data e origem `user`; pesquisas posteriores preservam esses valores.
- Fontes originais e observações coletadas continuam no histórico de fontes, separado das anotações e correções. A nova coleta não apaga notas, tarefas ou transições comerciais.
- `/action ID response|note texto` registra acontecimentos declarados pelo usuário. Não comprova automaticamente um resultado comercial.
- `/lead ID` mostra justificativas da avaliação salva, hipóteses, fontes, pesquisas relacionadas, tarefas e os últimos 20 eventos comerciais. `/evaluations ID` permite consultar avaliações; a exportação existente mantém o histórico completo.

Não foi acrescentada geração de mensagens, envio ou automação de contato nesta fase.

## Auditoria e migração

Foram reaproveitados `companies`, `lead_events`, `source_history`, `run_companies`, `lead_evaluations`, os comandos comerciais e o terminal. Não há uma segunda tabela de empresas/leads. A única nova entidade é `lead_tasks`, vinculada por chave estrangeira ao cadastro existente; a próxima ação é derivada das tarefas, sem armazenamento duplicado.

A migração 3 amplia a restrição de estados de `companies` para incluir `verifying` e adiciona `manual_fields`. A reconstrução preserva registros, índices, gatilhos e referências. Antes de migrar um banco existente com dados, é criado backup local; a migração é transacional, verifica chaves estrangeiras e restaura sua fiscalização. Correções antigas identificáveis no histórico são preservadas como campos manuais quando ainda correspondem ao valor atual. Histórico ambíguo não recebe classificação inventada.

O banco operacional não foi usado para testes. A migração será aplicada na próxima inicialização normal. Mantenha o backup criado em `data/backups` (ou na pasta `backups` junto do banco configurado).

## Validação

- Suíte completa final: `python -m pytest -q -p no:cacheprovider --tb=short` — **341 testes e 16 subtestes aprovados**, em 52,23 segundos. `git diff --check` também passou.
- Testes automatizados em bancos temporários: todos os estágios, histórico/idempotência, tarefas e datas inválidas, vencimento, conclusão/reabertura, edição, filtros/ordens, indicadores, persistência após reiniciar, pesquisa repetida sem duplicação ou perda de notas/tarefas, proteção de campos manuais e migração de versões antigas.
- Falha simulada depois da reconstrução da tabela: rollback preservou versão anterior, empresas, fontes e eventos. Integridade, índices, gatilhos e chaves estrangeiras verificados após a migração bem-sucedida.
- Teste nativo: `python tests/native_phase6_check.py` — PASS. Percorre o worker e a janela Tkinter com pesquisa sintética e banco em memória, exercita os novos atalhos e confirma que o cronômetro de pesquisa não aparece na gestão de leads.
- Captura da janela de teste: `data/phase6/overview.png`, inspecionada visualmente. Apenas dados sintéticos.

Arquivos principais: `database/migrations.py`, `database/leads.py`, `database/repositories.py`, `core/lead_commands.py`, `ui/terminal.py`, `tests/test_phase6_workflow.py` e `tests/native_phase6_check.py`. Os testes antigos de migração foram ajustados para a versão 3 e para construir bancos antigos de verdade.

As alterações da Fase 5 que já estavam no diretório foram preservadas. Esta fase valida a organização comercial local; não substitui a verificação de qualidade das fontes reais documentada na Fase 5.
