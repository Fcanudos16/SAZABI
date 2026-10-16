# Fase 7 — perfil comercial e estratégias de prospecção

O `/search` continua usando a Search Skill, os mesmos provedores e o mesmo cadastro de empresas. A seleção e qualificação agora consultam o perfil comercial existente, aplicam estratégias declarativas e guardam a configuração usada em cada pesquisa. Reinicie o SAZABI para carregar as alterações.

## Configuração no terminal

Foram adicionados os botões **Perfil** e **Estratégias** ao terminal compacto. Também é possível usar `/profile` e `/strategies`. Nenhum novo serviço foi ativado no perfil da equipe: o valor legado `services: null` continua herdando a lista já configurada em `services.yaml`; uma lista explícita em `commercial_profile.json` prevalece, e `[]` significa nenhum serviço oferecido.

Exemplos de edição (use somente capacidades reais da equipe):

```text
/profile set services desenvolvimento de sites;automação;integrações
/profile set technologies Python;JavaScript
/profile set priority_segments clínica;oficina
/profile set priority_locations São Paulo
/profile set company_sizes pequena
/profile set automation_processes agendamento;pedidos
/profile set project_complexity pequena;média
/profile set interesting_traits múltiplas unidades
/profile set excluded_segments indústria
/profile set exclusion_terms franquia
/profile set excluded_projects loja virtual
```

Os exemplos não foram aplicados ao perfil real. Campos opcionais podem ficar vazios. `set campo -` limpa uma lista. Continuam disponíveis `accepted_projects`, `excluded_projects` e `differentiators`.

Tecnologias e complexidade são limites declarados da equipe, não tecnologias ou escopo presumidos dos leads. Processos de interesse podem orientar a seleção quando a consulta não define um objetivo; características desejadas e complexidade aparecem como pontos a validar. Não recebem pontos por simples configuração, sem evidências sobre a empresa.

Pesos, limiares, atualidade e regras estruturadas são editáveis no mesmo terminal:

```text
/profile json thresholds {"moderate":45,"high":75}
/profile json fresh_days 60
/profile json weights {"service_fit":30,"evidence":25,"digital_features":10,"segment":5,"customer_profile":10,"information_quality":15,"public_contact":5}
```

Pesos inteiros devem somar 100. Configurações inválidas são recusadas antes de substituir o arquivo. A gravação é atômica e o perfil é relido nas próximas operações; não é necessário reiniciar a cada edição.

## Estratégias

| ID | Objetivo | Evidências consideradas |
|---|---|---|
| `digital` | Presença digital | Lacunas explicitamente descritas, como ausência declarada de um canal; não aparência do site |
| `manual` | Possíveis processos manuais | Agendamento, atendimento ou processos manuais descritos pela fonte |
| `integration` | Possibilidades de integração | Dois ou mais canais/ferramentas nomeados em uma declaração de utilização |
| `custom` | Sistemas personalizados | Operação em unidades, equipe, processo manual e sinais de expansão pertinentes |

Esses modelos têm `enabled=true`, mas só são elegíveis quando compatíveis com os serviços já oferecidos e com seus filtros de segmento. Ativar uma estratégia não adiciona serviços ao perfil.

```text
/strategies disable digital
/strategies enable manual
/search estratégia=manual clínicas em São Paulo
/search estratégia=integration oficinas em Campinas
```

Uma estratégia explicitamente solicitada que esteja desativada, seja desconhecida ou incompatível é recusada antes da consulta ao provedor. Sem estratégia explícita, a seleção considera a regra do segmento, o objetivo escrito na consulta e, na ausência deste, os processos de interesse configurados. A alternativa padrão é `custom` quando elegível, ou a primeira estratégia compatível. O nome escolhido sempre aparece no resultado.

Se todas estiverem desativadas ou nenhum serviço for compatível, `/search` continua como pesquisa exploratória. Não gera hipóteses comerciais nem reapresenta hipóteses de uma estratégia antiga pelo cache. O resultado explica essa limitação.

## Critérios por segmento

As regras ficam no próprio perfil, em `segment_rules`. Use os segmentos normalizados exibidos pelo sistema (`clínica`, `oficina` etc.). Por exemplo:

```text
/profile json segment_rules {"clínica":{"strategy":"manual","signals":["scheduling","customer_service"],"min_signals":1},"oficina":{"strategy":"custom","signals":["manual_process","multiple_locations"],"excluded_terms":["franquia"],"min_signals":2}}
```

Esse comando substitui o mapa de regras completo. Não pressupõe que clínicas usem atendimento manual ou que oficinas tenham múltiplas unidades: apenas define quais sinais procurar e quantos tipos distintos são exigidos. As conclusões precisam de observações públicas com URL e data recente. Repetir a mesma evidência não satisfaz um requisito de tipos distintos.

Exclusões de segmento são comparadas ao segmento disponível; termos de exclusão ao nome, segmento e descrição disponíveis. Ausência de informação não comprova uma exclusão nem uma compatibilidade. Projetos excluídos continuam removendo recomendações. Um lead excluído pode permanecer no cadastro/histórico da pesquisa, mas fica sem recomendação sustentada e não recebe classificação moderada/alta só por corresponder ao segmento.

