# SAZABI — sistema de design desktop

## Direção visual

Preto como estrutura, superfícies de grafite e vermelho como assinatura das ações. A identidade anterior azul/ciano foi substituída.
A composição usa uma faixa única de métricas, um ponto de entrada para pesquisa e duas áreas de trabalho: atividade e operação.
Não há métricas fictícias no modo real, gráficos decorativos, emojis na navegação, fontes remotas ou animações contínuas de fundo.

## Implementação

| Arquivo | Responsabilidade |
|---|---|
| `ui/tokens.py` | Cores, escala tipográfica, espaço, raio, duração e limites do layout |
| `ui/components.py` | Superfícies, botões, foco, indicador de estado, iluminação e rolagem |
| `ui/dashboard.py` | Métricas, atividade real e informação operacional |
| `ui/layout.py` | Navegação, composição e reorganização em janela compacta |
| `ui/window_chrome.py` | Barra de título escura no Windows, quando suportada |
| `desktop.py` | Estados, comandos, fila de trabalho, pausa, configuração e encerramento |
| `core/dashboard.py` | Projeção somente de leitura do SQLite para o painel |

O SQLite é acessado exclusivamente na thread do agente. A interface recebe eventos e snapshots; não consulta o banco na thread gráfica.
As métricas são atualizadas ao iniciar e após cada comando. Não existe polling de rede para animar o painel.

## Tokens

- Base: `#070707`; navegação: `#0D0D0F`; superfície: `#121214`; elevação: `#18181B`.
- Ação: `#E10600`; destaque: `#FF1A14`; vermelho escuro: `#7A0502`; bordô: `#3A0808`.
- Texto: `#F5F5F5`; secundário: `#A3A3AB`; foco: `#F6AEAA`.
- Espaçamento: 4, 8, 12, 16, 24 e 32 px. Raios: 8 px em botões e 12 px em superfícies.
- Uma família tipográfica instalada: Inter, Geist, Manrope, IBM Plex Sans, Segoe UI ou Arial, nessa ordem.
- Hover: transição de 120 ms. Indicador de processamento: variação discreta a cada 650 ms.

Os tons secundários foram levemente elevados em relação à paleta inicial para legibilidade em superfícies escuras.

## Componentes e estados

### GlassButton

Botão nativo com moldura arredondada desenhada em Canvas. Variantes principal e secundária; seleção persistente na navegação.
Estados: normal, hover, pressionado, foco, selecionado e desabilitado. O foco claro não depende apenas do vermelho.
Tab/Shift+Tab percorrem controles; Enter e Espaço acionam o botão focado.
Durante uma ação, envio e novos comandos ficam indisponíveis, mas a consulta visual ao painel e à conversa permanece acessível.

### Surface e AtmosphereHeader

Superfícies opacas com borda fina, reflexo superior discreto e uma iluminação radial estática atrás do cabeçalho.
Tkinter não oferece `backdrop-filter` CSS. O acabamento de vidro é uma aproximação nativa por cores e reflexos;
não há blur real do conteúdo atrás da janela nem transparência de toda a aplicação.

### StatusIndicator

| Estado | Significado |
|---|---|
| ONLINE | Agente local inicializado e disponível; não comprova conexão com API |
| PROCESSANDO | Comando em execução; rótulo e ponto discreto indicam atividade |
| PAUSADO | Usuário bloqueou novos comandos pela configuração |
| ERRO | Inicialização ou comando falhou; mensagem textual acompanha o estado |
| OFFLINE | Agente ainda não disponível ou encerrado |

Pausar durante uma execução é desabilitado. A pausa não é apresentada como cancelamento de rede.
O indicador só anima durante processamento. A opção Reduzir animações desativa hover interpolado e pulso.

## Dados do painel

- Prospecções: total de empresas na memória local, incluindo descartadas.
- Processados: empresas com investigação registrada.
- Qualificados: empresas não descartadas com ao menos uma hipótese moderada ou forte, sem duplicar hipóteses.
- Contatados: empresas em `CONTACTED` ou `CLIENT`; não é contagem de mensagens enviadas.
- Atividade: últimas cinco pesquisas, com data, conclusão registrada e resultados persistidos.
- Automação: sob demanda. Rotinas contínuas não estão implementadas e não são simuladas visualmente.

## Layout adaptável e acessibilidade

Abaixo de 980 px, a barra lateral dá lugar a um seletor de navegação e ação de pesquisa no topo.
Abaixo de 760 px na área do painel, métricas se reorganizam em duas colunas e os blocos inferiores passam a uma coluna.
Tamanho mínimo: 480 × 640 px. Há rolagem vertical e quebra de texto; o campo de comando permanece acessível na conversa.
É uma aplicação desktop: esse layout não oferece execução nativa em Android/iOS.

Ctrl+K abre a pesquisa e foca o campo; Enter envia; Escape fecha Configuração. Os botões têm rótulos e feedback textual.
Falta de API não impede abrir o programa ou consultar dados locais. O uso normal não oferece modo de demonstração.
Configuração inclui campo de chave mascarado, validação na Tavily, gravação local e ativação sem reiniciar.
Sucesso e falha aparecem em texto; a chave nunca entra na conversa. Falhas de pesquisa também aparecem no histórico.
O painel usa contraste alto, com cor secundária legível. Não foi realizada certificação WCAG nem auditoria com leitor de tela.

## Verificação

`python run_tests.py` executa a suíte offline. O teste gráfico pode ser ignorado onde Tcl/Tk ou sessão gráfica não estiverem disponíveis.
`python tests/native_desktop_check.py` valida a janela nativa em banco temporário na memória, sem chamadas externas.
`--screenshots` acrescenta capturas somente da janela de teste em `data/desktop-previews/` (fora do Git).
O roteiro verifica painel vazio, atualização com fonte sintética injetada somente no teste, modo sem API,
configuração com sucesso/falha controlados, navegação, pausa/retomada e largura compacta.
