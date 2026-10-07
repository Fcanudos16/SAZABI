"""SAZABI — bot pessoal de inteligência comercial. Uso: python main.py"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core.bootstrap import build_agent
from core.command_router import route
from core.config import load_config
from utils.logger import setup_logging

BANNER = """SAZABI — olheiro digital da software house
Modo: {mode}. Digite /help para ver os comandos, ou "sair" para encerrar.
"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="SAZABI V1")
    parser.add_argument('--telegram', action='store_true', help='bot privado com allowlist obrigatória')
    parser.add_argument('--cli', action='store_true', help='usa terminal em vez da janela desktop')
    parser.add_argument('--backup', action='store_true', help='cria backup SQLite verificado e sai')
    base = Path(__file__).resolve().parent
    parser.add_argument("--env", default=str(base / '.env'), help="caminho do arquivo .env")
    parser.add_argument("--services", default=str(base / 'services.yaml'), help="arquivo com os serviços da software house")
    parser.add_argument("--db", default=None, help="caminho do banco SQLite")
    parser.add_argument("--verbose", action="store_true", help="mostra logs também no terminal")
    parser.add_argument("-c", "--command", default=None, help="executa uma única mensagem e sai")
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):                 # emojis/acentos no Windows
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")

    config = load_config(args.env, args.services, db_path=args.db)
    if config.database_path != ':memory:' and not Path(config.database_path).is_absolute():
        config.database_path = str(base / config.database_path)
    if not Path(config.log_file).is_absolute():
        config.log_file = str(base / config.log_file)
    setup_logging(config.log_level, config.log_file, console=args.verbose)
    if not (args.cli or args.telegram or args.backup or args.command is not None):
        from desktop import run_desktop
        return run_desktop(config)
    agent = build_agent(config)

    if args.backup:
        try:
            print('Backup verificado: ' + agent.db.backup())
        finally:
            agent.db.close()
        return 0
    if not config.mock and config.database_path != ':memory:':
        agent.db.backup()
    if args.telegram:
        from dataclasses import replace
        from notifications.telegram import TelegramAPI, TelegramBot
        from notifications.notifier import NullNotifier
        agent.db.close()
        def factory(uid):
            return build_agent(replace(config, session_scope=f'telegram:{uid}:'), notifier=NullNotifier())
        try:
            TelegramBot(TelegramAPI(config.telegram_token), config.telegram_allowed_ids, factory).run()
        except KeyboardInterrupt:
            return 0
        except (ValueError, RuntimeError) as error:
            print(str(error))
            return 1
        return 0

    if args.command:
        try:
            print(agent.handle(args.command))
        finally:
            agent.db.close()
        return 0

    print(BANNER.format(mode="mock (dados fictícios)" if config.mock else "real"))
    if not config.mock and not config.search_api_key:
        print('Pesquisa real desativada: configure SEARCH_API_KEY (Tavily).\n')
    while True:
        try:
            text = input("você> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if route(text).name == "exit":
            print("SAZABI> Até logo.")
            break
        print(f"\nSAZABI>\n{agent.handle(text)}\n")
    agent.db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
