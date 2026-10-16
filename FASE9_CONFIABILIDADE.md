# Fase 9 — confiabilidade operacional

## Auditoria e decisões

A implementação reutiliza o worker serial, os repositórios SQLite, o cancelamento cooperativo, as notificações e o terminal nativo. Não cria serviço externo ou processo permanente.

Riscos concretos encontrados e tratados:

- Uma falha no backup inicial impedia abrir o desktop: agora é registrada e o histórico permanece acessível quando o banco está utilizável.
- Backups sem retenção limitada: agora são publicados após validação, com limpeza das cópias excedentes somente após sucesso.
- Duas sessões podiam disputar o mesmo banco: desktop e CLI mantêm um bloqueio de sessão liberado pelo sistema operacional ao sair.
- Pesquisas abandonadas eram indistinguíveis de falhas comuns: a recuperação marca execuções em andamento como `interrupted`, preservando os dados já confirmados. Atualização periódica abandonada fica `unknown`, sem repetição automática.
- Logs já tinham rotação, mas faltavam padrões de mascaramento: foram adicionados Groq, credenciais em URLs, parâmetros e JSON com segredos.
- Manutenção e chegada de comandos poderiam disputar o cancelamento: a seleção de manutenção usa o mesmo bloqueio de submissão; comandos interrompem cooperativamente a manutenção.

Timeouts, validação de URLs/SSRF, robots, cache, limites de consultas, tratamento de fontes e integração LAYLA existentes foram preservados. GET tem retentativas limitadas; POST não recebe repetição automática indiscriminada.

## Uso

Iniciar, no CMD:

```bat
cd /d "C:\Users\sandinilson\Downloads\Farelinho coisas\SAZABI"
python main.py
```

No terminal do SAZABI:

| Comando | Resultado |
|---|---|
| `/health` | Resumo operacional, integrações configuradas, últimas operações |
| `/diagnostics` | Mesmo diagnóstico sem consultas, nomes dos leads ou chaves |
| `/backup` | Cria e valida uma cópia do banco |
| `/backups` | Lista cópias e orienta a restauração offline |
| `/integrity` | Verifica integridade e referências do SQLite |
| `/maintenance` | Mostra opções persistidas |
| `/maintenance refresh-status ID` | Última tentativa, sucesso, falhas e próxima tentativa do lead |
| `/maintenance reset-refresh ID` | Libera novas tentativas após revisão manual |

Há botões Saúde, Backup e Manutenção no terminal. O cronômetro da pesquisa continua restrito à pesquisa; comandos administrativos não o exibem.

Exemplos de configuração (valores JSON):

```text
/maintenance set auto_backup true
/maintenance set backup_hours 24
/maintenance set retention 10
/maintenance set notifications true
/maintenance set due_alerts true
/maintenance set due_days 1
/maintenance set auto_refresh true
/maintenance set refresh_minutes 60
/maintenance set stale_days 14
```

Padrões: backup automático ligado, intervalo de 24 horas entre tentativas, 10 cópias; notificações ligadas; alertas de prazo e atualização periódica desligados. A preferência visual de notificações da interface também é respeitada. Configurações ficam em `settings` (`ops.*`); credenciais continuam no `.env`.

A verificação de manutenção acontece aproximadamente a cada 30 segundos de ociosidade do desktop. Não interrompe uma pesquisa para cumprir horário. CLI faz somente a manutenção inicial, sem ciclo periódico. Modo mock não executa manutenção automática no worker. Ao fechar o aplicativo, não há novas tarefas agendadas; cancelamento aguarda os limites das operações em andamento.

## Backups e recuperação

O banco padrão é `data/sazabi.db`; `DATABASE_PATH` ou `--db` podem alterar esse local. Cópias ficam em `backups` ao lado do banco, com nome e data UTC. O backup usa a API transacional SQLite, verifica integridade e chaves estrangeiras e só então publica o arquivo `.db`. Arquivos `.pending` não são cópias concluídas. Falhas preservam cópias anteriores. A transferência tem limite de 30 segundos, além do tempo de validação.

Para restaurar, feche todas as instâncias do SAZABI e ferramentas que usem esse banco. Escolha o arquivo real listado por `/backups`; substitua o nome ilustrativo abaixo:

```bat
cd /d "C:\Users\sandinilson\Downloads\Farelinho coisas\SAZABI"
python scripts\restore_backup.py --db "data\sazabi.db" --backup "data\backups\sazabi_DATA_HORA.db"
```

O utilitário valida a cópia, mostra os caminhos e exige digitar `RESTAURAR`. Antes de substituir dados, cria uma cópia validada do estado atual em `rescue`, ao lado do banco. Essa pasta não participa da retenção automática. O log da recuperação fica em `logs/recovery.log` ao lado do banco. Arquivos de outra aplicação, corrompidos ou de versão futura são recusados. Backups antigos sem as tabelas exigidas também são recusados.

Se o banco atual estiver corrompido a ponto de não permitir a cópia de resgate, a restauração sobre ele é recusada. Nesse caso, restaure para um novo caminho, por exemplo `--db "data\sazabi_recuperado.db"`, abra com `python main.py --db "data\sazabi_recuperado.db"` e confira os dados. Preserve o banco original e seus arquivos auxiliares para investigação. Não é necessário apagar arquivos `.session.lock`: o bloqueio ativo pertence ao sistema operacional.

