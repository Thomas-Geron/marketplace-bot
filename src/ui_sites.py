# src/ui_sites.py
"""
Sites como cartões selecionáveis (Compra e Venda usam os mesmos).

Cada cartão é um Canvas: caixa de marcação no canto, monograma do site
(não é logotipo), nome e um selo de situação ("Só lista", "Plano pago",
"Em breve"…). O cartão inteiro clica; Espaço alterna pelo teclado.

Estados: normal (branco), hover (borda mais escura), marcado (roxo bem
claro + borda roxa), inativo (cinza, sem clique) e foco (anel claro).
A imagem de fundo é refeita quando a largura muda — a grade redistribui
as colunas conforme o espaço (`GradeSites`).
"""
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

import ui_imagens
import ui_tema
from ui_componentes import dica_flutuante

C = ui_tema.CORES

# monograma e cor de cada site (identificação rápida, não é a marca)
MONOGRAMAS = {
    "facebook": ("FB", "#1d4ed8", "#e8f0fe"),
    "facebook_pagina": ("FB", "#1d4ed8", "#e8f0fe"),
    "icarros": ("iC", "#c2410c", "#fff1e6"),
    "webmotors": ("WM", "#be123c", "#ffe4e6"),
    "mobiauto": ("MA", "#0f766e", "#ccfbf1"),
    "olx": ("OLX", "#7e22ce", "#f3e8ff"),
    "napista": ("NP", "#15803d", "#dcfce7"),
    "leiloes": ("LS", "#334155", "#e2e8f0"),
    "kavak": ("KV", "#0369a1", "#e0f2fe"),
    "demo": ("DM", "#475569", "#f1f5f9"),
}

_CACHE = {}


def _fundo(widget, largura, altura, estado, foco):
    raiz = widget.winfo_toplevel()
    chave = (str(raiz), largura, altura, estado, foco)
    if chave in _CACHE:
        return _CACHE[chave]
    s = ui_tema.escala(raiz)
    cores = {
        "normal": ("#ffffff", C["borda"], 1.0),
        "hover": ("#ffffff", C["borda_forte"], 1.0),
        "marcado": (C["primaria_suave"], C["primaria"], 1.5),
        "marcado_hover": ("#ede9fe", C["primaria_hover"], 1.5),
        "inativo": (C["fundo"], C["borda"], 1.0),
    }
    preenche, borda, esp = cores[estado]
    img = ui_imagens.retangulo(
        raiz, largura, altura, round(10 * s), preenche, borda=borda,
        espessura=esp * max(1.0, round(s)), espessura_anel=max(2, round(3 * s)),
        anel=C["primaria_borda"] if foco else None)
    _CACHE[chave] = ui_tema.guardar(raiz, img)
    return _CACHE[chave]


def _peca(widget, chave, fabrica):
    raiz = widget.winfo_toplevel()
    chave = (str(raiz),) + chave
    if chave not in _CACHE:
        _CACHE[chave] = ui_tema.guardar(raiz, fabrica(raiz))
    return _CACHE[chave]


