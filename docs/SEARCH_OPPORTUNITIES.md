# Atualização comercial de /search — 16/10/2026

## Auditoria antes das alterações

O comando usa `skills/search/skill.py`, que chama o fluxo existente em `core/agent.py`. A busca Tavily identifica páginas; `WebSource.extract` valida a identidade declarada e a cidade. `CompanyFinder`, normalização e deduplicação mantêm os IDs das empresas. `CompanyInvestigator` usa cache e coleta observações; `SignalDetector`, `OpportunityAnalyzer`, estratégias e `CommercialService` já produziam hipóteses e avaliações locais. SQLite conserva fontes, histórico, pesquisas, empresas e avaliações. O worker entrega `SkillResult` por fila ao terminal Tk, sem compartilhar a conexão SQLite com a interface.

Conflitos encontrados: a classificação comercial antiga tem pesos configuráveis diferentes dos cinco pesos solicitados; o relatório de pesquisa apresentava candidatos sem confirmar todos os filtros; a investigação seguia apenas links institucionais; não havia expansão por empresa. A integração LAYLA já é opcional e independente. Nenhuma chamada à LAYLA/Groq foi acrescentada.

## Fluxo e compatibilidade

Busca existente → identificação → deduplicação → investigação/cache → sinais/estratégias existentes → avaliação imutável com `search_brief` → confirmação dos filtros → cartões ordenados por prioridade → terminal com Ver mais/Ver menos, fontes e cópia.

Os cartões exigem nome, site, aderência aos filtros de cidade, estado, segmento e porte quando informados; necessidade solicitada também precisa corresponder às evidências/solução. Exclusões do perfil não recebem cartão. Os dados insuficientes ficam explícitos. Candidatos pendentes conservam nome/URL/motivo no diagnóstico; falhas não reapresentam avaliações anteriores como novas. Wikipédia e domínios governamentais não viram identidades comerciais; páginas editoriais e governamentais ficam descartadas na descoberta.

As observações de uma investigação parcial continuam aproveitáveis, com estado parcial salvo na avaliação. Falha de geração preserva coleta e empresas, sinaliza pesquisa parcial e não interrompe os demais resultados. O diagnóstico expandido conserva o relatório anterior e as pendências. `/lead` e `/evaluations` mostram também os detalhes novos quando presentes. O botão Último restaura os controles interativos.

Não houve migração SQL, remoção de histórico, nova dependência, novo provedor ou nova chave. O JSON existente de `lead_evaluations` recebe campos adicionais e a versão do avaliador passa a `commercial-4`, invalidando o cache antigo sem apagar avaliações. A pontuação anterior permanece nos comandos/filtros legados; a prioridade de `/search` fica explicitamente separada em `search_brief`, com seus próprios componentes e justificativa.

## Evidências e pontuação

As regras existentes continuam responsáveis pelos sinais e pelas soluções compatíveis com os serviços e estratégias configurados. Foram acrescentadas declarações explícitas de automação/software e menções a integrações entre sistemas. A investigação prioriza serviços, processos, vagas/carreiras e notícias, ainda limitada à página inicial e duas páginas internas, com cache, robots, limites HTTP e cancelamento existentes.

A análise comercial utiliza somente fatos elegíveis vinculados à recomendação escolhida. Deduplica textos iguais, preserva até três evidências e separa texto original de interpretação. Declarações explícitas de necessidade no domínio da empresa podem ser diretas; processos manuais contextualizados e vagas são indiretos; canais e indícios menos conclusivos são fracos. Negação e vagas impedem a promoção a necessidade direta. A presença de vaga nunca é apresentada como solicitação de fornecedor. Quando a mesma investigação permite automação pontual e gestão ampla, a automação tem preferência.

| Componente | Direta | Indireta | Fraca | Insuficiente | Máximo |
|---|---:|---:|---:|---:|---:|
| Força das evidências | 35 | 20 | 8 | 0 | 35 |
| Clareza | 25 | 18 | 8 | 0 | 25 |
| Compatibilidade | 20 se há recomendação compatível, senão 0 | idem | idem | 0 | 20 |
| Relevância | 10 | 6 | 2 | 0 | 10 |
| Validação comercial | 10 se telefone cadastrado consta de fonte elegível, senão 0 | idem | idem | idem | 10 |

A soma e o ajuste ficam registrados. Evidência fraca/insuficiente tem teto de 44; alta começa em 75 e média em 45. Região e segmento não somam pontos. Quantidade de páginas não aumenta a força. A pontuação não estima probabilidade de venda. Contato, orçamento, intenção de compra e escopo precisam de validação independente.

