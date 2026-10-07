"""Single source for the native desktop's visual language."""
COLORS = {
    'background': '#070707', 'sidebar': '#0d0d0f', 'surface': '#121214',
    'raised': '#18181b', 'highlight': '#222225', 'border': '#29292d',
    'text': '#f5f5f5', 'muted': '#a3a3ab', 'disabled': '#74747c',
    'red': '#e10600', 'bright': '#ff1a14', 'wine': '#3a0808',
    'deep_red': '#7a0502', 'hover': '#291314', 'primary': '#211012',
    'primary_border': '#632523', 'focus': '#f6aeaa', 'selection': '#542321',
    'error': '#ff9a94', 'paused': '#dbc49c', 'online': '#ea524d',
}
SPACE = {'xs': 4, 'sm': 8, 'md': 12, 'lg': 16, 'xl': 24, 'xxl': 32}
RADIUS = {'button': 8, 'surface': 12, 'modal': 14}
SIZE = {'sidebar': 210, 'button': 40, 'compact': 980, 'stack': 760,
        'min_width': 480, 'min_height': 640}
MOTION = {'step': 20, 'steps': 6, 'pulse': 650, 'poll': 75}
STATES = {'ONLINE': 'online', 'PROCESSANDO': 'bright', 'PAUSADO': 'paused',
          'ERRO': 'error', 'OFFLINE': 'muted'}


def typography(root):
    from tkinter import font
    installed = set(font.families(root))
    family = next((f for f in ('Inter', 'Geist', 'Manrope', 'IBM Plex Sans', 'Segoe UI')
                   if f in installed), 'Arial')
    return {'body': (family, 10), 'small': (family, 9), 'label': (family, 9, 'bold'),
            'title': (family, 25, 'bold'), 'heading': (family, 15, 'bold'),
            'number': (family, 28, 'bold'), 'brand': (family, 17, 'bold'),
            'message': (family, 11)}


def mix(a, b, amount):
    channels = [round(int(a[i:i+2], 16) * (1-amount) + int(b[i:i+2], 16) * amount)
                for i in (1, 3, 5)]
    return '#' + ''.join(f'{v:02x}' for v in channels)
