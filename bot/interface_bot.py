"""
Interface do bot (painel desktop Tkinter) — com log embutido e botão Prosseguir.
- Rodar     : grava parametros.json e inicia o run.py, mostrando o log NA JANELA.
- Prosseguir: substitui o ENTER do terminal (libera o login).
- Parar     : encerra o bot a qualquer momento.

Coloque este arquivo dentro de bot/ (ao lado de run.py, config.py, sinal.py).
Rode com:  python interface_bot.py

O alvo do bot continua sendo o que estiver no URL_BUSCA do config.py (o clone).
"""

import os
import sys
import json
import queue
import threading
import subprocess
import tkinter as tk
from tkinter import ttk

from sinal import dar_sinal, limpar_sinal

BASE = os.path.dirname(os.path.abspath(__file__))
CAMINHO_PARAMS = os.path.join(BASE, "parametros.json")

processo = None
log_queue = queue.Queue()


def so_digitos(proposto):
    return proposto == "" or proposto.isdigit()


def ler_saida(proc):
    """Thread separada: lê o que o bot imprime e joga na fila."""
    for linha in proc.stdout:
        log_queue.put(linha)
    log_queue.put("\n[bot encerrado]\n")


def drenar_log():
    """Thread principal: tira as linhas da fila e mostra no log (a cada 100ms)."""
    while not log_queue.empty():
        txt_log.insert("end", log_queue.get_nowait())
        txt_log.see("end")
    root.after(100, drenar_log)


def rodar():
    global processo
    if processo is not None and processo.poll() is None:
        status.set("O bot já está rodando.")
        return

    params = {
        "produto":    ent_produto.get().strip(),
        "preco_min":  ent_min.get().strip(),
        "preco_max":  ent_max.get().strip(),
        "cep":        ent_cep.get().strip(),
        "raio_km":    cmb_raio.get(),
        "quantidade": ent_qtd.get().strip(),
        "mensagem":   txt_msg.get("1.0", "end").strip(),
        "dry_run":    bool(var_dry.get()),
    }
    if not params["produto"] or not params["mensagem"]:
        status.set("Erro: Produto e Mensagem são obrigatórios.")
        return

    with open(CAMINHO_PARAMS, "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)

    limpar_sinal()               # descarta sinal antigo pra não 'prosseguir' sozinho
    txt_log.delete("1.0", "end")

    # -u = saida sem buffer, pra o log aparecer na hora
    processo = subprocess.Popen(
        [sys.executable, "-u", "run.py"],
        cwd=BASE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    threading.Thread(target=ler_saida, args=(processo,), daemon=True).start()

    modo = "DRY-RUN" if params["dry_run"] else "ENVIO REAL"
    status.set(f"Bot iniciado ({modo}). Faça o login e clique em Prosseguir.")


def prosseguir():
    """Cria o sinal que libera o bot (substitui o ENTER)."""
    if processo is not None and processo.poll() is None:
        dar_sinal()
        status.set("Sinal enviado — o bot vai prosseguir.")
    else:
        status.set("O bot não está rodando.")


def parar():
    global processo
    if processo is not None and processo.poll() is None:
        processo.terminate()
        processo = None
        status.set("Bot parado.")
    else:
        status.set("O bot não está rodando.")


def ao_fechar():
    parar()
    root.destroy()


# ===================== janela =====================
root = tk.Tk()
root.title("Painel do Bot — estudo de seguranca")
root.geometry("460x700")
root.protocol("WM_DELETE_WINDOW", ao_fechar)

frm = ttk.Frame(root, padding=14)
frm.pack(fill="both", expand=True)

vcmd = (root.register(so_digitos), "%P")
linha = 0

def campo(label):
    global linha
    ttk.Label(frm, text=label).grid(row=linha, column=0, sticky="w", pady=(6, 0))
    linha += 1

campo("Produto")
ent_produto = ttk.Entry(frm); ent_produto.grid(row=linha, column=0, sticky="we"); linha += 1

campo("Valor minimo (vazio = sem minimo)")
ent_min = ttk.Entry(frm, validate="key", validatecommand=vcmd)
ent_min.grid(row=linha, column=0, sticky="we"); linha += 1

campo("Valor maximo (vazio = sem maximo)")
ent_max = ttk.Entry(frm, validate="key", validatecommand=vcmd)
ent_max.grid(row=linha, column=0, sticky="we"); linha += 1

campo("CEP")
ent_cep = ttk.Entry(frm); ent_cep.grid(row=linha, column=0, sticky="we"); linha += 1

campo("Raio (km)")
cmb_raio = ttk.Combobox(frm, state="readonly",
                        values=["1","2","5","10","20","40","60","80","100","250","500"])
cmb_raio.set("60"); cmb_raio.grid(row=linha, column=0, sticky="we"); linha += 1

campo("Quantidade (vazio = todos)")
ent_qtd = ttk.Entry(frm, validate="key", validatecommand=vcmd)
ent_qtd.grid(row=linha, column=0, sticky="we"); linha += 1

campo("Mensagem que o bot vai enviar")
txt_msg = tk.Text(frm, height=3); txt_msg.grid(row=linha, column=0, sticky="we"); linha += 1

var_dry = tk.IntVar(value=1)
ttk.Checkbutton(frm, text="Modo teste (dry-run) - nao envia, so simula",
                variable=var_dry).grid(row=linha, column=0, sticky="w", pady=6); linha += 1

botoes = ttk.Frame(frm); botoes.grid(row=linha, column=0, sticky="we", pady=4); linha += 1
tk.Button(botoes, text="Rodar", command=rodar,
          bg="#2e7d32", fg="white", width=11).pack(side="left", padx=(0, 6))
tk.Button(botoes, text="Prosseguir", command=prosseguir,
          bg="#1565c0", fg="white", width=13).pack(side="left", padx=(0, 6))
tk.Button(botoes, text="Parar", command=parar,
          bg="#c62828", fg="white", width=11).pack(side="left")

ttk.Label(frm, text="Log do bot:").grid(row=linha, column=0, sticky="w", pady=(8, 0)); linha += 1
txt_log = tk.Text(frm, height=10, bg="#0d1117", fg="#d6deeb")
txt_log.grid(row=linha, column=0, sticky="we"); linha += 1

status = tk.StringVar(value="Pronto. Preencha os campos e clique em Rodar.")
ttk.Label(frm, textvariable=status, foreground="#555",
          wraplength=430).grid(row=linha, column=0, sticky="w", pady=(8, 0))

frm.columnconfigure(0, weight=1)
drenar_log()      # inicia o polling do log
root.mainloop()
