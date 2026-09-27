# src/ui_licenca.py
"""
Tela da licença: confere no Giro antes de a janela montar qualquer página.

Sem plano que inclua o bot, sem pagamento em dia, sem token ou sem internet,
não dá para chegar ao Rodar — a janela principal só aparece depois do "ok"
do Giro (mesma ideia do termo de riscos, em ui_termo.py).
"""
import tkinter as tk
import webbrowser
from tkinter import ttk

import licenca
import ui_tema

C = ui_tema.CORES

EXPLICACAO = ("O MarketplaceBot faz parte do plano Revenda. O bot confere no "
              "Giro se a sua loja tem o plano e se o pagamento está em dia — "
              "por isso ele precisa de internet para abrir.")
ONDE_TOKEN = ("Cole aqui o token da sua loja. Você gera no site do Giro, em "
              "Bot > \"Token dos bots\". É o mesmo token do Giro Bot.")


def exigir(root, versao_app=""):
    """Devolve os dados da licença quando o Giro liberar; None se fechar."""
    janela = tk.Toplevel(root, bg=C["fundo"])
    janela.title("MarketplaceBot — Licença")
    ui_tema.icone(janela)
    ui_tema.geometria(janela, 620, 520, minimo=(520, 460), centralizar=True)
    janela.grab_set()
    janela.focus_force()
    resultado = {"licenca": None}
    pad = ui_tema.px(janela, 16)
    largura = ui_tema.px(janela, 540)

    tk.Label(janela, text="Licença da sua loja", bg=C["fundo"], fg=C["texto"],
             font=(ui_tema.FONTE_FORTE, 13), anchor="w").pack(
        fill="x", padx=pad, pady=(pad, 2))
    tk.Label(janela, text=EXPLICACAO, bg=C["fundo"], fg=C["texto_suave"],
             font=(ui_tema.FONTE, 9), anchor="w", justify="left",
             wraplength=largura).pack(fill="x", padx=pad)

    estado = tk.Label(janela, text="", bg=C["fundo"], fg=C["texto"], anchor="w",
                      justify="left", wraplength=largura,
                      font=(ui_tema.FONTE, 10))
    estado.pack(fill="x", padx=pad, pady=(pad, 0))

    tk.Label(janela, text=ONDE_TOKEN, bg=C["fundo"], fg=C["texto_suave"],
             font=(ui_tema.FONTE, 9), anchor="w", justify="left",
             wraplength=largura).pack(fill="x", padx=pad, pady=(pad, 4))
    linha = tk.Frame(janela, bg=C["fundo"])
    linha.pack(fill="x", padx=pad)
    var_token = tk.StringVar(value=licenca.token())
    entrada = ttk.Entry(linha, textvariable=var_token, show="•", width=46)
    entrada.pack(side="left", fill="x", expand=True)
    var_mostrar = tk.IntVar(value=0)
    ttk.Checkbutton(linha, text="Mostrar", variable=var_mostrar,
                    command=lambda: entrada.configure(
                        show="" if var_mostrar.get() else "•")).pack(
        side="left", padx=(ui_tema.px(janela, 8), 0))

    links = tk.Frame(janela, bg=C["fundo"])
    links.pack(fill="x", padx=pad, pady=(ui_tema.px(janela, 10), 0))
    for texto_link, url in (("Abrir onde gerar o token", licenca.PAGINA_TOKEN),
                            ("Abrir Meu plano", licenca.PAGINA_PLANO)):
        ttk.Button(links, text=texto_link, style="Secundario.TButton",
                   cursor="hand2",
                   command=lambda u=url: webbrowser.open(u)).pack(
            side="left", padx=(0, ui_tema.px(janela, 8)))

    botoes = tk.Frame(janela, bg=C["fundo"])
    botoes.pack(fill="x", padx=pad, pady=pad, side="bottom")
    bt_conferir = ttk.Button(botoes, text="Conferir e usar o bot",
                             style="Primario.TButton", cursor="hand2")
    bt_conferir.pack(side="right")
    ttk.Button(botoes, text="Fechar o programa", style="Secundario.TButton",
               cursor="hand2", command=janela.destroy).pack(
        side="right", padx=(0, ui_tema.px(janela, 10)))

    def conferir():
        estado.configure(text="Conferindo no Giro…", fg=C["texto_suave"])
        bt_conferir.state(["disabled"])
        janela.update_idletasks()
        licenca.salvar_token(var_token.get())
        try:
            resultado["licenca"] = licenca.consultar()
        except licenca.Bloqueado as exc:
            estado.configure(text=str(exc), fg=C["erro_texto"])
        except licenca.SemResposta as exc:
            estado.configure(text=f"{exc}\n\nSem conferir no Giro o bot não "
                                  "inicia. Veja a internet e tente de novo.",
                             fg=C["erro_texto"])
        finally:
            bt_conferir.state(["!disabled"])
        if resultado["licenca"]:
            janela.destroy()

    bt_conferir.configure(command=conferir)
    janela.protocol("WM_DELETE_WINDOW", janela.destroy)   # fechar = não usar
    if var_token.get():
        janela.after(200, conferir)          # já tem token: confere sozinho
    else:
        estado.configure(text="Ainda não há token neste computador.",
                         fg=C["texto"])
    root.wait_window(janela)
    return resultado["licenca"]
