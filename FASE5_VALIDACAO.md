# SAZABI — Fase 5: validação real da prospecção

Avaliação realizada em 15–16/10/2026 (America/Sao_Paulo). Os arquivos de evidência usam UTC. A prospecção funciona com limitações de cobertura e de identificação. Esta avaliação não comprova demanda comercial, intenção de compra ou probabilidade de venda.

## Método e escopo

Foi auditado o fluxo existente: comando `/search`, Search Skill, `CompanyFinder`, fonte Tavily/site público, normalização e deduplicação, investigação, SQLite e qualificação determinística. A implementação foi mantida. Groq não foi usado para inventar ou preencher informações da amostra.

Foram feitas três consultas reais, com limite de dez resultados cada: clínicas, oficinas mecânicas e pet shops em São Paulo, capital. A Tavily já autorizada forneceu os links; as páginas foram acessadas pelo coletor existente, respeitando robots.txt, limites de tamanho, timeout e intervalos. Não foram adicionados provedores pagos ou dependências.

As respostas e páginas analisadas foram congeladas em `data/phase5/capture.json`. A comparação anterior/posterior usa exatamente essa captura, sem novas consultas, evitando atribuir mudanças do buscador às correções. O replay mantém as datas originais das observações. A consulta construída pelo código novo não é enviada à rede no replay: portanto ele mede extração, tratamento de erros e classificação, não a precisão da nova consulta.

Cada execução usa um SQLite novo em `data/phase5`, sem notificações e sem escrever no banco operacional. O banco de auditoria foi fechado e reaberto em modo de leitura para verificar persistência. A repetição adicional da primeira consulta foi exclusivamente offline.

## Amostra e revisão individual

A meta exploratória de aproximadamente 20–30 empresas **não foi alcançada**: houve 29 resultados de busca, mas somente 16 negócios identificáveis por suas próprias páginas. Não se contabilizaram redes sociais bloqueadas ou o publicador de uma matéria como empresas verificadas.

A revisão individual está em [review.csv](reports/phase5/review.csv), com URL original, data de acesso, decisão, identidade e justificativa por resultado. Os cálculos reproduzíveis estão em [metrics.json](reports/phase5/metrics.json).

“Identidade” significa nome/autodeclaração observada no próprio domínio; não houve validação independente de CNPJ, propriedade do domínio, situação cadastral ou atividade atual. Data de consulta não significa data de atualização do conteúdo ou de ocorrência de um evento.

| Indicador | Resultado | Denominador e interpretação |
|---|---:|---|
| Resultados de busca | 29 | 10 clínicas, 9 oficinas, 10 pet shops |
| Páginas utilizáveis | 17/29 (58,62%) | HTML acessível, incluindo uma matéria editorial |
| Negócios com identidade autodeclarada | 16/29 (55,17%) | Exclui a matéria e os 12 acessos indisponíveis |
| Candidatos com localização e segmento sustentados na revisão | 8/29 (27,59%) | Localidade declarada no site, sem confirmação cadastral independente |
| Dados insuficientes | 16/29 (55,17%) | 12 páginas indisponíveis + 4 localidades ambíguas/conflitantes |
| Descartes na revisão | 5/29 (17,24%) | 4 fora do município/país + 1 publicador editorial |
| URLs duplicadas | 0/29 (0%) | Não demonstra ausência de duplicação entre empresas inacessíveis |
| Empresas extraídas automaticamente | 7 antes; 5 depois | Mesma captura; cinco não equivalem a cinco leads aprovados |
| Empresas extraídas com hipótese comercial | 3/5 (60%) | Evidência de múltiplas unidades; necessidade não comprovada |
| Necessidades comerciais verificadas | 0 | Sem contato, entrevista ou confirmação operacional |
| Média da pesquisa real inicial | 30,60 segundos | Três pesquisas: 37,05; 34,21; 20,54 segundos |

As categorias de revisão se repartem em 8 locais + 5 descartados + 16 insuficientes = 29. O indicador de identidade se sobrepõe a essas categorias: uma empresa de Portugal pode ter identidade observável e ser descartada por localização.

### Empresas examinadas

