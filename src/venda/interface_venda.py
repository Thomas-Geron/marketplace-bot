# src/venda/interface_venda.py
"""
Interface do módulo Venda/Anúncio (Tkinter).

Fluxo: login na conta do usuário (Supabase) → lista os veículos DELE →
usuário marca veículos + sites → Rodar grava parametros_venda.json e
inicia o anunciador como subprocesso (mesmo padrão da tela de Compra:
log na janela, botão Prosseguir libera após login manual nos sites).
"""
import json
import queue
import subprocess
import threading
import tkinter as tk
from tkinter import ttk

from paths import get_parametros_venda_path, get_venda_command
from sinal import dar_sinal, limpar_sinal
from venda import anunciados
from venda.banco import BancoVeiculos
from venda.config_venda import modo_demo
from venda.sites import listar_sites

processo = None
log_queue = queue.Queue()


def iniciar():
    global processo
    banco = BancoVeiculos()
    veiculos = []          # dicts normalizados vindos do banco
    vars_sites = {}        # site_id -> IntVar

    root = tk.Tk()
    root.title("MarketplaceBot — Venda/Anúncio")
    root.geometry("560x760")

    frm = ttk.Frame(root, padding=14)
    frm.pack(fill="both", expand=True)

    status = tk.StringVar(value="Entre com sua conta para carregar seus veículos.")

    # ============================ login ============================
    frm_login = ttk.LabelFrame(frm, text="Conta", padding=10)
    frm_login.pack(fill="x")

    ttk.Label(frm_login, text="E-mail").grid(row=0, column=0, sticky="w")
    ent_email = ttk.Entry(frm_login, width=32)
    ent_email.grid(row=0, column=1, sticky="we", padx=6)

    ttk.Label(frm_login, text="Senha").grid(row=1, column=0, sticky="w")
    ent_senha = ttk.Entry(frm_login, width=32, show="•")
    ent_senha.grid(row=1, column=1, sticky="we", padx=6)

    lbl_conta = ttk.Label(frm_login, text="", foreground="#2e7d32")

    if modo_demo():
        ttk.Label(
            frm_login,
            text="MODO DEMONSTRAÇÃO: Supabase não configurado "
                 "(qualquer login entra; veículos de exemplo).",
            foreground="#b26a00", wraplength=480,
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))

    # ========================= veículos ============================
    frm_veic = ttk.LabelFrame(frm, text="Seus veículos (marque os que quer anunciar)", padding=10)
    lst_veiculos = tk.Listbox(frm_veic, selectmode="multiple", height=9, activestyle="none")
    scroll = ttk.Scrollbar(frm_veic, orient="vertical", command=lst_veiculos.yview)
    lst_veiculos.configure(yscrollcommand=scroll.set)
    lst_veiculos.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")

    def preencher_lista():
        lst_veiculos.delete(0, "end")
        registros = anunciados.carregar()
        for v in veiculos:
            preco = f"R$ {v['preco']:,}".replace(",", ".") if v.get("preco") else "sem preço"
            linha = f"{v['titulo']}  —  {preco}"
            ja = anunciados.sites_do_veiculo(v["id"], registros)
            if ja:
                linha += f"   [já em: {', '.join(ja)}]"
            lst_veiculos.insert("end", linha)

    def carregar_veiculos():
        nonlocal veiculos
        try:
            veiculos = banco.listar_veiculos()
        except Exception as exc:
            status.set(f"Erro ao buscar veículos: {exc}")
            return
        preencher_lista()
        status.set(f"{len(veiculos)} veículo(s) carregado(s). "
                   "Marque veículos e sites e clique em Rodar.")

    def apos_login():
        lbl_conta.config(text=f"Conectado: {banco.email}")
        lbl_conta.grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))
        frm_veic.pack(fill="both", expand=True, pady=(10, 0))
        frm_sites.pack(fill="x", pady=(10, 0))
        frm_acoes.pack(fill="x", pady=(10, 0))
        carregar_veiculos()

    def entrar():
        ok, erro = banco.login(ent_email.get().strip(), ent_senha.get())
        if not ok:
            status.set(erro)
            return
        apos_login()

    ttk.Button(frm_login, text="Entrar", command=entrar).grid(
        row=0, column=2, rowspan=2, padx=(8, 0), sticky="ns"
    )
    frm_login.columnconfigure(1, weight=1)

    # =========================== sites =============================
    frm_sites = ttk.LabelFrame(
        frm, text="Sites (você fará o login manualmente em cada um)", padding=10
    )
    for site in listar_sites():
        var = tk.IntVar(value=0)
        vars_sites[site.id] = var
        ttk.Checkbutton(frm_sites, text=site.nome, variable=var).pack(anchor="w")
    ttk.Label(
        frm_sites,
        text="Cada veículo é anunciado no máximo UMA vez por site (anti-spam).",
        foreground="#555",
    ).pack(anchor="w", pady=(6, 0))

    # ====================== ações + log ============================
    frm_acoes = ttk.Frame(frm)

    var_dry = tk.IntVar(value=1)
    ttk.Checkbutton(
        frm_acoes, text="Modo teste (dry-run) - preenche mas não publica",
        variable=var_dry,
    ).pack(anchor="w")

    def ler_saida(proc):
        for linha in proc.stdout:
            log_queue.put(linha)
        log_queue.put("\n[anunciador encerrado]\n")

    def drenar_log():
        while not log_queue.empty():
            txt_log.insert("end", log_queue.get_nowait())
            txt_log.see("end")
        root.after(100, drenar_log)

    def rodar():
        global processo
        if processo is not None and processo.poll() is None:
            status.set("O anunciador já está rodando.")
            return

        selecionados = [veiculos[i] for i in lst_veiculos.curselection()]
        sites_sel = [sid for sid, var in vars_sites.items() if var.get()]
        if not selecionados or not sites_sel:
            status.set("Marque ao menos um veículo e um site.")
            return

        params = {
            "veiculos": selecionados,
            "sites": sites_sel,
            "dry_run": bool(var_dry.get()),
        }
        with open(get_parametros_venda_path(), "w", encoding="utf-8") as f:
            json.dump(params, f, ensure_ascii=False, indent=2)

        limpar_sinal()
        txt_log.delete("1.0", "end")
        processo = subprocess.Popen(
            get_venda_command(),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        threading.Thread(target=ler_saida, args=(processo,), daemon=True).start()
        status.set("Anunciador iniciado. Logue nos sites abertos e clique em Prosseguir.")

    def prosseguir():
        if processo is not None and processo.poll() is None:
            dar_sinal()
            status.set("Sinal enviado — o anunciador vai prosseguir.")
        else:
            status.set("O anunciador não está rodando.")

    def parar():
        global processo
        if processo is not None and processo.poll() is None:
            processo.terminate()
            processo = None
            preencher_lista()  # atualiza os marcadores [já em: ...]
            status.set("Anunciador parado.")
        else:
            status.set("O anunciador não está rodando.")

    botoes = ttk.Frame(frm_acoes)
    botoes.pack(fill="x", pady=6)
    tk.Button(botoes, text="Rodar", command=rodar,
              bg="#2e7d32", fg="white", width=11).pack(side="left", padx=(0, 6))
    tk.Button(botoes, text="Prosseguir", command=prosseguir,
              bg="#1565c0", fg="white", width=13).pack(side="left", padx=(0, 6))
    tk.Button(botoes, text="Parar", command=parar,
              bg="#c62828", fg="white", width=11).pack(side="left")

    ttk.Label(frm_acoes, text="Log do anunciador:").pack(anchor="w", pady=(6, 0))
    txt_log = tk.Text(frm_acoes, height=9, bg="#0d1117", fg="#d6deeb")
    txt_log.pack(fill="both", expand=True)

    ttk.Label(frm, textvariable=status, foreground="#555",
              wraplength=520).pack(anchor="w", pady=(8, 0))

    def ao_fechar():
        parar()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", ao_fechar)

    # sessão salva: pula a tela de login
    if banco.tentar_sessao_salva():
        apos_login()

    drenar_log()
    root.mainloop()
