# src/venda/interface_venda.py
"""
Página de Venda/Anúncio (dentro da janela do app, ver interface_principal.py).

Fluxo: conta do usuário (Supabase) → lista os veículos DELE → usuário marca
veículos + sites → Rodar grava parametros_venda.json e inicia o anunciador
como subprocesso (log na página, Prosseguir libera após o login manual nos
sites).

Regras de tela que valem registrar:
- a conta é a mesma do rodapé da lateral (`app.banco`): conectada, o bloco
  de login some e o topo mostra só "● Conectado"; Sair fica na lateral;
- os campos sensíveis (dados pessoais e usuário/senha por site) só
  aparecem quando um site que precisa deles está MARCADO;
- a tabela marca por caixa de marcação, com busca e filtro que escondem
  linhas sem desmarcar nada (ver ui_tabela.py).

Além de anunciar, a página desfaz o que já foi feito, de dois jeitos que
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
import execucoes
import tutorial
import ui_tema
from paths import get_parametros_venda_path, get_venda_command
from sinal import dar_sinal, limpar_sinal
from ui_componentes import Banner, CabecalhoPagina, Cartao, dica_flutuante, placeholder
from ui_execucao import BarraAcoes, LogExecucao, pede_prosseguir
from ui_scroll import criar_area_rolavel
from ui_sites import CartaoSite, GradeSites
from ui_tabela import TabelaVeiculos
from venda import anunciados
from venda.config_venda import modo_demo
from venda.sites import listar_sites, obter_site

processo = None
log_queue = queue.Queue()
FIM_DO_BOT = object()
C = ui_tema.CORES

FILTROS = {"Todos os veículos": "todos",
           "Ainda não anunciados": "nao_anunciados",
           "Já anunciados": "anunciados"}


def sites_ordenados():
    """Utilizáveis primeiro; os 'Em breve' no fim."""
    return sorted(listar_sites(),
                  key=lambda s: (not getattr(s, "disponivel", True), s.nome))


def selo_do_site(site):
    """(texto, tipo) do selo e a explicação do cartão do site."""
    if not getattr(site, "disponivel", True):
        motivo = getattr(site, "motivo_indisponivel", "")
        return ("Em breve", "neutro"), f"Ainda não disponível: {motivo}."
    if site.id == "demo":
        return ("Teste local", "neutro"), ("Formulário de demonstração no "
                                           "próprio computador.")
    if getattr(site, "publicacao_manual", False):
        return ("Plano pago", "aviso"), ("Pago: o bot preenche tudo e para "
                                         "antes do plano — escolher e pagar "
                                         "é decisão sua.")
    if getattr(site, "navegador", "chrome") != "chrome":
        return ("Abre no Edge", "info"), "Roda no Microsoft Edge do computador."
    return ("Disponível", "sucesso"), None


def formatar_preco(valor):
    """18950.0 -> 'R$ 18.950' (o banco manda float e aparecia '.0')."""
    try:
        return f"R$ {float(valor):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return str(valor)


class Pagina:
    def __init__(self, frame, ao_mostrar, encerrar, guia, sair_da_conta):
        self.frame, self.ao_mostrar, self.encerrar = frame, ao_mostrar, encerrar
        self.guia, self.sair_da_conta = guia, sair_da_conta


def montar(pai, app):
    """Monta a página de Venda dentro de `pai`. Devolve uma `Pagina`."""
    global log_queue
    banco = app.banco
    root = app.root
    veiculos = []          # dicts normalizados vindos do banco
    vars_sites = {}        # site_id -> IntVar
    log_queue = queue.Queue()
    px = lambda valor: ui_tema.px(root, valor)  # noqa: E731
    espaco = px(20)

    frame = tk.Frame(pai, bg=C["fundo"])
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)
    conteudo = criar_area_rolavel(frame, padding=28, empacotar=False)
    conteudo.master.master.grid(row=0, column=0, sticky="nsew")
    conteudo.columnconfigure(0, weight=1)
    tela_rolavel = conteudo.master
    status = tk.StringVar(value="Entre com sua conta para carregar seus veículos.")
    var_dry = tk.IntVar(value=1)
    agendado = {"log": None}

    # ------------------------------ topo ------------------------------
    cabeca = CabecalhoPagina(conteudo, "Venda / Anúncio",
                             "Anuncia os veículos do seu banco nos sites escolhidos.",
                             voltar=lambda: app.ir("inicio"),
                             ajuda=lambda: guia.iniciar())
    cabeca.grid(row=0, column=0, sticky="we", pady=(0, px(20)))
    selo_conta = ui_tema.selo(cabeca.direita, "Conectado", "sucesso",
                              fundo=C["fundo"], ponto=True)
    dica_flutuante(selo_conta, lambda: f"Conta: {banco.email or ''}")

    lbl_verificando = ttk.Label(conteudo, text="Conectando à sua conta…",
                                style="Subtitulo.TLabel")
    lbl_verificando.grid(row=1, column=0, sticky="w")

    # ------------------------------ conta ------------------------------
    sec_conta = Cartao(conteudo, "Entre na sua conta", subtitulo=(
        "Use o mesmo e-mail e senha do sistema onde os veículos estão "
        "cadastrados. Depois do primeiro acesso a página já abre conectada."))
    corpo_conta = sec_conta.corpo
    corpo_conta.columnconfigure(0, weight=1)
    ttk.Label(corpo_conta, text="E-mail", style="Rotulo.TLabel").grid(
        row=0, column=0, sticky="w", pady=(0, px(4)))
    ent_email_conta = ttk.Entry(corpo_conta, width=36)
    ent_email_conta.grid(row=1, column=0, sticky="we")
    ttk.Label(corpo_conta, text="Senha", style="Rotulo.TLabel").grid(
        row=2, column=0, sticky="w", pady=(px(12), px(4)))
    ent_senha_conta = ttk.Entry(corpo_conta, width=36, show="•")
    ent_senha_conta.grid(row=3, column=0, sticky="we")
    lbl_erro_login = ttk.Label(corpo_conta, text="", style="Ajuda.TLabel",
                               foreground=C["erro_texto"])
    lbl_erro_login.grid(row=4, column=0, sticky="w", pady=(px(8), 0))
    if modo_demo():
        Banner(corpo_conta, "MODO DEMONSTRAÇÃO: Supabase não configurado — "
                            "qualquer login entra e os veículos são de exemplo.",
               "aviso", fechavel=False, fundo=C["cartao"]).grid(
            row=6, column=0, sticky="we", pady=(px(12), 0))

    # ---------------------------- colunas -----------------------------
    colunas = tk.Frame(conteudo, bg=C["fundo"])
    esquerda = tk.Frame(colunas, bg=C["fundo"])
    direita = tk.Frame(colunas, bg=C["fundo"])
    esquerda.columnconfigure(0, weight=1)
    direita.columnconfigure(0, weight=1)
    estado_colunas = {"n": 0}

    def reorganizar_colunas(_evento=None):
        duas = colunas.winfo_width() >= px(1100)
        n = 2 if duas else 1
        if n == estado_colunas["n"]:
            return
        estado_colunas["n"] = n
        if duas:
            colunas.columnconfigure(0, weight=3, uniform="colunas")
            colunas.columnconfigure(1, weight=2, uniform="colunas")
            esquerda.grid(row=0, column=0, sticky="nwe", padx=(0, px(10)))
            direita.grid(row=0, column=1, sticky="nwe", padx=(px(10), 0))
        else:
            colunas.columnconfigure(0, weight=1, uniform="")
            colunas.columnconfigure(1, weight=0, uniform="")
            esquerda.grid(row=0, column=0, sticky="nwe", padx=0)
            direita.grid(row=1, column=0, sticky="nwe", padx=0)

    colunas.bind("<Configure>", reorganizar_colunas, add="+")

    # ---------------------------- veículos -----------------------------
    sec_veic = Cartao(esquerda, "Selecione os veículos", numero=1)
    sec_veic.grid(row=0, column=0, sticky="we", pady=(0, espaco))
    corpo_v = sec_veic.corpo
    corpo_v.columnconfigure(0, weight=1)
    lbl_contagem = ttk.Label(sec_veic.acoes, text="", style="Ajuda.TLabel")
    lbl_contagem.pack(side="right")

    ferramentas = ttk.Frame(corpo_v, style="Superficie.TFrame")
    ferramentas.grid(row=0, column=0, sticky="we", pady=(0, px(12)))
    ferramentas.columnconfigure(0, weight=1)
    ent_busca = ttk.Entry(ferramentas, width=28)
    ent_busca.grid(row=0, column=0, sticky="we", padx=(0, px(10)))
    placeholder(ent_busca, "Buscar veículo…")
    cmb_filtro = ttk.Combobox(ferramentas, state="readonly", width=20,
                              values=list(FILTROS))
    cmb_filtro.set("Todos os veículos")
    cmb_filtro.grid(row=0, column=1, sticky="e")

    def atualizar_contagem(total, visiveis, marcados):
        partes = [f"{total} veículo{'s' if total != 1 else ''}"]
        if visiveis != total:
            partes.append(f"{visiveis} na busca")
        partes.append(f"{marcados} selecionado{'s' if marcados != 1 else ''}")
        lbl_contagem.configure(text="  •  ".join(partes))

    tabela = TabelaVeiculos(
        corpo_v, ao_mudar=atualizar_contagem, linhas_visiveis=8,
        formatar_preco=lambda v: formatar_preco(v["preco"]) if v.get("preco")
        else "sem preço")
    tabela.grid(row=1, column=0, sticky="we")
    ent_busca.bind("<KeyRelease>",
                   lambda _e: tabela.aplicar_filtro(busca=ent_busca.get()),
                   add="+")
    cmb_filtro.bind("<<ComboboxSelected>>", lambda _e: tabela.aplicar_filtro(
        filtro=FILTROS[cmb_filtro.get()]), add="+")

    rodape_v = ttk.Frame(corpo_v, style="Superficie.TFrame")
    rodape_v.grid(row=2, column=0, sticky="we", pady=(px(14), 0))
    rodape_v.columnconfigure(0, weight=1)
    ttk.Label(rodape_v, text="Com os veículos marcados",
              style="Rotulo.TLabel").grid(row=0, column=0, sticky="w")
    botoes_marcados = ttk.Frame(rodape_v, style="Superficie.TFrame")
    botoes_marcados.grid(row=0, column=1, sticky="e")
    ui_tema.texto_suave(
        rodape_v, "Anunciar de novo só libera a trava local (o anúncio antigo "
                  "continua no ar); Excluir anúncio tira o anúncio do ar no "
                  "site marcado.").grid(row=1, column=0, columnspan=2,
                                        sticky="we", pady=(px(6), 0))

    # ------------------------------ sites ------------------------------
    sec_sites = Cartao(direita, "Sites para anunciar", numero=2, subtitulo=(
        "Cada veículo é anunciado no máximo UMA vez por site (anti-spam)."))
    sec_sites.grid(row=0, column=0, sticky="we", pady=(0, espaco))
    grade_sites = GradeSites(sec_sites.corpo, largura_min=132)
    grade_sites.pack(fill="x")
    for site in sites_ordenados():
        var = tk.IntVar(value=0)
        var.trace_add("write", lambda *_: atualizar_campos_sensiveis())
        vars_sites[site.id] = var
        selo, explicacao = selo_do_site(site)
        grade_sites.adicionar(CartaoSite(
            grade_sites, site.id, site.nome.replace(" (cotação de venda)", ""),
            var, selo=selo, disponivel=getattr(site, "disponivel", True),
            dica=explicacao))

    # a Página não usa o Marketplace (o Facebook responde "Pages can't use
    # Marketplace"): o anúncio dela é um post no feed, e o bot precisa saber
    # em QUAL Página postar quando a conta administra mais de uma
    quadro_pagina_fb = ttk.Frame(sec_sites.corpo, style="Superficie.TFrame")
    quadro_pagina_fb.columnconfigure(0, weight=1)
    ttk.Label(quadro_pagina_fb, text="Página do Facebook",
              style="Rotulo.TLabel").grid(row=0, column=0, sticky="w",
                                          pady=(0, px(4)))
    ent_pagina_fb = ttk.Entry(quadro_pagina_fb, width=28)
    ent_pagina_fb.grid(row=1, column=0, sticky="we")
    placeholder(ent_pagina_fb, "Em branco = a única que você administra")

    # o mesmo post pode ir para grupos de que a PÁGINA participa
    quadro_grupos_fb = ttk.Frame(sec_sites.corpo, style="Superficie.TFrame")
    ttk.Label(quadro_grupos_fb, text="Grupos (um por linha)",
              style="Rotulo.TLabel").pack(anchor="w", pady=(0, px(4)))
    txt_grupos_fb = ui_tema.campo_texto(quadro_grupos_fb, altura=3)
    txt_grupos_fb.moldura.pack(fill="x")
    ui_tema.texto_suave(
        quadro_grupos_fb,
        "Só entram grupos em que a PÁGINA entrou. Poucos e relevantes: "
        "disparo em muitos grupos de uma vez é o que o Facebook trata como "
        "spam.").pack(anchor="w", fill="x", pady=(px(4), 0))

    # -------------------- dados sensíveis (dinâmico) --------------------
    # fica embaixo da tabela: a coluna dos sites já é a mais comprida
    sec_dados = Cartao(esquerda, "Seus dados e logins",
                       subtitulo="Não são salvos.")
    corpo_d = sec_dados.corpo
    corpo_d.columnconfigure(0, weight=1)
    Banner(corpo_d, "Nada aqui é gravado em disco: vai só para o processo do "
                    "bot e some quando ele termina. Sites com 2FA ou captcha "
                    "continuam exigindo você na janela.", "info",
           fechavel=False, fundo=C["cartao"]).grid(row=0, column=0,
                                                   sticky="we",
                                                   pady=(0, px(12)))

    quadro_pessoais = ttk.Frame(corpo_d, style="Superficie.TFrame")
    quadro_pessoais.grid(row=1, column=0, sticky="we")
    campos_pessoais = {}
    for indice, (campo, rotulo) in enumerate(
            (("nome", "Nome"), ("cpf", "CPF"),
             ("telefone", "Telefone"), ("email", "E-mail"))):
        linha_g, coluna_g = divmod(indice, 2)
        quadro_pessoais.columnconfigure(coluna_g, weight=1)
        ttk.Label(quadro_pessoais, text=rotulo, style="Rotulo.TLabel").grid(
            row=linha_g * 2, column=coluna_g, sticky="w", pady=(px(4), px(4)),
            padx=(0 if coluna_g == 0 else px(10), 0))
        entrada = ttk.Entry(quadro_pessoais, width=15)
        entrada.grid(row=linha_g * 2 + 1, column=coluna_g, sticky="we",
                     padx=(0, px(10)) if coluna_g == 0 else (px(10), 0))
        campos_pessoais[campo] = entrada

    campos_login = {}
    quadros_login = {}
    proxima = 2
    for site in listar_sites():
        if not getattr(site, "exige_login", False):
            continue
        quadro = ttk.Frame(corpo_d, style="Superficie.TFrame")
        ttk.Label(quadro, text=f"{site.nome} — usuário e senha",
                  style="Rotulo.TLabel").grid(row=0, column=0, columnspan=2,
                                              sticky="w", pady=(px(14), px(4)))
        usuario = ttk.Entry(quadro, width=20)
        usuario.grid(row=1, column=0, sticky="we", padx=(0, px(10)))
        placeholder(usuario, "Usuário")
        senha = ttk.Entry(quadro, width=16, show="•")
        senha.grid(row=1, column=1, sticky="we")
        quadro.columnconfigure(0, weight=1)
        quadro.columnconfigure(1, weight=1)
        quadros_login[site.id] = (quadro, proxima)
        campos_login[site.id] = {"usuario": usuario, "senha": senha}
        proxima += 1

    # ------------------------------- log -------------------------------
    log = LogExecucao(conteudo, "Log do anunciador", altura=11)

    # ----------------------------- funções -----------------------------
    def nome_site(site_id):
        try:
            return obter_site(site_id).nome
        except KeyError:
            return site_id

    def preencher_lista():
        registros = anunciados.carregar()
        tabela.carregar(veiculos, lambda v: [
            nome_site(s) for s in anunciados.sites_do_veiculo(v["id"], registros)])

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
                quadro.grid(row=onde, column=0, sticky="we")
            else:
                quadro.grid_remove()

        if "facebook_pagina" in marcados:
            quadro_pagina_fb.pack(fill="x", pady=(px(6), 0))
            quadro_grupos_fb.pack(fill="x", pady=(px(12), 0))
        else:
            quadro_pagina_fb.pack_forget()
            quadro_grupos_fb.pack_forget()

        if precisa_pessoais or com_login:
            sec_dados.grid(row=1, column=0, sticky="we", pady=(0, espaco))
        else:
            sec_dados.grid_remove()

    def obter(site_id):
        for site in listar_sites():
            if site.id == site_id:
                return site
        return None

    def mostrar_login():
        lbl_verificando.grid_remove()
        for alvo in (colunas, log):
            alvo.grid_remove()
        barra.grid_remove()
        selo_conta.pack_forget()
        sec_conta.grid(row=1, column=0, sticky="w", pady=(0, espaco))
        sec_conta.configure(width=px(520))

    def apos_login():
        lbl_verificando.grid_remove()
        sec_conta.grid_remove()
        lbl_erro_login.configure(text="")
        selo_conta.pack(side="right")
        colunas.grid(row=1, column=0, sticky="we")
        log.grid(row=2, column=0, sticky="we")
        barra.grid(row=1, column=0, sticky="we")
        app.definir_conta(banco.email)
        atualizar_campos_sensiveis()
        carregar_veiculos()
        # primeira vez: o passo a passo abre depois que a lista carrega
        if app.atual == "venda":
            guia.iniciar_se_primeira_vez()

    def sair_da_conta():
        if processo is not None and processo.poll() is None:
            parar()
        banco.logout()
        app.definir_conta(None)
        mostrar_login()
        status.set("Sessão encerrada.")

    def entrar(_evento=None):
        ok, erro = banco.login(ent_email_conta.get().strip(),
                               ent_senha_conta.get())
        if not ok:
            lbl_erro_login.configure(text=erro)
            status.set(erro)
            return
        ent_senha_conta.delete(0, "end")
        apos_login()

    ttk.Button(corpo_conta, text="Entrar", style="Primario.TButton",
               cursor="hand2", command=entrar).grid(
        row=5, column=0, sticky="w", pady=(px(12), 0))
    ent_senha_conta.bind("<Return>", entrar)

    # a execução em curso, para o Histórico
    rodada = {"execucao": None, "parada": False}

    def ler_saida(proc):
        for saida in proc.stdout:
            log_queue.put(saida)
        log_queue.put(FIM_DO_BOT)

    def drenar_log():
        while not log_queue.empty():
            item = log_queue.get_nowait()
            if item is FIM_DO_BOT:
                log.adicionar("Anunciador encerrado.")
                terminou()
                continue
            log.adicionar(item)
            execucoes.linha(rodada["execucao"], item)
            if pede_prosseguir(item):
                barra.definir_estado("aguardando")
            elif item.strip() == "Prosseguindo.":
                barra.definir_estado("rodando")
        agendado["log"] = root.after(100, drenar_log)

    def terminou():
        global processo
        processo = None
        barra.definir_estado("parado")
        log.ao_vivo(False)
        preencher_lista()        # atualiza "Já anunciado em"
        if rodada["execucao"] is not None:
            execucoes.salvar(rodada["execucao"],
                             "parada" if rodada["parada"] else "concluída")
            rodada["execucao"] = None
        status.set("Execução encerrada. Confira o log.")

    def escolha_atual():
        """(veículos marcados na tabela, sites marcados). Vazio = erro."""
        return ([veiculos[i] for i in tabela.marcados()],
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
                    "pagina_facebook": ent_pagina_fb.get().strip(),
                    "grupos_facebook": [
                        linha.strip() for linha
                        in txt_grupos_fb.get("1.0", "end").splitlines()
                        if linha.strip()],
                },
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
        log.limpar()
        processo = subprocess.Popen(
            get_venda_command(),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, env=ambiente,
        )
        threading.Thread(target=ler_saida, args=(processo,), daemon=True).start()
        rodada.update(parada=False, execucao=execucoes.nova(
            "Exclusão" if acao == "excluir" else "Venda",
            [obter_site(s).nome for s in sites_sel],
            [v["titulo"] for v in selecionados], params["dry_run"]))
        if acao == "excluir":
            status.set("Excluindo anúncios. Confira o login nos sites abertos "
                       "e clique em Prosseguir.")
        else:
            status.set("Anunciador iniciado. Logue nos sites abertos e clique "
                       "em Prosseguir.")
        barra.definir_estado("rodando")
        log.ao_vivo(True)
        root.after(150, lambda: tela_rolavel.yview_moveto(1.0))

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
            barra.definir_estado("rodando")
        else:
            status.set("O anunciador não está rodando.")

    def parar():
        global processo
        if processo is not None and processo.poll() is None:
            processo.terminate()
            processo = None
            rodada["parada"] = True
            preencher_lista()  # atualiza os marcadores [já em: ...]
            status.set("Anunciador parado.")
        else:
            status.set("O anunciador não está rodando.")
        barra.definir_estado("parado")
        log.ao_vivo(False)

    def encerrar():
        if processo is not None and processo.poll() is None:
            parar()
        # sem cancelar, o polling do log dispara depois do destroy e o Tk
        # reclama de "invalid command name"
        if agendado["log"] is not None:
            try:
                root.after_cancel(agendado["log"])
            except Exception:
                pass

    bt_de_novo = ttk.Button(botoes_marcados, text="Anunciar de novo",
                            style="Secundario.TButton", cursor="hand2",
                            command=anunciar_de_novo)
    bt_de_novo.pack(side="left", padx=(0, px(8)))
    bt_excluir = ttk.Button(botoes_marcados, text="Excluir anúncio",
                            style="Perigo.TButton", cursor="hand2",
                            command=excluir_anuncio)
    bt_excluir.pack(side="left")

    barra = BarraAcoes(frame, var_dry, rodar, prosseguir, parar, status,
                       verbo="publica")

    # ---------------------------- passo a passo ----------------------------
    # abre sozinho só na primeira visita já conectada; depois, pelo "?"
    guia = tutorial.Tutorial(root, "venda-v2", rolavel=conteudo, passos=[
        tutorial.Passo(
            "Página de Venda",
            "Aqui você escolhe quais veículos do seu sistema anunciar e em "
            "quais sites. O bot abre os sites e preenche os anúncios por "
            "você."),
        tutorial.Passo(
            "Sua conta",
            "Entre com o mesmo e-mail e senha do sistema onde os veículos "
            "estão cadastrados. Depois do primeiro acesso a página já abre "
            "conectada.",
            lambda: [sec_conta], opcional=True),
        tutorial.Passo(
            "Conta conectada",
            "Mostra que a conta está conectada (pare o mouse para ver qual). "
            "Para trocar de conta, use Sair no rodapé da barra lateral.",
            lambda: [selo_conta], opcional=True),
        tutorial.Passo(
            "1. Seus veículos",
            "Marque a caixa de cada veículo que quer anunciar — ou a caixa do "
            "cabeçalho para marcar todos os que estão à vista. 'Já anunciado "
            "em' mostra onde ele já foi publicado: o bot não repete o mesmo "
            "anúncio no mesmo site.",
            lambda: [tabela], opcional=True),
        tutorial.Passo(
            "Buscar e filtrar",
            "Digite parte do nome para achar um veículo, ou mostre só os que "
            "ainda não foram anunciados. Buscar não desmarca nada.",
            lambda: [ferramentas], opcional=True),
        tutorial.Passo(
            "Anunciar de novo e Excluir anúncio",
            "Valem para os veículos marcados. Anunciar de novo libera o "
            "veículo para ser anunciado outra vez (o anúncio antigo continua "
            "no ar). Excluir anúncio tira o anúncio do ar no site marcado — e "
            "pede confirmação antes.",
            lambda: [botoes_marcados], opcional=True),
        tutorial.Passo(
            "2. Sites para anunciar",
            "Clique nos cartões dos sites. 'Plano pago' quer dizer que o bot "
            "preenche tudo e para antes do plano — pagar é decisão sua; 'Abre "
            "no Edge' roda no Microsoft Edge; 'Em breve' ainda não está "
            "disponível.",
            lambda: [sec_sites], opcional=True),
        tutorial.Passo(
            "Seus dados e logins",
            "Aparece quando um site marcado pede login ou dados pessoais. "
            "Nada fica salvo: vai só para o bot enquanto ele roda.",
            lambda: [sec_dados], opcional=True),
        tutorial.Passo(
            "Modo teste",
            "Ligado, o bot preenche os formulários mas não publica. Use para "
            "conferir antes de publicar de verdade — desligado, a faixa fica "
            "amarela.",
            lambda: [barra.bloco_teste], opcional=True),
        tutorial.Passo(
            "Rodar, Prosseguir e Parar",
            "Rodar abre os sites marcados, cada um numa aba. Faça o login em "
            "cada aba e clique em Prosseguir (ele fica roxo quando o bot está "
            "esperando). Parar interrompe a qualquer momento.",
            lambda: [barra.bt_prosseguir, barra.bt_parar, barra.bt_rodar],
            opcional=True),
        tutorial.Passo(
            "Acompanhe pelo log",
            "Tudo o que o anunciador faz aparece aqui, com hora e ícone por "
            "tipo: informação, sucesso, aviso ou erro.",
            lambda: [log], opcional=True),
        tutorial.Passo(
            "Precisa rever?",
            "Clique no ? a qualquer momento para ver este passo a passo de "
            "novo.",
            lambda: [cabeca.bt_ajuda]),
    ])

    def ao_mostrar():
        if banco.logado:
            guia.iniciar_se_primeira_vez()

    # sessão salva (conferida pela janela ao abrir): pula a tela de login
    app.quando_sessao_verificada(
        lambda ok: apos_login() if ok else mostrar_login())

    drenar_log()
    return Pagina(frame, ao_mostrar, encerrar, guia, sair_da_conta)


def iniciar():
    """Abre o app direto na Venda (compatibilidade)."""
    import interface_principal
    interface_principal.iniciar("venda")
