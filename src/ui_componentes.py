# src/ui_componentes.py
"""
Blocos visuais básicos, reaproveitados por todas as telas:

- `Cartao`: seção em cartão branco arredondado, com título numerado,
  subtítulo, ações à direita e o conteúdo em `.corpo`;
- `CabecalhoPagina`: título + descrição da página, com Voltar e ajuda;
- `Marcador` e `Interruptor`: caixa de marcação e toggle desenhados em
  Canvas (a caixa do ttk não tem cantos nem cor do tema), ligados a IntVar,
  com teclado (Espaço) e anel de foco;
- `placeholder()`: texto de exemplo dentro do campo, que NÃO entra no
  `.get()` (é um rótulo por cima, que some ao focar ou digitar);
- `dica_flutuante()`: balão ao parar o mouse;
- `Banner`: faixa de dica/aviso, que pode ser fechada.

Cor e medida vêm de ui_tema; nada de hexadecimal solto aqui além do que o
próprio ui_tema não cobre.
"""
import tkinter as tk
from tkinter import ttk

import ui_animacao
import ui_imagens
import ui_tema

C = ui_tema.CORES


def _px(widget, valor):
    return ui_tema.px(widget, valor)


# ------------------------------------------------------------ molduras
_ESTILOS_MOLDURA = {}


def estilo_moldura(janela, preenchimento, borda=None, fundo=None, raio=10):
    """Estilo de ttk.Frame arredondado (criado uma vez por raiz e cores).

    `fundo` é a cor de quem está atrás (o ttk não mistura transparência).
    """
    raiz = janela.winfo_toplevel()
    fundo = fundo or C["cartao"]
    chave = (str(raiz), preenchimento, borda, fundo, raio)
    if chave in _ESTILOS_MOLDURA:
        return _ESTILOS_MOLDURA[chave]
    nome = f"Moldura{len(_ESTILOS_MOLDURA)}"
    s = ui_tema.escala(raiz)
    r = round(raio * s)
    # meio grande: o ttk repete o pedaço do meio para preencher o widget, e
    # meio pequeno vira milhares de cópias por pintura (ver ui_tema._ret)
    largura, altura = round(1200 * s), round(480 * s)
    imagem = ui_tema.guardar(raiz, ui_imagens.retangulo(
        raiz, largura, altura, r, preenchimento, borda=borda,
        espessura=max(1.0, round(s)), fundo=fundo))
    estilo = ttk.Style(raiz)
    # width/height: sem eles o elemento pede o tamanho da imagem grande
    estilo.element_create(f"{nome}.fundo", "image", imagem, border=r + 2,
                          sticky="nsew", width=2 * (r + 2), height=2 * (r + 2))
    estilo.layout(f"{nome}.TFrame", [(f"{nome}.fundo", {"sticky": "nsew"})])
    _ESTILOS_MOLDURA[chave] = f"{nome}.TFrame"
    return f"{nome}.TFrame"


# ---------------------------------------------------------------- ícone
def icone(pai, nome, tamanho=12, cor=None, fundo=None, **kw):
    """Rótulo com um glifo da fonte de ícones do Windows."""
    return tk.Label(pai, text=ui_tema.ICONES.get(nome, nome),
                    font=(ui_tema.FONTE_ICONES, tamanho),
                    fg=cor or C["texto_suave"], bg=fundo or C["cartao"],
                    borderwidth=0, **kw)


# -------------------------------------------------------------- cartão
class Cartao(ttk.Frame):
    """Seção em cartão. Monte o conteúdo em `.corpo` (fundo branco)."""

    def __init__(self, pai, titulo, subtitulo=None, numero=None, **kw):
        # o cartão tem 3 px de sombra embaixo e dos lados: entra no respiro
        super().__init__(pai, style="Cartao.TFrame",
                         padding=(_px(pai, 23), _px(pai, 19),
                                  _px(pai, 23), _px(pai, 23)), **kw)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        topo = ttk.Frame(self, style="Superficie.TFrame")
        topo.grid(row=0, column=0, sticky="we")
        if numero is not None:
            ttk.Label(topo, text=f"{numero}.", style="Numero.TLabel").pack(
                side="left", padx=(0, _px(pai, 6)))
        self.titulo = ttk.Label(topo, text=titulo, style="Secao.TLabel")
        self.titulo.pack(side="left")
        # ações do cartão (ex.: Copiar/Limpar do log) ficam à direita
        self.acoes = ttk.Frame(topo, style="Superficie.TFrame")
        self.acoes.pack(side="right")
        self.subtitulo = None
        if subtitulo:
            self.subtitulo = ui_tema.texto_suave(self, subtitulo)
            self.subtitulo.grid(row=1, column=0, sticky="we",
                                pady=(_px(pai, 2), 0))
        self.corpo = ttk.Frame(self, style="Superficie.TFrame")
        self.corpo.grid(row=2, column=0, sticky="nsew",
                        pady=(_px(pai, 14), 0))


