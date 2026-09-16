"""
Página de COMPRA (dentro da janela do app, ver interface_principal.py).

- Rodar     : grava parametros.json e inicia o run.py, mostrando o log.
- Prosseguir: substitui o ENTER do terminal (libera o login).
- Parar     : encerra o bot a qualquer momento.

Layout em duas colunas (uma só em janela estreita): à esquerda o que e
onde buscar, à direita região, contato, mensagem e o resumo do que vai
rodar; o log embaixo e a barra de ações fixa no rodapé, com o MODO TESTE
em destaque. Rodar/Prosseguir/Parar habilitam conforme o estado do bot —
e "aguardando" é reconhecido pela linha que o bot imprime ao esperar o
Prosseguir.

Cada site aceita filtros diferentes. Em vez de mostrar campo desabilitado,
a página MOSTRA OU ESCONDE cada bloco conforme as fontes marcadas — ver
`campos_do_site()` e `atualizar_campos_do_site()`.
"""

import os
import json
import queue
import threading
import subprocess
import tkinter as tk
from tkinter import ttk

import contato
import execucoes
import tutorial
import ui_tema
from paths import get_parametros_path, get_bot_command
from sinal import dar_sinal, limpar_sinal
from ui_componentes import Banner, CabecalhoPagina, Cartao, placeholder
from ui_execucao import BarraAcoes, LogExecucao, ResumoExecucao, pede_prosseguir
from ui_scroll import criar_area_rolavel
from ui_sites import CartaoSite, GradeSites

BASE = os.path.dirname(os.path.abspath(__file__))
CAMINHO_PARAMS = str(get_parametros_path())
C = ui_tema.CORES

# Sites oferecidos na Compra (rotulo -> id usado no parametros.json).
# A OLX voltou (ago/2026) rodando no Microsoft Edge aberto normalmente —
# era o navegador sob automacao que o Cloudflare barrava (ver navegador.py).
SITES_COMPRA = [
    ("Facebook Marketplace", "facebook"),
    ("iCarros", "icarros"),
    ("Webmotors", "webmotors"),
    ("Mobiauto", "mobiauto"),
    ("OLX", "olx"),
    ("NaPista (só lista)", "napista"),
    ("Leilões: Loop e Sodré (só lista)", "leiloes"),
]

# nome curto e selo de cada fonte no cartão
CARTOES_SITES = {
    "facebook": ("Facebook Marketplace", ("Mensagem", "primaria")),
    "icarros": ("iCarros", ("Formulário", "info")),
    "webmotors": ("Webmotors", ("Formulário", "info")),
    "mobiauto": ("Mobiauto", ("Formulário", "info")),
    "olx": ("OLX", ("Abre no Edge", "info")),
    "napista": ("NaPista", ("Só lista", "neutro")),
    "leiloes": ("Leilões Loop e Sodré", ("Só lista", "neutro")),
}

SEPARADOR = chr(10) * 2   # linha em branco entre as dicas

DICAS = {
    "facebook": ("Filtra por CEP e raio em km. O Facebook limita quantas "
                 "mensagens dá para enviar de uma vez; quando o aviso "
                 "aparecer na tela, o bot para o Marketplace e segue para "
                 "as outras fontes marcadas."),
    "olx": ("Roda no Microsoft Edge do computador (aberto normalmente) — é "
            "o navegador sob automação que a OLX bloqueia. A região vem do "
            "estado do CEP (a OLX não tem raio em km) e o chat exige login "
            "no Edge. Rode poucos anúncios por vez."),
    "icarros": ("Pode escrever só o modelo (ex.: 'onix'): o bot põe a marca. "
                "Não exige login, mas o formulário do anúncio envia seu "
                "nome/e-mail/telefone ao vendedor. A região vem do estado do "
                "CEP e o preço é filtrado pelo bot."),
    "webmotors": ("Pode escrever só o modelo (ex.: 'palio'): o bot põe a "
                  "marca, que a Webmotors exige. "
                  "O formulário do anúncio envia seu nome/e-mail/telefone ao "
                  "vendedor (CPF não: lá quem pede CPF é o financiamento, "
                  "que o bot não preenche). Não filtra por região nesta "
                  "versão e pode pedir 'Pressione e segure' — o bot espera "
                  "você resolver na janela."),
    "mobiauto": ("Pode escrever só o modelo (ex.: 'onix'): o bot põe a "
                 "marca. Não exige login: o bloco 'Fale com o vendedor' pede "
                 "nome/e-mail/celular e a mensagem — CPF não, quem pede CPF "
                 "ali é o financiamento, e o bot não mexe nele. A região vem "
                 "do estado do CEP e o preço é filtrado pelo bot."),
    "leiloes": ("Procura lotes nos leilões da Loop (grupo Santander) e da "
                "Sodré Santoro, incluindo os judiciais, e LISTA com data, "
                "lance, origem e condição. O bot NUNCA dá lance. 'Média/grande "
                "monta' é carro sinistrado — ponha 'monta' em 'Ignorar com' "
                "para tirar. Leilão é nacional: a cidade vem no resultado."),
    "napista": ("A NaPista não tem formulário de mensagem — só WhatsApp e "
                "telefone da loja. Aqui o bot PROCURA e LISTA os anúncios que "
                "batem com a busca (link, preço, ano, km e cidade); falar com "
                "a loja é com você. Nenhuma mensagem é enviada."),
}

