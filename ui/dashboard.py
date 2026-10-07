"""Editorial dashboard backed by actual local research data."""
import tkinter as tk
from ui.tokens import COLORS as C, SPACE as S, SIZE, mix
from ui.components import Surface, ScrollPage, AtmosphereHeader, label, wrapping_label
from utils.timeutils import fmt_date


class Dashboard(ScrollPage):
    def __init__(self, parent, app, config):
        super().__init__(parent)
        self.app, self.config, self.fonts = app, config, app.fonts
        self.snapshot = None
        body = self.content
        heading = AtmosphereHeader(body, self.fonts)
        heading.pack(fill='x', padx=S['xxl'], pady=(S['xl'], S['sm']))

        metrics = Surface(body, padding=S['lg'])
        metrics.pack(fill='x', padx=S['xxl'], pady=(0, S['xl']))
        self.metrics, self.metric_cells = {}, []
        for key, title in [('found', 'Prospecções'), ('processed', 'Processados'),
                           ('qualified', 'Qualificados'), ('contacted', 'Contatados')]:
            cell = tk.Frame(metrics.content, bg=C['surface'])
            number = label(cell, '—', self.fonts, 'number')
            number.pack(anchor='w')
            label(cell, title, self.fonts, 'small', 'muted').pack(anchor='w', pady=(2, 0))
            self.metrics[key] = number
            self.metric_cells.append(cell)
        self.metric_parent = metrics.content
        self.metrics_note = wrapping_label(body,
            'Qualificados: hipóteses com evidência moderada ou forte. Contatados: registros manuais.',
            self.fonts, 'small')
        self.metrics_note.pack(fill='x', padx=S['xxl'], pady=(0, S['xl']))

        hero = Surface(body)
        hero.pack(fill='x', padx=S['xxl'], pady=(0, S['xl']))
        self.light = tk.Canvas(hero.content, bg=C['surface'], height=28, highlightthickness=0)
        self.light.pack(fill='x')
        self.light.bind('<Configure>', self._atmosphere)
        wrapping_label(hero.content, 'Encontre o próximo movimento.', self.fonts, 'heading', 'text').pack(fill='x', pady=(0, 8))
        wrapping_label(hero.content,
            'Defina uma região e um segmento. O SAZABI investiga sinais públicos e organiza possíveis oportunidades.',
            self.fonts).pack(fill='x', pady=(0, 12))
        controls = tk.Frame(hero.content, bg=C['surface'])
        controls.pack(fill='x')
        app.action_button(controls, 'Nova pesquisa', app.open_search, primary=True).pack(side='left')
        app.action_button(controls, 'Abrir conversa', lambda: app.show_page('chat'), navigation=True).pack(side='left', padx=(10, 0))

        self.lower = tk.Frame(body, bg=C['background'])
        self.lower.pack(fill='x', padx=S['xxl'], pady=(0, S['xxl']))
        self.activity = Surface(self.lower)
        label(self.activity.content, 'Atividade recente', self.fonts, 'heading').pack(anchor='w')
        self.activity_summary = label(self.activity.content, 'Carregando o histórico local…', self.fonts, 'small', 'muted')
        self.activity_summary.pack(anchor='w', pady=(6, 18))
        self.rows = tk.Frame(self.activity.content, bg=C['surface'])
        self.rows.pack(fill='x')
        app.action_button(self.activity.content, 'Ver histórico', lambda: app.submit('/history')).pack(anchor='w', pady=(16, 0))

        self.operation = Surface(self.lower)
        label(self.operation.content, 'Operação', self.fonts, 'heading').pack(anchor='w', pady=(0, 18))
        source = 'Dados fictícios' if config.mock else 'Tavily configurada' if config.search_api_key else 'Sem chave de pesquisa'
        for title, value in [('FONTE', source), ('AUTOMAÇÕES', 'Sob demanda'),
                             ('CONTATO COM EMPRESAS', 'Manual, pela equipe'), ('ARMAZENAMENTO', 'Local neste computador')]:
            label(self.operation.content, title, self.fonts, 'label', 'muted').pack(anchor='w', pady=(12, 4))
            widget = wrapping_label(self.operation.content, value, self.fonts, color='text')
            widget.pack(fill='x')
            if title == 'FONTE':
                self.source_label = widget
        wrapping_label(self.operation.content, 'Nenhuma rotina contínua configurada.', self.fonts, 'small').pack(fill='x', pady=(18, 0))
        app.action_button(self.operation.content, 'Configuração', app.open_settings, navigation=True).pack(anchor='w', pady=(18, 0))
        self.compact = None
        body.bind('<Configure>', self._responsive, add='+')
        self.bind_wheel()

    def _atmosphere(self, event):
        self.light.delete('all')
        for x in range(0, event.width, 4):
            amount = .6 * max(0, 1-x/max(1, event.width)) ** 2
            self.light.create_line(x, 18, x+4, 18, fill=mix(C['surface'], C['deep_red'], amount), width=1)
        self.light.create_text(0, 2, anchor='nw', text='PESQUISA ORIENTADA POR EVIDÊNCIAS',
                               font=self.fonts['label'], fill=C['muted'])

    def _responsive(self, event):
        narrow = event.width < SIZE['stack']
        if narrow == self.compact:
            return
        self.compact = narrow
        for cell in self.metric_cells:
            cell.grid_forget()
        for col in range(4):
            self.metric_parent.columnconfigure(col, weight=0, uniform='')
        for i, cell in enumerate(self.metric_cells):
            col, row = (i % 2, i // 2) if narrow else (i, 0)
            self.metric_parent.columnconfigure(col, weight=1, uniform='metric')
            cell.grid(row=row, column=col, sticky='ew', padx=(0, 12), pady=(0, 12 if narrow else 0))
        self.activity.grid_forget()
        self.operation.grid_forget()
        self.lower.columnconfigure(0, weight=3)
        self.lower.columnconfigure(1, weight=0 if narrow else 2)
        self.activity.grid(row=0, column=0, sticky='new', padx=(0, 0 if narrow else 16))
        self.operation.grid(row=1 if narrow else 0, column=0 if narrow else 1, sticky='new', pady=(16 if narrow else 0, 0))

    def update_snapshot(self, data):
        if data == self.snapshot:
            return
        self.snapshot = data
        for key, widget in self.metrics.items():
            widget.configure(text=f"{data[key]:,}".replace(',', '.'))
        noun = 'pesquisa' if data['searches'] == 1 else 'pesquisas'
        self.activity_summary.configure(text=f"{data['searches']} {noun} no histórico")
        for widget in self.rows.winfo_children():
            widget.destroy()
        if not data['runs']:
            wrapping_label(self.rows, 'Ainda não há pesquisas registradas.', self.fonts, color='text').pack(fill='x', pady=(8, 6))
            wrapping_label(self.rows, 'Sua primeira pesquisa aparecerá aqui, com o resultado e a data da execução.', self.fonts).pack(fill='x')
        for run in data['runs']:
            tk.Frame(self.rows, height=1, bg=C['border']).pack(fill='x', pady=(0, 12))
            wrapping_label(self.rows, (run['query'] or 'Pesquisa sem descrição')[:180], self.fonts, color='text').pack(fill='x')
            ending = {'failed': 'Falhou', 'partial': 'Parcial', 'completed': 'Finalizada'}.get(run['status'], 'Registro anterior' if run['finished_at'] else 'Sem conclusão registrada')
            wrapping_label(self.rows, f"{fmt_date(run['started_at'])} · {ending}", self.fonts, 'small').pack(fill='x', pady=(4, 4))
            wrapping_label(self.rows, f"{run['found']} resultados · {run['opportunities']} oportunidades potenciais", self.fonts, 'small').pack(fill='x', pady=(0, 14))
        self.bind_wheel()