class CartaoSite(tk.Canvas):
    """Cartão de um site. `selo` = (texto, tipo) de ui_tema.SELOS."""

    def __init__(self, pai, site_id, nome, variavel, selo=None,
                 disponivel=True, dica=None, comando=None, fundo=None):
        self.px = lambda v: ui_tema.px(pai, v)  # noqa: E731
        super().__init__(pai, width=self.px(148), height=self.px(122),
                         bg=fundo or C["cartao"], highlightthickness=0,
                         borderwidth=0, takefocus=1 if disponivel else 0,
                         cursor="hand2" if disponivel else "arrow")
        self.site_id, self.nome = site_id, nome
        self.variavel, self.selo = variavel, selo
        self.disponivel, self.comando = disponivel, comando
        self._hover = False
        self._rastreio = variavel.trace_add(
            "write", lambda *_: self.after_idle(self.redesenhar))
        for evento, acao in (("<Button-1>", self.alternar),
                             ("<space>", self.alternar),
                             ("<Enter>", lambda _e: self._sobre(True)),
                             ("<Leave>", lambda _e: self._sobre(False)),
                             ("<FocusIn>", lambda _e: self.redesenhar()),
                             ("<FocusOut>", lambda _e: self.redesenhar()),
                             ("<Configure>", lambda _e: self.redesenhar())):
            self.bind(evento, acao, add="+")
        self.bind("<Destroy>", self._soltar, add="+")
        if dica:
            dica_flutuante(self, dica)

    def _soltar(self, _evento=None):
        try:
            self.variavel.trace_remove("write", self._rastreio)
        except (tk.TclError, ValueError):
            pass

    def _sobre(self, dentro):
        self._hover = dentro
        self.redesenhar()

    def alternar(self, _evento=None):
        if not self.disponivel:
            return "break"
        self.focus_set()
        self.variavel.set(0 if self.variavel.get() else 1)
        if self.comando:
            self.comando()
        return "break"

    def redesenhar(self):
        if not self.winfo_exists():
            return
        largura = max(self.winfo_width(), self.px(120))
        altura = int(self["height"])
        marcado = bool(self.variavel.get())
        if not self.disponivel:
            estado = "inativo"
        elif marcado:
            estado = "marcado_hover" if self._hover else "marcado"
        else:
            estado = "hover" if self._hover else "normal"
        foco = self.focus_get() is self and self.disponivel
        self.delete("all")
        self.create_image(0, 0, anchor="nw",
                          image=_fundo(self, largura, altura, estado, foco))

        # caixa de marcação no canto
        lado = self.px(16)
        s = ui_tema.escala(self)
        tipo_marca = ("inativo" if not self.disponivel
                      else "marcado" if marcado else "vazio")
        marca = _peca(self, ("marcacao", lado, tipo_marca), lambda raiz:
                      ui_imagens.marcacao(raiz, lado, tipo_marca, C["primaria"],
                                          C["borda_forte"], escala=s))
        self.create_image(self.px(12), self.px(12), image=marca, anchor="nw")

        # monograma
        sigla, cor_texto, cor_tinta = MONOGRAMAS.get(
            self.site_id, (self.nome[:2].upper(), C["texto_suave"], C["hover"]))
        if not self.disponivel:
            cor_texto, cor_tinta = C["inativo_texto"], C["inativo_fundo"]
        tile = self.px(36)
        img_tile = _peca(self, ("tile", tile, cor_tinta), lambda raiz:
                         ui_imagens.retangulo(raiz, tile, tile, round(9 * s),
                                              cor_tinta))
        meio = largura // 2
        self.create_image(meio, self.px(32), image=img_tile)
        self.create_text(meio, self.px(32), text=sigla, fill=cor_texto,
                         font=(ui_tema.FONTE_FORTE, 9 if len(sigla) < 3 else 8))

        # nome (até duas linhas)
        cor_nome = C["texto"] if self.disponivel else C["inativo_texto"]
        self.create_text(meio, self.px(70), text=self.nome, fill=cor_nome,
                         font=(ui_tema.FONTE_FORTE, 9), justify="center",
                         width=largura - self.px(16))

        # selo de situação
        if self.selo:
            texto, tipo = self.selo
            fundo_selo, cor_selo = ui_tema.SELOS.get(tipo, ui_tema.SELOS["neutro"])
            fonte = (ui_tema.FONTE_FORTE, 7)
            medida = tkfont.Font(root=self, font=fonte).measure(texto)
            pw, ph = medida + self.px(14), self.px(18)
            pilula = _peca(self, ("pilula", pw, ph, fundo_selo), lambda raiz:
                           ui_imagens.retangulo(raiz, pw, ph, ph / 2, fundo_selo))
            y = altura - self.px(19)
            self.create_image(meio, y, image=pilula)
            self.create_text(meio, y, text=texto, fill=cor_selo, font=fonte)


class GradeSites(ttk.Frame):
    """Grade responsiva de CartaoSite: tantas colunas quantas couberem."""

    def __init__(self, pai, largura_min=148, fundo_estilo="Superficie.TFrame"):
        super().__init__(pai, style=fundo_estilo)
        self.cartoes = []
        self._colunas = 0
        self._largura_min = ui_tema.px(pai, largura_min)
        self._vao = ui_tema.px(pai, 10)
        self.bind("<Configure>", self._reorganizar, add="+")

    def adicionar(self, cartao):
        self.cartoes.append(cartao)
        self._colunas = 0
        self.after_idle(self._reorganizar)
        return cartao

    def _reorganizar(self, _evento=None):
        largura = self.winfo_width()
        if largura <= 1:
            largura = self._largura_min * 4
        colunas = max(1, min(len(self.cartoes) or 1,
                             (largura + self._vao) // (self._largura_min + self._vao)))
        if colunas == self._colunas:
            return
        for c in range(max(colunas, self._colunas) + 1):
            self.columnconfigure(c, weight=0, uniform="")
        for c in range(colunas):
            self.columnconfigure(c, weight=1, uniform="sites")
        for i, cartao in enumerate(self.cartoes):
            linha, coluna = divmod(i, colunas)
            cartao.grid(row=linha, column=coluna, sticky="we",
                        padx=(0 if coluna == 0 else self._vao // 2,
                              0 if coluna == colunas - 1 else self._vao // 2),
                        pady=(0, self._vao))
        self._colunas = colunas
