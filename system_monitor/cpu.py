import psutil


def start_cpu_measurement():
    """Faz a primeira leitura de CPU, que serve só como ponto de partida.

    O psutil calcula o uso comparando com a chamada anterior. Na primeira
    chamada não existe "anterior", então o resultado costuma ser 0.0.
    """
    psutil.cpu_percent(interval=None)


def get_cpu_usage():
    """Retorna o uso da CPU em porcentagem desde a última chamada."""
    cpu_usage = psutil.cpu_percent(interval=None)
    return cpu_usage


def get_physical_cores():
    """Retorna a quantidade de núcleos físicos (pode ser None)."""
    return psutil.cpu_count(logical=False)


def get_logical_cores():
    """Retorna a quantidade de núcleos lógicos (threads)."""
    return psutil.cpu_count(logical=True)


def get_cpu_frequency_mhz():
    """Retorna a frequência atual da CPU em MHz, ou None se indisponível."""
    try:
        frequency = psutil.cpu_freq()
    except (NotImplementedError, OSError, psutil.Error):
        return None

    if frequency is None:
        return None

    return frequency.current
