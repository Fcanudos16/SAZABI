"""SAZABI — bot pessoal de inteligência comercial. Uso: python main.py --mock"""
from __future__ import annotations

import argparse
import sys

from core.bootstrap import build_agent
from core.command_router import route
from core.config import load_config
from utils.logger import setup_logging

BANNER = """SAZABI — olheiro digital da software house
Modo: {mode}. Digite /help para ver os comandos, ou "sair" para encerrar.
"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="SAZABI V1")
    parser.add_argument("--mock", action="store_true", help="usa dados fictícios, sem APIs externas")
    parser.add_argument('--telegram', action='store_true', help='bot privado com allowlist obrigatória')
    parser.add_argument('--backup', action='store_true', help='cria backup SQLite verificado e sai')
    parser.add_argument("--env", default=".env", help="caminho do arquivo .env")
    parser.add_argument("--services", default="services.yaml", help="arquivo com os serviços da software house")
    parser.add_argument("--db", default=None, help="caminho do banco SQLite")
    parser.add_argument("--verbose", action="store_true", help="mostra logs também no terminal")
    parser.add_argument("-c", "--command", default=None, help="executa uma única mensagem e sai")
    args = parser.parse_args(argv)
    if args.mock and args.telegram:
        parser.error('--mock não permite Telegram nem chamadas externas')

    for stream in (sys.stdout, sys.stderr):                 # emojis/acentos no Windows
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")

    config = load_config(args.env, args.services, mock=args.mock, db_path=args.db)
    setup_logging(config.log_level, config.log_file, console=args.verbose)
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
        print('Pesquisa real desativada: configure SEARCH_API_KEY (Brave).\n')
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
