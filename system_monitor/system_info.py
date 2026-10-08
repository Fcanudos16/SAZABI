import platform


def get_os_name():
    """Retorna o nome do sistema operacional (ex.: "Windows 11")."""
    system_name = platform.system()

    if system_name == "Windows":
        return get_windows_name()

    return f"{system_name} {platform.release()}"


def get_windows_name():
    """Diferencia Windows 10 de Windows 11.

    O Python pode reportar "10" mesmo no Windows 11, então usamos o
    número da build: a partir da 22000 é Windows 11.
    """
    release = platform.release()

    try:
        build_number = int(platform.version().split(".")[-1])
    except ValueError:
        return f"Windows {release}"

    if build_number >= 22000:
        return "Windows 11"

    return f"Windows {release}"


def get_hostname():
    """Retorna o nome da máquina."""
    return platform.node()


def get_architecture():
    """Retorna a arquitetura (ex.: "AMD64")."""
    return platform.machine()


def get_processor_name():
    """Retorna o nome do processador da melhor forma disponível."""
    system_name = platform.system()

    if system_name == "Windows":
        name = read_windows_processor_name()
    elif system_name == "Linux":
        name = read_linux_processor_name()
    else:
        name = None

    if name:
        return name

    # Plano B: pode ser um texto técnico, mas é melhor que nada
    fallback_name = platform.processor()
    if fallback_name:
        return fallback_name

    return "Desconhecido"


def read_windows_processor_name():
    """Lê o nome do processador no registro do Windows."""
    import winreg

    registry_path = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path) as key:
            name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            return name.strip()
    except OSError:
        return None


def read_linux_processor_name():
    """Lê o nome do processador em /proc/cpuinfo."""
    try:
        with open("/proc/cpuinfo", "r") as cpuinfo_file:
            for line in cpuinfo_file:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        return None

    return None