## Ajustar ou adicionar uma estratégia

`/profile` apresenta a estrutura completa. No campo `strategies` do mesmo JSON, cada estratégia declara:

- `enabled`, `objective`, `services` e `triggers`;
- `segments`, `signals` e `min_signals`;
- `query_terms` e `excluded_terms`;
- `sources`, `evidence` e `limits`.

É possível editar o arquivo ou substituir o mapa com `/profile json strategies {JSON}`. Identificadores usam letras minúsculas, números e sublinhado, começando com letra. Novas combinações dos sinais existentes podem ser adicionadas sem reescrever o motor. Criar um novo detector de evidência continua exigindo código e testes; um texto em JSON não cria uma capacidade de observação.

Os sinais disponíveis são `digital_gap`, `ecommerce`, `manual_process`, `scheduling`, `customer_service`, `digital_tools`, `multiple_locations`, `operational_complexity`, `growth`, `hiring` e `new_unit`.

`sources` aceita os papéis existentes `site público da empresa` e `descoberta Tavily`; não instala conectores nem altera permissões. `evidence` e `limits` descrevem a política para revisão. As condições executáveis são sinais permitidos, mínimos, exclusões e critérios do perfil; continuam obrigatórias URL pública, data válida e atualidade. Nenhum texto de configuração é executado como código.

## Intenção, pesquisa e evidência

Consultas específicas preservam segmento, localidade, porte e objetivo informados. Em consultas amplas, como `/search empresas`, podem ser usados o primeiro segmento, a primeira localidade e o primeiro porte prioritários. Esses preenchimentos aparecem como “Critérios do perfil”. Não há multiplicação automática da pesquisa por todas as prioridades, evitando consumo implícito de várias consultas.

`query_terms` de uma estratégia só acrescenta um objetivo quando o usuário não informou um. Os modelos padrão deixam esse campo vazio: a especialização inicial está na seleção, filtragem de sinais e qualificação, sem inventar novas consultas ou necessidades.

Integração exige observação que nomeie pelo menos dois canais/ferramentas e descreva uso. O detector atual reconhece WhatsApp, Shopify, WooCommerce, Salesforce, HubSpot, Bling, Tiny e Omie. A presença conjunta gera uma hipótese de integração, nunca uma afirmação de que os canais estão desconectados. Um site simples ou antigo, sozinho, não gera recomendação de substituição.

O resultado de `/search` informa estratégia, critérios aplicados, limitações e resumo da compatibilidade comercial. `/lead ID` e `/evaluations ID` permitem consultar justificativas, fontes e hipóteses. Segmento preferido, sozinho, não permite pontuação elevada. O estágio comercial, as notas e as tarefas da Fase 6 permanecem preservados.

## Histórico e restauração

```text
/strategies run 12
/profile reset strategies
/profile reset segment_rules
/profile reset weights
/profile reset thresholds
```

`run 12` consulta a configuração original da pesquisa 12, sem recalculá-la com o perfil atual. A migração 4 adiciona `strategy_json` à tabela existente `research_runs`; pesquisas antigas recebem `{}`, indicando que não tinham esse registro. A criação do registro de pesquisa já inclui o plano, inclusive em pesquisas que depois são interrompidas. Avaliações mantêm seu próprio perfil e contexto imutáveis, com versão do motor `commercial-3`.

Restaurar estratégias/regras/pesos/limiares não muda os serviços, tecnologias ou prioridades comerciais cadastrados. Os padrões dos novos campos são compatíveis com arquivos antigos; uma edição pelo terminal grava esses campos no mesmo arquivo de perfil. As migrações mantêm o backup automático de bancos existentes com dados.

## Custos e validação

Suíte final: `python -m pytest -q -p no:cacheprovider --tb=short` — **353 testes e 16 subtestes aprovados**, em 70,98 segundos. `git diff --check` também passou.

Foram reutilizados Tavily e o coletor público existente. Tavily continua consumindo créditos conforme a configuração já autorizada. Não foi adicionada API, dependência, autenticação alternativa, envio de mensagem ou geração de abordagem nesta fase. Cache de observações continua sendo reutilizado; as hipóteses são recalculadas localmente quando o perfil/estratégia muda.

Testes usam empresas sintéticas, banco isolado e cópia temporária do perfil. Cobrem persistência, compatibilidade com configurações antigas, seleção explícita/automática, regras por segmento, exclusões, mínimos de sinais, perfil incompleto/inválido, preservação da intenção, estratégias desativadas, snapshots imutáveis e manutenção de notas/tarefas/estágios após nova pesquisa.

`python tests/native_phase7_check.py` passou na interface Tkinter: edição de perfil isolado, pesquisa explícita, estratégia desativada, consulta histórica e botões **Perfil/Estratégias**. A captura `data/phase7/strategies.png` foi inspecionada visualmente. O terminal permanece com até 620 pixels de largura, e o cronômetro da pesquisa não aparece nas configurações.

Esta fase não executou coleta comercial real adicional: a integração foi validada com fontes sintéticas; a auditoria das fontes reais continua documentada na Fase 5. Para avaliar ganho de precisão comercial, será necessária outra amostra real com o perfil efetivo da equipe preenchido.