| Empresa autodeclarada | Resultado de localização/identidade | Utilidade comercial observada |
|---|---|---|
| Policlínica São Paulo | Beja, Portugal; descartar | Fora da região |
| Clínica São Paulo | Mogi das Cruzes/SP; descartar | Fora da capital |
| Clínica Dentária São Paulo | Lisboa, Portugal; descartar | Falso positivo do nome corrigido |
| Centro Médico Doutor São Paulo | Declara Zona Leste de São Paulo | Identidade não extraída automaticamente; necessidade não confirmada |
| Clínica da Cidade — Tatuapé | Unidade São Paulo/SP; distinguir matriz Campinas | Múltiplas unidades permitem explorar integração; não comprovam problema |
| Centro Médico Cirúrgico São Paulo | Nova Iguaçu/RJ; descartar | Fora da região; texto com problemas de codificação |
| Clínica São Francisco | Endereços em São Paulo | Já anuncia agendamento online; extração de identidade pendente |
| Riveros | AutoRepair, São Paulo/SP | Já anuncia agendamento online; recomendação contraditória removida |
| Auto Mecânica do Vale | Endereço Zona Oeste, São Paulo/SP | Nome publicitário longo impede extração conservadora; necessidade desconhecida |
| Stradale | Três endereços em São Paulo/SP | Possível integração entre unidades, sem dor confirmada |
| High Torque | Nome observado; distritos/UF sem município explícito | Localização exige revisão antes de prospecção |
| Petlove / Petsupermarket | Identidade societária e lojas em São Paulo | Sem hipótese relevante sustentada; porte/aderência precisam de revisão |
| Breeds | Identidade observada; “SP” ambíguo | Comércio online existente; localização insuficiente |
| Pet Life | Nome, ruas e bairros observados | Município não confirmado; não inferir apenas pelo bairro |
| Cobasi | Schema São Paulo; rodapé legal Barueri/SP | Hipótese multiunidade é exploratória; conflito de matriz/unidade pendente |
| Bem Locão | Metadados de endereço São Paulo/SP | Identidade não extraída automaticamente; necessidade desconhecida |

O publicador Exame foi revisado separadamente como página editorial. As outras 12 entradas têm fonte indisponível e não receberam identidade confirmada a partir do snippet da Tavily.

## Erros encontrados e correções

1. **Falhas de páginas apareciam como pesquisa completa.** Erros por URL e advertências do provedor agora chegam ao finder/investigator e ao status da pesquisa. As três execuções da captura passaram de `completed` para `partial`. Uma página complementar indisponível preserva evidência válida da principal e registra a limitação.
2. **A cidade no nome era confundida com localização.** O extrator exige localidade publicada; normaliza sufixos explícitos como `/SP`, `, Brasil` e `, capital`, sem atribuir a cidade solicitada quando não há evidência. Clínica em Lisboa deixou de entrar como candidata da capital.
3. **Objeto genérico de uma organização prevalecia sobre unidade local.** Dados estruturados com endereço e tipo local têm preferência. A clínica Tatuapé e a oficina Riveros mantêm segmento e localização declarados. Nome da unidade é combinado com a marca quando necessário; entidades HTML são decodificadas.
4. **Artigo de imprensa virava empresa prospectada.** Páginas editoriais estruturadas não são convertidas em prospect pelo nome do publicador. A política é conservadora e pode deixar páginas de blog oficial pendentes.
5. **Agendamento já online gerava proposta de digitalização do agendamento.** Evidência positiva de canal existente suprime a hipótese correspondente e aparece como fator contrário na qualificação. Riveros passou de 48 para 20 pontos e perdeu essa recomendação.
6. **Links genéricos de carreira e inaugurações históricas aumentavam a pontuação.** Regras de contratação/expansão agora exigem expressões mais específicas. Mesmo assim, expressões sem data continuam exigindo revisão de atualidade.
7. **Resultados malformados podiam parecer busca vazia.** Respostas inválidas falham explicitamente; listas mistas preservam os válidos e registram os rejeitados. Consulta legitimamente vazia continua distinguida de falha técnica.
8. **Consulta pouco específica favorecia nomes semelhantes.** A consulta mantém “São Paulo”, explicita cidade/UF e usa “oficinas mecânicas” no lugar de “oficina”; a palavra isolada “Brasil” foi retirada após um smoke retornar a marca Oficina Brasil. Precisão final deve ser medida em novas amostras, não presumida pelo replay.

O mecanismo de qualificação foi versionado como `commercial-2` para invalidar resultados de avaliação antigos quando recalculados. Os registros operacionais anteriores não foram apagados nem corrigidos automaticamente em massa.

## Classificação e limites remanescentes

No replay, Clínica da Cidade e Cobasi ficaram com 53 pontos, Stradale 48 (moderados), Riveros 20 e Petlove 15 (baixos). As três recomendações exploram múltiplas unidades. Isso comprova apenas uma característica da operação, não ausência de integração, orçamento disponível ou interesse de compra.

Cobasi permanece aceita pelo extrator com o endereço estruturado em São Paulo, mas a revisão sinalizou conflito com o rodapé de Barueri. Deve ficar pendente de aprovação humana. A extração automática cobre quatro dos oito candidatos locais revisados; outros quatro exigem leitura manual por falta de identidade estruturada aceita. Essas limitações estão documentadas, sem preenchimento inventado.

O perfil utilizado mantém os serviços configurados, sem filtros de porte/localidade/segmento prioritário suficientemente específicos para eliminar grandes varejistas. Pontuação de compatibilidade de serviço não substitui aprovação do perfil de cliente ideal. Contatos, tamanho da equipe, situação financeira, sistemas internos e intenção de compra não encontrados permanecem desconhecidos.

## Falhas, testes e persistência

Suíte final: `python -m pytest -q -p no:cacheprovider` — **330 testes aprovados e 16 subtestes aprovados**, em 48,68 segundos. Os 21 casos da Fase 5 também passaram isoladamente. `git diff --check` passou. O cache do pytest foi desativado nessa execução porque uma execução anterior, também aprovada, apresentou advertência de permissão no diretório de cache.

