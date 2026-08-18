# src/ui_tema.py
"""
Aparência comum das telas do bot.

As telas foram crescendo cada uma por conta própria (fontes do sistema,
cores soltas no meio do código, espaçamentos diferentes). Aqui ficam a
paleta, os estilos ttk e os atalhos de seção/botão, para as três telas
parecerem o mesmo programa.
"""
import tkinter as tk
from tkinter import ttk

CORES = {
    "fundo": "#f4f6f8",
    "cartao": "#ffffff",
    "titulo": "#1f2933",
    "texto": "#3e4c59",
    "suave": "#7b8794",
    "destaque": "#1565c0",
    "aviso": "#b26a00",
    "ok": "#2e7d32",
    "perigo": "#c62828",
    "neutro": "#455a64",
    "borda": "#d9dee4",
}

FONTE = "Segoe UI"


def aplicar_tema(janela):
    """Estilos ttk + fundo da janela. Chamar logo depois de criar a Tk."""
    janela.configure(bg=CORES["fundo"])
    estilo = ttk.Style(janela)
    try:
        estilo.theme_use("clam")   # o único tema do Windows que aceita cor
    except tk.TclError:
        pass

    estilo.configure(".", background=CORES["fundo"], foreground=CORES["texto"],
                     font=(FONTE, 9))
    estilo.configure("TFrame", background=CORES["fundo"])
    estilo.configure("TLabel", background=CORES["fundo"])
    estilo.configure("TCheckbutton", background=CORES["fundo"])
    estilo.configure("TLabelframe", background=CORES["fundo"],
                     bordercolor=CORES["borda"], relief="solid", borderwidth=1)
    estilo.configure("TLabelframe.Label", background=CORES["fundo"],
                     foreground=CORES["titulo"], font=(FONTE, 9, "bold"))
    estilo.configure("TEntry", fieldbackground=CORES["cartao"],
                     bordercolor=CORES["borda"], padding=3)
    estilo.configure("TCombobox", fieldbackground=CORES["cartao"], padding=3)

    estilo.configure("Titulo.TLabel", font=(FONTE, 13, "bold"),
                     foreground=CORES["titulo"])
    estilo.configure("Secao.TLabel", font=(FONTE, 9, "bold"),
                     foreground=CORES["titulo"])
    estilo.configure("Suave.TLabel", foreground=CORES["suave"])
    estilo.configure("Aviso.TLabel", foreground=CORES["aviso"])
    estilo.configure("Ok.TLabel", foreground=CORES["ok"])
    return estilo


def secao(pai, titulo):
    """Bloco com título — agrupa campos que pertencem ao mesmo assunto."""
    return ttk.LabelFrame(pai, text=f" {titulo} ", padding=10)


def botao(pai, texto, comando, cor="destaque", largura=12):
    """Botão colorido (o ttk não pinta botão de forma confiável no Windows)."""
    return tk.Button(pai, text=texto, command=comando,
                     bg=CORES[cor], fg="white", width=largura,
                     font=(FONTE, 9, "bold"), relief="flat",
                     activebackground=CORES[cor], activeforeground="white",
                     cursor="hand2")


def dica(pai, texto="", largura=430):
    """Linha de explicação em laranja (o que o site aceita, avisos)."""
    return ttk.Label(pai, text=texto, style="Aviso.TLabel", wraplength=largura,
                     justify="left")


def caixa_log(pai, altura=10):
    return tk.Text(pai, height=altura, bg="#0d1117", fg="#d6deeb",
                   insertbackground="#d6deeb", relief="flat",
                   font=("Consolas", 9), wrap="word")
