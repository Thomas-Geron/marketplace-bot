# src/ui_tabela.py
"""
Tabela de veículos da Venda: caixa de marcação por linha, "selecionar
todos" no cabeçalho, status em selo, linha com hover e fundo roxo claro
quando marcada, busca por texto e filtro por "já anunciado".

Feita de frames (e não `ttk.Treeview`) porque a Treeview não tem caixa de
marcação nem selo colorido por célula. A marcação é a fonte da verdade
(`marcados()`), e não a seleção de uma lista: filtrar ou buscar esconde
linhas sem desmarcar nada.
"""
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

import ui_animacao
import ui_scroll
import ui_tema
from ui_componentes import Marcador, estilo_moldura

C = ui_tema.CORES

# (título, largura mínima, peso)
COLUNAS = (("", 44, 0), ("Veículo", 220, 5), ("Preço", 110, 0),
           ("Status", 130, 0), ("Já anunciado em", 150, 3))


def _grade(frame, janela):
    for i, (_, minimo, peso) in enumerate(COLUNAS):
        frame.columnconfigure(i, minsize=ui_tema.px(janela, minimo),
                              weight=peso, uniform=f"col{i}" if peso else "")


def encurtar(texto, fonte, largura):
    """Corta com reticências para caber em `largura` pixels."""
    if fonte.measure(texto) <= largura:
        return texto
    baixo, alto = 0, len(texto)
    while baixo < alto:
        meio = (baixo + alto + 1) // 2
        if fonte.measure(texto[:meio] + "…") <= largura:
            baixo = meio
        else:
            alto = meio - 1
    return texto[:baixo].rstrip() + "…"


class _Linha:
    def __init__(self, tabela, indice, veiculo, anunciado_em):
        self.indice, self.veiculo = indice, veiculo
        self.titulo = veiculo.get("titulo") or ""
        self.anunciado_em = anunciado_em
        self.var = tk.IntVar(value=0)
        px = lambda v: ui_tema.px(tabela, v)  # noqa: E731
        corpo = tabela.corpo
        self.frame = tk.Frame(corpo, bg=C["cartao"], height=px(46))
        self.frame.grid_propagate(False)
        _grade(self.frame, tabela)
        self.frame.rowconfigure(0, weight=1)
        self.marca = Marcador(self.frame, self.var, fundo=C["cartao"],
                              comando=tabela._marcacao_mudou)
        self.marca.grid(row=0, column=0, padx=(px(12), 0))
        self.lbl_titulo = tk.Label(self.frame, text=self.titulo, anchor="w",
                                   bg=C["cartao"], fg=C["texto"], width=1,
                                   font=(ui_tema.FONTE, 10))
        self.lbl_titulo.grid(row=0, column=1, sticky="we", padx=(px(4), px(12)))
        self.lbl_preco = tk.Label(self.frame, text=tabela.formatar_preco(veiculo),
                                  anchor="w", bg=C["cartao"], fg=C["texto"],
                                  font=(ui_tema.FONTE_FORTE, 10))
        self.lbl_preco.grid(row=0, column=2, sticky="w")
        status = (veiculo.get("status") or "").strip() or "—"
        self.selo = ui_tema.selo(self.frame, status.capitalize(),
                                 "sucesso" if "dispon" in status.lower()
                                 else "neutro", ponto=True)
        self.selo.grid(row=0, column=3, sticky="w")
        texto_anuncio = ", ".join(anunciado_em) if anunciado_em else "—"
        self.lbl_anuncio = tk.Label(self.frame, text=texto_anuncio, anchor="w",
                                    bg=C["cartao"], width=1,
                                    fg=C["texto"] if anunciado_em else C["placeholder"],
                                    font=(ui_tema.FONTE, 9))
        self.lbl_anuncio.grid(row=0, column=4, sticky="we", padx=(0, px(12)))
        tk.Frame(self.frame, bg=C["hover"], height=1).place(
            relx=0, rely=1.0, relwidth=1, anchor="sw")
        self.hover = False
        self.cor_atual = C["cartao"]
        self.var.trace_add("write", lambda *_: self.pintar())
        for w in (self.frame, self.lbl_titulo, self.lbl_preco, self.selo,
                  self.lbl_anuncio):
            w.bind("<Enter>", lambda _e: self._sobre(True), add="+")
            w.bind("<Leave>", self._saiu, add="+")
            w.bind("<Button-1>", lambda _e: self.marca.alternar(), add="+")
            w.configure(cursor="hand2")

    def _sobre(self, sim):
        if self.hover != sim:
            self.hover = sim
            self.pintar()

    def _saiu(self, evento):
        dentro = self.frame.winfo_containing(evento.x_root, evento.y_root)
        while dentro is not None and dentro is not self.frame:
            dentro = dentro.master
        if dentro is None:
            self._sobre(False)

    def pintar(self):
        """Fundo da linha anda até a cor do estado (hover, marcada)."""
        if self.var.get():
            alvo = C["primaria_suave"]
        elif self.hover:
            alvo = C["fundo"]
        else:
            alvo = C["cartao"]
        origem = self.cor_atual

        def passo(p):
            self._aplicar(ui_animacao.cor(origem, alvo, p))

        ui_animacao.animar(self.frame, "fundo", passo, "rapida")

    def _aplicar(self, cor):
        self.cor_atual = cor
        for w in (self.frame, self.lbl_titulo, self.lbl_preco, self.selo,
                  self.lbl_anuncio):
            w.configure(bg=cor)
        self.marca.fundo(cor)

    def combina(self, busca, filtro):
        if busca and busca not in self.titulo.lower():
            return False
        if filtro == "nao_anunciados" and self.anunciado_em:
            return False
        if filtro == "anunciados" and not self.anunciado_em:
            return False
        return True