A abordagem usa nome, trecho público e serviço configurado, terminando com pergunta exploratória. Sem evidência suficiente, não gera mensagem. Copiar abordagem copia somente essa mensagem. Não existe envio automático nesta atualização.

## Arquivos alterados

| Arquivo | Alteração |
|---|---|
| `analysis/search_brief.py` | Resumo, evidências, sinais vinculados, pontuação reproduzível, solução prática, abordagem, validação de filtros e texto expandido. |
| `analysis/qualification.py` | Versão do avaliador e sinais estruturados preservados na avaliação. |
| `analysis/commercial.py` | Persistência/cache da análise e do estado parcial no JSON existente. |
| `analysis/signal_detector.py` | Reconhecimento de necessidades declaradas e contexto de integração. |
| `research/web_source.py` | Rejeição de fontes não comerciais e seleção de páginas internas relevantes. |
| `core/agent.py` | Estado por empresa e isolamento de falhas na análise comercial. |
| `skills/search/skill.py` | Cartões somente para resultados aderentes, ordenação, pendências e diagnóstico estruturado. |
| `core/commercial_commands.py`, `core/lead_commands.py` | Consulta da análise persistida pelos comandos existentes. |
| `ui/terminal.py` | Expansão individual, fontes clicáveis, cópia e restauração do último resultado interativo. |
| `tests/test_search_brief.py` | Cenários sintéticos de evidência, prioridade, filtros, falha, persistência e coleta limitada. |
| `tests/native_search_brief_check.py` | Verificação Tk de expansão, isolamento, cópia, restauração e dimensão compacta. |
| `docs/SEARCH_OPPORTUNITIES.md` | Auditoria, decisões, entrega e validação. |

## Saídas efetivamente produzidas pelos testes

São resultados reais da execução do código sobre **empresas e fontes fictícias**, não descobertas de empresas reais. A execução gravou os objetos completos em `data/search-brief-check/examples.json`.

| Entrada sintética | Saída observada |
|---|---|
| “Precisamos automatizar o controle manual de pedidos.” | Necessidade identificada; direta; 90/100; alta; automação de processos internos. |
| “Utilizamos planilhas para controle manual de pedidos.” | Oportunidade provável; indireta; 64/100; média. |
| “Vaga para desenvolver integrações entre sistemas.” | Oportunidade provável; 64/100; limitação explícita de que vaga não solicita fornecedor. |
| “Bem-vindos ao nosso site.” | Necessidade específica não determinada; hipótese; 0/100; nenhuma abordagem. |

Exemplo de resumo executado: “Empresa Beta (fictícia) pode se beneficiar de automação de processos internos; é preciso confirmar o processo atual.”

## Validação e limites

O teste nativo passou: expansão/recolhimento independentes, clipboard igual somente à mensagem, Último restaurando interatividade e janela de até 620 px. Captura inspecionada: `data/search-brief-check/terminal.png`. A suíte cobre histórico, deduplicação, comandos relacionados, ausência de resultados e múltiplas empresas.

Resultado final: **384 testes passaram, 16 subtestes passaram, nenhuma falha**, em 85,36 segundos. Comando: `python -m pytest -q -p no:cacheprovider --basetemp <diretório-novo> tests`. O teste nativo `python tests/native_search_brief_check.py` passou novamente após as alterações finais. `git diff --check` não encontrou erros de whitespace.

As primeiras tentativas tiveram problemas de ambiente: leitura da pasta `.test-deps`, temporário padrão do pytest, restrição de loopback e timeout de inicialização. Usar `python -m pytest`, `--basetemp` com diretório novo e permissão para os servidores locais permitiu validar a suíte. Duas regressões da legenda de estratégia foram corrigidas. Nenhum teste foi removido para ocultar falha.

Limitações conhecidas: regras linguísticas conservadoras não compreendem qualquer redação; apenas páginas públicas acessíveis e dois links internos por empresa são examinados. Datas de publicação não são extraídas pelo modelo atual de observações: aparecem como não informadas, separadas da data de consulta. Fontes primárias são declarações públicas, não auditoria independente. A deduplicação reconhece textos iguais, mas não todas as paráfrases de uma notícia. A origem externa é apresentada como requerendo confirmação. A qualificação de porte depende do dado disponível e pode deixar candidatos pendentes. Nenhuma pesquisa real com Tavily, validação de fornecedor externo, envio de mensagem ou novo teste de múltiplos monitores foi realizado nesta entrega. Mascote, efeitos, janelas e topmost não foram redesenhados.
