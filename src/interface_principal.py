# src/interface_principal.py
"""
Tela inicial do MarketplaceBot: escolha entre os dois modos.

  Compra        → interface_bot.py (buscar anúncios e enviar mensagens)
  Venda/Anúncio → venda/interface_venda.py (anunciar veículos do banco)

O app fica num laço: cada tela devolve "voltar" (o seletor reaparece) ou
"sair" (o app encerra). Assim dá para trocar de modo sem fechar e reabrir.
"""
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

import ui_tema

# ícones da fonte de sistema do Windows (Segoe MDL2 Assets / Fluent Icons)
ICONES = {"compra": "", "venda": ""}   # carrinho, etiqueta
TINTAS = {"compra": ("#e7f3e8", "#0f7b0f"), "venda": ("#e6f0fb", "#005fb8")}


def _fonte_icones(janela):
    familias = set(tkfont.families(janela))
    for nome in ("Segoe Fluent Icons", "Segoe MDL2 Assets"):
        if nome in familias:
            return nome
    return None


def _cartao(pai, modo, titulo, descricao, comando):
    """Bloco clicável de um modo: ícone, título, explicação e seta."""
    cores = ui_tema.CORES
    px = lambda v: ui_tema.px(pai, v)  # noqa: E731
    fundo, fundo_hover = cores["cartao"], "#f5f8fc"
    tinta_fundo, tinta = TINTAS[modo]

    quadro = tk.Frame(pai, bg=fundo, cursor="hand2", highlightthickness=1,
                      highlightbackground=cores["borda"],
                      highlightcolor=cores["borda"])
    quadro.pack(fill="x", pady=(0, px(12)))
    interno = tk.Frame(quadro, bg=fundo, padx=px(18), pady=px(16))
    interno.pack(fill="both", expand=True)
    interno.columnconfigure(1, weight=1)

    fonte_icone = _fonte_icones(pai)
    icone = tk.Label(interno, text=ICONES[modo] if fonte_icone else titulo[0],
                     bg=tinta_fundo, fg=tinta, width=3, height=1,
                     font=((fonte_icone, 16) if fonte_icone
                           else (ui_tema.FONTE_FORTE, 14)))
    icone.grid(row=0, column=0, rowspan=2, sticky="ns", padx=(0, px(14)),
               ipady=px(6))

    nome = tk.Label(interno, text=titulo, bg=fundo, fg=cores["titulo"],
                    font=(ui_tema.FONTE_FORTE, 12), anchor="w")
    nome.grid(row=0, column=1, sticky="we")
    texto = tk.Label(interno, text=descricao, bg=fundo, fg=cores["suave"],
                     font=(ui_tema.FONTE, 9), anchor="w", justify="left",
                     wraplength=px(290))
    texto.grid(row=1, column=1, sticky="we", pady=(px(2), 0))
    seta = tk.Label(interno, text="›", bg=fundo, fg=cores["suave"],
                    font=(ui_tema.FONTE, 20))
    seta.grid(row=0, column=2, rowspan=2, sticky="e", padx=(px(10), 0))

    fundos = (quadro, interno, nome, texto, seta)

    def realce(ligado):
        cor = fundo_hover if ligado else fundo
        for alvo in fundos:
            alvo.configure(bg=cor)
        quadro.configure(highlightbackground=tinta if ligado else cores["borda"])

    # o cartão inteiro clica e reage ao mouse, não só o texto
    for alvo in (*fundos, icone):
        alvo.bind("<Button-1>", lambda _e: comando())
        alvo.bind("<Enter>", lambda _e: realce(True))
        alvo.bind("<Leave>", lambda _e: realce(False))
    return quadro


def escolher_modo():
    """Mostra o seletor. Retorna 'compra', 'venda' ou None (fechou a janela)."""
    escolha = {"modo": None}

    root = tk.Tk()
    root.title("MarketplaceBot")
    ui_tema.aplicar_tema(root)
    ui_tema.geometria(root, 480, 380)
    root.resizable(False, False)

    frm = ttk.Frame(root, padding=ui_tema.px(root, 28))
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text="MarketplaceBot", style="Titulo.TLabel").pack(anchor="w")
    ttk.Label(frm, text="O que você quer fazer hoje?",
              style="Subtitulo.TLabel").pack(anchor="w",
                                             pady=(0, ui_tema.px(root, 20)))

    def selecionar(modo):
        escolha["modo"] = modo
        root.destroy()

    _cartao(frm, "compra", "Compra",
            "Busca anúncios nos sites e envia mensagens aos vendedores.",
            lambda: selecionar("compra"))
    _cartao(frm, "venda", "Venda / Anúncio",
            "Anuncia os veículos do seu banco nos sites escolhidos.",
            lambda: selecionar("venda"))

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
