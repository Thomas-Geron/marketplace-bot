# src/interface_principal.py
"""
Tela inicial do MarketplaceBot: escolha entre os dois modos.

  Compra        → interface_bot.py (buscar anúncios e enviar mensagens)
  Venda/Anúncio → venda/interface_venda.py (anunciar veículos do banco)

O app fica num laço: cada tela devolve "voltar" (o seletor reaparece) ou
"sair" (o app encerra). Assim dá para trocar de modo sem fechar e reabrir.
"""
import tkinter as tk
from tkinter import ttk

import ui_tema


def _cartao(pai, titulo, descricao, comando, cor):
    """Bloco clicável de um modo: título grande + explicação embaixo."""
    quadro = tk.Frame(pai, bg=ui_tema.CORES["cartao"], cursor="hand2",
                      highlightbackground=ui_tema.CORES["borda"],
                      highlightthickness=1)
    quadro.pack(fill="x", pady=(0, 10))

    faixa = tk.Frame(quadro, bg=ui_tema.CORES[cor], width=5)
    faixa.pack(side="left", fill="y")

    interno = tk.Frame(quadro, bg=ui_tema.CORES["cartao"], padx=14, pady=12)
    interno.pack(side="left", fill="both", expand=True)
    tk.Label(interno, text=titulo, bg=ui_tema.CORES["cartao"],
             fg=ui_tema.CORES["titulo"], font=(ui_tema.FONTE, 11, "bold"),
             anchor="w").pack(fill="x")
    tk.Label(interno, text=descricao, bg=ui_tema.CORES["cartao"],
             fg=ui_tema.CORES["suave"], font=(ui_tema.FONTE, 9),
             anchor="w", justify="left", wraplength=330).pack(fill="x",
                                                              pady=(2, 0))

    # o cartão inteiro clica, não só o texto
    for alvo in (quadro, interno, *interno.winfo_children()):
        alvo.bind("<Button-1>", lambda _e: comando())
    return quadro


def escolher_modo():
    """Mostra o seletor. Retorna 'compra', 'venda' ou None (fechou a janela)."""
    escolha = {"modo": None}

    root = tk.Tk()
    root.title("MarketplaceBot")
    root.geometry("400x300")
    root.resizable(False, False)
    ui_tema.aplicar_tema(root)

    frm = ttk.Frame(root, padding=18)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text="MarketplaceBot",
              style="Titulo.TLabel").pack(anchor="w")
    ttk.Label(frm, text="O que você quer fazer?",
              style="Suave.TLabel").pack(anchor="w", pady=(0, 14))

    def selecionar(modo):
        escolha["modo"] = modo
        root.destroy()

    _cartao(frm, "Compra",
            "Busca anúncios nos sites e envia mensagens aos vendedores.",
            lambda: selecionar("compra"), "ok")
    _cartao(frm, "Venda / Anúncio",
            "Anuncia os veículos do seu banco nos sites escolhidos.",
            lambda: selecionar("venda"), "destaque")

    try:
        from version import __version__
        ttk.Label(frm, text=f"versão {__version__}",
                  style="Suave.TLabel").pack(anchor="e", side="bottom")
    except Exception:
        pass

    root.mainloop()
    return escolha["modo"]


def iniciar():
    """Laço principal: seletor → modo escolhido → seletor de novo."""
    while True:
        modo = escolher_modo()
        if modo is None:          # fechou o seletor: encerra o app
            return

        if modo == "compra":
            import interface_bot

            acao = interface_bot.iniciar()
        else:
            from venda import interface_venda

            acao = interface_venda.iniciar()

        if acao != "voltar":      # fechou a tela do modo: encerra o app
            return
