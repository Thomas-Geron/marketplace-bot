# src/interface_extras.py
"""
Páginas de apoio da lateral: Anúncios salvos, Histórico e Configurações.

- Anúncios salvos: o que o bot JÁ guarda — contatados na Compra
  (visitados.json) e publicados na Venda (anunciados.json). Só leitura:
  apagar daqui destravaria o anti-spam.
- Histórico: execuções gravadas por execucoes.py, com o log de cada uma.
- Configurações: animações, rever o passo a passo, pasta de dados. A única
  preferência gravada fica em preferencias.json.
"""
import json
import os
import tkinter as tk
import webbrowser
from tkinter import ttk
from urllib.parse import urlparse

import execucoes
import tutorial
import ui_animacao
import ui_tema
from paths import get_data_dir, get_visitados_path
from ui_componentes import CabecalhoPagina, Cartao, Interruptor, placeholder
from ui_execucao import LogExecucao
from ui_scroll import criar_area_rolavel

C = ui_tema.CORES


# ------------------------------------------------------------ preferências
def _arquivo_prefs():
    return get_data_dir() / "preferencias.json"


def _prefs():
    try:
        return json.loads(_arquivo_prefs().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _salvar_pref(chave, valor):
    dados = _prefs()
    dados[chave] = valor
    try:
        _arquivo_prefs().write_text(json.dumps(dados), encoding="utf-8")
    except OSError:
        pass


def aplicar_preferencias():
    """Chamado ao abrir a janela."""
    if _prefs().get("animacoes") is False:
        ui_animacao.ATIVO = False


# ------------------------------------------------------------------ base
class _Pagina:
    """Página rolável com cabeçalho; o conteúdo vai em `self.conteudo`."""

    def __init__(self, pai, app, titulo, subtitulo):
        self.app = app
        self.px = lambda v: ui_tema.px(pai, v)  # noqa: E731
        self.frame = tk.Frame(pai, bg=C["fundo"])
        self.conteudo = criar_area_rolavel(self.frame, padding=28)
        self.conteudo.columnconfigure(0, weight=1)
        CabecalhoPagina(self.conteudo, titulo, subtitulo,
                        voltar=lambda: app.ir("inicio")).grid(
            row=0, column=0, sticky="we", pady=(0, self.px(20)))

    def ao_mostrar(self):
        pass

    def encerrar(self):
        pass


def _tabela(pai, colunas, altura):
    """Treeview com barra. `colunas` = [(id, título, largura, estica)]."""
    quadro = ttk.Frame(pai, style="Superficie.TFrame")
    quadro.columnconfigure(0, weight=1)
    arvore = ttk.Treeview(quadro, columns=[c[0] for c in colunas],
                          show="headings", height=altura, selectmode="browse")
    for ident, titulo, largura, estica in colunas:
        arvore.heading(ident, text=titulo, anchor="w")
        arvore.column(ident, width=ui_tema.px(pai, largura), stretch=estica,
                      anchor="w")
    barra = ttk.Scrollbar(quadro, orient="vertical", command=arvore.yview)
    arvore.configure(yscrollcommand=barra.set)
    arvore.grid(row=0, column=0, sticky="nsew")
    barra.grid(row=0, column=1, sticky="ns")
    return quadro, arvore


def _data_br(texto):
    """'2026-09-16 10:32:05' -> '16/09/2026 10:32'."""
    t = str(texto or "")
    return f"{t[8:10]}/{t[5:7]}/{t[:4]} {t[11:16]}" if len(t) >= 16 else t


# ---------------------------------------------------------- anúncios salvos
class PaginaSalvos(_Pagina):
    COLUNAS = [("data", "Data", 130, False), ("origem", "Origem", 150, False),
               ("site", "Site", 150, False), ("veiculo", "Veículo", 240, True),
               ("link", "Link", 280, True)]

    def __init__(self, pai, app):
        super().__init__(pai, app, "Anúncios salvos",
                         "Os anúncios que o bot já contatou na Compra e "
                         "publicou na Venda.")
        px = self.px
        cartao = Cartao(self.conteudo, "Anúncios", subtitulo=(
            "Dois cliques (ou Abrir anúncio) abre o link no navegador. Esta "
            "lista é a trava anti-spam: o bot não repete nenhum deles."))
        cartao.grid(row=1, column=0, sticky="we")
        self.lbl_total = ttk.Label(cartao.acoes, style="Ajuda.TLabel")
        self.lbl_total.pack(side="right")
        corpo = cartao.corpo
        corpo.columnconfigure(0, weight=1)
        ferramentas = ttk.Frame(corpo, style="Superficie.TFrame")
        ferramentas.grid(row=0, column=0, sticky="we", pady=(0, px(12)))
        ferramentas.columnconfigure(0, weight=1)
        self.busca = ttk.Entry(ferramentas)
        self.busca.grid(row=0, column=0, sticky="we", padx=(0, px(10)))
        placeholder(self.busca, "Buscar por veículo, site ou link…")
        self.busca.bind("<KeyRelease>", lambda _e: self._preencher(), add="+")
        ttk.Button(ferramentas, text="Abrir anúncio", style="Secundario.TButton",
                   cursor="hand2", command=self._abrir).grid(row=0, column=1)
        quadro, self.lista = _tabela(corpo, self.COLUNAS, 16)
        quadro.grid(row=1, column=0, sticky="we")
        self.lista.bind("<Double-1>", lambda _e: self._abrir())
        self.registros = []

    def ao_mostrar(self):
        self.registros = self.carregar()
        self._preencher()

    @staticmethod
    def carregar():
        """[{data, origem, site, veiculo, link}], mais recentes primeiro."""
        from interface_bot import CARTOES_SITES
        from venda import anunciados

        def site_da_url(url):
            dominio = urlparse(url).netloc
            for sid, (nome, _) in CARTOES_SITES.items():
                if sid in dominio:
                    return nome
            return dominio

        try:
            visitados = json.loads(get_visitados_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            visitados = []
        linhas = [{"data": r.get("data", ""), "origem": "Contatado (Compra)",
                   "site": site_da_url(r.get("url", "")),
                   "veiculo": r.get("produto", ""), "link": r.get("url", "")}
                  for r in visitados if isinstance(r, dict)]
        for r in anunciados.carregar():
            try:
                from venda.sites import obter_site
                site = obter_site(r["site"]).nome
            except (KeyError, ImportError):
                site = r.get("site", "")
            linhas.append({"data": r.get("data", ""), "origem": "Publicado (Venda)",
                           "site": site, "veiculo": r.get("titulo", ""), "link": ""})
        return sorted(linhas, key=lambda r: r["data"], reverse=True)

    def _preencher(self):
        termo = self.busca.get().strip().lower()
        visiveis = [r for r in self.registros
                    if not termo or termo in " ".join(r.values()).lower()]
        self.lista.delete(*self.lista.get_children())
        for i, r in enumerate(visiveis):
            self.lista.insert("", "end", iid=str(i), values=(
                _data_br(r["data"]), r["origem"], r["site"], r["veiculo"],
                r["link"] or "—"))
        self._visiveis = visiveis
        total = len(self.registros)
        self.lbl_total.configure(
            text=f"{total} anúncio{'s' if total != 1 else ''}"
            + (f"  •  {len(visiveis)} na busca" if termo else ""))

    def _abrir(self):
        selecao = self.lista.selection()
        if selecao and self._visiveis[int(selecao[0])]["link"]:
            webbrowser.open(self._visiveis[int(selecao[0])]["link"])


# ---------------------------------------------------------------- histórico
class PaginaHistorico(_Pagina):
    COLUNAS = [("data", "Início", 130, False), ("tipo", "Tipo", 80, False),
               ("modo", "Modo", 70, False), ("sites", "Sites", 200, True),
               ("veiculos", "Veículos", 200, True), ("duracao", "Duração", 90, False),
               ("resultado", "Resultado", 210, False), ("fim", "Fim", 90, False)]

    def __init__(self, pai, app):
        super().__init__(pai, app, "Histórico de execuções",
                         "Cada vez que você clicou em Rodar, com o resultado "
                         "e o log completo.")
        cartao = Cartao(self.conteudo, "Execuções", subtitulo=(
            f"As {execucoes.LIMITE} mais recentes. Clique numa linha para ver "
            "o log dela."))
        cartao.grid(row=1, column=0, sticky="we", pady=(0, self.px(20)))
        quadro, self.lista = _tabela(cartao.corpo, self.COLUNAS, 8)
        quadro.pack(fill="x")
        self.lista.bind("<<TreeviewSelect>>", lambda _e: self._mostrar_log())
        self.log = LogExecucao(self.conteudo, "Log da execução", altura=16)
        self.log.grid(row=2, column=0, sticky="we")
        self.execucoes = []

    def ao_mostrar(self):
        self.execucoes = execucoes.carregar()
        self.lista.delete(*self.lista.get_children())
        for i, e in enumerate(self.execucoes):
            c = e.get("contagem", {})
            minutos, segundos = divmod(e.get("duracao_s", 0), 60)
            self.lista.insert("", "end", iid=str(i), values=(
                _data_br(e.get("inicio")), e.get("tipo", ""),
                "Teste" if e.get("teste") else "Real",
                ", ".join(e.get("sites", [])), ", ".join(e.get("veiculos", [])),
                f"{minutos} min {segundos:02d} s",
                f"{c.get('sucesso', 0)} ok · {c.get('aviso', 0)} avisos · "
                f"{c.get('erro', 0)} erros", e.get("fim", "")))
        if self.execucoes:
            self.lista.selection_set("0")
        else:
            self.log.limpar()

    def _mostrar_log(self):
        selecao = self.lista.selection()
        if not selecao:
            return
        self.log.limpar()
        for hora, texto in self.execucoes[int(selecao[0])].get("log", []):
            self.log.adicionar(texto, hora)
        self.log.texto.see("1.0")


# ------------------------------------------------------------ configurações
class PaginaConfig(_Pagina):
    def __init__(self, pai, app):
        super().__init__(pai, app, "Configurações", "Preferências deste computador.")
        px = self.px

        aparencia = Cartao(self.conteudo, "Aparência")
        aparencia.grid(row=1, column=0, sticky="we", pady=(0, px(20)))
        corpo = aparencia.corpo
        corpo.columnconfigure(1, weight=1)
        self.var_anim = tk.IntVar(value=1 if ui_animacao.ATIVO else 0)
        Interruptor(corpo, self.var_anim, comando=self._animacoes).grid(
            row=0, column=0, rowspan=2, padx=(0, px(12)))
        ttk.Label(corpo, text="Animações e transições", style="Rotulo.TLabel").grid(
            row=0, column=1, sticky="w")
        ttk.Label(corpo, text="Desligue se o computador for lento ou se preferir "
                              "a tela sem movimento.", style="Ajuda.TLabel").grid(
            row=1, column=1, sticky="w")

        guia = Cartao(self.conteudo, "Passo a passo", subtitulo=(
            "Faz o passo a passo abrir sozinho de novo na próxima visita a "
            "cada página."))
        guia.grid(row=2, column=0, sticky="we", pady=(0, px(20)))
        ttk.Button(guia.corpo, text="Mostrar o passo a passo de novo",
                   style="Secundario.TButton", cursor="hand2",
                   command=self._rever).pack(anchor="w")
        self.lbl_guia = ttk.Label(guia.corpo, text="", style="Ajuda.TLabel")
        self.lbl_guia.pack(anchor="w", pady=(px(8), 0))

        dados = Cartao(self.conteudo, "Seus dados", subtitulo=(
            "Parâmetros, histórico de contatos e de execuções, anúncios "
            "publicados, sessão da conta e perfis do navegador ficam nesta "
            "pasta. Atualizar ou desinstalar o programa não mexe nela."))
        dados.grid(row=3, column=0, sticky="we")
        ttk.Label(dados.corpo, text=str(get_data_dir()), style="Texto.TLabel").pack(
            anchor="w", pady=(0, px(10)))
        ttk.Button(dados.corpo, text="Abrir a pasta", style="Secundario.TButton",
                   cursor="hand2",
                   command=lambda: os.startfile(get_data_dir())).pack(anchor="w")

    def _animacoes(self):
        ui_animacao.ATIVO = bool(self.var_anim.get())
        _salvar_pref("animacoes", ui_animacao.ATIVO)

    def _rever(self):
        tutorial.rever_todos()
        self.lbl_guia.configure(text="Pronto: o passo a passo abre de novo na "
                                     "próxima visita a cada página.")
