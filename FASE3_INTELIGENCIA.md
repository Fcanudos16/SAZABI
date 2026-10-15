# Fase 3 — inteligência comercial local

Esta fase usa `companies` e `sources` existentes, o mesmo SQLite e o terminal nativo. A avaliação lê observações já persistidas: não faz pesquisa, não consulta APIs e não exige chave. Nenhum dado de demonstração é inserido na base normal. O estágio comercial continua sob controle do usuário.

## Uso

1. Execute `python main.py`, abra o terminal pelo mascote e consulte `/leads`.
2. Confira `/profile`. Edite `commercial_profile.json` ou use, por exemplo, `/profile set services sistemas web;automação`. Informe apenas capacidades reais.
3. Execute `/qualify ID` para ver pontuação, critérios, fatos atribuídos às fontes, hipóteses, fatores contrários, lacunas e próxima ação.
4. Use `/qualify ID --refresh` para guardar uma nova avaliação deliberadamente. `/evaluations ID` lista versões e `/evaluations ID número` mostra uma versão específica.
5. `/draft ID email`, `/draft ID message` ou `/draft ID call` gera uma prévia. Revise; `/draft-save` guarda a última prévia. `/drafts ID` consulta os rascunhos guardados. Não existe envio de contato comercial nesta fase.
6. Opcionalmente, `/qualify-ai ID summary|compare|questions|draft` prepara um resumo para a LAYLA. Na interface desktop ele aparece no terminal de IA; só o botão **Enviar** transmite o texto. Na CLI, a prévia é exibida sem envio.

O ID completo aparece em `/leads`; prefixos hexadecimais únicos também são aceitos. Os comandos fazem parte do autocomplete e de `/help`. `/lead` e `/leads` mostram a última avaliação **salva**, que pode ter ficado desatualizada; `/qualify` revalida os dados atuais.

## Perfil comercial

`services: null` herda a lista já existente de `services.yaml`. Uma lista vazia desabilita recomendações. Os demais campos começam vazios: `technologies`, `accepted_projects`, `priority_segments`, `priority_locations`, `company_sizes`, `excluded_projects`, `differentiators`. Não foram inventados preços, clientes, tecnologias, diferenciais ou capacidade de entrega.

`/profile set CAMPO item;item` altera listas; `-` limpa. Para voltar à herança de serviços, edite o JSON e coloque `services: null`. Os tipos aceitos e excluídos são comparados por texto normalizado ao nome da solução e aos serviços associados; exclusões prevalecem. Use termos presentes nessas soluções, como `agendamento`, `WhatsApp`, `automação` ou `e-commerce`. Isso não é uma classificação semântica por IA. Tecnologias e diferenciais são preservados no perfil de cada avaliação; tecnologias geram uma pendência de validação técnica e diferenciais não são prometidos automaticamente nos rascunhos.

Pesos, limites e prazo de atualidade são editados diretamente no JSON. Os pesos devem ser inteiros de 0 a 100 e somar 100. Os limites obedecem `1 <= moderate < high <= 100`. `fresh_days` aceita de 1 a 3650 dias (padrão: 90). Arquivo inválido produz erro explícito; não é substituído por perfil inventado.

`COMMERCIAL_PROFILE_PATH` permite usar outro arquivo, inclusive uma cópia privada em `data/`. Caminhos relativos são resolvidos a partir da pasta do `.env`. O arquivo padrão é versionado; evite inserir informações privadas nele se pretende publicá-lo. Escritas pelo comando são atômicas.

## Pontuação, versão commercial-1

| Critério | Máximo padrão | Regra |
|---|---:|---|
| Compatibilidade de serviço (`service_fit`) | 25 | Existe hipótese sustentada e compatível com serviços/projetos configurados. |
| Evidência (`evidence`) | 25 | `int(peso × min(tipos relevantes distintos / 3, 1))`. Repetições não somam. |
| Funcionalidades/processos (`digital_features`) | 10 | Sinal explícito e relevante de lacuna digital, ausência declarada de loja virtual ou processo manual. |
| Segmento (`segment`) | 10 | Segmento cadastrado corresponde a prioridade configurada. |
| Perfil de cliente (`customer_profile`) | 10 | Metade do peso por localidade correspondente; metade por porte correspondente, com arredondamento para baixo. |
| Informação (`information_quality`) | 15 | Ao menos uma observação com texto, fonte nomeada, URL pública HTTP(S) e data de coleta dentro do prazo. |
| Canal comercial (`public_contact`) | 5 | Telefone cadastrado com ao menos oito dígitos também aparece em uma observação elegível. |

Não há pontos por campo ausente, design antigo, aparência de site ou simples falha de busca. Um telefone só cadastrado manualmente não confirma canal público. Segmento e porte vêm do cadastro e podem estar incompletos ou estimados. A data é de **coleta**, não de publicação, nem prova de que a empresa continua ativa. URLs são verificadas sintaticamente; a avaliação não faz nova conexão ou verificação de domínio.

Limites padrão: **Alta >= 70**, **Moderada >= 40**, **Baixa < 40**. Sem fonte elegível ou sem serviços configurados: **Dados insuficientes**. Sem hipótese compatível: no máximo 39. Alta exige pelo menos dois tipos distintos de sinal relevante; caso contrário, no máximo 69. Esses tetos acompanham os limites configurados e aparecem como ajustes negativos explícitos. Soma das contribuições e ajustes = pontuação final entre 0 e 100. Não é probabilidade de venda.

