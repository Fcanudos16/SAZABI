def format_bytes(sizes_in_bat):
    units = [ "B", "KiB", "MiB", "GiB", "TiB" ]
    size = float(sizes_in_bat)
    unit_index = 0

    while size >= 1024 and unit_index < len (units) - 1:
        size = size / 1024
        unit_index = unit_index + 1

    return f"{size:.2f} {units[unit_index]}"

def create_progress_bar(percent, width=20):
    if percent < 0:
        percent = 0
    elif percent >100:
        percent = 100

    filled_blocks = int(round(percent / 100 * width))
    empty_blocks = width - filled_blocks

    bar = "█" * filled_blocks + "░" * empty_blocks
    return f"{bar} {percent:3.0f}%"

def format_uptime(total_seconds):

    total_seconds = max(0, int(total_seconds))
    days = total_seconds // 86400
    remaining_seconds = total_seconds % 86400
    hours = remaining_seconds // 3600
    remaining_seconds = remaining_seconds % 3600
    minutes = remaining_seconds // 60
    seconds = remaining_seconds % 60

    if days > 0:
        return f"{days}d {hours:02d}h {minutes:02d}m {seconds:02d}s"

    return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"
