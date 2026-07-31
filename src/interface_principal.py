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


def escolher_modo():
    """Mostra o seletor. Retorna 'compra', 'venda' ou None (fechou a janela)."""
    escolha = {"modo": None}

    root = tk.Tk()
    root.title("MarketplaceBot")
    root.geometry("380x240")
    root.resizable(False, False)

    frm = ttk.Frame(root, padding=20)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text="O que você quer fazer?",
              font=("Segoe UI", 13, "bold")).pack(pady=(0, 16))

    def selecionar(modo):
        escolha["modo"] = modo
        root.destroy()

    tk.Button(
        frm, text="🛒  Compra\nbuscar anúncios e enviar mensagens",
        command=lambda: selecionar("compra"),
        bg="#2e7d32", fg="white", font=("Segoe UI", 10), height=3,
    ).pack(fill="x", pady=(0, 10))

    tk.Button(
        frm, text="📢  Venda / Anúncio\nanunciar veículos do seu banco nos sites",
        command=lambda: selecionar("venda"),
        bg="#1565c0", fg="white", font=("Segoe UI", 10), height=3,
    ).pack(fill="x")

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
