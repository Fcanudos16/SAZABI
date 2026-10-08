# Arte do mascote

Arte digital fornecida pelo usuário para o SAZABI. `original.jpg` é a cópia intacta de `download.jpg`, contendo seis poses em uma prancha. Não é arte gerada por IA.

SHA-256: `099f5270e553adf574061792cf5f3974318e97f00e9d489520f1fd1f7120cf57`.

`states.json` define os recortes de exibição `[esquerda, topo, direita, base]`, em pixels da prancha, para cada estado. Alterar o mapeamento não modifica a imagem. A janela tem uma máscara separada que deixa o fundo exterior transparente sem alterar RGB nem apagar olhos.

Não regravar, estilizar ou substituir esta arte automaticamente. Escala uniforme (98–100%) e rotação (até três graus) são somente apresentação, autorizadas na especificação. O cache reutiliza até 120 combinações, criadas em memória quando necessárias. Nenhum arquivo de sprite derivado é necessário para execução.

`state_models` associa estados às seis poses, permitindo reutilizar o mesmo modelo para trabalho e arraste. `animation.json` controla sono, transições, pulo, pouso, busca lateral e piscadas. Pálpebras normais são composição temporária; no sono não há fechamento desenhado por cima da arte. Sem novo asset oficial de sono, usa-se a pose original com deslocamento e bolhas independentes. A cabeça não é separada artificialmente do corpo.
