# src/interface_principal.py
"""
Janela única do MarketplaceBot: lateral fixa + página da vez.

  Início        → painel com os atalhos para Compra e Venda
  Compra        → interface_bot.montar()
  Venda/Anúncio → venda/interface_venda.montar()

Antes cada modo abria a SUA janela e o app ficava num laço de janelas.
Agora as páginas são montadas uma vez, na primeira visita, e ficam vivas:
trocar de página não perde o que foi preenchido nem derruba um bot que
esteja rodando. Fechar a janela encerra o que estiver em execução
(`encerrar()` de cada página).

A conta do Supabase é da Venda, mas aparece no rodapé da lateral: a sessão
salva é conferida uma vez, em segundo plano, ao abrir (`App.banco`), e a
página de Venda usa o mesmo objeto — o refresh token do Supabase só vale
uma vez, então duas renovações ao mesmo tempo derrubariam a sessão.
"""
import random
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

import tutorial
import ui_imagens
import ui_tema
from ui_componentes import Banner, CabecalhoPagina, dica_flutuante
from ui_scroll import criar_area_rolavel
from ui_tabela import encurtar

C = ui_tema.CORES

DICAS = [
    "Marque quantos sites quiser na Compra: o bot faz uma fonte de cada vez, "
    "na mesma execução.",
    "Deixe o modo teste ligado na primeira execução: o bot preenche tudo e "
    "não envia nem publica nada.",
    "Na Venda, cada veículo é anunciado no máximo uma vez por site — a trava "
    "evita spam.",
    "Pode escrever só o modelo (ex.: palio): na Webmotors, no iCarros e na "
    "Mobiauto o bot completa a marca.",
]


def _versao():
    try:
        from version import __version__
        return __version__
    except Exception:
        return ""


# ------------------------------------------------------------- lateral
class ItemLateral(tk.Canvas):
    """Item de navegação da lateral (selecionado = pílula roxa)."""

    def __init__(self, pai, nome_icone, texto, comando=None, em_breve=False):
        self.px = lambda v: ui_tema.px(pai, v)  # noqa: E731
        super().__init__(pai, width=self.px(208), height=self.px(40),
                         bg=C["lateral"], highlightthickness=0, borderwidth=0,
                         cursor="arrow" if em_breve else "hand2",
                         takefocus=0 if em_breve else 1)
        self.nome_icone, self.texto = nome_icone, texto
        self.comando, self.em_breve = comando, em_breve
        self.selecionado = self.hover = False
        self._imgs = {}
        if not em_breve:
            self.bind("<Button-1>", lambda _e: comando and comando())
            self.bind("<space>", lambda _e: comando and comando())
            self.bind("<Return>", lambda _e: comando and comando())
            self.bind("<Enter>", lambda _e: self._sobre(True))
            self.bind("<Leave>", lambda _e: self._sobre(False))
            self.bind("<FocusIn>", lambda _e: self.redesenhar())
            self.bind("<FocusOut>", lambda _e: self.redesenhar())
        self.redesenhar()

    def _sobre(self, sim):
        self.hover = sim
        self.redesenhar()

    def _pilula(self, cor):
        if cor not in self._imgs:
            self._imgs[cor] = ui_tema.guardar(self, ui_imagens.retangulo(
                self, int(self["width"]), int(self["height"]),
                self.px(8), cor))
        return self._imgs[cor]

    def redesenhar(self):
        self.delete("all")
        meio = int(self["height"]) // 2
        if self.selecionado:
            self.create_image(0, 0, anchor="nw", image=self._pilula(C["primaria"]))
        elif self.hover or self.focus_get() is self:
            self.create_image(0, 0, anchor="nw",
                              image=self._pilula(C["lateral_hover"]))
        cor = ("#ffffff" if self.selecionado
               else C["lateral_suave"] if self.em_breve else C["lateral_texto"])
        self.create_text(self.px(16), meio, anchor="w", fill=cor,
                         text=ui_tema.ICONES[self.nome_icone],
                         font=(ui_tema.FONTE_ICONES, 12))
        self.create_text(self.px(46), meio, anchor="w", fill=cor, text=self.texto,
                         font=(ui_tema.FONTE_FORTE if self.selecionado
                               else ui_tema.FONTE, 10))
        if self.em_breve:
            fonte = (ui_tema.FONTE_FORTE, 7)
            largura = tkfont.Font(root=self, font=fonte).measure("Em breve") \
                + self.px(12)
            chave = ("selo", largura)
            if chave not in self._imgs:
                self._imgs[chave] = ui_tema.guardar(self, ui_imagens.retangulo(
                    self, largura, self.px(16), self.px(8), "#1e293b"))
            x = int(self["width"]) - self.px(10) - largura // 2
            self.create_image(x, meio, image=self._imgs[chave])
            self.create_text(x, meio, text="Em breve", fill="#94a3b8", font=fonte)


