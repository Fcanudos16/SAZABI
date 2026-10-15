# SAZABI — fase 2: base local e gestão de leads

## Uso no terminal existente

Clique em **Leads** ou digite `/leads`. O terminal mantém suas dimensões; os comandos também aparecem nas sugestões ao digitar `/`. Cada empresa encontrada já é um cadastro persistente. `/save` marca um cadastro como favorito, não cria uma segunda cópia.

Use o ID mostrado na listagem. Os comandos novos aceitam um prefixo hexadecimal apenas quando ele identifica exatamente um registro; para `/save` e `/forget`, use o ID completo ou o nome não ambíguo.

| Operação | Comando |
|---|---|
| Listar | `/leads` |
| Buscar por nome | `/leads clínica` |
| Filtrar | `/leads status=qualified cidade="São Paulo" segmento=saúde` |
| Favoritos | `/leads salvos` |
| Arquivados | `/leads arquivados` |
| Próxima página (50 registros/página) | `/leads pagina=2` |
| Detalhes, fontes, pesquisas e histórico comercial | `/lead ID` |
| Guardar como favorito | `/save ID` |
| Alterar estágio | `/stage ID negotiating` |
| Editar observações | `/note ID Conversar na próxima sexta-feira` |
| Limpar observações | `/note ID -` |
| Corrigir dado | `/edit ID phone (19) 9999-0000` |
| Registrar resposta recebida | `/action ID response O usuário recebeu resposta por telefone` |
| Próxima ação | `/action ID next Validar o fluxo de agendamento` |
| Outra observação no histórico | `/action ID note Texto da observação` |
| Arquivar (pede sim/não) | `/archive ID` |
| Restaurar arquivo | `/restore ID` |
| Apagar definitivamente (confirmação existente) | `/forget ID` |
| Exportar apenas selecionados | `/export csv ID1,ID2` ou `/export json ID1,ID2` |
| Histórico de pesquisas | `/history`, `/history hoje` |

Estados comerciais: `new` (Novo lead), `qualified` (Qualificado), `contact_pending` (Contato pendente), `contacted` (Contatado), `negotiating` (Em negociação), `converted` (Convertido), `discarded` (Descartado). Pesquisar não marca contato ou negociação. Registrar contato/ação é uma anotação do usuário: o SAZABI não envia mensagens aos leads.

Campos editáveis: `phone`, `segment`, `city`, `address`, `description` e observações via `/note`. `-` limpa um campo. Edições são registradas no histórico; não alteram a data de verificação externa nem se tornam evidência de fonte pública. Site, identidade e ID não são editados por esse comando para evitar alterações silenciosas de identidade/deduplicação.

Arquivamento preserva fontes, notas, pesquisas e ações; retira o lead das listas ativas e recomendações. Descartar também é respeitado pela pesquisa. Exclusão definitiva remove os registros dependentes por foreign keys, após confirmação; use arquivar para conservar o histórico.

## Banco único e caminho estável

A entidade central continua sendo `companies`, identificada pelo UUID hexadecimal já existente. Não foi criada uma tabela paralela de leads. O banco padrão permanece `data/sazabi.db` junto ao projeto. `main.py`/`desktop.py` resolvem caminhos relativos a partir do projeto; `--db`/`DATABASE_PATH` mantêm a possibilidade de outro caminho. `.env` continua separado do banco e não é exportado.

| Estrutura | Responsabilidade |
|---|---|
| `companies` | Dados públicos e campos novos `commercial_status`, `notes`, `archived`; datas já existentes de criação/atualização/verificação. |
| `lead_events` | Identificação, migração, mudanças de estágio, edição com antes/depois, ações, arquivamento e restauração. |
| `duplicate_candidates` | Pares de IDs com evidência insuficiente para fusão; aparecem em `/leads` e `/lead`. |
| `sources` | Snapshot atual das observações. |
| `source_history` | Histórico das observações com URL, origem e data; não substitui o snapshot atual. |
| `signals`, `hypotheses` | Regras e oportunidades já existentes, sem inventar necessidades. |
| `research_runs`, `run_companies`, `discovery_results` | Execuções, vínculos com empresas, resultados identificados e páginas pendentes. |
| `saved_companies`, `ignored_companies` | Favoritos/ignorados existentes, mantidos compatíveis. |
| `schema_migrations` | Versões aplicadas e data de aplicação. |

