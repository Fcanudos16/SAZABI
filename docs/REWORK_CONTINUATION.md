# Continuação do rework pessoal — 24/10/2026

## Escopo

Atende à solicitação de continuar pesquisa web, revisão e operações Git.
LAYLA está explicitamente fora desta etapa, por solicitação do usuário.
A interface, as configurações de integração, os sprites e os dados existentes
foram preservados. Não houve commit/push no repositório real do SAZABI.

## Implementação

### Pesquisa e documentos

- `research/knowledge.py`: adaptadores independentes Wikimedia e páginas HTTPS,
  reutilizando `utils/http_client.py` (TLS, IP público fixado e limites).
- `/research web "consulta"` consulta a API pública MediaWiki, sem chave ou API
  paga; retorna títulos, links, trechos e horário de obtenção.
- `/research url URL`: lê documentação pública, verifica robots.txt, revalida
  redirecionamentos e recusa HTTP, credenciais e respostas binárias.
- `/research summarize arquivo`: resumo extrativo local, sem upload.
- `/research compare fonte1 fonte2`: extratos referenciados e comparação de termos
  frequentes; não inventa capacidades nem recomenda um produto sem evidência.
- `KNOWLEDGE_WEB=disabled` bloqueia pesquisa/leitura web sem impedir funções
  locais; `KNOWLEDGE_LANGUAGE=pt|en` escolhe idioma da descoberta Wikimedia.
- Nenhuma conexão é iniciada apenas por abrir o SAZABI ou preencher uma chave.

Limites explícitos: Wikimedia não é um índice completo da web. Resumos são
extrativos, não sínteses semânticas por LLM. Leituras binárias/PDF não entram
neste adaptador. Fontes bloqueadas, indisponíveis ou malformadas geram falha real.

### Revisão e propostas

- `skills/code_review.py`: regras AST para defaults mutáveis, captura ampla,
  erros silenciados, eval/exec, shell=True, TLS desativado, APIs inseguras,
  SQL dinâmico e controle de fluxo em finally. Mostra regra, severidade,
  arquivo/linha, evidência e recomendação. Não importa/executa o código analisado.
- `/review fix arquivo.py bare-except` prepara uma alteração de comportamento
  explícita; `/review propose original candidato` aceita alterações preparadas
  pelo usuário. Ambos mostram diff completo e validam sintaxe Python candidata.
- A confirmação exige que o original continue igual. A substituição preserva
  cópia local `.sazabi-original-*`, oferece prévia inversa e nunca afirma que
  testes passaram sem executá-los. Restaurar original inválido é identificado
  como restauração, sem falsa alegação de correção/validação de sintaxe.
- Teste de integração reproduz falha em projeto temporário, aplica uma proposta
  confirmada e executa novamente o teste real, verificando mudança de exit code.

Limites: análise estática determinística, sem interpretação semântica geral;
achados são indícios contextualizados, não prova de vulnerabilidade. Correção
automática disponível somente para a transformação documentada; outras alterações
usam arquivo candidato e revisão. Concorrência de outro editor no último instante
da escrita não é isolada por lock.

### Git

- `skills/git_local.py`: leitura preservada; add de arquivos individuais,
  commit staged, criação de branch e sugestão de mensagem.
- Push/pull com nome de remoto, branch atual, URL e SHAs explícitos. A preparação
  apenas consulta o remoto. Toda mutação exige `/confirm TOKEN` de uso único.
- Prévia vinculada a hashes de HEAD, índice, configuração e arquivos. Alterações
  conhecidas invalidam a confirmação. Tokens expiram em cinco minutos.
- Push sem force, tags ou mirror. Pull por fetch seguido de fast-forward,
  com proteção a arquivos ignorados; árvore remota é validada antes da escrita.
  Fetch concluído sem atualização de checkout é registrado como parcial.
- Recusa filtros realmente ativos, submódulos, metadados redirecionados,
  locks/operações pendentes e caminhos protegidos. Instalação global do LFS
  sem uso nos arquivos não é tratada como filtro ativo.
- Hooks e assinatura de commit são desativados só para a invocação e isso aparece
  na prévia; configuração do usuário não é alterada.
