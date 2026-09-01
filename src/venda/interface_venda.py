# src/venda/interface_venda.py
"""
Interface do módulo Venda/Anúncio (Tkinter).

Fluxo: login na conta do usuário (Supabase) → lista os veículos DELE →
usuário marca veículos + sites → Rodar grava parametros_venda.json e
inicia o anunciador como subprocesso (log na janela, botão Prosseguir
libera após o login manual nos sites).

Duas regras de tela que valem registrar:
- depois de entrar, o bloco de login some e vira uma linha "Conectado:
  fulano [Sair]" — ele já cumpriu o papel e só ocupava espaço;
- os campos sensíveis (dados pessoais e usuário/senha por site) só
  aparecem quando um site que precisa deles está MARCADO. Antes a tela
  pedia login de sites que nem dava para selecionar.

Além de anunciar, a tela desfaz o que já foi feito, de dois jeitos que
NÃO são a mesma coisa:
- "Anunciar de novo" só apaga o registro LOCAL (anunciados.json), que é
  a trava anti-spam — o anúncio no site continua no ar;
- "Excluir anúncio" abre o navegador e tira o anúncio DO AR no site (só
  para sites com `suporta_exclusao`), e o registro local cai junto.
Como a segunda é irreversível, ela pede confirmação antes.
"""
import json
import queue
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import contato
import ui_tema
from paths import get_parametros_venda_path, get_venda_command
from sinal import dar_sinal, limpar_sinal
from ui_scroll import criar_area_rolavel
from venda import anunciados
from venda.banco import BancoVeiculos
from venda.config_venda import modo_demo
from venda.sites import listar_sites, obter_site

processo = None
log_queue = queue.Queue()


def sites_ordenados():
    """Utilizáveis primeiro; os 'Em breve' no fim."""
    return sorted(listar_sites(),
                  key=lambda s: (not getattr(s, "disponivel", True), s.nome))


