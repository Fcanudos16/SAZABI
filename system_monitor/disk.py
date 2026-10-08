import os

import psutil


def get_disk_path():
    """Retorna a raiz do disco atual.

    No Windows costuma ser "C:\\"; no Linux, "/".
    """
    return os.path.abspath(os.sep)


def get_disk_info():
    """Retorna um dicionário com as informações do armazenamento."""
    disk_path = get_disk_path()
    disk = psutil.disk_usage(disk_path)

    disk_info = {
        "path": disk_path,
        "total": disk.total,
        "used": disk.used,
        "free": disk.free,
        "percent": disk.percent,
    }

    return disk_info