processo = None
log_queue = queue.Queue()
FIM_DO_BOT = object()     # marcador na fila: o processo terminou


def so_digitos(proposto):
    return proposto == "" or proposto.isdigit()


def campos_do_site(site):
    """Quais blocos da tela o site realmente usa.

    Regra separada da GUI para poder ser testada sozinha:
    - Facebook: CEP + raio em km; não tem ano/km/câmbio nem contato.
    - OLX: região pelo estado do CEP (sem raio) + ano/km/câmbio.
    - iCarros, Webmotors e Mobiauto: sem raio; exigem seus dados de contato,
      porque o formulário do anúncio os envia ao vendedor.
    - CPF é caso à parte: só o iCarros pede (em alguns anúncios). Na
      Webmotors e na Mobiauto o formulário do vendedor NÃO pede — nos
      dois, quem pede CPF é o formulário de financiamento, que o bot não
      preenche —, então o campo nem aparece.
    - NaPista não envia mensagem nenhuma: não pede contato.
    """
    return {
        "raio": site == "facebook",
        "extras": site == "olx",
        "contato": site in ("icarros", "webmotors", "mobiauto"),
        "cpf": site == "icarros",
    }


def so_digitos_ou_none(texto):
    """'40.000' -> 40000; vazio -> None."""
    digitos = "".join(c for c in str(texto or "") if c.isdigit())
    return int(digitos) if digitos else None


def campos_dos_sites(sites):
    """União do que as fontes MARCADAS usam.

    Com várias fontes na mesma execução, um campo aparece se pelo menos
    uma delas o usa — e só chega ao processo do bot por causa dela.
    """
    união = {"raio": False, "extras": False, "contato": False, "cpf": False}
    for site in sites or []:
        for chave, valor in campos_do_site(site).items():
            união[chave] = união[chave] or valor
    return união


class Pagina:
    """O que a janela do app precisa de cada página."""

    def __init__(self, frame, ao_mostrar, encerrar, guia):
        self.frame, self.ao_mostrar = frame, ao_mostrar
        self.encerrar, self.guia = encerrar, guia