def iniciar():
    """Abre o painel de Venda. Retorna 'voltar' ou 'sair'."""
    global processo, log_queue
    banco = BancoVeiculos()
    veiculos = []          # dicts normalizados vindos do banco
    vars_sites = {}        # site_id -> IntVar
    resultado = {"acao": "sair"}
    log_queue = queue.Queue()

    root = tk.Tk()
    root.title("MarketplaceBot — Venda/Anúncio")
    root.geometry("580x800")
    root.minsize(520, 560)
    ui_tema.aplicar_tema(root)

    frm = criar_area_rolavel(root)
    frm.columnconfigure(0, weight=1)
    status = tk.StringVar(value="Entre com sua conta para carregar seus veículos.")
    linha = 0

    # ------------------------------ topo ------------------------------
    topo = ttk.Frame(frm)
    topo.grid(row=linha, column=0, sticky="we"); linha += 1
    ui_tema.botao(topo, "← Voltar", lambda: encerrar("voltar"),
                  "neutro", 10).pack(side="left")
    ttk.Label(topo, text="  Venda / Anúncio",
              style="Titulo.TLabel").pack(side="left")
    ttk.Label(frm, text="Anuncia os veículos do seu banco nos sites escolhidos.",
              style="Suave.TLabel").grid(row=linha, column=0, sticky="w",
                                         pady=(0, 10)); linha += 1

    # ------------------------------ conta ------------------------------
    sec_conta = ui_tema.secao(frm, "Conta")
    sec_conta.grid(row=linha, column=0, sticky="we", pady=(0, 8))
    linha_conta = linha; linha += 1
    sec_conta.columnconfigure(1, weight=1)
    ttk.Label(sec_conta, text="E-mail").grid(row=0, column=0, sticky="w")
    ent_email_conta = ttk.Entry(sec_conta)
    ent_email_conta.grid(row=0, column=1, sticky="we", padx=6, pady=2)
    ttk.Label(sec_conta, text="Senha").grid(row=1, column=0, sticky="w")
    ent_senha_conta = ttk.Entry(sec_conta, show="•")
    ent_senha_conta.grid(row=1, column=1, sticky="we", padx=6, pady=2)
    if modo_demo():
        ui_tema.dica(sec_conta,
                     "MODO DEMONSTRAÇÃO: Supabase não configurado — qualquer "
                     "login entra e os veículos são de exemplo.",
                     largura=470).grid(row=2, column=0, columnspan=3,
                                       sticky="w", pady=(6, 0))

    # barra compacta que substitui o bloco de login depois de entrar
    barra_conta = ttk.Frame(frm)
    lbl_conta = ttk.Label(barra_conta, text="", style="Ok.TLabel")
    lbl_conta.pack(side="left")

    # ---------------------------- veículos -----------------------------
    sec_veic = ui_tema.secao(frm, "Seus veículos — marque os que quer anunciar")
    sec_veic.columnconfigure(0, weight=1)
    lst_veiculos = tk.Listbox(sec_veic, selectmode="multiple", height=9,
                              activestyle="none", relief="solid",
                              borderwidth=1, highlightthickness=0,
                              font=(ui_tema.FONTE, 9))
    rolagem = ttk.Scrollbar(sec_veic, orient="vertical",
                            command=lst_veiculos.yview)
    lst_veiculos.configure(yscrollcommand=rolagem.set)
    lst_veiculos.grid(row=0, column=0, sticky="we")
    rolagem.grid(row=0, column=1, sticky="ns")
    linha_veic = linha; linha += 1

    # ------------------------------ sites ------------------------------
    sec_sites = ui_tema.secao(frm, "Sites")
    sec_sites.columnconfigure(0, weight=1)
    linha_sites = linha; linha += 1

    # -------------------- dados sensíveis (dinâmico) --------------------
    sec_dados = ui_tema.secao(frm, "Seus dados e logins — não são salvos")
    sec_dados.columnconfigure(1, weight=1)
    sec_dados.columnconfigure(3, weight=1)
    linha_dados = linha; linha += 1

    ui_tema.dica(sec_dados,
                 "Nada aqui é gravado em disco: vai só para o processo do bot "
                 "e some quando ele termina. Sites com 2FA ou captcha "
                 "continuam exigindo você na janela.", largura=490).grid(
        row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))

    quadro_pessoais = ttk.Frame(sec_dados)
    quadro_pessoais.grid(row=1, column=0, columnspan=4, sticky="we")
    campos_pessoais = {}
    for coluna, (campo, rotulo) in enumerate(
            (("nome", "Nome"), ("cpf", "CPF"),
             ("telefone", "Telefone"), ("email", "E-mail"))):
        ttk.Label(quadro_pessoais, text=rotulo).grid(
            row=0, column=coluna, sticky="w", padx=(0, 4))
        entrada = ttk.Entry(quadro_pessoais, width=15)
        entrada.grid(row=1, column=coluna, sticky="we", padx=(0, 8))
        quadro_pessoais.columnconfigure(coluna, weight=1)
        campos_pessoais[campo] = entrada

    campos_login = {}
    quadros_login = {}
    proxima = 2
    for site in listar_sites():
        if not getattr(site, "exige_login", False):
            continue
        quadro = ttk.Frame(sec_dados)
        ttk.Label(quadro, text=f"{site.nome} — usuário e senha",
                  style="Secao.TLabel").grid(row=0, column=0, columnspan=2,
                                             sticky="w", pady=(8, 2))
        usuario = ttk.Entry(quadro, width=26)
        usuario.grid(row=1, column=0, sticky="we", padx=(0, 8))
        senha = ttk.Entry(quadro, width=20, show="•")
        senha.grid(row=1, column=1, sticky="we")
        quadro.columnconfigure(0, weight=1)
        quadro.columnconfigure(1, weight=1)
        quadro.grid(row=proxima, column=0, columnspan=4, sticky="we")
        quadros_login[site.id] = (quadro, proxima)
        campos_login[site.id] = {"usuario": usuario, "senha": senha}
        proxima += 1

    # ------------------------------ ações ------------------------------
    frm_acoes = ttk.Frame(frm)
    linha_acoes = linha; linha += 1
    var_dry = tk.IntVar(value=1)
    ttk.Checkbutton(frm_acoes, variable=var_dry,
                    text="Modo teste (dry-run) — preenche, mas não publica"
                    ).pack(anchor="w", pady=(0, 6))
    botoes = ttk.Frame(frm_acoes)
    botoes.pack(fill="x")

    sec_log = ui_tema.secao(frm, "Log do anunciador")
    sec_log.columnconfigure(0, weight=1)
    txt_log = ui_tema.caixa_log(sec_log, altura=9)
    txt_log.grid(row=0, column=0, sticky="we")
    linha_log = linha; linha += 1

    ttk.Label(frm, textvariable=status, style="Suave.TLabel",
              wraplength=520).grid(row=linha, column=0, sticky="w", pady=(8, 0))

    # ----------------------------- funções -----------------------------
    def preencher_lista():
        lst_veiculos.delete(0, "end")
        registros = anunciados.carregar()
        for v in veiculos:
            preco = (f"R$ {v['preco']:,}".replace(",", ".")
                     if v.get("preco") else "sem preço")
            texto = f"{v['titulo']}  —  {preco}"
            if v.get("status"):
                texto += f"  ({v['status']})"
            ja = anunciados.sites_do_veiculo(v["id"], registros)
            if ja:
                texto += f"   [já em: {', '.join(ja)}]"
            lst_veiculos.insert("end", texto)

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

    def atualizar_campos_sensiveis(*_):
        """Só pede dados/logins dos sites que estão MARCADOS agora."""
        marcados = [sid for sid, var in vars_sites.items() if var.get()]
        precisa_pessoais = any(
            getattr(obter(sid), "exige_dados_pessoais", False)
            for sid in marcados)
        com_login = [sid for sid in marcados
                     if getattr(obter(sid), "exige_login", False)]

        if precisa_pessoais:
            quadro_pessoais.grid()
        else:
            quadro_pessoais.grid_remove()
        for sid, (quadro, onde) in quadros_login.items():
            if sid in com_login:
                quadro.grid(row=onde, column=0, columnspan=4, sticky="we")
            else:
                quadro.grid_remove()

        if "facebook_pagina" in marcados:
            quadro_pagina_fb.pack(anchor="w", pady=(4, 0))
        else:
            quadro_pagina_fb.pack_forget()

        if precisa_pessoais or com_login:
            sec_dados.grid(row=linha_dados, column=0, sticky="we", pady=(0, 8))
        else:
            sec_dados.grid_remove()

    def obter(site_id):
        for site in listar_sites():
            if site.id == site_id:
                return site
        return None

    def apos_login():
        sec_conta.grid_remove()
        lbl_conta.config(text=f"Conectado: {banco.email}")
        barra_conta.grid(row=linha_conta, column=0, sticky="we", pady=(0, 8))
        ui_tema.botao(barra_conta, "Sair", sair_da_conta, "neutro", 8).pack(
            side="right")
        sec_veic.grid(row=linha_veic, column=0, sticky="we", pady=(0, 8))
        sec_sites.grid(row=linha_sites, column=0, sticky="we", pady=(0, 8))
        frm_acoes.grid(row=linha_acoes, column=0, sticky="we", pady=(0, 8))
        sec_log.grid(row=linha_log, column=0, sticky="we")
        atualizar_campos_sensiveis()
        carregar_veiculos()

    def sair_da_conta():
        for widget in barra_conta.winfo_children():
            if isinstance(widget, tk.Button):
                widget.destroy()
        barra_conta.grid_remove()
        for alvo in (sec_veic, sec_sites, sec_dados, frm_acoes, sec_log):
            alvo.grid_remove()
        sec_conta.grid(row=linha_conta, column=0, sticky="we", pady=(0, 8))
        status.set("Sessão encerrada nesta tela.")

    def entrar():
        ok, erro = banco.login(ent_email_conta.get().strip(),
                               ent_senha_conta.get())
        if not ok:
            status.set(erro)
            return
        apos_login()

    ui_tema.botao(sec_conta, "Entrar", entrar, "destaque", 10).grid(
        row=0, column=2, rowspan=2, padx=(8, 0), sticky="ns")

    for site in sites_ordenados():
        var = tk.IntVar(value=0)
        var.trace_add("write", atualizar_campos_sensiveis)
        vars_sites[site.id] = var
        disponivel = getattr(site, "disponivel", True)
        linha_site = ttk.Frame(sec_sites)
        linha_site.pack(anchor="w", fill="x", pady=1)
        ttk.Checkbutton(linha_site, text=site.nome, variable=var,
                        state="normal" if disponivel else "disabled").pack(
            side="left")
        if getattr(site, "publicacao_manual", False) and disponivel:
            ttk.Label(linha_site, text="pago — o bot para antes do plano",
                      style="Aviso.TLabel").pack(side="left", padx=(6, 0))
        if getattr(site, "navegador", "chrome") != "chrome" and disponivel:
            ttk.Label(linha_site, text="abre no Microsoft Edge",
                      style="Suave.TLabel").pack(side="left", padx=(6, 0))
        if not disponivel:
            ttk.Label(linha_site, text="Em breve",
                      style="Aviso.TLabel").pack(side="left", padx=(6, 0))
            motivo = getattr(site, "motivo_indisponivel", "")
            if motivo:
                ttk.Label(linha_site, text=f"({motivo})",
                          style="Suave.TLabel").pack(side="left", padx=(4, 0))
    # a Página não usa o Marketplace (o Facebook responde "Pages can't use
    # Marketplace"): o anúncio dela é um post no feed, e o bot precisa saber
    # em QUAL Página postar quando a conta administra mais de uma
    quadro_pagina_fb = ttk.Frame(sec_sites)
    ttk.Label(quadro_pagina_fb, text="Página do Facebook:").pack(side="left")
    ent_pagina_fb = ttk.Entry(quadro_pagina_fb, width=28)
    ent_pagina_fb.pack(side="left", padx=(6, 0))
    ttk.Label(quadro_pagina_fb,
              text="(em branco = a única que você administra)",
              style="Suave.TLabel").pack(side="left", padx=(6, 0))

    ttk.Label(sec_sites,
              text="Cada veículo é anunciado no máximo UMA vez por site "
                   "(anti-spam).", style="Suave.TLabel").pack(anchor="w",
                                                              pady=(6, 0))

    def ler_saida(proc):
        for saida in proc.stdout:
            log_queue.put(saida)
        log_queue.put("\n[anunciador encerrado]\n")

    agendado = {"log": None}

    def drenar_log():
        while not log_queue.empty():
            txt_log.insert("end", log_queue.get_nowait())
            txt_log.see("end")
        agendado["log"] = root.after(100, drenar_log)

    def escolha_atual():
        """(veículos marcados na lista, sites marcados). Vazio = erro."""
        return ([veiculos[i] for i in lst_veiculos.curselection()],
                [sid for sid, var in vars_sites.items() if var.get()])

    def rodar(acao="anunciar"):
        global processo
        if processo is not None and processo.poll() is None:
            status.set("O anunciador já está rodando.")
            return

        selecionados, sites_sel = escolha_atual()
        if not selecionados or not sites_sel:
            status.set("Marque ao menos um veículo e um site.")
            return

        params = {
            "veiculos": selecionados,
            "sites": sites_sel,
            "dry_run": bool(var_dry.get()),
            "acao": acao,
            "opcoes": {
                "facebook_pagina": {
                    "pagina_facebook": ent_pagina_fb.get().strip()},
            },
        }
        with open(get_parametros_venda_path(), "w", encoding="utf-8") as f:
            json.dump(params, f, ensure_ascii=False, indent=2)

        # dados sensíveis NÃO entram no JSON: seguem só no ambiente do
        # processo do anunciador e somem quando ele termina
        ambiente = contato.para_ambiente(
            dados={campo: entrada.get().strip()
                   for campo, entrada in campos_pessoais.items()},
            credenciais={sid: {"usuario": par["usuario"].get().strip(),
                               "senha": par["senha"].get()}
                         for sid, par in campos_login.items()},
        )

        limpar_sinal()
        txt_log.delete("1.0", "end")
        processo = subprocess.Popen(
            get_venda_command(),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, env=ambiente,
        )
        threading.Thread(target=ler_saida, args=(processo,), daemon=True).start()
        if acao == "excluir":
            status.set("Excluindo anúncios. Confira o login nos sites abertos "
                       "e clique em Prosseguir.")
        else:
            status.set("Anunciador iniciado. Logue nos sites abertos e clique "
                       "em Prosseguir.")

    def anunciar_de_novo():
        """Libera a trava anti-spam: some com o registro local do par
        veículo×site. Não mexe no anúncio que está no ar."""
        selecionados, sites_sel = escolha_atual()
        if not selecionados:
            status.set("Marque os veículos que quer anunciar de novo.")
            return
        # nenhum site marcado = libera o veículo em todos os sites
        alvos = sites_sel or [None]
        apagados = 0
        for v in selecionados:
            for site_id in alvos:
                apagados += anunciados.esquecer(v["id"], site_id)
        preencher_lista()
        if apagados:
            onde = "nos sites marcados" if sites_sel else "em todos os sites"
            status.set(f"{apagados} registro(s) liberado(s) {onde} — "
                       "esses veículos podem ser anunciados de novo.")
        else:
            status.set("Nada a liberar: esses veículos não constam como "
                       "anunciados.")

    def excluir_anuncio():
        """Tira o anúncio DO AR no site. Irreversível, então confirma."""
        selecionados, sites_sel = escolha_atual()
        if not selecionados or not sites_sel:
            status.set("Marque os veículos e o site do anúncio a excluir.")
            return

        sem_suporte = [obter_site(s).nome for s in sites_sel
                       if not getattr(obter_site(s), "suporta_exclusao", False)]
        capazes = [s for s in sites_sel
                   if getattr(obter_site(s), "suporta_exclusao", False)]
        if not capazes:
            status.set("Exclusão pelo bot ainda não calibrada em: "
                       + ", ".join(sem_suporte))
            return

        nomes = ", ".join(obter_site(s).nome for s in capazes)
        aviso = (f"Excluir {len(selecionados)} anúncio(s) em {nomes}?\n\n"
                 "O anúncio sai do ar no site — não dá para desfazer.")
        if sem_suporte:
            aviso += ("\n\nSerão ignorados (exclusão não calibrada): "
                      + ", ".join(sem_suporte))
        if not messagebox.askyesno("Excluir anúncio", aviso, icon="warning",
                                   default="no", parent=root):
            status.set("Exclusão cancelada.")
            return
        rodar("excluir")

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

    ui_tema.botao(botoes, "Rodar", rodar, "ok", 11).pack(side="left", padx=(0, 6))
    ui_tema.botao(botoes, "Prosseguir", prosseguir, "destaque", 13).pack(
        side="left", padx=(0, 6))
    ui_tema.botao(botoes, "Parar", parar, "perigo", 11).pack(side="left")

    botoes2 = ttk.Frame(botoes.master)
    botoes2.pack(fill="x", pady=(6, 0))
    ui_tema.botao(botoes2, "Anunciar de novo", anunciar_de_novo, "neutro",
                  17).pack(side="left", padx=(0, 6))
    ui_tema.botao(botoes2, "Excluir anúncio", excluir_anuncio, "perigo",
                  16).pack(side="left")
    ttk.Label(botoes.master,
              text="Anunciar de novo só libera a trava local; Excluir tira o "
                   "anúncio do ar no site.",
              style="Suave.TLabel").pack(anchor="w", pady=(4, 0))

    root.protocol("WM_DELETE_WINDOW", lambda: encerrar("sair"))

    # sessão salva: pula a tela de login
    if banco.tentar_sessao_salva():
        apos_login()

    drenar_log()
    root.mainloop()
    return resultado["acao"]