class Lateral(tk.Frame):
    def __init__(self, pai, app):
        px = lambda v: ui_tema.px(pai, v)  # noqa: E731
        super().__init__(pai, bg=C["lateral"], width=px(232))
        self.app = app
        self.pack_propagate(False)

        # marca
        topo = tk.Frame(self, bg=C["lateral"])
        topo.pack(fill="x", padx=px(16), pady=(px(22), px(26)))
        logo = tk.Canvas(topo, width=px(38), height=px(38), bg=C["lateral"],
                         highlightthickness=0)
        logo.pack(side="left")
        self._logo = ui_tema.guardar(self, ui_imagens.retangulo(
            self, px(38), px(38), px(10), C["primaria"],
            gradiente=("#8b5cf6", "#6d28d9")))
        logo.create_image(0, 0, anchor="nw", image=self._logo)
        logo.create_text(px(19), px(19), text="M", fill="#ffffff",
                         font=(ui_tema.FONTE_FORTE, 15))
        nomes = tk.Frame(topo, bg=C["lateral"])
        nomes.pack(side="left", padx=(px(10), 0))
        tk.Label(nomes, text="MarketplaceBot", bg=C["lateral"], fg="#ffffff",
                 font=(ui_tema.FONTE_FORTE, 12)).pack(anchor="w")
        tk.Label(nomes, text=f"v{_versao()}", bg=C["lateral"],
                 fg=C["lateral_suave"], font=(ui_tema.FONTE, 8)).pack(anchor="w")

        # navegação
        self.itens = {}
        for chave, nome_icone, texto in (("inicio", "inicio", "Início"),
                                         ("compra", "compra", "Compra"),
                                         ("venda", "venda", "Venda / Anúncio")):
            item = ItemLateral(self, nome_icone, texto,
                               comando=lambda c=chave: app.ir(c))
            item.pack(padx=px(12), pady=(0, px(4)))
            self.itens[chave] = item

        tk.Label(self, text="EM BREVE", bg=C["lateral"], fg="#475569",
                 font=(ui_tema.FONTE_FORTE, 8)).pack(anchor="w", padx=px(28),
                                                     pady=(px(20), px(6)))
        for nome_icone, texto in (("salvos", "Anúncios salvos"),
                                  ("historico", "Histórico"),
                                  ("config", "Configurações")):
            ItemLateral(self, nome_icone, texto, em_breve=True).pack(
                padx=px(12), pady=(0, px(4)))

        # conta (rodapé)
        rodape = tk.Frame(self, bg=C["lateral"])
        rodape.pack(side="bottom", fill="x", padx=px(16), pady=px(18))
        tk.Frame(self, bg="#1e293b", height=1).pack(side="bottom", fill="x")
        linha = tk.Frame(rodape, bg=C["lateral"])
        linha.pack(fill="x")
        self.ponto = tk.Label(linha, text="●", bg=C["lateral"],
                              font=(ui_tema.FONTE, 9))
        self.ponto.pack(side="left")
        self.lbl_estado = tk.Label(linha, bg=C["lateral"], fg=C["lateral_texto"],
                                   font=(ui_tema.FONTE_FORTE, 9))
        self.lbl_estado.pack(side="left", padx=(px(6), 0))
        self.lbl_email = tk.Label(rodape, bg=C["lateral"], fg=C["lateral_suave"],
                                  font=(ui_tema.FONTE, 9), anchor="w")
        self.lbl_email.pack(fill="x", pady=(px(2), px(10)))
        self.bt_conta = ttk.Button(rodape, style="Lateral.TButton",
                                   cursor="hand2")
        self.bt_conta.pack(fill="x")
        self._email = None
        dica_flutuante(self.lbl_email, lambda: self._email or "")
        self.conta(None, verificando=True)

    def selecionar(self, chave):
        for nome, item in self.itens.items():
            item.selecionado = nome == chave
            item.redesenhar()

    def conta(self, email, verificando=False):
        px = lambda v: ui_tema.px(self, v)  # noqa: E731
        self._email = email
        if email:
            self.ponto.configure(fg=C["sucesso"])
            self.lbl_estado.configure(text="Conectado")
            fonte = tkfont.Font(root=self, family=ui_tema.FONTE, size=9)
            self.lbl_email.configure(text=encurtar(email, fonte, px(196)))
            self.bt_conta.configure(text="Sair", command=self.app.sair_da_conta)
        else:
            self.ponto.configure(fg=C["lateral_suave"])
            self.lbl_estado.configure(text="Verificando conta…" if verificando
                                      else "Sem conta conectada")
            self.lbl_email.configure(text="Conta do sistema de veículos")
            self.bt_conta.configure(text="Entrar",
                                    command=lambda: self.app.ir("venda"))


