"""Windowless Windows launcher: only the mascot appears."""
from main import main


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        import logging
        logging.getLogger('sazabi').exception('Falha ao iniciar o mascote')
        from tkinter import Tk, messagebox
        root = Tk()
        root.withdraw()
        messagebox.showerror('SAZABI', 'Não foi possível iniciar. Confira a configuração e logs/sazabi.log.', parent=root)
        root.destroy()
