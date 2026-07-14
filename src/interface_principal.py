# src/interface_principal.py
"""
Tela inicial do MarketplaceBot: escolha entre os dois modos.

  Compra        → bot atual (interface_bot.py, intocado)
  Venda/Anúncio → anuncia veículos do seu banco nos sites escolhidos
"""
import tkinter as tk
from tkinter import ttk


def iniciar():
    escolha = {"modo": None}

    root = tk.Tk()
    root.title("MarketplaceBot")
    root.geometry("380x240")
    root.resizable(False, False)

    frm = ttk.Frame(root, padding=20)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text="O que você quer fazer?",
              font=("Segoe UI", 13, "bold")).pack(pady=(0, 16))

    def escolher(modo):
        escolha["modo"] = modo
        root.destroy()

    tk.Button(
        frm, text="🛒  Compra\nbuscar anúncios e enviar mensagens",
        command=lambda: escolher("compra"),
        bg="#2e7d32", fg="white", font=("Segoe UI", 10), height=3,
    ).pack(fill="x", pady=(0, 10))

    tk.Button(
        frm, text="📢  Venda / Anúncio\nanunciar veículos do seu banco nos sites",
        command=lambda: escolher("venda"),
        bg="#1565c0", fg="white", font=("Segoe UI", 10), height=3,
    ).pack(fill="x")

    root.mainloop()

    # abre o modo escolhido depois que a janela do seletor fechou
    if escolha["modo"] == "compra":
        import interface_bot  # noqa: F401 — o módulo executa a GUI ao ser importado
    elif escolha["modo"] == "venda":
        from venda import interface_venda

        interface_venda.iniciar()