As regras de sinais e oportunidades existentes são reutilizadas. Indícios positivos explícitos de agendamento online ou loja virtual retiram as respectivas hipóteses de ausência e aparecem como fatores contrários. Isso é conservador, mas limitado aos padrões de texto reconhecidos; não substitui uma auditoria funcional do site. Orçamento, urgência, intenção de compra e poder de decisão ficam como desconhecidos.

Os relatórios antigos de pesquisa e `/interesting` conservam seu indicador de **prioridade de investigação por sinais**; ele não equivale à qualificação comercial. Na exportação, esse indicador passa a `legacy_signal_score`; `score` é a última qualificação salva ou `null` se ainda não existe avaliação.

## Persistência e atualização

A migração 2 acrescenta `lead_evaluations` e `commercial_drafts`, com chaves estrangeiras e índices, sem recriar empresas nem apagar históricos. Bancos com dados recebem backup local antes da migração. Cada avaliação guarda perfil, regras/versão, pontuação, categoria, critérios, justificativas, fontes e datas, lacunas e próximas ações em um snapshot JSON.

O cache usa hash dos campos relevantes da empresa, observações, perfil, versão e dia UTC. Repetir a consulta com os mesmos dados no mesmo dia não cria outra versão. Mudanças ou `--refresh` geram uma nova avaliação. O histórico anterior não é sobrescrito. Fontes antigas continuam visíveis com suas datas, sem pontuar como recém-confirmadas.

Investigações bem-sucedidas e resultados de cache também executam a qualificação local. Falha de fonte não é tratada como nova confirmação. Perfil comercial inválido não elimina a pesquisa; o usuário recebe indicação para revisá-lo. Requalificação nunca muda automaticamente o estágio de relacionamento com o lead.

Rascunhos ficam apenas na memória do processo até `/draft-save`. Se dados/perfil mudarem ou o lead for arquivado/descartado, é necessário gerar outra prévia. Não há rascunho de abordagem quando faltam evidências ou oportunidades sustentadas. Os modelos identificam a empresa, citam a observação de origem e apresentam a solução como hipótese. Incluem `[seu nome]` para preenchimento humano, sem fingir identidade ou relacionamento anterior.

`/export json ID,ID` e CSV incluem avaliações e rascunhos dos IDs selecionados. O histórico detalhado inclui o perfil utilizado em cada avaliação; revise o arquivo antes de compartilhá-lo. Exclusão deliberada de uma empresa por `/forget`, já sujeita a confirmação, também exclui seus dados associados.

## LAYLA, custos e limites

É reutilizado o terminal e o transporte LAYLA existentes, com sessão/CSRF e endpoint local. A preparação de `/qualify-ai` não chama o provedor. Abrir o terminal pode conectar à instância local, mas só a ação Enviar submete a análise. O resumo tem no máximo 2.000 caracteres, duas observações e duas hipóteses; não inclui notas privadas, histórico comercial, cookie, configuração completa ou banco. Telefones/e-mails no trecho são removidos e parâmetros de consulta das URLs são omitidos. O usuário deve revisar o conteúdo antes de transmitir.

Conteúdo das fontes é identificado como não confiável. Respostas da LAYLA não alteram a pontuação, não viram fatos e não são persistidas automaticamente como avaliação ou rascunho. Falhas de sessão, autenticação, STANDBY e indisponibilidade continuam explícitas; a qualificação local permanece disponível. Não se presume gratuidade do modelo usado pela LAYLA.

Nenhum adaptador de busca novo foi criado. `/search` continua indisponível em produção até configurar um adaptador realmente gratuito autorizado; não há resultados fictícios substitutos. `/research` e pesquisa legada continuam usando créditos Tavily. Esta fase pode trabalhar com leads e fontes já disponíveis no SQLite, sem consumir API.

## Validação

Os testes usam exclusivamente empresas, fontes e bancos temporários de teste. Cobrem pontuação, limites, fontes antigas/futuras/sem data, fontes repetidas, busca inconclusiva, ausência de oportunidade, exclusões, mudanças no perfil, migração 1→2, cache, histórico, exportação e rascunhos com salvamento explícito. A suíte existente também verifica falhas da LAYLA em um servidor HTTP local de contrato; não é validação da instância real do usuário.

O teste nativo usa Tk e o worker reais para listar, qualificar, consultar versões, gerar/salvar rascunho, exportar e conferir persistência após reabertura. A auditoria nativa da LAYLA usa transporte substituído por fixture, verifica que a prévia não é enviada sozinha e que uma prévia recebida enquanto o terminal está ocupado fica disponível depois.

Resultados desta entrega: **245 testes passaram em 27,46 s** (`run_tests.py` com dependências locais de teste); `native_leads_check.py` e `native_audit_check.py` passaram. O teste nativo de leads também percorreu `/qualify-ai`, exibiu uma falha simulada da LAYLA e confirmou que `/qualify` continuou funcionando. `git diff --check` passou. Não foram feitas chamadas comerciais externas, envio de mensagens a empresas ou validação de respostas reais da LAYLA.