# ------------------------------------------------------------- início
class CartaoAcao(tk.Canvas):
    """Cartão grande e clicável do painel (gradiente, ícone, chips, seta)."""

    def __init__(self, pai, titulo, descricao, chips, cores, nome_icone,
                 comando):
        self.px = lambda v: ui_tema.px(pai, v)  # noqa: E731
        super().__init__(pai, height=self.px(190), bg=C["fundo"],
                         highlightthickness=0, borderwidth=0, cursor="hand2",
                         takefocus=1)
        self.titulo, self.descricao, self.chips = titulo, descricao, chips
        self.cores, self.nome_icone, self.comando = cores, nome_icone, comando
        self.hover = False
        self._imgs = {}
        self._tamanho = None
        self._agendado = None
        for evento, acao in (("<Button-1>", lambda _e: comando()),
                             ("<Return>", lambda _e: comando()),
                             ("<space>", lambda _e: comando()),
                             ("<Enter>", lambda _e: self._sobre(True)),
                             ("<Leave>", lambda _e: self._sobre(False)),
                             ("<FocusIn>", lambda _e: self.redesenhar()),
                             ("<FocusOut>", lambda _e: self.redesenhar())):
            self.bind(evento, acao)
        self.bind("<Configure>", self._redimensionou)

    def _sobre(self, sim):
        self.hover = sim
        self.redesenhar()

    def _redimensionou(self, _evento=None):
        if self._agendado:
            self.after_cancel(self._agendado)
        self._agendado = self.after(60, self.redesenhar)

    def _fundo(self, largura, altura, hover, foco):
        chave = (largura, altura, hover, foco)
        if chave not in self._imgs:
            if len(self._imgs) > 8:
                self._imgs.clear()
            inicio, fim = self.cores
            if hover:
                inicio = ui_imagens.misturar(inicio, "#ffffff", 0.08)
            self._imgs[chave] = ui_tema.guardar(self, ui_imagens.retangulo(
                self, largura, altura, self.px(16), fim, gradiente=(inicio, fim),
                sombra=self.px(14 if hover else 9),
                forca_sombra=0.20 if hover else 0.12,
                anel=C["primaria_borda"] if foco else None,
                espessura_anel=self.px(3) if foco else 0))
        return self._imgs[chave]

    def _peca(self, chave, fabrica):
        if chave not in self._imgs:
            self._imgs[chave] = ui_tema.guardar(self, fabrica())
        return self._imgs[chave]

    def redesenhar(self):
        self._agendado = None
        if not self.winfo_exists():
            return
        largura, altura = self.winfo_width(), int(self["height"])
        if largura <= 1:
            return
        px = self.px
        foco = self.focus_get() is self
        margem = px(14)                         # espaço da sombra
        subir = -px(2) if self.hover else 0     # elevação no hover
        self.delete("all")
        self.create_image(0, subir, anchor="nw",
                          image=self._fundo(largura, altura, self.hover, foco))
        x0, y0 = margem + px(24), margem + px(20) + subir
        tinta = ui_imagens.misturar(self.cores[1], "#ffffff", 0.22)
        tile = px(48)
        self.create_image(x0, y0, anchor="nw", image=self._peca(
            ("tile", tile, tinta), lambda: ui_imagens.retangulo(
                self, tile, tile, px(12), tinta)))
        self.create_text(x0 + tile // 2, y0 + tile // 2, fill="#ffffff",
                         text=ui_tema.ICONES[self.nome_icone],
                         font=(ui_tema.FONTE_ICONES, 18))
        texto_x = x0 + tile + px(18)
        largura_texto = largura - texto_x - margem - px(80)
        self.create_text(texto_x, y0 + px(2), anchor="nw", fill="#ffffff",
                         text=self.titulo, font=(ui_tema.FONTE_FORTE, 15))
        self.create_text(texto_x, y0 + px(34), anchor="nw", fill="#eef2ff",
                         text=self.descricao, font=(ui_tema.FONTE, 10),
                         width=max(px(120), largura_texto))
        # seta
        seta = px(34)
        sx = largura - margem - px(24) - seta // 2
        sy = y0 + tile // 2
        self.create_image(sx, sy, image=self._peca(
            ("seta", seta, tinta), lambda: ui_imagens.retangulo(
                self, seta, seta, seta / 2, tinta)))
        self.create_text(sx + (px(2) if self.hover else 0), sy, fill="#ffffff",
                         text=ui_tema.ICONES["seta"],
                         font=(ui_tema.FONTE_ICONES, 11))
        # chips com o que o modo faz
        fonte = tkfont.Font(root=self, family=ui_tema.FONTE_FORTE, size=8)
        cx = x0
        cy = altura - margem - px(30) + subir
        for chip in self.chips:
            w = fonte.measure(chip) + px(22)
            if cx + w > largura - margem - px(20):
                break
            self.create_image(cx, cy, anchor="nw", image=self._peca(
                ("chip", w, tinta), lambda w=w: ui_imagens.retangulo(
                    self, w, px(24), px(12), tinta)))
            self.create_text(cx + w // 2, cy + px(12), text=chip,
                             fill="#ffffff", font=fonte)
            cx += w + px(8)


