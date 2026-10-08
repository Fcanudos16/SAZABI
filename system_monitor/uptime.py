import time

import psutil


def get_uptime_seconds():
    """Retorna há quantos segundos o computador foi ligado."""
    boot_timestamp = psutil.boot_time()
    current_timestamp = time.time()

    return current_timestamp - boot_timestamp