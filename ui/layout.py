"""Responsive native navigation, dashboard and research workspace."""
import tkinter as tk
from tkinter import ttk

from ui.tokens import COLORS as C, SPACE as S, SIZE, typography
from ui.components import GlassButton, StatusIndicator, label, wrapping_label, Surface
from ui.dashboard import Dashboard


def build_layout(app, root, config):
    from ui.window_chrome import dark_titlebar
    root.title('SAZABI — Inteligência comercial')
    root.geometry('1220x860')
    root.minsize(SIZE['min_width'], SIZE['min_height'])
    root.configure(bg=C['background'])
    root.after_idle(lambda: dark_titlebar(root))
    app.fonts = typography(root)
    app.reduced_motion = tk.BooleanVar(root, value=False)
    app.buttons, app.nav_buttons = [], {}
    app.status = tk.StringVar(root, value='Inicializando a base local…')
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('Vertical.TScrollbar', background=C['border'], troughcolor=C['background'],
                    bordercolor=C['background'], arrowcolor=C['muted'])
    style.configure('TCombobox', fieldbackground=C['raised'], background=C['raised'],
                    foreground=C['text'], arrowcolor=C['text'], padding=6)
    style.map('TCombobox', fieldbackground=[('readonly', C['raised'])],
              foreground=[('readonly', C['text'])], selectbackground=[('readonly', C['raised'])],
              selectforeground=[('readonly', C['text'])])
    root.option_add('*TCombobox*Listbox.background', C['raised'])
    root.option_add('*TCombobox*Listbox.foreground', C['text'])

    def action_button(parent, text, command, primary=False, navigation=False, width=146):
        button = GlassButton(parent, text, command, app.fonts, primary,
                             lambda: not app.reduced_motion.get(), width=width)
        if not navigation:
            app.buttons.append(button)
        return button
    app.action_button = action_button

    app.sidebar = tk.Frame(root, width=SIZE['sidebar'], bg=C['sidebar'])
    app.sidebar.pack(side='left', fill='y')
    app.sidebar.pack_propagate(False)
    brand = tk.Frame(app.sidebar, bg=C['sidebar'])
    brand.pack(fill='x', padx=22, pady=(30, 24))
    tk.Frame(brand, width=3, height=27, bg=C['red']).pack(side='left', padx=(0, 10))
    label(brand, 'SAZABI', app.fonts, 'brand').pack(side='left')
    label(app.sidebar, 'INTELIGÊNCIA COMERCIAL', app.fonts, 'small', 'muted').pack(anchor='w', padx=22, pady=(0, 30))
    action_button(app.sidebar, 'Nova pesquisa', app.open_search, True).pack(fill='x', padx=16, pady=(0, 28))
    label(app.sidebar, 'ESPAÇO DE TRABALHO', app.fonts, 'label', 'muted').pack(anchor='w', padx=22, pady=(0, 12))
    navigation = [('Painel', lambda: app.show_page('dashboard')),
                  ('Conversa', lambda: app.show_page('chat')),
                  ('Resultados', lambda: app.submit('/results')),
                  ('Oportunidades', lambda: app.submit('/interesting')),
                  ('Histórico', lambda: app.submit('/history'))]
    for name, command in navigation:
        button = action_button(app.sidebar, name, command, navigation=name in ('Painel', 'Conversa'))
        button.pack(fill='x', padx=16, pady=3)
        app.nav_buttons[name] = button
    footer = tk.Frame(app.sidebar, bg=C['sidebar'])
    footer.pack(side='bottom', fill='x', padx=16, pady=22)
    action_button(footer, 'Configuração', app.open_settings, navigation=True).pack(fill='x', pady=(0, 20))
    label(footer, 'AMBIENTE PRIVADO', app.fonts, 'label', 'muted').pack(anchor='w', padx=6)
    wrapping_label(footer, 'Dados armazenados neste computador', app.fonts, 'small').pack(fill='x', padx=6, pady=(6, 0))

    app.main_area = tk.Frame(root, bg=C['background'])
    app.main_area.pack(side='left', fill='both', expand=True)
    header = tk.Frame(app.main_area, bg=C['background'])
    header.pack(fill='x', padx=S['xl'], pady=(18, 16))
    app.page_title = label(header, 'Visão geral', app.fonts, 'body', 'muted')
    app.page_title.pack(side='left')
    app.indicator = StatusIndicator(header, app.fonts, lambda: not app.reduced_motion.get())
    app.indicator.pack(side='right')
    tk.Frame(app.main_area, height=1, bg=C['border']).pack(fill='x')

    app.compact_bar = tk.Frame(app.main_area, bg=C['background'])
    app.nav_choice = ttk.Combobox(app.compact_bar, values=[n for n, _ in navigation] + ['Configuração'], state='readonly', width=18)
    app.nav_choice.set('Painel')
    app.nav_choice.pack(side='left', fill='x', expand=True, padx=(0, 12))
    def compact_select(event):
        choices = dict(navigation + [('Configuração', app.open_settings)])
        choices[app.nav_choice.get()]()
    app.nav_choice.bind('<<ComboboxSelected>>', compact_select)
    action_button(app.compact_bar, 'Pesquisar', app.open_search, True, width=120).pack(side='right')

    feedback = tk.Frame(app.main_area, bg=C['sidebar'])
    feedback.pack(side='bottom', fill='x')
    app.status_label = wrapping_label(feedback, '', app.fonts, 'small')
    app.status_label.configure(textvariable=app.status)
    app.status_label.pack(fill='x', padx=S['xl'], pady=10)
    app.pages = tk.Frame(app.main_area, bg=C['background'])
    app.pages.pack(fill='both', expand=True)
    app.dashboard = Dashboard(app.pages, app, config)
    app.chat_page = tk.Frame(app.pages, bg=C['background'])

    intro = tk.Frame(app.chat_page, bg=C['background'])
    intro.pack(fill='x', padx=S['xl'], pady=(S['xl'], 12))
    label(intro, 'Central de pesquisa', app.fonts, 'heading').pack(anchor='w')
    subtitle = 'Dados fictícios · nenhuma chamada externa' if config.mock else 'Tavily configurada' if config.search_api_key else 'Sem chave de pesquisa · sua memória local continua disponível'
    app.chat_source = wrapping_label(intro, subtitle, app.fonts, 'small')
    app.chat_source.pack(fill='x', pady=(6, 0))

    composer_area = tk.Frame(app.chat_page, bg=C['background'])
    composer_area.pack(side='bottom', fill='x', padx=S['xl'], pady=(12, 16))
    app.composer = tk.Frame(composer_area, bg=C['surface'], highlightthickness=1, highlightbackground=C['border'])
    app.composer.pack(fill='x')
    app.entry = tk.Entry(app.composer, bg=C['surface'], fg=C['text'], insertbackground=C['text'],
        disabledbackground=C['surface'], disabledforeground=C['muted'], font=app.fonts['message'],
        relief='flat', bd=0, highlightthickness=0, selectbackground=C['selection'])
    app.entry.pack(side='left', fill='x', expand=True, padx=14, pady=18)
    app.entry.bind('<Return>', lambda event: app.submit())
    app.entry.bind('<FocusIn>', lambda e: app.composer.configure(highlightbackground=C['focus']))
    app.entry.bind('<FocusOut>', lambda e: app.composer.configure(highlightbackground=C['border']))
    app.send_button = action_button(app.composer, 'Enviar', app.submit, True, width=90)
    app.send_button.pack(side='right', padx=8, pady=8)
    wrapping_label(composer_area, 'Enter para enviar · Ctrl+K para pesquisar · /help para comandos', app.fonts, 'small').pack(fill='x', pady=(8, 0))

    app.chat_area = tk.Frame(app.chat_page, bg=C['background'])
    app.chat_area.pack(fill='both', expand=True, padx=S['xl'])
    app.welcome = tk.Frame(app.chat_area, bg=C['background'])
    app.welcome.pack(fill='both', expand=True)
    empty = Surface(app.welcome)
    empty.pack(fill='x', pady=16)
    label(empty.content, 'O que vamos investigar?', app.fonts, 'heading').pack(anchor='w')
    wrapping_label(empty.content, 'Escreva um segmento e uma cidade ou consulte o que já está no histórico.', app.fonts).pack(fill='x', pady=(10, 18))
    action_button(empty.content, 'Clínicas em Campinas', lambda: app.prepare_search('procure clínicas em Campinas'), width=200).pack(anchor='w', pady=4)
    action_button(empty.content, 'Restaurantes em São Paulo', lambda: app.prepare_search('procure restaurantes em São Paulo'), width=230).pack(anchor='w', pady=4)

    app.transcript = tk.Frame(app.chat_area, bg=C['background'])
    scrollbar = ttk.Scrollbar(app.transcript, orient='vertical')
    scrollbar.pack(side='right', fill='y')
    app.output = tk.Text(app.transcript, wrap='word', font=app.fonts['message'], bg=C['background'], fg=C['text'],
        relief='flat', bd=0, padx=14, pady=16, spacing1=5, spacing3=12,
        selectbackground=C['selection'], yscrollcommand=scrollbar.set, state='disabled', takefocus=True)
    app.output.pack(fill='both', expand=True)
    scrollbar.configure(command=app.output.yview)
    app.output.tag_configure('user', foreground=C['text'], font=app.fonts['label'], justify='right')
    app.output.tag_configure('assistant', foreground=C['muted'], font=app.fonts['label'])
    app.output.tag_configure('user_body', background=C['primary'], foreground=C['text'], justify='right', lmargin1=35, lmargin2=35, rmargin=12)
    app.output.tag_configure('assistant_body', background=C['surface'], foreground=C['text'], lmargin1=12, lmargin2=12, rmargin=12)
    app.compact = None
    def responsive(event):
        if event.widget is not root:
            return
        compact = event.width < SIZE['compact']
        if compact == app.compact:
            return
        app.compact = compact
        if compact:
            app.sidebar.pack_forget()
            app.compact_bar.pack(fill='x', padx=S['xl'], pady=12, before=app.pages)
        else:
            app.compact_bar.pack_forget()
            app.sidebar.pack(side='left', fill='y', before=app.main_area)
    root.bind('<Configure>', responsive, add='+')
    root.bind('<Control-k>', lambda e: app.open_search())
    app.show_page('dashboard')