class CartaoAtalho(tk.Canvas):
    """Cartão pequeno do "Acesso rápido"."""

    def __init__(self, pai, nome_icone, titulo, descricao, comando=None):
        self.px = lambda v: ui_tema.px(pai, v)  # noqa: E731
        super().__init__(pai, height=self.px(84), bg=C["fundo"],
                         highlightthickness=0, borderwidth=0,
                         cursor="hand2" if comando else "arrow",
                         takefocus=1 if comando else 0)
        self.nome_icone, self.titulo = nome_icone, titulo
        self.descricao, self.comando = descricao, comando
        self.hover = False
        self._imgs = {}
        if comando:
            for evento, acao in (("<Button-1>", lambda _e: comando()),
                                 ("<Return>", lambda _e: comando()),
                                 ("<Enter>", lambda _e: self._sobre(True)),
                                 ("<Leave>", lambda _e: self._sobre(False))):
                self.bind(evento, acao)
        self.bind("<Configure>", lambda _e: self.redesenhar())

    def _sobre(self, sim):
        self.hover = sim
        self.redesenhar()

    def _img(self, chave, fabrica):
        if chave not in self._imgs:
            self._imgs[chave] = ui_tema.guardar(self, fabrica())
        return self._imgs[chave]

    def redesenhar(self):
        largura, altura = self.winfo_width(), int(self["height"])
        if largura <= 1:
            return
        px = self.px
        ativo = self.comando is not None
        borda = C["primaria_borda"] if self.hover else C["borda"]
        preenche = C["cartao"] if ativo else "#fbfcfd"
        self.delete("all")
        self.create_image(0, 0, anchor="nw", image=self._img(
            ("fundo", largura, altura, borda, preenche),
            lambda: ui_imagens.retangulo(self, largura, altura, px(12), preenche,
                                         borda=borda, sombra=px(3),
                                         forca_sombra=0.05)))
        tile = px(40)
        tinta = C["primaria_suave"] if ativo else C["inativo_fundo"]
        self.create_image(px(16), altura // 2 - px(2), anchor="w", image=self._img(
            ("tile", tinta), lambda: ui_imagens.retangulo(self, tile, tile,
                                                          px(10), tinta)))
        self.create_text(px(16) + tile // 2, altura // 2 - px(2),
                         text=ui_tema.ICONES[self.nome_icone],
                         fill=C["primaria"] if ativo else C["inativo_texto"],
                         font=(ui_tema.FONTE_ICONES, 14))
        tx = px(16) + tile + px(14)
        self.create_text(tx, altura // 2 - px(12), anchor="w", text=self.titulo,
                         fill=C["texto"] if ativo else C["texto_suave"],
                         font=(ui_tema.FONTE_FORTE, 10))
        self.create_text(tx, altura // 2 + px(8), anchor="w",
                         text=self.descricao, fill=C["texto_suave"],
                         font=(ui_tema.FONTE, 9),
                         width=largura - tx - px(12))