def montar(pai, app):
    """Monta a página de Compra dentro de `pai`. Devolve uma `Pagina`."""
    global log_queue
    log_queue = queue.Queue()   # fila nova: log velho não vaza para a sessão
    root = app.root
    px = lambda valor: ui_tema.px(root, valor)  # noqa: E731
    espaco = px(20)       # respiro entre um cartão e outro

    frame = tk.Frame(pai, bg=C["fundo"])
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)
    conteudo = criar_area_rolavel(frame, padding=28, empacotar=False)
    conteudo.master.master.grid(row=0, column=0, sticky="nsew")
    conteudo.columnconfigure(0, weight=1)
    tela_rolavel = conteudo.master
    vcmd = (root.register(so_digitos), "%P")

    status = tk.StringVar(value="Preencha os campos e clique em Rodar.")
    var_dry = tk.IntVar(value=1)
    vars_sites = {}          # site_id -> IntVar
    agendado = {"log": None, "resumo": False}

    def sites_escolhidos():
        """Fontes marcadas, na ordem em que aparecem na tela."""
        return [sid for _, sid in SITES_COMPRA if vars_sites[sid].get()]

    def site_escolhido():
        """A primeira marcada — para o que ainda trata uma fonte só."""
        marcados = sites_escolhidos()
        return marcados[0] if marcados else "facebook"

    # ------------------------------ topo ------------------------------
    cabeca = CabecalhoPagina(conteudo, "Compra",
                             "Busca anúncios e envia mensagens aos vendedores.",
                             voltar=lambda: app.ir("inicio"),
                             ajuda=lambda: guia.iniciar())
    cabeca.grid(row=0, column=0, sticky="we", pady=(0, px(20)))

    colunas = tk.Frame(conteudo, bg=C["fundo"])
    colunas.grid(row=1, column=0, sticky="we")
    esquerda = tk.Frame(colunas, bg=C["fundo"])
    direita = tk.Frame(colunas, bg=C["fundo"])
    esquerda.columnconfigure(0, weight=1)
    direita.columnconfigure(0, weight=1)
    estado_colunas = {"n": 0}

    def reorganizar_colunas(_evento=None):
        duas = colunas.winfo_width() >= px(1040)
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

    # ---------------------------- onde buscar ----------------------------
    sec_site = Cartao(esquerda, "Onde buscar", numero=1, subtitulo=(
        "Marque quantas quiser: o bot faz uma fonte de cada vez, na mesma "
        "execução — cada uma abre a sua janela e, quando precisa, pede um "
        "'Prosseguir'."))
    sec_site.grid(row=0, column=0, sticky="we", pady=(0, espaco))
    grade_sites = GradeSites(sec_site.corpo)
    grade_sites.pack(fill="x")
    for indice, (rotulo, site_id) in enumerate(SITES_COMPRA):
        var = tk.IntVar(value=1 if indice == 0 else 0)
        vars_sites[site_id] = var
        nome, selo = CARTOES_SITES.get(site_id, (rotulo, None))
        grade_sites.adicionar(CartaoSite(
            grade_sites, site_id, nome, var, selo=selo, dica=DICAS.get(site_id),
            comando=lambda: atualizar_campos_do_site()))
    lbl_site_dica = ui_tema.dica(sec_site.corpo)
    lbl_site_dica.pack(fill="x", pady=(px(4), 0))

    # ---------------------------- o que buscar ---------------------------
    sec_busca = Cartao(esquerda, "O que buscar", numero=2, subtitulo=(
        "Um veículo por linha, com a faixa de preço dele. O bot faz a fila "
        "em ordem, terminando um antes de começar o próximo."))
    sec_busca.grid(row=1, column=0, sticky="we", pady=(0, espaco))
    corpo_busca = sec_busca.corpo
    corpo_busca.columnconfigure(0, weight=1)

    # cabeçalho e linhas usam as MESMAS colunas (peso + largura mínima),
    # senão os títulos desalinham dos campos
    COLUNAS = (("Veículo", 150, 4), ("Preço de", 90, 2), ("até", 90, 2),
               ("Deve conter", 130, 3), ("", 40, 0))

    def grade_colunas(alvo):
        for coluna, (_, largura, peso) in enumerate(COLUNAS):
            alvo.columnconfigure(coluna, minsize=px(largura), weight=peso,
                                 uniform=f"v{coluna}" if peso else "")

    cabecalho = ttk.Frame(corpo_busca, style="Superficie.TFrame")
    cabecalho.grid(row=0, column=0, sticky="we", pady=(0, px(6)))
    grade_colunas(cabecalho)
    for coluna, (texto, _, _) in enumerate(COLUNAS):
        ttk.Label(cabecalho, text=texto, style="Rotulo.TLabel").grid(
            row=0, column=coluna, sticky="w")

    quadro_veiculos = ttk.Frame(corpo_busca, style="Superficie.TFrame")
    quadro_veiculos.grid(row=1, column=0, sticky="we")
    linhas_veiculos = []

    def remover_linha(linha_alvo):
        """Tira a linha da tela; a última sobrevive (sempre há uma vazia)."""
        if len(linhas_veiculos) <= 1:
            for campo in ("nome", "min", "max", "palavras"):
                linha_alvo[campo].delete(0, "end")
                linha_alvo[campo].atualizar_placeholder()
        else:
            linha_alvo["frame"].destroy()
            linhas_veiculos.remove(linha_alvo)
        pedir_resumo()

    def adicionar_linha(nome="", preco_min="", preco_max="", palavras=""):
        frame_linha = ttk.Frame(quadro_veiculos, style="Superficie.TFrame")
        frame_linha.pack(fill="x", pady=(0, px(8)))
        grade_colunas(frame_linha)
        ent_veiculo = ttk.Entry(frame_linha, width=4)
        ent_de = ttk.Entry(frame_linha, width=4, validate="key",
                           validatecommand=vcmd)
        ent_ate = ttk.Entry(frame_linha, width=4, validate="key",
                            validatecommand=vcmd)
        ent_palavras = ttk.Entry(frame_linha, width=4)
        for coluna, (entrada, exemplo) in enumerate((
                (ent_veiculo, "Ex.: Onix, Civic"), (ent_de, "R$ mín."),
                (ent_ate, "R$ máx."), (ent_palavras, "Ex.: repasse"))):
            entrada.grid(row=0, column=coluna, sticky="we", padx=(0, px(8)))
            placeholder(entrada, exemplo)
        for entrada, valor in ((ent_veiculo, nome), (ent_de, preco_min),
                               (ent_ate, preco_max),
                               (ent_palavras, palavras)):
            if valor:
                entrada.insert(0, str(valor))
        ent_veiculo.bind("<KeyRelease>", lambda _e: pedir_resumo(), add="+")
        linha_nova = {"frame": frame_linha, "nome": ent_veiculo,
                      "min": ent_de, "max": ent_ate,
                      "palavras": ent_palavras}
        remover = ttk.Button(frame_linha, text="✕", width=2, cursor="hand2",
                             style="IconePerigo.TButton",
                             command=lambda: remover_linha(linha_nova))
        remover.grid(row=0, column=4, sticky="w")
        linhas_veiculos.append(linha_nova)
        pedir_resumo()
        return linha_nova

    bt_adicionar = ttk.Button(corpo_busca, text="+  Adicionar veículo",
                              style="Destaque.TButton", cursor="hand2",
                              command=lambda: adicionar_linha())
    bt_adicionar.grid(row=2, column=0, sticky="w", pady=(px(4), 0))

    def veiculos_da_tela():
        """[{produto, preco_min, preco_max}] das linhas preenchidas."""
        itens = []
        for linha_atual in linhas_veiculos:
            nome_digitado = linha_atual["nome"].get().strip()
            if not nome_digitado:
                continue
            itens.append({"produto": nome_digitado,
                          "preco_min": linha_atual["min"].get().strip(),
                          "preco_max": linha_atual["max"].get().strip(),
                          # anúncio só vale se falar em alguma delas
                          "palavras": linha_atual["palavras"].get().strip()})
        return itens

    # -------------------------- filtros adicionais ------------------------
    sec_filtros = Cartao(esquerda, "Filtros adicionais")
    sec_filtros.grid(row=2, column=0, sticky="we", pady=(0, espaco))
    corpo_f = sec_filtros.corpo
    corpo_f.columnconfigure(4, weight=1)

    lbl_preco_padrao = ttk.Label(corpo_f, text="Preço padrão",
                                 style="Rotulo.TLabel")
    lbl_preco_padrao.grid(row=0, column=0, sticky="w", padx=(0, px(16)))
    ent_min = ttk.Entry(corpo_f, width=11, validate="key", validatecommand=vcmd)
    ent_min.grid(row=0, column=1, sticky="w")
    placeholder(ent_min, "R$ mín.")
    ttk.Label(corpo_f, text="até", style="Texto.TLabel").grid(
        row=0, column=2, padx=px(10))
    ent_max = ttk.Entry(corpo_f, width=11, validate="key", validatecommand=vcmd)
    ent_max.grid(row=0, column=3, sticky="w")
    placeholder(ent_max, "R$ máx.")
    ui_tema.texto_suave(
        corpo_f,
        "Vale para as linhas que ficarem sem faixa própria. Em \"Deve "
        "conter\", separe por vírgula (ex.: repasse, assumir financiamento) "
        "— o anúncio precisa falar em pelo menos uma.").grid(
        row=1, column=0, columnspan=5, sticky="we", pady=(px(4), px(14)))

    lbl_quantidade = ttk.Label(corpo_f, text="Quantidade", style="Rotulo.TLabel")
    lbl_quantidade.grid(row=2, column=0, sticky="w")
    ent_qtd = ttk.Entry(corpo_f, width=11, validate="key", validatecommand=vcmd)
    ent_qtd.grid(row=2, column=1, sticky="w")
    ttk.Label(corpo_f, text="por veículo (vazio = todos)",
              style="Ajuda.TLabel").grid(row=2, column=2, columnspan=3,
                                         sticky="w", padx=px(10))

    lbl_ignorar = ttk.Label(corpo_f, text="Ignorar com", style="Rotulo.TLabel")
    lbl_ignorar.grid(row=3, column=0, sticky="w", pady=(px(14), 0))
    ent_ignorar = ttk.Entry(corpo_f, width=30)
    ent_ignorar.grid(row=3, column=1, columnspan=4, sticky="we",
                     pady=(px(14), 0))
    placeholder(ent_ignorar, "Ex.: leilão, sinistro, batido")
    ui_tema.texto_suave(
        corpo_f,
        "Anúncio que falar em alguma dessas palavras é pulado. Vale para a "
        "busca inteira.").grid(row=4, column=0, columnspan=5, sticky="we",
                               pady=(px(4), 0))

    # -------------------------- filtros extras ---------------------------
    sec_extras = Cartao(esquerda, "Filtros extras",
                        subtitulo="Só a OLX usa estes filtros.")
    corpo_e = sec_extras.corpo
    for texto, coluna in (("Ano de", 0), ("até", 2), ("KM até", 4)):
        ttk.Label(corpo_e, text=texto, style="Rotulo.TLabel").grid(
            row=0, column=coluna, sticky="w", padx=(0 if coluna == 0 else px(12),
                                                    px(8)))
    ent_ano_min = ttk.Entry(corpo_e, width=7, validate="key",
                            validatecommand=vcmd)
    ent_ano_min.grid(row=0, column=1)
    ent_ano_max = ttk.Entry(corpo_e, width=7, validate="key",
                            validatecommand=vcmd)
    ent_ano_max.grid(row=0, column=3)
    ent_km_max = ttk.Entry(corpo_e, width=10, validate="key",
                           validatecommand=vcmd)
    ent_km_max.grid(row=0, column=5, sticky="w")
    ttk.Label(corpo_e, text="Câmbio", style="Rotulo.TLabel").grid(
        row=1, column=0, sticky="w", pady=(px(12), 0), padx=(0, px(8)))
    cmb_cambio = ttk.Combobox(corpo_e, state="readonly", width=18,
                              values=["Qualquer", "Manual", "Automático",
                                      "Semi-Automático", "Automatizado"])
    cmb_cambio.set("Qualquer")
    cmb_cambio.grid(row=1, column=1, columnspan=4, sticky="w",
                    pady=(px(12), 0))

    # ------------------------------ região ------------------------------
    sec_regiao = Cartao(direita, "Região", numero=3)
    sec_regiao.grid(row=0, column=0, sticky="we", pady=(0, espaco))
    corpo_r = sec_regiao.corpo
    corpo_r.columnconfigure(0, weight=1)
    corpo_r.columnconfigure(1, weight=1)
    ttk.Label(corpo_r, text="CEP", style="Rotulo.TLabel").grid(
        row=0, column=0, sticky="w", pady=(0, px(4)))
    ent_cep = ttk.Entry(corpo_r, width=14)
    ent_cep.grid(row=1, column=0, sticky="we", padx=(0, px(10)))
    placeholder(ent_cep, "00000-000")
    ent_cep.bind("<KeyRelease>", lambda _e: pedir_resumo(), add="+")
    lbl_raio = ttk.Label(corpo_r, text="Raio (km)", style="Rotulo.TLabel")
    lbl_raio.grid(row=0, column=1, sticky="w", pady=(0, px(4)))
    cmb_raio = ttk.Combobox(
        corpo_r, state="readonly", width=12,
        values=["1", "2", "5", "10", "20", "40", "60", "80", "100", "250", "500"])
    cmb_raio.set("60")
    cmb_raio.grid(row=1, column=1, sticky="we")
    cmb_raio.bind("<<ComboboxSelected>>", lambda _e: pedir_resumo(), add="+")
    ui_tema.texto_suave(
        corpo_r, "O CEP define a região da busca. O raio em km só vale para o "
                 "Facebook; nos outros sites a região vem do estado do CEP."
    ).grid(row=2, column=0, columnspan=2, sticky="we", pady=(px(8), 0))

    # ------------------------ dados de contato -------------------------
    sec_contato = Cartao(direita, "Seus dados de contato")
    corpo_c = sec_contato.corpo
    corpo_c.columnconfigure(0, weight=1)
    corpo_c.columnconfigure(1, weight=1)
    Banner(corpo_c, "O formulário do anúncio envia estes dados ao vendedor. "
                    "Nada é gravado em disco: vai só para o processo do bot e "
                    "some quando ele termina.", "info", fechavel=False,
           fundo=C["cartao"]).grid(row=0, column=0, columnspan=2, sticky="we",
                                   pady=(0, px(12)))
    entradas_contato = {}
    for indice, (campo, rotulo) in enumerate((("nome", "Nome"),
                                              ("email", "E-mail"),
                                              ("telefone", "Telefone"),
                                              ("cpf", "CPF"))):
        linha_g, coluna_g = divmod(indice, 2)
        lbl = ttk.Label(corpo_c, text=rotulo, style="Rotulo.TLabel")
        lbl.grid(row=1 + linha_g * 2, column=coluna_g, sticky="w",
                 pady=(px(4), px(4)), padx=(0 if coluna_g == 0 else px(10), 0))
        entrada = ttk.Entry(corpo_c, width=16)
        entrada.grid(row=2 + linha_g * 2, column=coluna_g, sticky="we",
                     padx=(0 if coluna_g else 0, px(10) if coluna_g == 0 else 0))
        entradas_contato[campo] = (lbl, entrada)
    ent_nome = entradas_contato["nome"][1]
    ent_email = entradas_contato["email"][1]
    ent_telefone = entradas_contato["telefone"][1]
    lbl_cpf, ent_cpf = entradas_contato["cpf"]

    # ------------------------------ mensagem ----------------------------
    sec_msg = Cartao(direita, "Mensagem enviada ao vendedor", numero=4)
    sec_msg.grid(row=2, column=0, sticky="we", pady=(0, espaco))
    txt_msg = ui_tema.campo_texto(sec_msg.corpo, altura=6)
    txt_msg.moldura.pack(fill="x")
    lbl_contagem = ttk.Label(sec_msg.corpo, text="0 caracteres",
                             style="Ajuda.TLabel")
    lbl_contagem.pack(anchor="e", pady=(px(6), 0))

    def contar(_evento=None):
        total = len(txt_msg.get("1.0", "end").strip())
        lbl_contagem.configure(text=f"{total} caractere{'s' if total != 1 else ''}")

    txt_msg.bind("<KeyRelease>", contar, add="+")

    # ------------------------------ resumo ------------------------------
    resumo = ResumoExecucao(direita)
    resumo.grid(row=3, column=0, sticky="we", pady=(0, espaco))
    resumo.linha("sites", "Sites", "globo")
    resumo.linha("veiculos", "Veículos", "carro")
    resumo.linha("regiao", "Região", "local")
    resumo.linha("modo", "Modo", "escudo")

    def atualizar_resumo():
        agendado["resumo"] = False
        marcados = sites_escolhidos()
        nomes = [CARTOES_SITES[s][0] for s in marcados]
        resumo.valor("sites", f"{len(marcados)} selecionado"
                              f"{'s' if len(marcados) != 1 else ''}"
                     if marcados else "Nenhum",
                     tipo=None if marcados else "erro",
                     detalhe=", ".join(nomes) or None)
        itens = veiculos_da_tela()
        resumo.valor("veiculos", str(len(itens)) if itens else "Nenhum",
                     tipo=None if itens else "aviso",
                     detalhe=", ".join(i["produto"] for i in itens[:4])
                     + ("…" if len(itens) > 4 else "") or None)
        cep = ent_cep.get().strip()
        raio = (f"raio de {cmb_raio.get()} km"
                if campos_dos_sites(marcados)["raio"] else None)
        resumo.valor("regiao", f"CEP {cep}" if cep else "CEP não informado",
                     tipo=None if cep else "aviso", detalhe=raio)
        resumo.valor("modo", "Teste" if var_dry.get() else "Envio real",
                     tipo="primaria" if var_dry.get() else "aviso")

    def pedir_resumo():
        if not agendado["resumo"]:
            agendado["resumo"] = True
            root.after_idle(atualizar_resumo)

    var_dry.trace_add("write", lambda *_: pedir_resumo())

    # -------------------------------- log -------------------------------
    log = LogExecucao(conteudo, "Log da execução", altura=12)
    log.grid(row=2, column=0, sticky="we")

    # ----------------------------- funções -------------------------------
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
                log.adicionar("Bot encerrado.")
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
        if rodada["execucao"] is not None:
            execucoes.salvar(rodada["execucao"],
                             "parada" if rodada["parada"] else "concluída")
            rodada["execucao"] = None
        status.set("Execução encerrada. Confira o log.")

    def rodar():
        global processo
        if processo is not None and processo.poll() is None:
            status.set("O bot já está rodando.")
            return

        faixas = veiculos_da_tela()
        produtos = [item["produto"] for item in faixas]
        params = {
            # a fila; `produto` fica como o primeiro por compatibilidade com
            # parametros.json antigos
            "produtos":   produtos,
            "produto":    produtos[0] if produtos else "",
            # faixa de preço POR veículo; a de baixo é só o padrão
            "faixas":     faixas,
            "preco_min":  ent_min.get().strip(),
            "preco_max":  ent_max.get().strip(),
            "cep":        ent_cep.get().strip(),
            "raio_km":    cmb_raio.get(),
            "quantidade": ent_qtd.get().strip(),
            "mensagem":   txt_msg.get("1.0", "end").strip(),
            "dry_run":    bool(var_dry.get()),
            "sites":      sites_escolhidos(),
            # `site` continua no JSON para parametros.json antigo/compat
            "site":       site_escolhido(),
            "ano_min":    ent_ano_min.get().strip(),
            "ano_max":    ent_ano_max.get().strip(),
            "km_max":     ent_km_max.get().strip(),
            "cambio":     cmb_cambio.get(),
            "ignorar_palavras": ent_ignorar.get().strip(),
        }
        if not produtos or not params["mensagem"]:
            status.set("Erro: informe ao menos um veículo e a mensagem.")
            return
        if not params["sites"]:
            status.set("Erro: marque ao menos uma fonte em 'Onde buscar'.")
            return
        for item in faixas:
            de, ate = (so_digitos_ou_none(item["preco_min"]),
                       so_digitos_ou_none(item["preco_max"]))
            if de is not None and ate is not None and de > ate:
                status.set(f"Erro em '{item['produto']}': o preço mínimo é "
                           "maior que o máximo.")
                return

        # dados pessoais NÃO entram no JSON: vão só no ambiente do processo
        # do bot e somem quando ele termina. E só vão para o site que os
        # pede de fato — o chat da OLX, por exemplo, não usa CPF nem nada
        # disso, então nada é passado adiante quando ela é a escolhida.
        usa = campos_dos_sites(sites_escolhidos())
        if usa["contato"]:
            dados_contato = {
                "nome": ent_nome.get().strip(),
                # CPF só para quem pede de verdade (hoje, só o iCarros)
                "cpf": ent_cpf.get().strip() if usa["cpf"] else "",
                "telefone": ent_telefone.get().strip(),
                "email": ent_email.get().strip(),
            }
        else:
            dados_contato = {}
        ambiente = contato.para_ambiente(dados_contato)

        with open(CAMINHO_PARAMS, "w", encoding="utf-8") as f:
            json.dump(params, f, ensure_ascii=False, indent=2)

        limpar_sinal()           # descarta sinal antigo pra não 'prosseguir' sozinho
        log.limpar()

        processo = subprocess.Popen(
            get_bot_command(),
            cwd=BASE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, env=ambiente,
        )
        threading.Thread(target=ler_saida, args=(processo,), daemon=True).start()
        rodada.update(parada=False, execucao=execucoes.nova(
            "Compra", [CARTOES_SITES[s][0] for s in params["sites"]],
            produtos, params["dry_run"]))

        modo = "modo teste" if params["dry_run"] else "ENVIO REAL"
        status.set(f"Bot iniciado ({modo}). Faça o login e clique em Prosseguir.")
        barra.definir_estado("rodando")
        log.ao_vivo(True)
        # o log fica à vista: é por ele que se acompanha a execução
        root.after(150, lambda: tela_rolavel.yview_moveto(1.0))

    def prosseguir():
        if processo is not None and processo.poll() is None:
            dar_sinal()
            status.set("Sinal enviado — o bot vai prosseguir.")
            barra.definir_estado("rodando")
        else:
            status.set("O bot não está rodando.")

    def parar():
        global processo
        if processo is not None and processo.poll() is None:
            processo.terminate()
            processo = None
            rodada["parada"] = True
            status.set("Bot parado.")
        else:
            status.set("O bot não está rodando.")
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

    # ------------------------------- ações ------------------------------
    barra = BarraAcoes(frame, var_dry, rodar, prosseguir, parar, status,
                       verbo="envia")
    barra.grid(row=1, column=0, sticky="we")

    # ------------- mostrar/esconder conforme o site escolhido ------------
    def atualizar_campos_do_site(*_):
        """Some com o que nenhuma fonte marcada usa, em vez de deixar campo
        cinza."""
        marcados = sites_escolhidos()
        usa = campos_dos_sites(marcados)

        if usa["raio"]:
            lbl_raio.grid()
            cmb_raio.grid()
        else:
            lbl_raio.grid_remove()
            cmb_raio.grid_remove()

        if usa["cpf"]:
            lbl_cpf.grid()
            ent_cpf.grid()
        else:
            lbl_cpf.grid_remove()
            ent_cpf.grid_remove()

        if usa["extras"]:
            sec_extras.grid(row=3, column=0, sticky="we", pady=(0, espaco))
        else:
            sec_extras.grid_remove()
        if usa["contato"]:
            sec_contato.grid(row=1, column=0, sticky="we", pady=(0, espaco))
        else:
            sec_contato.grid_remove()

        dicas = [f"{rotulo}: {DICAS[sid]}" for rotulo, sid in SITES_COMPRA
                 if sid in marcados and DICAS.get(sid)]
        lbl_site_dica.configure(text=SEPARADOR.join(dicas))
        pedir_resumo()

    adicionar_linha()
    atualizar_campos_do_site()   # estado inicial (Facebook marcado)
    contar()

    # ---------------------------- passo a passo ----------------------------
    # abre sozinho só na primeira visita; depois, pelo botão "?" do topo
    guia = tutorial.Tutorial(root, "compra-v2", rolavel=conteudo, passos=[
        tutorial.Passo(
            "Página de Compra",
            "Aqui você diz o que procurar e onde. O bot abre os sites, "
            "encontra os anúncios e manda a sua mensagem aos vendedores. "
            "Vamos ver cada parte."),
        tutorial.Passo(
            "1. Onde buscar",
            "Clique nos cartões para marcar um ou mais sites. O bot faz um de "
            "cada vez, na mesma execução. Pare o mouse sobre um cartão para "
            "ver o que aquele site aceita; o selo diz se ele manda mensagem, "
            "usa formulário ou só lista.",
            lambda: [sec_site]),
        tutorial.Passo(
            "2. Os veículos que você procura",
            "Uma linha por veículo. Em Veículo, escreva o modelo — só "
            "'palio' já basta, o bot completa a marca. Em Preço de / até, a "
            "faixa daquele carro. Em Deve conter, palavras que o anúncio "
            "precisa ter (ex.: repasse, assumir financiamento). O ✕ apaga a "
            "linha.",
            lambda: [cabecalho, quadro_veiculos]),
        tutorial.Passo(
            "Mais de um veículo",
            "Cria outra linha. O bot termina a busca de um veículo antes de "
            "começar a do próximo.",
            lambda: [bt_adicionar]),
        tutorial.Passo(
            "Filtros adicionais",
            "O preço padrão vale para as linhas sem faixa própria. Quantidade "
            "é o máximo de anúncios por veículo (vazio = todos). Ignorar com "
            "pula anúncios que falem nessas palavras — ex.: leilão, sinistro.",
            lambda: [sec_filtros]),
        tutorial.Passo(
            "3. Região",
            "O CEP define a região da busca (obrigatório). O raio em km só "
            "aparece com o Facebook marcado; nos outros sites a região vem do "
            "estado do CEP.",
            lambda: [sec_regiao]),
        tutorial.Passo(
            "Seus dados de contato",
            "Aparece quando um site marcado manda um formulário ao vendedor "
            "(iCarros, Webmotors, Mobiauto). Nome, e-mail e telefone vão só "
            "para o anúncio e somem quando o bot fecha — nada fica salvo.",
            lambda: [sec_contato], opcional=True),
        tutorial.Passo(
            "4. Mensagem ao vendedor",
            "O texto que o vendedor recebe. Escreva como se fosse você: "
            "apresente-se e diga o que quer saber do carro.",
            lambda: [sec_msg]),
        tutorial.Passo(
            "Resumo",
            "Confira aqui, antes de rodar, quantos sites e veículos entram, a "
            "região e o modo. O que estiver faltando aparece em amarelo.",
            lambda: [resumo]),
        tutorial.Passo(
            "Modo teste",
            "Ligado, o bot preenche tudo mas NÃO envia. Deixe ligado na "
            "primeira vez para conferir como fica; desligue quando quiser "
            "mandar as mensagens de verdade — a faixa fica amarela para "
            "lembrar.",
            lambda: [barra.bloco_teste]),
        tutorial.Passo(
            "Rodar",
            "Grava as suas escolhas e abre o navegador. O bot começa pela "
            "primeira fonte marcada.",
            lambda: [barra.bt_rodar]),
        tutorial.Passo(
            "Prosseguir",
            "Quando o navegador abrir, faça o login no site (se ele pedir) e "
            "confira a busca. Aí clique em Prosseguir para o bot continuar. "
            "Quando o bot estiver esperando, o botão fica roxo e aparece "
            "'Aguardando sua confirmação'.",
            lambda: [barra.bt_prosseguir]),
        tutorial.Passo(
            "Parar",
            "Interrompe o bot na hora, em qualquer momento.",
            lambda: [barra.bt_parar]),
        tutorial.Passo(
            "Acompanhe pelo log",
            "Tudo o que o bot faz aparece aqui, com a hora e um ícone: azul é "
            "informação, verde deu certo, amarelo é aviso ou anúncio pulado e "
            "vermelho é erro. Copiar leva o log para a área de transferência.",
            lambda: [log]),
        tutorial.Passo(
            "Precisa rever?",
            "Clique no ? a qualquer momento para ver este passo a passo de "
            "novo.",
            lambda: [cabeca.bt_ajuda]),
    ])

    drenar_log()
    return Pagina(frame, guia.iniciar_se_primeira_vez, encerrar, guia)


def iniciar():
    """Abre o app direto na Compra (compatibilidade)."""
    import interface_principal
    interface_principal.iniciar("compra")


if __name__ == "__main__":
    iniciar()