class TabelaVeiculos(ttk.Frame):
    """Monte dentro de um cartão. `ao_mudar(total, visiveis, marcados)`."""

    def __init__(self, pai, ao_mudar=None, linhas_visiveis=8,
                 formatar_preco=None):
        super().__init__(pai, style=estilo_moldura(pai, C["cartao"], C["borda"],
                                                   C["cartao"], raio=10),
                         padding=ui_tema.px(pai, 1))
        px = lambda v: ui_tema.px(pai, v)  # noqa: E731
        self.ao_mudar = ao_mudar
        self.formatar_preco = formatar_preco or (lambda v: str(v.get("preco", "")))
        self.linhas = []
        self._busca, self._filtro = "", "todos"
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # cabeçalho
        cabeca = tk.Frame(self, bg=C["fundo"], height=px(40))
        cabeca.grid(row=0, column=0, sticky="we")
        cabeca.grid_propagate(False)
        cabeca.rowconfigure(0, weight=1)
        _grade(cabeca, pai)
        self.var_todos = tk.IntVar(value=0)
        self.marca_todos = Marcador(cabeca, self.var_todos, fundo=C["fundo"],
                                    comando=self._todos_clicado)
        self.marca_todos.grid(row=0, column=0, padx=(px(12), 0))
        for i, (titulo, _, _) in enumerate(COLUNAS[1:], start=1):
            tk.Label(cabeca, text=titulo, bg=C["fundo"], fg=C["texto_suave"],
                     font=(ui_tema.FONTE_FORTE, 9), anchor="w").grid(
                row=0, column=i, sticky="we",
                padx=(px(4), 0) if i == 1 else 0)
        tk.Frame(self, bg=C["borda"], height=1).grid(row=0, column=0,
                                                     sticky="swe")

        # corpo rolável
        self.tela = tk.Canvas(self, bg=C["cartao"], highlightthickness=0,
                              borderwidth=0, height=px(46) * linhas_visiveis,
                              yscrollincrement=px(23))
        self.tela.grid(row=1, column=0, sticky="nsew")
        self.barra = ttk.Scrollbar(self, orient="vertical",
                                   command=self.tela.yview)
        self.tela.configure(yscrollcommand=self.barra.set)
        self.barra.grid(row=0, column=1, rowspan=2, sticky="ns")
        self.corpo = tk.Frame(self.tela, bg=C["cartao"])
        self.corpo.columnconfigure(0, weight=1)
        self._id = self.tela.create_window((0, 0), window=self.corpo,
                                           anchor="nw")
        self.vazio = tk.Label(self.corpo, text="Nenhum veículo para mostrar.",
                              bg=C["cartao"], fg=C["texto_suave"],
                              font=(ui_tema.FONTE, 10), pady=px(28))
        self.corpo.bind("<Configure>", self._ajustar, add="+")
        self.tela.bind("<Configure>", self._ajustar, add="+")
        ui_scroll.registrar(self.tela)
        self._fonte = tkfont.Font(root=pai, family=ui_tema.FONTE, size=10)
        self._fonte_menor = tkfont.Font(root=pai, family=ui_tema.FONTE, size=9)
        self._largura_cortes = None

    # ------------------------------------------------------------ dados
    def carregar(self, veiculos, anunciado_em):
        """`anunciado_em`: função veiculo -> lista de nomes de sites.
        Mantém marcados os veículos que continuam na lista (pelo id)."""
        antes = {str(l.veiculo.get("id")) for l in self.linhas if l.var.get()}
        for linha in self.linhas:
            linha.frame.destroy()
        self.linhas = []
        for i, veiculo in enumerate(veiculos):
            linha = _Linha(self, i, veiculo, anunciado_em(veiculo))
            if str(veiculo.get("id")) in antes:
                linha.var.set(1)
            self.linhas.append(linha)
        self._largura_cortes = None
        self.aplicar_filtro()

    def marcados(self):
        """Índices (na lista carregada) dos veículos marcados, em ordem."""
        return [l.indice for l in self.linhas if l.var.get()]

    def aplicar_filtro(self, busca=None, filtro=None):
        if busca is not None:
            self._busca = busca.strip().lower()
        if filtro is not None:
            self._filtro = filtro
        visiveis = 0
        for linha in self.linhas:
            if linha.combina(self._busca, self._filtro):
                linha.frame.grid(row=visiveis, column=0, sticky="we")
                visiveis += 1
            else:
                linha.frame.grid_remove()
        if visiveis:
            self.vazio.grid_remove()
        else:
            self.vazio.grid(row=0, column=0, sticky="we")
        self.tela.yview_moveto(0)
        self._marcacao_mudou()

    def _visiveis(self):
        return [l for l in self.linhas if l.frame.winfo_manager() == "grid"]

    def _todos_clicado(self):
        alvo = 1 if self.var_todos.get() else 0
        for linha in self._visiveis():
            linha.var.set(alvo)
        self._marcacao_mudou()

    def _marcacao_mudou(self):
        visiveis = self._visiveis()
        marcados_visiveis = sum(1 for l in visiveis if l.var.get())
        todos = bool(visiveis) and marcados_visiveis == len(visiveis)
        if self.var_todos.get() != int(todos):
            self.var_todos.set(int(todos))
        self.marca_todos.parcial = 0 < marcados_visiveis < len(visiveis)
        self.marca_todos.redesenhar()
        if self.ao_mudar:
            self.ao_mudar(len(self.linhas), len(visiveis),
                          sum(1 for l in self.linhas if l.var.get()))

    # ------------------------------------------------------------ desenho
    def _ajustar(self, _evento=None):
        largura = self.tela.winfo_width()
        self.tela.itemconfigure(self._id, width=largura)
        self.tela.configure(scrollregion=(0, 0, largura,
                                          self.corpo.winfo_reqheight()))
        if largura > 1 and largura != self._largura_cortes:
            self._largura_cortes = largura
            self.after_idle(self._cortar_textos)

    def _cortar_textos(self):
        """Títulos longos terminam em '…' em vez de serem cortados no meio."""
        if not self.linhas:
            return
        primeira = self.linhas[0]
        self.update_idletasks()
        w_titulo = primeira.lbl_titulo.winfo_width() - ui_tema.px(self, 4)
        w_anuncio = primeira.lbl_anuncio.winfo_width() - ui_tema.px(self, 4)
        if w_titulo <= 1:
            return
        for linha in self.linhas:
            linha.lbl_titulo.configure(text=encurtar(linha.titulo, self._fonte,
                                                     w_titulo))
            if linha.anunciado_em:
                linha.lbl_anuncio.configure(text=encurtar(
                    ", ".join(linha.anunciado_em), self._fonte_menor, w_anuncio))
