"""
Interface do bot de COMPRA (painel desktop Tkinter) — log embutido e
botão Prosseguir.
- Rodar     : grava parametros.json e inicia o run.py, mostrando o log NA JANELA.
- Prosseguir: substitui o ENTER do terminal (libera o login).
- Parar     : encerra o bot a qualquer momento.
- Voltar    : fecha esta tela e devolve o usuário à escolha Compra/Venda.

Tudo vive dentro de iniciar(), que devolve "voltar" (usuário quer trocar de
modo) ou "sair" (fechou a janela). Isso é o que permite abrir a tela mais de
uma vez no mesmo processo — quando o módulo montava a GUI no import, trocar
de modo exigia fechar e reabrir o app.
"""

import os
import sys
import json
import queue
import threading
import subprocess
import tkinter as tk
from tkinter import ttk

import contato
from sinal import dar_sinal, limpar_sinal
from paths import get_parametros_path, get_bot_command

BASE = os.path.dirname(os.path.abspath(__file__))
CAMINHO_PARAMS = str(get_parametros_path())

# Sites oferecidos na Compra (rotulo -> id usado no parametros.json).
# A OLX saiu da lista a pedido do usuario (jul/2026): ela bloqueia a
# navegacao automatizada (Cloudflare 1020) e o bot nao disfarca isso.
# Para voltar, basta reincluir ("OLX", "olx") aqui — src/compra_olx.py
# continua pronto e calibrado.
SITES_COMPRA = [
    ("Facebook Marketplace", "facebook"),
    ("iCarros", "icarros"),
]

CINZA = "#999999"
PRETO = "#000000"

processo = None
log_queue = queue.Queue()


def so_digitos(proposto):
    return proposto == "" or proposto.isdigit()


def estados_por_site(site):
    """Estado ('normal'/'readonly'/'disabled') de cada grupo de campos para o
    site escolhido. Regra separada da GUI para poder ser testada sozinha.

    - Facebook: CEP + raio em km; não tem ano/km/câmbio nem contato.
    - OLX: região pelo estado do CEP (sem raio) + ano/km/câmbio.
    - iCarros: sem raio; exige nome/e-mail/telefone (o formulário do anúncio).
    """
    olx = site == "olx"
    icarros = site == "icarros"
    return {
        "extras": "normal" if olx else "disabled",
        "cambio": "readonly" if olx else "disabled",
        "raio": "disabled" if (olx or icarros) else "readonly",
        "contato": "normal" if icarros else "disabled",
    }