class PaginaInicio:
    def __init__(self, pai, app):
        self.app = app
        px = lambda v: ui_tema.px(pai, v)  # noqa: E731
        self.frame = tk.Frame(pai, bg=C["fundo"])
        conteudo = criar_area_rolavel(self.frame, padding=32)
        conteudo.columnconfigure(0, weight=1)
        self.rolavel = conteudo

        cabeca = CabecalhoPagina(conteudo, "Olá!", "O que você quer fazer hoje?",
                                 ajuda=lambda: self.guia.iniciar())
        cabeca.grid(row=0, column=0, sticky="we", pady=(0, px(20)))

        grade = tk.Frame(conteudo, bg=C["fundo"])
        grade.grid(row=1, column=0, sticky="we")
        self.cta_compra = CartaoAcao(
            grade, "Compra", "Busca anúncios nos sites e envia mensagens aos "
            "vendedores.", ["Vários sites", "Faixa de preço por veículo",
                            "Filtro por palavras"],
            ("#3b82f6", "#4f46e5"), "compra", lambda: app.ir("compra"))
        self.cta_venda = CartaoAcao(
            grade, "Venda / Anúncio", "Anuncia os veículos do seu banco nos "
            "sites escolhidos.", ["Vários sites", "Modo teste",
                                  "Um anúncio por site"],
            ("#8b5cf6", "#6d28d9"), "venda", lambda: app.ir("venda"))
        self._grade_cta = grade
        self._colunas_cta = None
        grade.bind("<Configure>", self._reorganizar, add="+")

        ttk.Label(conteudo, text="Acesso rápido", style="Grupo.TLabel").grid(
            row=2, column=0, sticky="w", pady=(px(20), px(10)))
        atalhos = tk.Frame(conteudo, bg=C["fundo"])
        atalhos.grid(row=3, column=0, sticky="we")
        self.atalho_ajuda = CartaoAtalho(
            atalhos, "ajuda", "Ajuda", "Passo a passo desta tela",
            comando=lambda: self.guia.iniciar())
        self.atalhos = [
            CartaoAtalho(atalhos, "salvos", "Anúncios salvos", "Em breve"),
            CartaoAtalho(atalhos, "historico", "Histórico de execuções",
                         "Em breve"),
            CartaoAtalho(atalhos, "config", "Configurações", "Em breve"),
            self.atalho_ajuda,
        ]
        self._grade_atalhos = atalhos
        self._colunas_atalhos = None
        atalhos.bind("<Configure>", self._reorganizar, add="+")

        self.banner = Banner(conteudo, random.choice(DICAS), "dica",
                             titulo="Dica:")
        self.banner.grid(row=4, column=0, sticky="we", pady=(px(24), 0))

        self.guia = tutorial.Tutorial(app.root, "inicio", rolavel=conteudo,
                                      passos=[
            tutorial.Passo(
                "Bem-vindo ao MarketplaceBot",
                "Este passo a passo mostra rapidinho como o programa funciona. "
                "Use Próximo e Anterior (ou as setas do teclado) — e dá para "
                "rever tudo depois, a qualquer momento."),
            tutorial.Passo(
                "Navegação",
                "A barra da esquerda leva a qualquer parte do programa. Trocar "
                "de página não perde o que você preencheu nem para um bot que "
                "esteja rodando.",
                lambda: [app.lateral]),
            tutorial.Passo(
                "Compra",
                "Procura carros à venda nos sites que você escolher — Facebook, "
                "Webmotors, OLX, iCarros e outros — e envia a sua mensagem aos "
                "vendedores. Também lista lotes de leilão.",
                lambda: [self.cta_compra]),
            tutorial.Passo(
                "Venda / Anúncio",
                "Anuncia os veículos cadastrados no seu sistema nos sites de "
                "classificados, preenchendo os formulários por você.",
                lambda: [self.cta_venda]),
            tutorial.Passo(
                "Sua conta",
                "A conta do sistema de veículos aparece aqui embaixo. Sair "
                "desconecta este computador da conta.",
                lambda: [app.lateral.bt_conta]),
            tutorial.Passo(
                "Ajuda quando quiser",
                "Cada página tem o botão ?. Clique nele sempre que quiser ver o "
                "passo a passo daquela página de novo.",
                lambda: [cabeca.bt_ajuda]),
        ])

    def _reorganizar(self, _evento=None):
        px = lambda v: ui_tema.px(self.frame, v)  # noqa: E731
        largura = self._grade_cta.winfo_width()
        colunas = 2 if largura >= px(760) else 1
        if colunas != self._colunas_cta:
            self._colunas_cta = colunas
            for c in range(2):
                self._grade_cta.columnconfigure(c, weight=1 if c < colunas else 0,
                                                uniform="cta" if c < colunas else "")
            for i, cartao in enumerate((self.cta_compra, self.cta_venda)):
                linha, coluna = divmod(i, colunas)
                cartao.grid(row=linha, column=coluna, sticky="we",
                            padx=(0 if coluna == 0 else px(10),
                                  px(10) if coluna < colunas - 1 else 0))
        largura = self._grade_atalhos.winfo_width()
        colunas = 4 if largura >= px(900) else 2
        if colunas != self._colunas_atalhos:
            self._colunas_atalhos = colunas
            for c in range(4):
                self._grade_atalhos.columnconfigure(
                    c, weight=1 if c < colunas else 0,
                    uniform="atalho" if c < colunas else "")
            for i, cartao in enumerate(self.atalhos):
                linha, coluna = divmod(i, colunas)
                cartao.grid(row=linha, column=coluna, sticky="we",
                            padx=(0 if coluna == 0 else px(6),
                                  px(6) if coluna < colunas - 1 else 0),
                            pady=(0, px(12)))

    def ao_mostrar(self):
        self.guia.iniciar_se_primeira_vez()

    def encerrar(self):
        pass


