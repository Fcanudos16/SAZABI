"""SAZABI desktop companion entry point; never starts the obsolete dashboard."""
import argparse
from pathlib import Path
from core.config import load_config
from core.worker import AgentWorker, ConnectRequest, OllamaRequest
from utils.logger import setup_logging


def DesktopApp(*args, **kwargs):
    from ui.companion import CompanionApp
    return CompanionApp(*args, **kwargs)


def main():
    parser = argparse.ArgumentParser(description='SAZABI desktop local')
    parser.add_argument('--env', default=str(Path(__file__).parent / '.env'))
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    config = load_config(args.env, str(base / 'services.yaml'))
    if config.database_path != ':memory:' and not Path(config.database_path).is_absolute():
        config.database_path = str(base / config.database_path)
    if not Path(config.log_file).is_absolute():
        config.log_file = str(base / config.log_file)
    setup_logging(config.log_level, config.log_file)
    return run_desktop(config)


def run_desktop(config):
    """Open the desktop independently of external API configuration."""
    try:
        import tkinter as tk
    except ImportError:
        print('Tkinter ausente. Instale o componente Tcl/Tk do Python para abrir a interface.')
        return 1
    try:
        root = tk.Tk()
    except tk.TclError:
        print('Não foi possível iniciar Tcl/Tk. Verifique a instalação do Python e a sessão gráfica.')
        return 1
    root.withdraw()
    try:
        DesktopApp(root, config)
    except (RuntimeError, OSError, ValueError) as error:
        from tkinter import messagebox
        messagebox.showerror('SAZABI', str(error), parent=root)
        root.destroy()
        return 1
    root.mainloop()
    return 0


if __name__ == '__main__':
    main()