- `core/processes.py`: executor compartilhado com cancelamento, ambiente reduzido,
  stdin fechado, argv sem shell, limite de tempo e de saída, inclusive para
  processos que terminam rapidamente com saída excessiva.

Limites: checkout Git normal para escrita, HTTPS sem credenciais na URL ou
remoto local autorizado. SSH, LFS ativo e worktrees/submódulos não são suportados
para mutação. Não há reset --hard, clean, exclusão de branch ou push forçado.
Autenticação Git HTTPS externa não foi validada; testes usam remoto bare local
real e não modificam um serviço externo.

## Evidência executada

- Primeira rodada das extensões: 37 aprovados e 8 falhas. As falhas de Git
  identificaram bloqueio excessivo por configuração global de LFS. Corrigido
  para verificar atributos de filtro aplicados aos arquivos.
- Segunda rodada: **18 testes de extensão aprovados**, 181,59 s, incluindo
  operações Git reais com remoto bare local, propostas, desfazer e contratos
  de pesquisa. Testes de transporte/parse usam respostas controladas, sem trocar
  implementações funcionais por mocks no produto.
- `python tests/knowledge_live_check.py`: **aprovado**, com acesso real à API
  Wikimedia em inglês e a `https://docs.python.org/3/library/pathlib.html`.
  Retornou resultados reais e documentação com referências. Não carregou .env,
  não enviou documentos locais e não chamou Tavily/Groq.
- `python tests/native_personal_check.py`: **aprovado** com Tk/worker reais,
  tarefa persistida durante a sessão, diff, confirmação que altera arquivo
  temporário, erros e geometria compacta. Captura
  `data/rework-review-preview.png` inspecionada: terminal preto/verde, sem
  barras brancas ou painel extrapolando a janela.
- Compilação dos módulos novos e `git diff --check` aprovados durante execução.
- `python run_tests.py`: **428 passed, 1 skipped, 16 subtests passed**,
  295,78 s. O skip corresponde à disponibilidade de Tk na execução restrita;
  o teste nativo separado foi executado e aprovado fora dessa restrição.
- Rodada final de extensões: **22 passed**, 221,39 s, incluindo pull divergente,
  preservação de arquivo ignorado, recusa de arquivo protegido e restauração
  honesta de um original com sintaxe inválida.
- Último endurecimento inclui atributos Git efetivos no fingerprint da prévia
  (inclusive `.git/info/attributes` e configuração global de atributos).
  Regressão direcionada: **5 passed, 18 deselected**, 29,65 s; confirmações
  recusadas após mudança de conteúdo, índice, configuração, HEAD ou atributos.
- Compilação final dos seis módulos e `git diff --check` aprovados. Nenhum diff
  em `assets` ou `integrations/layla` nesta continuação. As contagens acima são
  execuções distintas e não devem ser somadas como testes únicos.

## Arquivos e dependências

Novos: `core/processes.py`, `skills/git_local.py`, `skills/code_review.py`,
`research/knowledge.py`, `tests/test_personal_extensions.py`,
`tests/knowledge_live_check.py` e este relatório.

Atualizados: `skills/personal.py`, `core/config.py`, `.env.example`,
`tests/native_personal_check.py`, expectativas pessoais em
`tests/test_real_pipeline.py`, `README.md`, `docs/PERSONAL_GUIDE.md` e
referência de continuação em `docs/REWORK_REPORT.md`.

Sem dependências novas, instalação global, alteração de segredos ou exclusão
de dados. Alterações locais anteriores permanecem no checkout. O legado comercial
segue isolado do fluxo principal, ainda necessário por componentes/testes
preservados. Sua remoção física não foi confundida com apagar dados do usuário.

## Referências técnicas consultadas

- [MediaWiki — API Search](https://www.mediawiki.org/wiki/API:Search)
- [MediaWiki — API Etiquette](https://www.mediawiki.org/wiki/API:Etiquette)
- [Git — push](https://git-scm.com/docs/git-push)
- [Git — merge, fast-forward e proteção a arquivos ignorados](https://git-scm.com/docs/git-merge)

As funcionalidades acima estão integradas ao registro, worker, terminal e
histórico existentes. A LAYLA permanece preservada e adiada; não é necessária
para nenhum desses fluxos locais/públicos.