Backups cobrem o banco (leads, notas, tarefas, histórico e configurações nele persistidas), não o `.env`, arquivos de perfil/serviços ou imagens do projeto. Não incluem automaticamente credenciais externas; textos privados já gravados no banco continuam presentes nas cópias. Mantenha esses arquivos em armazenamento privado. O ajuste de modo do arquivo não equivale a criptografia nem garante uma ACL NTFS exclusiva no Windows.

## Falhas, alertas e atualização opcional

Pesquisas interrompidas podem ser consultadas no histórico e repetidas explicitamente depois de revisar resultados persistidos. Atualizações abandonadas exigem revisão e `reset-refresh`. Não há retomada cega nem promessa de execução após encerrar.

Atualização periódica seleciona no máximo um lead por intervalo: não arquivado, não convertido/descartado, com site e dados além do prazo configurado. Reutiliza a investigação existente com atualização explícita. Preserva notas, estágio, tarefas e contexto da conversa. Registra tentativa, sucesso, resultado parcial, observações antigas não reconfirmadas e próxima tentativa. Falha de consulta não significa empresa inativa. Após três falhas, suspende aquele lead; o atraso aumenta entre tentativas. Atualizações de sites podem gerar tráfego nas fontes quando ativadas.

Alertas de backup são deduplicados por dia; tarefas por ID e vencimento, com até três avisos por ciclo. O histórico de deduplicação guarda até 500 chaves, portanto não promete supressão eterna após esse limite. O diário operacional mantém 100 eventos; `/health` mostra os últimos 10.

Logs usam rotação de 1 MB com três arquivos anteriores. Identificadores de execução permitem relacionar início, fim e erros sem registrar a consulta completa nesses eventos. Mascaramento reduz exposição de padrões conhecidos; revise diagnósticos antes de compartilhá-los. Saúde indica configuração das integrações, não conectividade comprovada. O tempo médio usa somente pesquisas concluídas/parciais com duração válida e informa o tamanho da amostra.

## Manutenção do projeto

Antes de atualizar o código, crie `/backup`, confira `/integrity`, encerre o SAZABI e preserve separadamente as configurações locais necessárias. Instale apenas dependências previstas pelo projeto. Após atualizar, inicie, consulte `/health`, confirme a migração e confira alguns leads e tarefas. Para voltar a uma versão anterior, use código e backup de esquema compatíveis; não force um banco de versão futura em código antigo.

Se a aplicação não iniciar: consulte `logs/sazabi.log`, verifique permissões, espaço e configuração; outra sessão com o mesmo banco deve ser encerrada normalmente. Falhas de fonte/limite de API devem ser resolvidas antes de repetir pesquisas. Não é necessário habilitar atualização periódica para usar os backups.

## Arquivos desta fase

- `core/maintenance.py`, `core/maintenance_commands.py`: manutenção, métricas, alertas e comandos.
- `database/database.py`, `database/restore.py`, `database/recovery.py`: backup, restauração e bloqueios/recuperação.
- `scripts/restore_backup.py`: confirmação e recuperação fora da interface.
- `core/worker.py`, `main.py`: ciclo de sessão e encerramento.
- `core/agent.py`, `utils/logger.py`: correlação e proteção de logs/entradas de segredos.
- `core/commands/registry.py`, `core/commands/router.py`, `ui/companion.py`, `ui/terminal.py`: integração dos comandos e avisos.
- `.gitignore`, `tests/test_phase4.py`, `tests/test_phase9_maintenance.py`, `tests/native_phase9_check.py`: bloqueios ignorados e validação.

## Validação e limites

Resultado em 16/10/2026: `python -m pytest -q -p no:cacheprovider` — **365 testes e 16 subtestes aprovados**. `python tests/native_phase9_check.py` e `python tests/native_countdown_check.py` aprovados; `git diff --check` sem erros. A execução precisou sair do sandbox porque ele impedia criar os bancos temporários. Nenhum banco de produção foi usado para restauração de teste.

Os testes de backup/restauração usam bancos descartáveis. Incluem retenção, publicação com falha, cópia de resgate, confirmação, bloqueio de sessão, arquivos inválidos, integridade, falha no backup inicial, retentativas limitadas, contexto comercial preservado, cancelamento, deduplicação, redação e rotação de logs. A suíte existente cobre também fontes, concorrência e recuperação de pesquisas.

Teste nativo: backup, integridade, erro de gravação simulado, recuperação para `/health`, configuração, botões e fechamento do worker. Evidência visual: `data/phase9/health.png`.

Não foram simuladas queda física de energia, falha real de disco, corrupção durante uma escrita do sistema operacional ou execução prolongada por vários dias. Testes sintéticos não comprovam disponibilidade atual de Groq, Tavily ou LAYLA. Os bloqueios protegem os pontos de entrada do SAZABI; ferramentas externas que ignoram esses bloqueios continuam exigindo cuidado. Não há garantia de sistema infalível.