# -------------------------------------------------------------- cabeçalho
class CabecalhoPagina(ttk.Frame):
    """Topo da página: [Voltar] Título / descrição ........ [extra] [?]."""

    def __init__(self, pai, titulo, subtitulo, voltar=None, ajuda=None):
        super().__init__(pai, style="Pagina.TFrame")
        self.columnconfigure(1, weight=1)
        coluna = 0
        if voltar:
            ttk.Button(self, text="←  Voltar", style="Fantasma.TButton",
                       cursor="hand2", command=voltar).grid(
                row=0, column=0, sticky="nw", padx=(0, _px(pai, 12)),
                pady=(_px(pai, 4), 0))
        coluna = 1
        textos = ttk.Frame(self, style="Pagina.TFrame")
        textos.grid(row=0, column=coluna, sticky="w")
        ttk.Label(textos, text=titulo, style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(textos, text=subtitulo, style="Subtitulo.TLabel").pack(
            anchor="w")
        # espaço para status da conta, filtros etc.
        self.direita = ttk.Frame(self, style="Pagina.TFrame")
        self.direita.grid(row=0, column=2, sticky="ne", pady=(_px(pai, 4), 0))
        self.bt_ajuda = None
        if ajuda:
            self.bt_ajuda = ttk.Button(self, text="?   Ajuda",
                                       style="Secundario.TButton",
                                       cursor="hand2", command=ajuda)
            self.bt_ajuda.grid(row=0, column=3, sticky="ne",
                               padx=(_px(pai, 8), 0), pady=(_px(pai, 4), 0))
            dica_flutuante(self.bt_ajuda, "Ver o passo a passo desta tela")


# ---------------------------------------------------- balão de ajuda
def dica_flutuante(widget, texto):
    """Balão escuro com `texto` ao parar o mouse sobre o widget.
    `texto` pode ser função (lida na hora de mostrar).

    O balão é um rótulo DENTRO da janela (place na raiz), e não um
    Toplevel: mostrar um Toplevel ativa a janela dele no Windows, e bastava
    passar o mouse num cartão para o campo em que se digitava perder o
    teclado.
    """
    estado = {"janela": None, "agendado": None}

    def mostrar():
        estado["agendado"] = None
        conteudo = texto() if callable(texto) else texto
        if (estado["janela"] is not None or not conteudo
                or not widget.winfo_exists()):
            return
        raiz = widget.winfo_toplevel()
        balao = tk.Label(raiz, text=conteudo, bg="#1e293b", fg="#f8fafc",
                         font=(ui_tema.FONTE, 9), justify="left",
                         wraplength=_px(widget, 320), padx=_px(widget, 10),
                         pady=_px(widget, 6), borderwidth=0)
        balao.update_idletasks()
        largura, altura = balao.winfo_reqwidth(), balao.winfo_reqheight()
        x = (widget.winfo_rootx() - raiz.winfo_rootx()
             + (widget.winfo_width() - largura) // 2)
        x = max(_px(widget, 4), min(x, raiz.winfo_width() - largura - _px(widget, 4)))
        y = widget.winfo_rooty() - raiz.winfo_rooty() + widget.winfo_height() \
            + _px(widget, 6)
        if y + altura > raiz.winfo_height():          # sem espaço: em cima
            y = widget.winfo_rooty() - raiz.winfo_rooty() - altura - _px(widget, 6)
        balao.place(x=x, y=max(0, y))
        balao.lift()
        estado["janela"] = balao

    def esconder(_evento=None):
        if estado["agendado"] is not None:
            try:
                widget.after_cancel(estado["agendado"])
            except tk.TclError:
                pass
            estado["agendado"] = None
        if estado["janela"] is not None:
            estado["janela"].destroy()
            estado["janela"] = None

    def agendar(_evento=None):
        esconder()
        estado["agendado"] = widget.after(450, mostrar)

    widget.bind("<Enter>", agendar, add="+")
    widget.bind("<Leave>", esconder, add="+")
    widget.bind("<ButtonPress>", esconder, add="+")
    widget.bind("<Destroy>", esconder, add="+")


# ------------------------------------------------------ placeholder
def placeholder(entrada, texto):
    """Texto de exemplo dentro do campo. É um rótulo POR CIMA: o valor do
    campo continua vazio (`.get()` devolve "")."""
    rotulo = tk.Label(entrada, text=texto, bg="#ffffff", fg=C["placeholder"],
                      font=(ui_tema.FONTE, 10), borderwidth=0, cursor="xterm")

    def atualizar(_evento=None):
        try:
            vazio = not entrada.get()
            focado = entrada.focus_get() is entrada
        except (tk.TclError, KeyError):
            return
        if vazio and not focado and "disabled" not in entrada.state():
            rotulo.place(x=_px(entrada, 13), rely=0.5, anchor="w")
        else:
            rotulo.place_forget()

    rotulo.bind("<Button-1>", lambda _e: entrada.focus_set())
    for evento in ("<FocusIn>", "<FocusOut>", "<KeyRelease>"):
        entrada.bind(evento, lambda _e: entrada.after_idle(atualizar), add="+")
    entrada.after_idle(atualizar)
    entrada.atualizar_placeholder = atualizar
    return rotulo


# ------------------------------------------------ marcador e interruptor
_IMAGENS = {}


def _imagem(widget, chave, fabrica):
    raiz = widget.winfo_toplevel()
    chave = (str(raiz),) + chave
    if chave not in _IMAGENS:
        _IMAGENS[chave] = ui_tema.guardar(raiz, fabrica(raiz))
    return _IMAGENS[chave]


class _Alternavel(tk.Canvas):
    """Base de Marcador/Interruptor: Canvas clicável ligado a uma IntVar."""

    def __init__(self, pai, largura, altura, variavel=None, comando=None,
                 fundo=None):
        self._folga = _px(pai, 3)
        super().__init__(pai, width=largura + 2 * self._folga,
                         height=altura + 2 * self._folga,
                         bg=fundo or C["cartao"], highlightthickness=0,
                         borderwidth=0, cursor="hand2", takefocus=1)
        self.variavel = variavel if variavel is not None else tk.IntVar(value=0)
        self.comando = comando
        self._ativo = True
        self._largura, self._altura = largura, altura
        self._rastreio = self.variavel.trace_add(
            "write", lambda *_: self.after_idle(self._variavel_mudou))
        self.bind("<Button-1>", self.alternar)
        self.bind("<space>", self.alternar)
        self.bind("<FocusIn>", lambda _e: self.redesenhar())
        self.bind("<FocusOut>", lambda _e: self.redesenhar())
        self.bind("<Destroy>", self._soltar, add="+")
        self.redesenhar()

    def _soltar(self, _evento=None):
        try:
            self.variavel.trace_remove("write", self._rastreio)
        except (tk.TclError, ValueError):
            pass

    def _variavel_mudou(self):
        if self.winfo_exists():
            self.redesenhar()

    def alternar(self, _evento=None):
        if not self._ativo:
            return "break"
        self.focus_set()
        self.variavel.set(0 if self.variavel.get() else 1)
        if self.comando:
            self.comando()
        return "break"

    def ativo(self, sim=True):
        self._ativo = bool(sim)
        self.configure(cursor="hand2" if sim else "arrow",
                       takefocus=1 if sim else 0)
        self.redesenhar()

    def fundo(self, cor):
        self.configure(bg=cor)

    def _desenhar_foco(self):
        if self.focus_get() is self and self._ativo:
            self.create_rectangle(1, 1, self._largura + 2 * self._folga - 2,
                                  self._altura + 2 * self._folga - 2,
                                  outline=C["primaria_borda"], width=2)

    def redesenhar(self):
        raise NotImplementedError


class Marcador(_Alternavel):
    """Caixa de marcação do tema. `parcial=True` mostra o traço (seleção
    incompleta, usada no "selecionar todos")."""

    def __init__(self, pai, variavel=None, comando=None, fundo=None,
                 tamanho=18):
        self._lado = _px(pai, tamanho)
        self.parcial = False
        super().__init__(pai, self._lado, self._lado, variavel, comando, fundo)

    def redesenhar(self):
        if not self.winfo_exists():
            return
        if not self._ativo:
            estado = "inativo"
        elif self.variavel.get():
            estado = "marcado"
        elif self.parcial:
            estado = "parcial"
        else:
            estado = "vazio"
        lado = self._lado
        s = ui_tema.escala(self)
        img = _imagem(self, ("marcacao", lado, estado), lambda raiz:
                      ui_imagens.marcacao(raiz, lado, estado, C["primaria"],
                                          C["borda_forte"], escala=s))
        self.delete("all")
        self._desenhar_foco()
        self.create_image(self._folga, self._folga, image=img, anchor="nw")


class Interruptor(_Alternavel):
    """Toggle (liga/desliga) do tema. O botão desliza até o outro lado."""

    def __init__(self, pai, variavel=None, comando=None, fundo=None):
        self._posicao = None
        super().__init__(pai, _px(pai, 40), _px(pai, 22), variavel, comando,
                         fundo)

    def _variavel_mudou(self):
        if self.winfo_exists():
            self._posicao.ir(1.0 if self.variavel.get() else 0.0)

    def redesenhar(self):
        if not self.winfo_exists():
            return
        if self._posicao is None:       # primeiro desenho: sem animação
            self._posicao = ui_animacao.Transicao(
                self, "posicao", lambda _v: self.redesenhar(),
                valor=1.0 if self.variavel.get() else 0.0, duracao="media")
        posicao = ui_animacao.degrau(self._posicao.valor, 8)
        ligado = posicao >= 0.5
        inativo = not self._ativo
        w, h = self._largura, self._altura
        img = _imagem(self, ("interruptor", w, h, posicao, inativo), lambda raiz:
                      ui_imagens.interruptor(raiz, w, h, ligado, C["primaria"],
                                             C["borda_campo"], inativo,
                                             posicao=posicao))
        self.delete("all")
        self._desenhar_foco()
        self.create_image(self._folga, self._folga, image=img, anchor="nw")


# ---------------------------------------------------------------- banner
class Banner(ttk.Frame):
    """Faixa discreta de dica/aviso (fundo claro, ícone, texto, fechar)."""

    TIPOS = {
        "dica": ("#f5f3ff", "#ddd6fe", C["primaria"], "lampada", "#3b0764"),
        "info": ("#eff6ff", "#bfdbfe", C["secundaria"], "info", "#1e3a8a"),
        "aviso": ("#fffbeb", "#fde68a", C["aviso"], "aviso", "#78350f"),
    }

    def __init__(self, pai, texto, tipo="dica", titulo=None, fechavel=True,
                 fundo=None, ao_fechar=None):
        preenche, borda, cor_icone, nome_icone, cor_texto = self.TIPOS[tipo]
        super().__init__(pai, style=estilo_moldura(pai, preenche, borda,
                                                   fundo or C["fundo"]),
                         padding=(_px(pai, 14), _px(pai, 10)))
        self.columnconfigure(1, weight=1)
        icone(self, nome_icone, 13, cor_icone, preenche).grid(
            row=0, column=0, sticky="n", padx=(0, _px(pai, 10)),
            pady=(_px(pai, 1), 0))
        conteudo = (f"{titulo}  " if titulo else "") + texto
        self.rotulo = tk.Label(self, text=conteudo, bg=preenche, fg=cor_texto,
                               font=(ui_tema.FONTE, 9), justify="left",
                               anchor="w", borderwidth=0)
        self.rotulo.grid(row=0, column=1, sticky="we")
        self.bind("<Configure>", lambda e: self.rotulo.configure(
            wraplength=max(200, e.width - _px(pai, 90))), add="+")
        if fechavel:
            fechar = icone(self, "fechar", 9, C["texto_suave"], preenche,
                           cursor="hand2")
            fechar.grid(row=0, column=2, sticky="n", padx=(_px(pai, 10), 0),
                        pady=(_px(pai, 2), 0))

            def fechar_banner(_e=None):
                self.grid_remove() if self.winfo_manager() == "grid" \
                    else self.pack_forget()
                if ao_fechar:
                    ao_fechar()
            fechar.bind("<Button-1>", fechar_banner)

    def texto(self, texto):
        self.rotulo.configure(text=texto)