def iniciar():
    """Abre o painel de Compra. Retorna 'voltar' ou 'sair'."""
    global processo
    resultado = {"acao": "sair"}

    # fila nova a cada abertura: log velho não pode vazar para a sessão nova
    global log_queue
    log_queue = queue.Queue()

    root = tk.Tk()
    root.title("MarketplaceBot — Compra")
    root.geometry("460x880")

    frm = ttk.Frame(root, padding=14)
    frm.pack(fill="both", expand=True)

    vcmd = (root.register(so_digitos), "%P")
    linha = 0

    def campo(label):
        nonlocal linha
        ttk.Label(frm, text=label).grid(row=linha, column=0, sticky="w",
                                        pady=(6, 0))
        linha += 1

    def site_escolhido():
        """id do site marcado no combo."""
        return dict(SITES_COMPRA).get(cmb_site.get(), "facebook")

    def ler_saida(proc):
        """Thread separada: lê o que o bot imprime e joga na fila."""
        for saida in proc.stdout:
            log_queue.put(saida)
        log_queue.put("\n[bot encerrado]\n")

    agendado = {"log": None}

    def drenar_log():
        """Thread principal: tira as linhas da fila e mostra no log."""
        while not log_queue.empty():
            txt_log.insert("end", log_queue.get_nowait())
            txt_log.see("end")
        agendado["log"] = root.after(100, drenar_log)

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
            "site":       site_escolhido(),
            "ano_min":    ent_ano_min.get().strip(),
            "ano_max":    ent_ano_max.get().strip(),
            "km_max":     ent_km_max.get().strip(),
            "cambio":     cmb_cambio.get(),
        }
        if not params["produto"] or not params["mensagem"]:
            status.set("Erro: Produto e Mensagem são obrigatórios.")
            return

        # dados pessoais NÃO entram no JSON: vão só no ambiente do processo
        # do bot e somem quando ele termina
        ambiente = contato.para_ambiente({
            "nome": ent_nome.get().strip(),
            "cpf": ent_cpf.get().strip(),
            "telefone": ent_telefone.get().strip(),
            "email": ent_email.get().strip(),
        })

        with open(CAMINHO_PARAMS, "w", encoding="utf-8") as f:
            json.dump(params, f, ensure_ascii=False, indent=2)

        limpar_sinal()           # descarta sinal antigo pra não 'prosseguir' sozinho
        txt_log.delete("1.0", "end")

        # -u = saida sem buffer, pra o log aparecer na hora
        processo = subprocess.Popen(
            get_bot_command(),
            cwd=BASE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, env=ambiente,
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

    def encerrar(acao):
        """Sair da tela: o bot em execução é sempre parado antes."""
        resultado["acao"] = acao
        parar()
        # sem cancelar, o polling do log dispara depois do destroy e o Tk
        # reclama de "invalid command name"
        if agendado["log"] is not None:
            try:
                root.after_cancel(agendado["log"])
            except Exception:
                pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", lambda: encerrar("sair"))

    # ---------------- topo: voltar para a escolha de modo ----------------
    topo = ttk.Frame(frm)
    topo.grid(row=linha, column=0, sticky="we", pady=(0, 8)); linha += 1
    tk.Button(topo, text="← Voltar", command=lambda: encerrar("voltar"),
              bg="#455a64", fg="white", width=10).pack(side="left")
    ttk.Label(topo, text="  Compra — buscar anúncios e enviar mensagens",
              font=("Segoe UI", 9, "bold")).pack(side="left")

    campo("Site de busca")
    cmb_site = ttk.Combobox(frm, state="readonly",
                            values=[rotulo for rotulo, _ in SITES_COMPRA])
    cmb_site.set(SITES_COMPRA[0][0])
    cmb_site.grid(row=linha, column=0, sticky="we"); linha += 1
    lbl_site_dica = ttk.Label(frm, text="", foreground="#b26a00", wraplength=430)
    lbl_site_dica.grid(row=linha, column=0, sticky="w"); linha += 1

    campo("Produto")
    ent_produto = ttk.Entry(frm)
    ent_produto.grid(row=linha, column=0, sticky="we"); linha += 1

    campo("Valor minimo (vazio = sem minimo)")
    ent_min = ttk.Entry(frm, validate="key", validatecommand=vcmd)
    ent_min.grid(row=linha, column=0, sticky="we"); linha += 1

    campo("Valor maximo (vazio = sem maximo)")
    ent_max = ttk.Entry(frm, validate="key", validatecommand=vcmd)
    ent_max.grid(row=linha, column=0, sticky="we"); linha += 1

    campo("CEP")
    ent_cep = ttk.Entry(frm)
    ent_cep.grid(row=linha, column=0, sticky="we"); linha += 1

    lbl_raio = ttk.Label(frm, text="Raio (km)")
    lbl_raio.grid(row=linha, column=0, sticky="w", pady=(6, 0)); linha += 1
    cmb_raio = ttk.Combobox(
        frm, state="readonly",
        values=["1", "2", "5", "10", "20", "40", "60", "80", "100", "250", "500"])
    cmb_raio.set("60")
    cmb_raio.grid(row=linha, column=0, sticky="we"); linha += 1

    campo("Quantidade (vazio = todos)")
    ent_qtd = ttk.Entry(frm, validate="key", validatecommand=vcmd)
    ent_qtd.grid(row=linha, column=0, sticky="we"); linha += 1

    # filtros que so a OLX tem hoje (o Facebook ignora estes campos)
    ttk.Separator(frm, orient="horizontal").grid(
        row=linha, column=0, sticky="we", pady=(10, 2)); linha += 1
    lbl_extras = ttk.Label(frm, text="Filtros extras (somente OLX)")
    lbl_extras.grid(row=linha, column=0, sticky="w", pady=(6, 0)); linha += 1

    frm_extra = ttk.Frame(frm)
    frm_extra.grid(row=linha, column=0, sticky="we"); linha += 1
    ttk.Label(frm_extra, text="Ano de").grid(row=0, column=0, sticky="w")
    ent_ano_min = ttk.Entry(frm_extra, width=8, validate="key",
                            validatecommand=vcmd)
    ent_ano_min.grid(row=0, column=1, padx=(4, 10))
    ttk.Label(frm_extra, text="ate").grid(row=0, column=2, sticky="w")
    ent_ano_max = ttk.Entry(frm_extra, width=8, validate="key",
                            validatecommand=vcmd)
    ent_ano_max.grid(row=0, column=3, padx=(4, 10))
    ttk.Label(frm_extra, text="KM ate").grid(row=0, column=4, sticky="w")
    ent_km_max = ttk.Entry(frm_extra, width=10, validate="key",
                           validatecommand=vcmd)
    ent_km_max.grid(row=0, column=5, padx=(4, 0))

    lbl_cambio = ttk.Label(frm, text="Cambio (somente OLX)")
    lbl_cambio.grid(row=linha, column=0, sticky="w", pady=(6, 0)); linha += 1
    cmb_cambio = ttk.Combobox(frm, state="readonly",
                              values=["Qualquer", "Manual", "Automático",
                                      "Semi-Automático", "Automatizado"])
    cmb_cambio.set("Qualquer")
    cmb_cambio.grid(row=linha, column=0, sticky="we"); linha += 1

    lbl_contato = ttk.Label(frm, text="Seus dados de contato (somente iCarros)")
    lbl_contato.grid(row=linha, column=0, sticky="w", pady=(6, 0)); linha += 1
    ttk.Label(frm, text="Não são salvos: só o processo do bot os recebe, "
                        "e somem quando ele termina.",
              foreground="#b26a00", wraplength=430).grid(
        row=linha, column=0, sticky="w"); linha += 1
    frm_contato = ttk.Frame(frm)
    frm_contato.grid(row=linha, column=0, sticky="we"); linha += 1
    ttk.Label(frm_contato, text="Nome").grid(row=0, column=0, sticky="w")
    ent_nome = ttk.Entry(frm_contato, width=14)
    ent_nome.grid(row=0, column=1, padx=(4, 8))
    ttk.Label(frm_contato, text="E-mail").grid(row=0, column=2, sticky="w")
    ent_email = ttk.Entry(frm_contato, width=18)
    ent_email.grid(row=0, column=3, padx=(4, 8))
    ttk.Label(frm_contato, text="Telefone").grid(row=1, column=0, sticky="w",
                                                 pady=(4, 0))
    ent_telefone = ttk.Entry(frm_contato, width=14)
    ent_telefone.grid(row=1, column=1, padx=(4, 8), pady=(4, 0))
    ttk.Label(frm_contato, text="CPF").grid(row=1, column=2, sticky="w",
                                            pady=(4, 0))
    ent_cpf = ttk.Entry(frm_contato, width=18)
    ent_cpf.grid(row=1, column=3, padx=(4, 8), pady=(4, 0))

    ttk.Separator(frm, orient="horizontal").grid(
        row=linha, column=0, sticky="we", pady=(4, 6)); linha += 1

    campo("Mensagem que o bot vai enviar")
    txt_msg = tk.Text(frm, height=3)
    txt_msg.grid(row=linha, column=0, sticky="we"); linha += 1

    var_dry = tk.IntVar(value=1)
    ttk.Checkbutton(frm, text="Modo teste (dry-run) - nao envia, so simula",
                    variable=var_dry).grid(row=linha, column=0, sticky="w",
                                           pady=6); linha += 1

    botoes = ttk.Frame(frm)
    botoes.grid(row=linha, column=0, sticky="we", pady=4); linha += 1
    tk.Button(botoes, text="Rodar", command=rodar,
              bg="#2e7d32", fg="white", width=11).pack(side="left", padx=(0, 6))
    tk.Button(botoes, text="Prosseguir", command=prosseguir,
              bg="#1565c0", fg="white", width=13).pack(side="left", padx=(0, 6))
    tk.Button(botoes, text="Parar", command=parar,
              bg="#c62828", fg="white", width=11).pack(side="left")

    ttk.Label(frm, text="Log do bot:").grid(row=linha, column=0, sticky="w",
                                            pady=(8, 0)); linha += 1
    txt_log = tk.Text(frm, height=10, bg="#0d1117", fg="#d6deeb")
    txt_log.grid(row=linha, column=0, sticky="we"); linha += 1

    status = tk.StringVar(value="Pronto. Preencha os campos e clique em Rodar.")
    ttk.Label(frm, textvariable=status, foreground="#555",
              wraplength=430).grid(row=linha, column=0, sticky="w", pady=(8, 0))

    def atualizar_campos_do_site(*_):
        """Cada site aceita filtros diferentes: o que o site escolhido nao usa
        fica desabilitado, em vez de dar a impressao de que sera aplicado.
        - Facebook: filtra por CEP + raio em km; nao tem ano/km/cambio.
        - OLX: filtra por estado (derivado do CEP) e tem ano/km/cambio.
        - iCarros: exige seus dados de contato no formulario do anuncio.
        """
        site = site_escolhido()
        olx = site == "olx"
        icarros = site == "icarros"
        estados = estados_por_site(site)

        for entrada in (ent_ano_min, ent_ano_max, ent_km_max):
            entrada.configure(state=estados["extras"])
        cmb_cambio.configure(state=estados["cambio"])
        cmb_raio.configure(state=estados["raio"])
        for entrada in (ent_nome, ent_email, ent_telefone, ent_cpf):
            entrada.configure(state=estados["contato"])

        lbl_raio.configure(
            text=("Raio (km) - este site nao usa raio" if (olx or icarros)
                  else "Raio (km)"),
            foreground=CINZA if (olx or icarros) else PRETO)
        for rotulo, texto in ((lbl_extras, "Filtros extras"),
                              (lbl_cambio, "Cambio")):
            rotulo.configure(
                text=texto if olx else f"{texto} - somente OLX",
                foreground=PRETO if olx else CINZA)
        lbl_contato.configure(
            text=("Seus dados de contato (o anuncio do iCarros exige)"
                  if icarros else "Seus dados de contato - somente iCarros"),
            foreground=PRETO if icarros else CINZA)

        if olx:
            dica = ("OLX: a regiao vem do estado do CEP (a OLX nao tem raio em "
                    "km) e o chat exige login. Rode poucos anuncios por vez: a "
                    "OLX bloqueia navegacao automatizada insistente.")
        elif icarros:
            dica = ("iCarros: escreva MARCA e MODELO em Produto (ex.: "
                    "'chevrolet onix'). Nao exige login, mas o formulario do "
                    "anuncio manda seu nome/e-mail/telefone ao vendedor. A "
                    "regiao vem do estado do CEP e o preco e filtrado pelo bot.")
        else:
            dica = "Facebook: filtra por CEP + raio em km."
        lbl_site_dica.configure(text=dica)

    cmb_site.bind("<<ComboboxSelected>>", atualizar_campos_do_site)
    atualizar_campos_do_site()   # estado inicial (Facebook)

    frm.columnconfigure(0, weight=1)
    drenar_log()      # inicia o polling do log
    root.mainloop()
    return resultado["acao"]


if __name__ == "__main__":
    iniciar()
