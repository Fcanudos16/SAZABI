# SAZABI pessoal — operação local

## Inicialização no Windows

Python com Tcl/Tk; dependência de execução já existente: psutil. pytest é usado
pelos testes. Nenhuma dependência foi adicionada pelo rework. Se já houver venv,
ative-o com `.venv\Scripts\activate` no CMD. Neste checkout não foi encontrado
venv; os testes reutilizam Python instalado e `.test-deps` via `run_tests.py`.

```cmd
cd /d "C:\Users\sandinilson\Downloads\Farelinho coisas\SAZABI"
python main.py
python main.py --cli
python main.py -c "/help"
python run_tests.py
python tests\native_personal_check.py
```

Uma instalação nova pode usar `python -m venv .venv`, ativar o ambiente e
`python -m pip install -r requirements.txt`. Não é necessário fazê-lo em um
ambiente existente que já funciona. `iniciar_sazabi.cmd` permanece disponível.

## Comandos reais

| Comando | Função |
| --- | --- |
| `/task add "Título" priority=alta due=2026-12-31 category=casa project=Casa` | Criar tarefa |
| `/task list pending` ou `overdue` ou `all` | Consultar tarefas |
| `/task edit 1 title="Novo título"` | Alterar título; também aceita os campos acima |
| `/task done 1` | Concluir tarefa |
| `/task export tarefas.json` | Exportar, recusando sobrescrita |
| `/files find . name=texto ext=.py min=0 max=100000 after=2026-01-01` | Filtrar arquivos |
| `/files duplicates .` | Duplicatas por tamanho e SHA-256 |
| `/files organize pasta` | Prévia por extensão, apenas filhos diretos |
| `/files move "origem" "destino"` | Prévia para mover ou renomear arquivo |
| `/confirm TOKEN` / `/cancel TOKEN` | Consumir ou descartar prévia específica |
| `/project .` | Inventário e arquivos de dependências |
| `/review .` | Riscos Python com arquivo/linha e recomendação |
| `/review fix arquivo.py bare-except` | Prévia de troca de except sem tipo por Exception |
| `/review propose original.py candidato.py` | Diff completo da versão candidata, sem aplicação automática |
| `/test pasta` | Prévia: run_tests.py, pytest.ini ou unittest discover |
| `/git status .`, `branches`, `log`, `diff` | Git somente leitura |
| `/git add pasta arquivo` | Prévia de staging de arquivos individuais |
| `/git commit pasta "Mensagem"` | Prévia e confirmação do commit staged |
| `/git branch pasta codex/nome` | Criar branch local sem trocar o checkout |
| `/git message pasta` | Sugestão determinística de mensagem pelos arquivos staged |
| `/git push pasta origin main` | Publicar a branch atual após confirmação |
| `/git pull pasta origin main` | Fetch e atualização fast-forward após confirmação |
| `/run` / `/run nome` | Listar/preparar rotina explicitamente configurada |
| `/research "termo" .` / `/search "termo" .` | Trechos locais referenciados |
| `/research web "consulta"` | Descoberta Wikimedia com título, link e trecho |
| `/research url https://docs.python.org/3/library/pathlib.html` | Leitura pública e resumo extrativo |
| `/research summarize arquivo.md` | Resumo extrativo local, sem upload |
| `/research compare fonte1 fonte2` | Comparação documental de arquivos/URLs |
| `/history` / `/settings` / `/backup` | Histórico, limites e backup verificado |
| `/ai` | Terminal LAYLA existente, envio manual |

`project` nas tarefas representa uma lista/projeto por nome, sem entidade de
projeto separada. A revisão estática não é uma revisão semântica completa nem
correção automática. Pesquisa local aceita md, txt, py, rst e log até 1 MB,
apresentando até 50 trechos. Resumos selecionam trechos com origem/linha,
sem inventar fatos. A comparação mostra extratos e termos frequentes, não
declara qual biblioteca é superior. Linhas web pertencem ao texto extraído.

## Permissões e configuração

Configure somente no `.env` e reinicie:

```dotenv
LOCAL_ROOTS=C:\Users\SeuUsuario\Documents\Projetos;C:\Users\SeuUsuario\Downloads\Organizar
LOCAL_ROUTINES_JSON={"verificar":{"argv":["C:/Python/python.exe","check.py"],"cwd":"C:/Users/SeuUsuario/Documents/Projetos"}}
KNOWLEDGE_WEB=wikimedia
KNOWLEDGE_LANGUAGE=pt
```

Use caminhos reais do seu computador. Sem LOCAL_ROOTS, somente a pasta do SAZABI
é autorizada. Há recusa de caminhos externos, UNC, links/junctions, .git, .env,
credenciais usuais e banco/log ativos. Pastas ocultas e ambientes/dependências
são ignorados em buscas. Inventário limitado a 5.000 arquivos, hashes a 100 MB
por arquivo, organização a 100 itens. Caminhos com espaços exigem aspas.

Prévia identifica origem/destino ou argv/cwd; token é de uso único, dura cinco
minutos e não sobrevive à reinicialização. Arquivos alterados invalidam a prévia.
Movimentos não sobrescrevem destino e produzem uma prévia inversa para desfazer.
Falhas parciais registram movimentos já executados; não fingem atomicidade.
Nenhum comando de exclusão permanente é oferecido.

Testes/rotinas executam código com os privilégios do usuário, **não em sandbox**.
Confirme apenas código confiável. Podem acessar a rede e arquivos fora das raízes:
as raízes restringem as operações do SAZABI, não o código aprovado. A execução
usa argv sem shell, entrada fechada, ambiente reduzido, limite de 60 segundos e
limite monitorado de saída de 1 MB; exibição truncada em 16 KB. Prévia compara
código/configuração antes da execução; não protege dependências externas nem
alterações concorrentes após a verificação. Processos destacados pelo próprio
script não são uma fronteira de isolamento garantida.

