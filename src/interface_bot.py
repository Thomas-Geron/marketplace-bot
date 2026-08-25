"""
Interface do bot de COMPRA (painel desktop Tkinter).

- Rodar     : grava parametros.json e inicia o run.py, mostrando o log NA JANELA.
- Prosseguir: substitui o ENTER do terminal (libera o login).
- Parar     : encerra o bot a qualquer momento.
- Voltar    : fecha esta tela e devolve o usuário à escolha Compra/Venda.

Tudo vive dentro de iniciar(), que devolve "voltar" (usuário quer trocar de
modo) ou "sair" (fechou a janela) — é isso que permite abrir a tela mais de
uma vez no mesmo processo.

Cada site aceita filtros diferentes. Em vez de mostrar campo desabilitado (o
usuário fica olhando algo que não pode usar e sem saber por quê), a tela
MOSTRA OU ESCONDE cada bloco conforme o site escolhido — ver
`campos_do_site()` e `atualizar_campos_do_site()`.
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
import ui_tema
from sinal import dar_sinal, limpar_sinal
from paths import get_parametros_path, get_bot_command
from ui_scroll import criar_area_rolavel

BASE = os.path.dirname(os.path.abspath(__file__))
CAMINHO_PARAMS = str(get_parametros_path())

# Sites oferecidos na Compra (rotulo -> id usado no parametros.json).
# A OLX voltou (ago/2026) rodando no Microsoft Edge aberto normalmente —
# era o navegador sob automacao que o Cloudflare barrava (ver navegador.py).
SITES_COMPRA = [
    ("Facebook Marketplace", "facebook"),
    ("iCarros", "icarros"),
    ("Webmotors", "webmotors"),
    ("OLX", "olx"),
]

DICAS = {
    "facebook": "Filtra por CEP e raio em km.",
    "olx": ("Roda no Microsoft Edge do computador (aberto normalmente) — é "
            "o navegador sob automação que a OLX bloqueia. A região vem do "
            "estado do CEP (a OLX não tem raio em km) e o chat exige login "
            "no Edge. Rode poucos anúncios por vez."),
    "icarros": ("Escreva MARCA e MODELO em Produto (ex.: 'chevrolet onix'). "
                "Não exige login, mas o formulário do anúncio envia seu "
                "nome/e-mail/telefone ao vendedor. A região vem do estado do "
                "CEP e o preço é filtrado pelo bot."),
    "webmotors": ("O formulário do anúncio envia seu nome/e-mail/telefone ao "
                  "vendedor. Não filtra por região nesta versão e pode pedir "
                  "'Pressione e segure' — o bot espera você resolver na janela."),
}

processo = None
log_queue = queue.Queue()


def so_digitos(proposto):
    return proposto == "" or proposto.isdigit()


def campos_do_site(site):
    """Quais blocos da tela o site realmente usa.

    Regra separada da GUI para poder ser testada sozinha:
    - Facebook: CEP + raio em km; não tem ano/km/câmbio nem contato.
    - OLX: região pelo estado do CEP (sem raio) + ano/km/câmbio.
    - iCarros e Webmotors: sem raio; exigem seus dados de contato, porque o
      formulário do anúncio os envia ao vendedor.
    """
    return {
        "raio": site == "facebook",
        "extras": site == "olx",
        "contato": site in ("icarros", "webmotors"),
    }


def iniciar():
    """Abre o painel de Compra. Retorna 'voltar' ou 'sair'."""
    global processo, log_queue
    resultado = {"acao": "sair"}
    log_queue = queue.Queue()   # fila nova: log velho não vaza para a sessão

    root = tk.Tk()
    root.title("MarketplaceBot — Compra")
    root.geometry("470x780")
    root.minsize(430, 520)
    ui_tema.aplicar_tema(root)

    frm = criar_area_rolavel(root)
    frm.columnconfigure(0, weight=1)
    vcmd = (root.register(so_digitos), "%P")

    def site_escolhido():
        return dict(SITES_COMPRA).get(cmb_site.get(), "facebook")

    def ler_saida(proc):
        for saida in proc.stdout:
            log_queue.put(saida)
        log_queue.put("\n[bot encerrado]\n")

    agendado = {"log": None}

    def drenar_log():
        while not log_queue.empty():
            txt_log.insert("end", log_queue.get_nowait())
            txt_log.see("end")
        agendado["log"] = root.after(100, drenar_log)

    def rodar():
        global processo
        if processo is not None and processo.poll() is None:
            status.set("O bot já está rodando.")
            return

        produtos = [nome.strip() for nome in
                    txt_produtos.get("1.0", "end").splitlines() if nome.strip()]
        params = {
            # a fila; `produto` fica como o primeiro por compatibilidade com
            # parametros.json antigos
            "produtos":   produtos,
            "produto":    produtos[0] if produtos else "",
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
        if not produtos or not params["mensagem"]:
            status.set("Erro: informe ao menos um produto e a mensagem.")
            return

        # dados pessoais NÃO entram no JSON: vão só no ambiente do processo
        # do bot e somem quando ele termina. E só vão para o site que os
        # pede de fato — o chat da OLX, por exemplo, não usa CPF nem nada
        # disso, então nada é passado adiante quando ela é a escolhida.
        if campos_do_site(site_escolhido())["contato"]:
            dados_contato = {
                "nome": ent_nome.get().strip(),
                "cpf": ent_cpf.get().strip(),
                "telefone": ent_telefone.get().strip(),
                "email": ent_email.get().strip(),
            }
        else:
            dados_contato = {}
        ambiente = contato.para_ambiente(dados_contato)

        with open(CAMINHO_PARAMS, "w", encoding="utf-8") as f:
            json.dump(params, f, ensure_ascii=False, indent=2)

        limpar_sinal()           # descarta sinal antigo pra não 'prosseguir' sozinho
        txt_log.delete("1.0", "end")

        processo = subprocess.Popen(
            get_bot_command(),
            cwd=BASE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, env=ambiente,
        )
        threading.Thread(target=ler_saida, args=(processo,), daemon=True).start()

        modo = "DRY-RUN" if params["dry_run"] else "ENVIO REAL"
        status.set(f"Bot iniciado ({modo}). Faça o login e clique em Prosseguir.")

    def prosseguir():
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
    linha = 0

    # ------------------------------ topo ------------------------------
    topo = ttk.Frame(frm)
    topo.grid(row=linha, column=0, sticky="we"); linha += 1
    ui_tema.botao(topo, "← Voltar", lambda: encerrar("voltar"),
                  "neutro", 10).pack(side="left")
    ttk.Label(topo, text="  Compra", style="Titulo.TLabel").pack(side="left")
    ttk.Label(frm, text="Busca anúncios e envia mensagens aos vendedores.",
              style="Suave.TLabel").grid(row=linha, column=0, sticky="w",
                                         pady=(0, 10)); linha += 1

    # ---------------------------- onde buscar ----------------------------
    sec_site = ui_tema.secao(frm, "Onde buscar")
    sec_site.grid(row=linha, column=0, sticky="we", pady=(0, 8)); linha += 1
    sec_site.columnconfigure(0, weight=1)
    cmb_site = ttk.Combobox(sec_site, state="readonly",
                            values=[rotulo for rotulo, _ in SITES_COMPRA])
    cmb_site.set(SITES_COMPRA[0][0])
    cmb_site.grid(row=0, column=0, sticky="we")
    lbl_site_dica = ui_tema.dica(sec_site, largura=400)
    lbl_site_dica.grid(row=1, column=0, sticky="w", pady=(6, 0))

    # ---------------------------- o que buscar ---------------------------
    sec_busca = ui_tema.secao(frm, "O que buscar")
    sec_busca.grid(row=linha, column=0, sticky="we", pady=(0, 8)); linha += 1
    sec_busca.columnconfigure(1, weight=1)

    ttk.Label(sec_busca, text="Produtos").grid(row=0, column=0, sticky="nw",
                                               pady=(2, 0))
    txt_produtos = tk.Text(sec_busca, height=3, relief="solid", borderwidth=1,
                           font=(ui_tema.FONTE, 9), wrap="none")
    txt_produtos.grid(row=0, column=1, columnspan=3, sticky="we", pady=2)
    ttk.Label(sec_busca,
              text="Um por linha — o bot faz a fila em ordem, terminando um "
                   "nome antes de começar o próximo.",
              style="Suave.TLabel", wraplength=360, justify="left").grid(
        row=1, column=0, columnspan=4, sticky="w", pady=(0, 6))

    ttk.Label(sec_busca, text="Preço de").grid(row=2, column=0, sticky="w")
    ent_min = ttk.Entry(sec_busca, width=10, validate="key", validatecommand=vcmd)
    ent_min.grid(row=2, column=1, sticky="w", padx=(0, 8), pady=2)
    ttk.Label(sec_busca, text="até").grid(row=2, column=2, sticky="e")
    ent_max = ttk.Entry(sec_busca, width=10, validate="key", validatecommand=vcmd)
    ent_max.grid(row=2, column=3, sticky="w", pady=2)

    ttk.Label(sec_busca, text="Quantidade").grid(row=3, column=0, sticky="w")
    ent_qtd = ttk.Entry(sec_busca, width=10, validate="key", validatecommand=vcmd)
    ent_qtd.grid(row=3, column=1, sticky="w", pady=2)
    ttk.Label(sec_busca, text="por produto (vazio = todos)",
              style="Suave.TLabel").grid(row=3, column=2, columnspan=2,
                                         sticky="w")

    # ------------------------------ região ------------------------------
    sec_regiao = ui_tema.secao(frm, "Região")
    sec_regiao.columnconfigure(1, weight=1)
    ttk.Label(sec_regiao, text="CEP").grid(row=0, column=0, sticky="w")
    ent_cep = ttk.Entry(sec_regiao, width=14)
    ent_cep.grid(row=0, column=1, sticky="w", pady=2)
    lbl_raio = ttk.Label(sec_regiao, text="Raio (km)")
    lbl_raio.grid(row=1, column=0, sticky="w")
    cmb_raio = ttk.Combobox(
        sec_regiao, state="readonly", width=12,
        values=["1", "2", "5", "10", "20", "40", "60", "80", "100", "250", "500"])
    cmb_raio.set("60")
    cmb_raio.grid(row=1, column=1, sticky="w", pady=2)
    linha_regiao = linha
    sec_regiao.grid(row=linha, column=0, sticky="we", pady=(0, 8)); linha += 1

    # -------------------------- filtros extras --------------------------
    sec_extras = ui_tema.secao(frm, "Filtros extras")
    sec_extras.columnconfigure(5, weight=1)
    ttk.Label(sec_extras, text="Ano de").grid(row=0, column=0, sticky="w")
    ent_ano_min = ttk.Entry(sec_extras, width=7, validate="key",
                            validatecommand=vcmd)
    ent_ano_min.grid(row=0, column=1, padx=(4, 8))
    ttk.Label(sec_extras, text="até").grid(row=0, column=2, sticky="w")
    ent_ano_max = ttk.Entry(sec_extras, width=7, validate="key",
                            validatecommand=vcmd)
    ent_ano_max.grid(row=0, column=3, padx=(4, 8))
    ttk.Label(sec_extras, text="KM até").grid(row=0, column=4, sticky="w")
    ent_km_max = ttk.Entry(sec_extras, width=9, validate="key",
                           validatecommand=vcmd)
    ent_km_max.grid(row=0, column=5, padx=(4, 0), sticky="w")
    ttk.Label(sec_extras, text="Câmbio").grid(row=1, column=0, sticky="w",
                                              pady=(6, 0))
    cmb_cambio = ttk.Combobox(sec_extras, state="readonly", width=18,
                              values=["Qualquer", "Manual", "Automático",
                                      "Semi-Automático", "Automatizado"])
    cmb_cambio.set("Qualquer")
    cmb_cambio.grid(row=1, column=1, columnspan=3, sticky="w", pady=(6, 0))
    linha_extras = linha
    linha += 1

    # ------------------------ dados de contato -------------------------
    sec_contato = ui_tema.secao(frm, "Seus dados de contato")
    sec_contato.columnconfigure(1, weight=1)
    sec_contato.columnconfigure(3, weight=1)
    ui_tema.dica(sec_contato,
                 "O formulário do anúncio envia estes dados ao vendedor. "
                 "Nada é gravado em disco: vai só para o processo do bot e "
                 "some quando ele termina.", largura=390).grid(
        row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))
    ttk.Label(sec_contato, text="Nome").grid(row=1, column=0, sticky="w")
    ent_nome = ttk.Entry(sec_contato, width=16)
    ent_nome.grid(row=1, column=1, sticky="we", padx=(4, 8), pady=2)
    ttk.Label(sec_contato, text="E-mail").grid(row=1, column=2, sticky="w")
    ent_email = ttk.Entry(sec_contato, width=18)
    ent_email.grid(row=1, column=3, sticky="we", padx=(4, 0), pady=2)
    ttk.Label(sec_contato, text="Telefone").grid(row=2, column=0, sticky="w")
    ent_telefone = ttk.Entry(sec_contato, width=16)
    ent_telefone.grid(row=2, column=1, sticky="we", padx=(4, 8), pady=2)
    ttk.Label(sec_contato, text="CPF").grid(row=2, column=2, sticky="w")
    ent_cpf = ttk.Entry(sec_contato, width=18)
    ent_cpf.grid(row=2, column=3, sticky="we", padx=(4, 0), pady=2)
    linha_contato = linha
    linha += 1

    # ------------------------------ mensagem ----------------------------
    sec_msg = ui_tema.secao(frm, "Mensagem enviada ao vendedor")
    sec_msg.grid(row=linha, column=0, sticky="we", pady=(0, 8)); linha += 1
    sec_msg.columnconfigure(0, weight=1)
    txt_msg = tk.Text(sec_msg, height=3, relief="solid", borderwidth=1,
                      font=(ui_tema.FONTE, 9), wrap="word")
    txt_msg.grid(row=0, column=0, sticky="we")
    var_dry = tk.IntVar(value=1)
    ttk.Checkbutton(sec_msg, variable=var_dry,
                    text="Modo teste (dry-run) — preenche, mas não envia").grid(
        row=1, column=0, sticky="w", pady=(6, 0))

    # ------------------------------- ações ------------------------------
    acoes = ttk.Frame(frm)
    acoes.grid(row=linha, column=0, sticky="we", pady=(0, 8)); linha += 1
    ui_tema.botao(acoes, "Rodar", rodar, "ok", 11).pack(side="left", padx=(0, 6))
    ui_tema.botao(acoes, "Prosseguir", prosseguir, "destaque", 13).pack(
        side="left", padx=(0, 6))
    ui_tema.botao(acoes, "Parar", parar, "perigo", 11).pack(side="left")

    # -------------------------------- log -------------------------------
    sec_log = ui_tema.secao(frm, "Log do bot")
    sec_log.grid(row=linha, column=0, sticky="we"); linha += 1
    sec_log.columnconfigure(0, weight=1)
    txt_log = ui_tema.caixa_log(sec_log, altura=10)
    txt_log.grid(row=0, column=0, sticky="we")

    status = tk.StringVar(value="Pronto. Preencha os campos e clique em Rodar.")
    ttk.Label(frm, textvariable=status, style="Suave.TLabel",
              wraplength=420).grid(row=linha, column=0, sticky="w", pady=(8, 0))

    # ------------- mostrar/esconder conforme o site escolhido ------------
    def atualizar_campos_do_site(*_):
        """Some com o que o site não usa, em vez de deixar campo cinza."""
        site = site_escolhido()
        usa = campos_do_site(site)

        if usa["raio"]:
            lbl_raio.grid()
            cmb_raio.grid()
        else:
            lbl_raio.grid_remove()
            cmb_raio.grid_remove()

        for secao_alvo, visivel, onde in (
                (sec_extras, usa["extras"], linha_extras),
                (sec_contato, usa["contato"], linha_contato)):
            if visivel:
                secao_alvo.grid(row=onde, column=0, sticky="we", pady=(0, 8))
            else:
                secao_alvo.grid_remove()

        lbl_site_dica.configure(text=DICAS.get(site, ""))

    cmb_site.bind("<<ComboboxSelected>>", atualizar_campos_do_site)
    atualizar_campos_do_site()   # estado inicial (Facebook)

    drenar_log()
    root.mainloop()
    return resultado["acao"]


if __name__ == "__main__":
    iniciar()