Na amostra real: 8 recusas por robots.txt, 2 acessos recusados pela fonte e 2 respostas descompactadas acima do limite. Não foram contornados os bloqueios. Snippets não foram promovidos a fatos verificados.

- `tests/test_phase5_quality.py`: casos sintéticos explicitamente identificados; localização, unidade local, publicador, fonte indisponível, resposta vazia, campos ausentes, conteúdo inválido, lista mista, rate limit 429, erro de gravação, canais existentes, sinais genéricos e página complementar indisponível.
- `tests/test_backend_recovery.py`, `test_phase4.py`, `test_slash_skills.py`, `test_deduplication.py` e `test_agent_flow.py`: rollback, cancelamento, timeout, recuperação, deduplicação e persistência.
- Teste nativo `python tests/native_countdown_check.py`: PASS para timer manual, comandos, alerta, escala e pesquisa com sucesso/cancelamento/falha/timeout/região, ocultação/reabertura e menu. A exceção sintética impressa é intencional nesse teste, não uma falha real da coleta.
- Repetição offline da consulta de clínicas: 1 encontrada, 0 novas, 1 já conhecida. O banco permaneceu com 5 empresas e 398 observações/fontes. Após fechar/reabrir: 4 pesquisas, 39 resultados de descoberta e 5 avaliações; contagens idênticas.

O tempo de replay não deve ser comparado ao tempo de rede como ganho de desempenho. Os testes sintéticos não entram nas métricas da amostra real. O cronômetro manual e o cronômetro exclusivo do terminal foram preservados.

### Consultas reais complementares

Separadas dos denominadores da amostra inicial:

- Consulta intermediária: 3 páginas, nenhuma empresa extraída, 8,70 segundos, `partial`. Duas páginas da marca Oficina Brasil estavam bloqueadas e a terceira tinha localidade insuficiente. Demonstrou necessidade de melhorar os termos da consulta.
- Consulta final corrigida, em 16/10/2026: 10 páginas, 1 oficina identificada (Riveros, São Paulo), 78,75 segundos, `partial`. Persistiu 1 empresa, 109 observações/fontes, 1 pesquisa, 10 resultados e 1 avaliação, com contagens verificadas após reabertura. Foram registrados um limite de tamanho, uma falha de conexão, uma recusa de acesso e um bloqueio por robots.txt. As demais páginas ficaram pendentes por identidade/localização ou classificação editorial. Nenhuma oportunidade comercial foi gerada para a oficina que já anuncia agendamento online.

Essa consulta confirma funcionamento real após as correções, mas uma única consulta não comprova ganho generalizável de precisão. Um site de oficina classificado como editorial ficou pendente, mostrando o custo da regra conservadora. O limite de pesquisa foi elevado para 600 segundos somente no processo de auditoria; a configuração operacional de 180 segundos foi preservada. A coleta final terminou abaixo de ambos.

## Reprodução e artefatos

Na pasta do projeto, em PowerShell ou CMD:

```text
python scripts/phase5_audit.py --mode replay --capture data/phase5/capture.json --output data/phase5/after-final.json --repeat-first
python scripts/phase5_review.py
python -m pytest -q -p no:cacheprovider
python tests/native_countdown_check.py
```

Os dois primeiros comandos não acessam a rede. `phase5_review.py` contém as decisões de revisão explícitas e recalcula denominadores. A captura inicial tem SHA-256 `71afc22e5411d784f0d9ce13877c405d83bb97cbefcd2bbcc743b1942fc5ecd0`.

Artefatos locais: `data/phase5/capture.json` (respostas/páginas), `baseline.json` (antes), `after-final.json` (replay corrigido e banco utilizado), `smoke-live.json` (consulta intermediária real), `smoke-final-capture.json` e `smoke-final.json` (consulta final real). A pasta `data` é ignorada pelo Git; é necessário conservar esses arquivos para reproduzir a mesma amostra em outra máquina. Datas, URLs e trechos estão nas observações; não há chaves de API nos relatórios.

Para **nova coleta**, que consome créditos Tavily e pode retornar outra amostra:

```text
python scripts/phase5_audit.py --mode live --capture data/phase5/nova-captura.json --output data/phase5/nova-coleta.json
```

O coletor recusa sobrescrever uma captura existente. O script de revisão corresponde à captura inicial; não reutilizar suas decisões por índice em uma nova amostra.

Arquivos de implementação alterados: `research/web_source.py`, `research/company_finder.py`, `research/company_investigator.py`, `analysis/signal_detector.py`, `analysis/qualification.py`. Novos: `tests/test_phase5_quality.py`, `scripts/phase5_audit.py`, `scripts/phase5_review.py`, este relatório e `reports/phase5/*`.

## Recomendações

Ampliar a amostra até 20–30 empresas locais efetivamente verificadas, mantendo registros dos descartes; definir porte e perfil de cliente desejado antes de qualificar grandes redes; revisar matriz versus unidade e fatos com data incerta; melhorar a extração de identidade para páginas sem schema sem reduzir os requisitos de evidência. Só priorizar abordagem comercial após confirmar identidade, região e hipótese específica com fonte. Não foi realizado contato com terceiros.
