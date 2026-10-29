# SAZABI — agente pessoal local

Assistente modular para Windows, com terminal preto e verde e mascote 2D original.
Gerencia tarefas, pesquisa e organiza arquivos com prévia, revisa projetos,
prepara alterações de código e operações Git e executa rotinas autorizadas.
Pesquisa páginas públicas e documentos locais sem exigir chaves de API.

```cmd
python main.py
python main.py --cli
python main.py -c "/help"
```

- [Instalação, comandos, configuração e segurança](docs/PERSONAL_GUIDE.md)
- [Auditoria anterior às mudanças](docs/REWORK_AUDIT.md)
- [Relatório de implementação e validação](docs/REWORK_REPORT.md)
- [Continuação: pesquisa, revisão e Git](docs/REWORK_CONTINUATION.md)
- [Documentação comercial histórica, fora do fluxo padrão](docs/LEGACY_COMMERCIAL_README.md)

A interface nativa, sprites, animações, countdown, monitor e terminal opcional
LAYLA foram reaproveitados. `/search` e `/research` pesquisam documentos locais
ou, explicitamente com `web`/`url`, fontes públicas; não fazem prospecção.
Dados antigos permanecem no SQLite existente.

## Testes

```cmd
python run_tests.py
python tests\native_personal_check.py
```

A suíte inclui componentes comerciais preservados em harness explícito e testes
do novo fluxo pessoal. O teste nativo usa banco em memória e não chama serviços
externos. Consulte o relatório para os resultados realmente executados.

## Limites atuais

Pesquisa web usa Wikimedia para descoberta e HTTPS para documentação indicada.
Resumos são extrativos e revisão Python é estática, sem alegar compreensão
semântica completa. Git permite add/commit/branch e push/pull com confirmação;
pull exige fast-forward. SSH, LFS ativo e worktrees de escrita são recusados.
Execução aprovada de scripts não é uma sandbox. A integração LAYLA permanece
preservada, com validação real adiada por solicitação do usuário.