`commercial_status` é o estágio comercial, enquanto o campo antigo `status` também representa estados de investigação/favorito. Contatado, convertido e descartado são sincronizados com os estados legados correspondentes. Pesquisas atualizam o cadastro sem escrever em notas, arquivamento ou estágio comercial. O score continua derivado das regras existentes, sem criar outra pontuação armazenada ou alegar probabilidade de compra.

## Migração e preservação

`database/migrations.py` aplica a versão **1** de forma aditiva e transacional. Não troca IDs nem recria cadastros. Antes de migrar uma base com registros, cria backup SQLite verificado em `backups/` ao lado do banco. Se backup/migração falhar, a aplicação informa falha de inicialização; não ignora o problema nem apaga a base.

A migração adiciona campos/tabelas/índices/trigger, copia as fontes atuais para o histórico e registra a preservação dos cadastros anteriores. Mapeia `CONTACTED` para `contacted`, `CLIENT` para `converted`, `DISCARDED` para `discarded`, `INTERESTING` para `qualified`; os demais começam em `new`, sem inferir contato. Notas antigas de favoritos são copiadas para as observações do lead e preservadas também no registro original. Reabrir a base não reaplica a migração. Versão de esquema mais recente que a suportada é rejeitada.

Os novos cadastros geram evento de identificação. Uma atualização de estágio, nota ou arquivamento e seu evento são gravados na mesma transação. A pesquisa usa transação por empresa para cadastro, vínculo e investigação: cancelamento/erro reverte a empresa incompleta; empresas já concluídas e execuções anteriores permanecem. Falhas de fontes registram resultado parcial e conservam evidência de descoberta e fontes antigas. As consultas parametrizam valores; campos editáveis vêm de uma lista fixa.

O SQLite permanece em WAL, com foreign keys e espera de bloqueio. O worker é proprietário da conexão. A transação por empresa pode manter o lock de escrita durante sua coleta: outra instância pode receber aviso de banco bloqueado e deve tentar novamente depois. Queda abrupta do processo reverte a transação incompleta via SQLite; uma execução interrompida abruptamente pode permanecer marcada `running`, sem ser reclassificada automaticamente como concluída. O teste de interrupção cobre cancelamento/erro cooperativo, não simulação de corte físico de energia.

## Deduplicação e atualização

Domínio próprio e telefone normalizados continuam critérios fortes. Para nome/localização, exige-se cidade conhecida e nome normalizado equivalente, sem conflito de endereço/domínio informado. Nome apenas semelhante não basta para fusão: é sinalizado para revisão. Variações de protocolo, `www`, maiúsculas, acentos e espaços são normalizadas conforme o identificador.

A atualização de empresa conhecida preenche dados faltantes pelo mecanismo existente, conserva campos já preenchidos, mantém referências a várias pesquisas e não altera notas/estágio por consequência de uma busca. Fontes antigas não são apagadas do histórico ao atualizar o snapshot. Pares suspeitos não são fundidos automaticamente nem removidos sem revisão; não foi criado botão de fusão destrutiva.

## Exportações locais

Os arquivos ficam em `exports/` ao lado do banco (normalmente `data/exports/`). O terminal mostra o caminho absoluto. Não existe seleção implícita de todos: IDs ausentes, desconhecidos ou ambíguos recusam a operação; IDs repetidos são deduplicados.