# -------------------------------------------------------------- janela
class App:
    def __init__(self, pagina_inicial="inicio"):
        self.root = tk.Tk()
        self.root.title("MarketplaceBot")
        ui_tema.aplicar_tema(self.root)
        ui_tema.geometria(self.root, 1440, 900, minimo=(1000, 620),
                          centralizar=True)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        from venda.banco import BancoVeiculos
        self.banco = BancoVeiculos()
        self.verificando_sessao = True
        self._ao_verificar = []

        self.lateral = Lateral(self.root, self)
        self.lateral.grid(row=0, column=0, sticky="ns")
        self.area = tk.Frame(self.root, bg=C["fundo"])
        self.area.grid(row=0, column=1, sticky="nsew")
        self.paginas = {}
        self.atual = None
        self.root.protocol("WM_DELETE_WINDOW", self.fechar)

        self._resultado_sessao = None
        threading.Thread(target=self._verificar_sessao, daemon=True).start()
        self.root.after(150, self._aguardar_sessao)
        self.ir(pagina_inicial)

    # ------------------------------------------------------ sessão
    def _verificar_sessao(self):
        # roda fora da thread principal: aqui NÃO se toca no Tk
        try:
            ok = self.banco.tentar_sessao_salva()
        except Exception:
            ok = False
        self._resultado_sessao = ok

    def _aguardar_sessao(self):
        if self._resultado_sessao is None:
            try:
                self.root.after(150, self._aguardar_sessao)
            except tk.TclError:
                pass        # janela fechou antes da resposta
            return
        self._sessao_verificada(self._resultado_sessao)

    def _sessao_verificada(self, ok):
        self.verificando_sessao = False
        self.definir_conta(self.banco.email if ok else None)
        pendentes, self._ao_verificar = self._ao_verificar, []
        for funcao in pendentes:
            funcao(ok)

    def quando_sessao_verificada(self, funcao):
        """Chama `funcao(ok)` já (se verificada) ou quando terminar."""
        if self.verificando_sessao:
            self._ao_verificar.append(funcao)
        else:
            funcao(self.banco.logado)

    def definir_conta(self, email):
        self.lateral.conta(email)

    def sair_da_conta(self):
        venda = self.paginas.get("venda")
        if venda is not None:
            venda.sair_da_conta()
        else:
            self.banco.logout()
            self.definir_conta(None)

    # ------------------------------------------------------ páginas
    def _montar(self, nome):
        if nome == "inicio":
            return PaginaInicio(self.area, self)
        if nome == "compra":
            import interface_bot
            return interface_bot.montar(self.area, self)
        from venda import interface_venda
        return interface_venda.montar(self.area, self)

    def ir(self, nome):
        if nome == self.atual:
            return
        if nome not in self.paginas:
            self.paginas[nome] = self._montar(nome)
        if self.atual is not None:
            self.paginas[self.atual].frame.pack_forget()
            guia = getattr(self.paginas[self.atual], "guia", None)
            if guia is not None and guia.ativo:
                guia.ativo = False
                guia.encerrar_sem_marcar()
        self.atual = nome
        self.paginas[nome].frame.pack(fill="both", expand=True)
        self.lateral.selecionar(nome)
        titulos = {"inicio": "MarketplaceBot", "compra": "MarketplaceBot — Compra",
                   "venda": "MarketplaceBot — Venda / Anúncio"}
        self.root.title(titulos[nome])
        self.root.after_idle(self.paginas[nome].ao_mostrar)

    def fechar(self):
        for pagina in self.paginas.values():
            try:
                pagina.encerrar()
            except Exception:
                pass
        self.root.destroy()


def iniciar(pagina="inicio"):
    """Abre a janela do app na página pedida e roda até fechar."""
    app = App(pagina)
    app.root.mainloop()
