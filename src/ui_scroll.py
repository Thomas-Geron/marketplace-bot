# src/ui_scroll.py
"""
Áreas roláveis das telas.

`criar_area_rolavel()` embrulha o conteúdo num Canvas com barra de rolagem
e devolve o frame interno — quem usa faz pack/grid normalmente.

A roda do mouse é UMA ligação só por janela (`_instalar_roda`): ela vê o
que está sob o ponteiro e rola a área rolável mais próxima que ainda tem
para onde ir. Assim a tabela de veículos rola dentro da página, a página
continua rolando quando a tabela chega ao fim, e caixas de texto com
rolagem própria (log, mensagem) cuidam de si. A lista suspensa (Combobox)
deixa de trocar de valor com a roda — era fácil mudar o raio sem querer
ao rolar a página.
"""
import tkinter as tk
from tkinter import ttk

import ui_tema

_ROLAVEIS = set()


def registrar(tela):
    """Canvas que a roda do mouse deve rolar."""
    _ROLAVEIS.add(str(tela))
    tela.bind("<Destroy>", lambda _e: _ROLAVEIS.discard(str(tela)), add="+")
    _instalar_roda(tela.winfo_toplevel())


def _pode_rolar(widget, para_baixo):
    try:
        inicio, fim = widget.yview()
    except (tk.TclError, AttributeError):
        return False
    return fim < 1.0 if para_baixo else inicio > 0.0


def _instalar_roda(raiz):
    if getattr(raiz, "_roda_instalada", False):
        return
    raiz._roda_instalada = True
    raiz.unbind_class("TCombobox", "<MouseWheel>")

    def rolar(evento):
        try:
            alvo = raiz.winfo_containing(evento.x_root, evento.y_root)
        except (KeyError, tk.TclError):
            return
        para_baixo = evento.delta < 0
        passos = -1 if evento.delta > 0 else 1
        widget = alvo
        while widget is not None:
            if isinstance(widget, (tk.Text, tk.Listbox, ttk.Treeview)) and \
                    _pode_rolar(widget, para_baixo):
                return        # a própria caixa rola (ligação de classe)
            if str(widget) in _ROLAVEIS and _pode_rolar(widget, para_baixo):
                widget.yview_scroll(passos * 3, "units")
                return
            widget = widget.master

    raiz.bind_all("<MouseWheel>", rolar)


def criar_area_rolavel(pai, padding=20, empacotar=True, fundo=None):
    """Devolve o frame onde o conteúdo deve ser montado.

    Com `empacotar=False`, quem chama posiciona `interno.master.master`
    (o contêiner da tela + barra).
    """
    fundo = fundo or ui_tema.CORES["fundo"]
    container = tk.Frame(pai, bg=fundo)
    if empacotar:
        container.pack(fill="both", expand=True)

    # o Canvas é tk puro: sem o fundo do tema ele aparece cinza do sistema
    tela = tk.Canvas(container, highlightthickness=0, borderwidth=0, bg=fundo,
                     yscrollincrement=ui_tema.px(pai, 14))
    barra = ttk.Scrollbar(container, orient="vertical", command=tela.yview)
    tela.configure(yscrollcommand=barra.set)
    tela.pack(side="left", fill="both", expand=True)
    barra.pack(side="right", fill="y")

    interno = ttk.Frame(tela, padding=ui_tema.px(pai, padding),
                        style="Pagina.TFrame")
    id_janela = tela.create_window((0, 0), window=interno, anchor="nw")

    def ajustar(_evento=None):
        # a região rolável acompanha o conteúdo; a largura acompanha a janela
        tela.configure(scrollregion=(0, 0, tela.winfo_width(),
                                     max(interno.winfo_reqheight(),
                                         tela.winfo_height())))
        tela.itemconfigure(id_janela, width=tela.winfo_width())

    interno.bind("<Configure>", ajustar, add="+")
    tela.bind("<Configure>", ajustar, add="+")
    registrar(tela)
    return interno
