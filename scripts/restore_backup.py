"""Offline, explicitly confirmed restoration. Close SAZABI first."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from database.restore import restore_backup,validate_backup


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',required=True)
    parser.add_argument('--backup',required=True)
    args=parser.parse_args()
    from utils.logger import setup_logging
    setup_logging(log_file=str(Path(args.db).resolve().parent/'logs'/'recovery.log'))
    try:
        info=validate_backup(args.backup)
        print('Destino:',Path(args.db).resolve())
        print('Backup selecionado:',Path(args.backup).resolve(),'—',info)
        if input('Feche todas as instâncias. Digite RESTAURAR para substituir os dados: ').strip()!='RESTAURAR':
            print('Cancelado.');return 1
        rescue=restore_backup(args.db,args.backup,confirmed=True)
        print('Restauração validada. Cópia anterior:',rescue or 'Destino ainda não existia.')
        return 0
    except Exception as error:
        import logging
        logging.getLogger('sazabi.recovery').exception('Restauração não concluída')
        print('Restauração não confirmada:',type(error).__name__,str(error))
        return 1


if __name__=='__main__':raise SystemExit(main())
