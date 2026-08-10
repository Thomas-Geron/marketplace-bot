# src/ui_scroll.py
"""
Área rolável para as telas do bot.

As duas telas cresceram (filtros por site, dados de contato, logins) e
passaram a estourar a altura da janela em telas menores: sem rolagem, os
botões de ação e o log ficavam inalcançáveis. Este helper embrulha o
conteúdo num Canvas com barra de rolagem e devolve o frame interno — quem
usa continua fazendo pack/grid normalmente, sem saber da rolagem.
"""
import tkinter as tk
from tkinter import ttk


def criar_area_rolavel(janela, padding=14):
    """Devolve o frame onde o conteúdo deve ser montado."""
    container = ttk.Frame(janela)
    container.pack(fill="both", expand=True)

    tela = tk.Canvas(container, highlightthickness=0, borderwidth=0)
    barra = ttk.Scrollbar(container, orient="vertical", command=tela.yview)
    tela.configure(yscrollcommand=barra.set)

    tela.pack(side="left", fill="both", expand=True)
    barra.pack(side="right", fill="y")

    interno = ttk.Frame(tela, padding=padding)
    id_janela = tela.create_window((0, 0), window=interno, anchor="nw")

    def ajustar(_evento=None):
        # a região rolável acompanha o conteúdo; a largura acompanha a janela
        tela.configure(scrollregion=tela.bbox("all"))
        tela.itemconfigure(id_janela, width=tela.winfo_width())

    interno.bind("<Configure>", ajustar)
    tela.bind("<Configure>", ajustar)

    def rolar(evento):
        tela.yview_scroll(int(-evento.delta / 120), "units")

    # só captura a roda do mouse enquanto o ponteiro está sobre esta área,
    # senão uma tela roubaria a rolagem da outra no mesmo processo
    interno.bind("<Enter>", lambda _e: tela.bind_all("<MouseWheel>", rolar))
    interno.bind("<Leave>", lambda _e: tela.unbind_all("<MouseWheel>"))
    janela.bind("<Destroy>", lambda _e: tela.unbind_all("<MouseWheel>"))

    return interno
