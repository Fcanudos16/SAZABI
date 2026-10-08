import psutil


def get_memory_info():
    """Retorna um dicionário com as informações da memória RAM.

    Os valores de bytes vêm em bytes puros; a formatação é feita depois.
    """
    memory = psutil.virtual_memory()

    memory_info = {
        "total": memory.total,
        "used": memory.used,
        "available": memory.available,
        "percent": memory.percent,
    }

    return memory_info