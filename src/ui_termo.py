# src/ui_termo.py
"""Janelas do termo de riscos: o aceite obrigatório e a leitura a qualquer hora.

O aceite roda ANTES de a janela principal montar qualquer página: a principal
fica escondida e, sem aceite, o app fecha — não existe um instante em que dê
para clicar em Rodar sem ter aceitado.
"""
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

import termo
import ui_tema

C = ui_tema.CORES


def _caixa_de_texto(pai, dados, altura):
    caixa = ScrolledText(pai, height=altura, wrap="word", font=(ui_tema.FONTE, 10),
                         relief="solid", borderwidth=1, padx=12, pady=10)
    caixa.insert("1.0", termo.texto(dados))
    caixa.configure(state="disabled")
    return caixa


def exigir_aceite(root, dados: dict, versao_app: str) -> bool:
    """Mostra o termo e só devolve True com cada declaração marcada e o nome completo."""
    janela = tk.Toplevel(root, bg=C["fundo"])
    janela.title("MarketplaceBot — Termo de riscos")
    ui_tema.icone(janela)
    ui_tema.geometria(janela, 780, 760, minimo=(620, 560), centralizar=True)
    janela.grab_set()
    janela.focus_force()
    aceitou = {"ok": False}
    pad = ui_tema.px(janela, 16)

    tk.Label(janela, text="Antes de usar: leia o termo de riscos", bg=C["fundo"], fg=C["texto"],
             font=(ui_tema.FONTE_FORTE, 13), anchor="w").pack(fill="x", padx=pad, pady=(pad, 2))
    tk.Label(janela, bg=C["fundo"], fg=C["texto_suave"], font=(ui_tema.FONTE, 9), anchor="w",
             justify="left", wraplength=ui_tema.px(janela, 700),
             text="O MarketplaceBot não é oficial. Para usar, marque cada declaração e digite seu nome "
                  "completo, que vale como assinatura.").pack(fill="x", padx=pad)
    _caixa_de_texto(janela, dados, 14).pack(fill="both", expand=True, padx=pad, pady=(10, 8))

    marcas = []
    for declaracao in dados.get("declaracoes", []):
        v = tk.BooleanVar(value=False)
        marcas.append(v)
        tk.Checkbutton(janela, text=declaracao, variable=v, command=lambda: atualizar(),
                       bg=C["fundo"], activebackground=C["fundo"], fg=C["texto"], anchor="w",
                       justify="left", wraplength=ui_tema.px(janela, 700),
                       font=(ui_tema.FONTE, 9)).pack(fill="x", padx=pad, pady=1)

    tk.Label(janela, text="Seu nome completo", bg=C["fundo"], fg=C["texto"],
             font=(ui_tema.FONTE_FORTE, 9), anchor="w").pack(fill="x", padx=pad, pady=(10, 2))
    nome = tk.StringVar()
    ttk.Entry(janela, textvariable=nome, width=48).pack(anchor="w", padx=pad)
    nome.trace_add("write", lambda *_: atualizar())

    botoes = tk.Frame(janela, bg=C["fundo"])
    botoes.pack(fill="x", padx=pad, pady=pad)
    bt_aceito = ttk.Button(botoes, text="Li, entendi os riscos e aceito", style="Primario.TButton",
                           state="disabled")
    bt_aceito.pack(side="right")
    ttk.Button(botoes, text="Não aceito (fechar)", style="Secundario.TButton",
               command=janela.destroy).pack(side="right", padx=(0, 10))

    def atualizar():
        pronto = bool(marcas) and all(v.get() for v in marcas) and termo.nome_valido(nome.get())
        bt_aceito.configure(state="normal" if pronto else "disabled")

    def aceitar():
        termo.registrar(dados, nome.get(), versao_app)
        aceitou["ok"] = True
        janela.destroy()

    bt_aceito.configure(command=aceitar)
    janela.protocol("WM_DELETE_WINDOW", janela.destroy)  # fechar no X = não aceitar
    root.wait_window(janela)
    return aceitou["ok"]


def mostrar(root, dados: dict) -> None:
    """Só leitura (link do aviso fixo)."""
    janela = tk.Toplevel(root, bg=C["fundo"])
    janela.title("MarketplaceBot — Termo de riscos")
    ui_tema.icone(janela)
    ui_tema.geometria(janela, 760, 640, centralizar=True)
    janela.transient(root)
    pad = ui_tema.px(janela, 16)
    _caixa_de_texto(janela, dados, 24).pack(fill="both", expand=True, padx=pad, pady=(pad, 8))
    ttk.Button(janela, text="Fechar", style="Secundario.TButton",
               command=janela.destroy).pack(anchor="e", padx=pad, pady=(0, pad))
