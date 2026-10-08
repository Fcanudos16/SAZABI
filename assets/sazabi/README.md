# Arte do mascote

Arte digital fornecida pelo usuário para o SAZABI. `original.jpg` é a cópia intacta de `download.jpg`, contendo seis poses em uma prancha. Não é arte gerada por IA.

SHA-256: `099f5270e553adf574061792cf5f3974318e97f00e9d489520f1fd1f7120cf57`.

`states.json` define os recortes de exibição `[esquerda, topo, direita, base]`, em pixels da prancha, para cada estado. Alterar o mapeamento não modifica a imagem. A janela tem uma máscara separada que deixa o fundo exterior transparente sem alterar RGB nem apagar olhos.

Não regravar, estilizar, escalar ou substituir esta arte automaticamente. Nenhum arquivo de sprite derivado é necessário para execução.

`animation.json` controla sono, transições e sobreposições de piscada. Pálpebras são máscaras temporárias sobre os olhos existentes, com cor amostrada do rosto; não são gravadas na imagem. Bolhas são elementos independentes. A cabeça não é separada artificialmente do corpo: detalhes e proporções da arte plana permanecem intactos.