CSV usa UTF-8 com BOM, escaping pelo módulo `csv` e neutralização de células iniciadas por fórmulas. JSON usa UTF-8 e conserva acentos. Incluem dados do lead, estágio, notas, score indicativo, hipóteses, fontes/histórico, pesquisas e ações; estruturas aninhadas viram JSON nas células CSV. A exportação consulta somente campos/tabelas autorizados, nunca `.env`, configurações, cookies ou conversas gerais. Arquivos são escritos temporariamente e publicados por substituição atômica; falhas não produzem exportação parcialmente concluída.

## Backup e recuperação

Para criar um backup verificado:

```powershell
python main.py --backup
```

Para banco alternativo, use o mesmo `--db` empregado pela aplicação. O procedimento utiliza `sqlite3.Connection.backup()` e verifica `PRAGMA integrity_check`; inclui dados ainda no WAL. A conexão do arquivo de backup é fechada explicitamente, inclusive no Windows. Não copie apenas o `.db` enquanto o aplicativo estiver aberto.

Para recuperar:

1. Feche todas as instâncias do SAZABI e confirme que os workers encerraram.
2. Preserve o banco atual e eventuais arquivos `-wal`/`-shm` juntos em uma pasta separada, sem sobrescrever o backup escolhido.
3. Copie o `.db` do backup para o caminho configurado. Não deixe WAL/SHM de outra base ao lado da cópia restaurada.
4. Reabra o SAZABI. Backups anteriores à fase 2 serão migrados automaticamente; confirme os registros em `/leads` e `/history`.

Backups e exportações contêm dados comerciais locais; proteja a pasta com as permissões da conta Windows. Não há envio automático da base nem criptografia adicional introduzida nesta fase.

## Implementação e verificação

Arquivos principais: `database/migrations.py`, `database/leads.py`, `database/{database,repositories}.py`, `core/lead_commands.py`, `core/commands/{registry,router}.py`, `core/{agent,reports}.py`, `utils/deduplication.py`, `ui/{terminal,autocomplete}.py`. Testes: `tests/test_leads.py`, `tests/native_leads_check.py`, ajustes dos contratos em `tests/test_deduplication.py`, `tests/test_slash_skills.py` e `tests/native_desktop_check.py`.

As verificações usam bases isoladas e dados explicitamente sintéticos. Cobrem migração de esquema anterior com backup, idempotência, reinício, relacionamento pesquisa/empresa, estágios, notas, ações, filtros, favoritos, arquivamento, preservação comercial em nova pesquisa, duplicação suspeita, CSV/JSON selecionados, falha de gravação, banco bloqueado, cancelamento e evidências parciais. O teste Tk usa o worker real e verifica operações e exportação pelo terminal, além do encerramento e reabertura do banco.

A fase 2 não conecta um provedor gratuito: `/search` continua retornando `unconfigured` em produção quando falta um adaptador autorizado. O pipeline foi validado com fontes simuladas; não houve busca Tavily paga nem contato comercial real. `/research` e demais rotas legadas mantêm o provedor existente. `/ai` continua separado.

### Resultados finais desta fase

- Suíte completa: **211 passed**, em 25,29 s, com bancos e fontes de teste isolados.
- `python tests/native_leads_check.py`: **PASS** — operações no Tk/worker real, controles visíveis dentro da janela compacta, arquivo exportado, encerramento e dados recuperados ao reabrir SQLite.
- `python tests/native_audit_check.py`: **PASS** — bloqueio de repetição e aviso de fonte ausente em `/search`; rascunho/envio/reset do `/ai` com LAYLA simulada.
- `git diff --check`: sem erros.
- O roteiro geral de animações `native_desktop_check.py` não foi reexecutado nesta fase; sua limitação de foco registrada na auditoria anterior não foi declarada resolvida.
- A base real do usuário não foi usada nos testes nem migrada manualmente. A migração será aplicada automaticamente ao abrir esta versão do SAZABI.

Durante a validação, foi corrigido o fechamento da conexão de destino do backup: o context manager de SQLite sozinho não fechava o arquivo, causando bloqueio no Windows. Também foi ajustado o nome do backup de banco em memória, evitando `:` no nome de arquivo Windows. As verificações finais acima ocorreram após essas correções.