## Persistência e recuperação

Tarefas e operações usam `personal_tasks` e `personal_operations` no mesmo SQLite.
Planos/runs interrompidos são marcados como falha ao abrir nova sessão. Histórico
mostra até 30 operações e guarda resultado limitado a 12 KB, com redação de
padrões de segredo. Não guarda o comando bruto. O SQLite continua sendo dado
privado local, sem criptografia de conteúdo pessoal. Não insira segredos em tarefas.

`/backup` usa backup SQLite com checagem de integridade. Restauração reutiliza
`scripts/restore_backup.py`: feche o SAZABI, consulte `--help` e forneça `--db`
e `--backup`. O utilitário existente solicita confirmação e guarda cópia rescue.

## LAYLA e serviços opcionais

Bridge existente preservada: conexão loopback, sessão/CSRF e contrato Mark 5
observado no cliente. `/ai` abre rascunho; envio ocorre explicitamente no terminal.
O SAZABI não anexa arquivos, histórico nem credenciais automaticamente e não
executa a resposta recebida. Testes do bridge usam servidor de contrato local;
isso não valida uma instalação LAYLA real ou seus provedores.

Tavily/Groq comerciais estão fora do fluxo pessoal. `/search` não chama esses
provedores. O adaptador Wikimedia usa a API pública documentada para descoberta
enciclopédica; não é um índice completo da web nem garante fontes primárias.
Use `url` com a documentação oficial para verificar detalhes técnicos. Nenhum
arquivo local é enviado. `KNOWLEDGE_WEB=disabled` bloqueia ambos os modos web;
o núcleo e os documentos locais continuam funcionando. Leitura HTTPS revalida
redirecionamentos, respeita robots.txt e usa o transporte existente com IP público
fixado, TLS e limite de 1 MB. Falhas de acesso são mostradas sem resultados fictícios.

## Revisão e alterações

Regras: sintaxe, eval/exec, defaults mutáveis, except amplo/silencioso, shell=True,
TLS desativado, APIs inseguras, SQL dinâmico e controle de fluxo em finally.
São indícios que precisam de contexto; não são uma auditoria semântica completa.
Nenhum código do projeto é importado para revisá-lo. A proposta `bare-except`
muda o tratamento de KeyboardInterrupt/SystemExit; confira se faz sentido.
`propose` aceita um arquivo candidato já preparado, valida sintaxe Python e
mostra diff completo limitado a 14.000 caracteres. Não usa um modelo externo.

Ao confirmar, o arquivo precisa continuar igual à prévia. A gravação usa um
temporário e substituição, conserva cópia `.sazabi-original-*` no mesmo diretório
e oferece confirmação inversa para desfazer. Cópias são locais, não são apagadas
automaticamente e devem ser tratadas como privadas. Uma alteração aplicada não
é um bug corrigido: use `/test` e confira a saída/exit code. Escritas concorrentes
durante a última verificação não são isoladas por um lock do editor.

## Git protegido

Informe a raiz exata do checkout. Escrita usa confirmação de cinco minutos
vinculada a HEAD, índice, configuração e hashes dos arquivos. Alterações
conhecidas invalidam a prévia; recusa locks, merges/rebases pendentes, paths
protegidos, links/submódulos e filtros ativos. A simples instalação global do
LFS não bloqueia arquivos que não usam LFS. `add` aceita arquivos explícitos,
sem pasta inteira, force ou curingas. `commit` mostra o diff staged e não faz
staging automático. Hooks e assinatura de commit são desativados **nessa
invocação** e informados na prévia; nenhuma configuração Git é modificada.

Push/pull exigem nome de remoto configurado e a branch local atual. A preparação
consulta o HEAD remoto, mostra URL e SHAs e não publica nada. A confirmação
revalida o remoto. Push usa apenas uma branch, sem force nem tags. Pull exige
índice/árvore limpos; faz fetch, confirma o SHA e só então tenta fast-forward,
protegendo arquivos ignorados. Se fetch ocorreu mas o checkout não pôde avançar,
o resultado é parcial. Revise `/git status` antes de repetir.

Suporte remoto: HTTPS sem credenciais na URL, usando a autenticação Git já
configurada, ou repositório local dentro das raízes autorizadas. SSH, remotos
múltiplos, LFS ativo, submódulos e worktrees de escrita são recusados; use seu
cliente Git para esses fluxos. Não há reset --hard, clean, exclusão de branch,
rebase ou push forçado. Testes automatizados usam remotos bare locais reais;
não comprovam autenticação HTTPS em um serviço externo.

## Arquitetura e extensão

Parser/CommandRegistry/SkillRegistry/SkillResult e worker existentes continuam
sendo o caminho único da interface. `skills/personal.py` registra habilidades
explícitas; `core/local_policy.py` controla caminhos e `database/personal.py`
persiste dados no banco existente. Para acrescentar habilidade, implemente seu
execute(query, context), valide parâmetros/permissões, retorne SkillResult,
registre explicitamente e crie testes de integração com DB/pastas temporários.
Não use descoberta dinâmica, eval ou execução automática de respostas externas.

Legado comercial fica fora do registro padrão e da manutenção automática.
`legacy_commercial` é um parâmetro interno usado pelo harness de regressão;
não existe opção .env nem menu para ativá-lo. Módulos e dados antigos ainda
existem porque há dependências compartilhadas; não foram apagados indiscriminadamente.
