# src/ui_tema.py
"""
Tokens e estilos do visual do MarketplaceBot (set/2026).

Identidade: lateral escura, conteúdo claro, roxo como cor principal, azul
de apoio, verde/âmbar/vermelho só para estado. Toda cor, fonte, espaço e
raio sai daqui — telas e componentes (ui_componentes.py) não inventam cor.

Base técnica: tema Sun Valley (sv-ttk) por baixo, para barra de rolagem e
lista suspensa; por cima, estilos próprios cujas bordas arredondadas são
imagens geradas em código (ui_imagens.py). Três pegadinhas do Tk:
- elemento de imagem do ttk mistura a transparência com o cinza do sistema,
  então cada imagem ttk é "assada" sobre a cor de quem está atrás (por isso
  existem Fantasma e FantasmaCartao, um para o fundo e outro para o cartão);
- `ttk.Frame` ignora `padding` do estilo: o respiro vai no próprio widget;
- `preparar_dpi()` roda antes da primeira janela, e todo tamanho em pixel
  passa por `px()`.
"""
import ctypes
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

try:
    import sv_ttk
except ImportError:          # sem o tema, as telas abrem com o ttk padrão
    sv_ttk = None

import ui_imagens
from paths import get_resource_dir

CORES = {
    # identidade
    "primaria": "#7c3aed",
    "primaria_hover": "#6d28d9",
    "primaria_pressao": "#5b21b6",
    "primaria_suave": "#f5f3ff",
    "primaria_borda": "#ddd6fe",
    "primaria_texto": "#5b21b6",
    "secundaria": "#3b82f6",
    "sucesso": "#10b981",
    "aviso": "#f59e0b",
    "erro": "#ef4444",
    # texto de estado sobre branco (contraste de leitura)
    "sucesso_texto": "#047857",
    "aviso_texto": "#b45309",
    "erro_texto": "#b91c1c",
    "info_texto": "#1d4ed8",
    # superfícies
    "fundo": "#f8fafc",
    "cartao": "#ffffff",
    "borda": "#e5e7eb",
    "borda_campo": "#cbd5e1",
    "borda_forte": "#94a3b8",
    "hover": "#f1f5f9",
    "texto": "#0f172a",
    "texto_suave": "#64748b",
    "placeholder": "#94a3b8",
    "inativo_fundo": "#f1f5f9",
    "inativo_texto": "#94a3b8",
    "info_fundo": "#eff6ff",
    # lateral
    "lateral": "#0f172a",
    "lateral_hover": "#1e293b",
    "lateral_texto": "#cbd5e1",
    "lateral_suave": "#64748b",
}
# nomes antigos, ainda usados pelo tutorial e por telas antigas
CORES.update({
    "destaque": CORES["primaria"], "titulo": CORES["texto"],
    "suave": CORES["texto_suave"], "ok": CORES["sucesso_texto"],
    "perigo": CORES["erro_texto"], "neutro": CORES["texto_suave"],
    "log_fundo": CORES["fundo"], "log_texto": CORES["texto"],
})

# tipos de selo: (fundo, texto)
SELOS = {
    "sucesso": ("#ecfdf5", "#047857"),
    "info": ("#eff6ff", "#1d4ed8"),
    "aviso": ("#fffbeb", "#b45309"),
    "erro": ("#fef2f2", "#b91c1c"),
    "neutro": ("#f1f5f9", "#475569"),
    "primaria": ("#f5f3ff", "#6d28d9"),
}
SELOS.update({"Pago": SELOS["aviso"], "Breve": SELOS["neutro"],
              "Info": SELOS["info"]})

ESPACO = {"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 32}
RAIO = {"p": 6, "m": 8, "g": 12}

FONTE = "Segoe UI"
FONTE_FORTE = "Segoe UI Semibold"
FONTE_MONO = "Consolas"
FONTE_ICONES = "Segoe MDL2 Assets"

# glifos da fonte de ícones do Windows (mesmo traço em todos)
ICONES = {
    "inicio": "", "compra": "", "venda": "",
    "salvos": "", "historico": "", "config": "",
    "ajuda": "", "voltar": "", "seta": "",
    "copiar": "", "lixo": "", "busca": "",
    "filtro": "", "lampada": "", "local": "",
    "mensagem": "", "carro": "", "globo": "",
    "aviso": "", "ok": "", "info": "", "fechar": "",
    "mais": "", "conta": "", "banco": "",
    "escudo": "", "sair": "", "lista": "",
    "enviar": "", "loja": "", "play": "", "parar": "",
}


# ---------------------------------------------------------------- escala
def preparar_dpi():
    """Texto nítido em monitor com escala (125%, 150%…).

    Tem de rodar ANTES da primeira janela. "System aware" (1) e não "per
    monitor" (2): o Tk 8.6 não se redesenha ao trocar de monitor.
    """
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def escala(janela):
    """Fator da escala do monitor (1.0 = 100%)."""
    try:
        return max(1.0, janela.winfo_fpixels("1i") / 96.0)
    except Exception:
        return 1.0


def px(janela, valor):
    """Converte um tamanho pensado em 100% para pixels desta tela."""
    return int(round(valor * escala(janela)))


def geometria(janela, largura, altura, minimo=None, centralizar=False):
    """Tamanho da janela pela escala do monitor, sem passar da tela."""
    f = escala(janela)
    largura_max = janela.winfo_screenwidth() - px(janela, 40)
    alto_max = janela.winfo_screenheight() - px(janela, 80)
    w, h = min(int(largura * f), largura_max), min(int(altura * f), alto_max)
    if centralizar:
        x = max(0, (janela.winfo_screenwidth() - w) // 2)
        y = max(0, (janela.winfo_screenheight() - h) // 2 - px(janela, 20))
        janela.geometry(f"{w}x{h}+{x}+{y}")
    else:
        janela.geometry(f"{w}x{h}")
    if minimo:
        janela.minsize(min(int(minimo[0] * f), largura_max),
                       min(int(minimo[1] * f), alto_max))


def icone(janela):
    """O ícone do app no lugar da pena do Tk."""
    try:
        janela.iconbitmap(str(get_resource_dir() / "assets" / "icon.ico"))
    except Exception:
        pass


def _fonte_existe(janela, familia):
    try:
        return familia in tkfont.families(janela)
    except Exception:
        return False


# ---------------------------------------------------------------- imagens
def guardar(janela, imagem):
    """PhotoImage sem referência some da tela: a raiz guarda todas."""
    raiz = janela.winfo_toplevel()
    if not hasattr(raiz, "_ui_imagens"):
        raiz._ui_imagens = []
    raiz._ui_imagens.append(imagem)
    return imagem


def _ret(janela, tamanho, raio, preenchimento, **kw):
    """Imagem de 9 fatias para elemento ttk. `tamanho` = lado ou (l, a).

    O MEIO da imagem precisa ser grande: o ttk preenche o miolo do widget
    REPETINDO o pedaço do meio, e com 8 px de meio um cartão de 700×380
    virava milhares de cópias por pintura — a página de Compra levava ~11 s
    na 1ª visita e ~1 s a cada volta. Com meio maior que o widget comum,
    doze cartões pintam em ~25 ms.
    """
    largura, altura = tamanho if isinstance(tamanho, tuple) else (tamanho, tamanho)
    return guardar(janela, ui_imagens.retangulo(janela, largura, altura, raio,
                                                preenchimento, **kw))


# (preenchimento, borda, preenchimento hover, borda hover, pressão,
#  texto, fundo onde fica)
_BOTOES = {
    "Primario": dict(fill=CORES["primaria"], hover=CORES["primaria_hover"],
                     pressao=CORES["primaria_pressao"], texto="#ffffff",
                     inativo_fill="#c4b5fd", inativo_texto="#f5f3ff",
                     fundo=CORES["cartao"]),
    "Secundario": dict(fill="#ffffff", borda=CORES["borda_campo"],
                       hover="#f8fafc", hover_borda=CORES["borda_forte"],
                       pressao="#f1f5f9", texto=CORES["texto"],
                       inativo_fill="#f8fafc", inativo_borda="#e2e8f0",
                       inativo_texto=CORES["inativo_texto"],
                       fundo=CORES["cartao"]),
    "Destaque": dict(fill=CORES["primaria_suave"], borda="#c4b5fd",
                     hover="#ede9fe", hover_borda=CORES["primaria"],
                     pressao="#ddd6fe", texto=CORES["primaria_texto"],
                     inativo_fill="#f8fafc", inativo_borda="#e2e8f0",
                     inativo_texto=CORES["inativo_texto"],
                     fundo=CORES["cartao"]),
    "Perigo": dict(fill="#ffffff", borda="#fca5a5", hover="#fef2f2",
                   hover_borda="#f87171", pressao="#fee2e2",
                   texto=CORES["erro_texto"], inativo_fill="#ffffff",
                   inativo_borda="#fee2e2", inativo_texto="#fca5a5",
                   fundo=CORES["cartao"]),
    "PerigoCheio": dict(fill="#dc2626", hover="#b91c1c", pressao="#991b1b",
                        texto="#ffffff", inativo_fill="#fecaca",
                        inativo_texto="#ffffff", fundo=CORES["cartao"]),
    "Fantasma": dict(fill=CORES["fundo"], hover="#eef2f6", pressao="#e2e8f0",
                     texto=CORES["texto_suave"], inativo_fill=CORES["fundo"],
                     inativo_texto=CORES["inativo_texto"],
                     fundo=CORES["fundo"]),
    "FantasmaCartao": dict(fill=CORES["cartao"], hover="#f1f5f9",
                           pressao="#e2e8f0", texto=CORES["texto_suave"],
                           inativo_fill=CORES["cartao"],
                           inativo_texto=CORES["inativo_texto"],
                           fundo=CORES["cartao"]),
    "IconePerigo": dict(fill=CORES["cartao"], hover="#fef2f2",
                        pressao="#fee2e2", texto="#dc2626",
                        inativo_fill=CORES["cartao"],
                        inativo_texto=CORES["inativo_texto"],
                        fundo=CORES["cartao"]),
    "Lateral": dict(fill=CORES["lateral"], borda="#334155",
                    hover=CORES["lateral_hover"], hover_borda="#475569",
                    pressao="#334155", texto=CORES["lateral_texto"],
                    inativo_fill=CORES["lateral"],
                    inativo_texto=CORES["lateral_suave"],
                    fundo=CORES["lateral"]),
}


def _estilos_botoes(janela, estilo, forte):
    s = escala(janela)
    raio, anel = round(RAIO["m"] * s), max(2, round(2 * s))
    lado = (round(320 * s), round(72 * s))     # meio grande: ver _ret
    borda_9 = raio + anel + 2
    for nome, b in _BOTOES.items():
        def img(fill, borda=None, com_anel=False):
            return _ret(janela, lado, raio, fill, borda=borda, fundo=b["fundo"],
                        espessura=max(1.0, round(s)), espessura_anel=anel,
                        anel=CORES["primaria_borda"] if com_anel else None)
        normal = img(b["fill"], b.get("borda"))
        estados = [
            ("disabled", img(b["inativo_fill"], b.get("inativo_borda"))),
            ("pressed", img(b["pressao"], b.get("hover_borda", b.get("borda")))),
            ("active", img(b["hover"], b.get("hover_borda", b.get("borda")))),
            ("focus", img(b["fill"], b.get("borda"), com_anel=True)),
        ]
        elemento = f"{nome}.botao"
        # sem `padding=`, o ttk usa o `border` também como respiro interno
        # e o botão fica com o dobro da altura
        # width/height: sem eles o elemento pede o tamanho da IMAGEM (que é
        # grande de propósito, ver _ret) e todo botão nascia com 320×72
        estilo.element_create(elemento, "image", normal, *estados,
                              border=borda_9, padding=0, sticky="nsew",
                              width=2 * borda_9, height=2 * borda_9)
        estilo.layout(f"{nome}.TButton", [(elemento, {"sticky": "nsew", "children": [
            ("Button.padding", {"sticky": "nsew", "children": [
                ("Button.label", {"sticky": "nsew"})]})]})])
        pequeno = nome in ("IconePerigo",)
        estilo.configure(
            f"{nome}.TButton", foreground=b["texto"], background=b["fundo"],
            anchor="center", font=(forte if nome in ("Primario", "PerigoCheio")
                                   else FONTE, 10),
            padding=(px(janela, 9), px(janela, 6)) if pequeno
            else (px(janela, 16), px(janela, 8)))
        estilo.map(f"{nome}.TButton", foreground=[("disabled", b["inativo_texto"])])


def _estilos_campos(janela, estilo):
    """Entry e Combobox: branco, borda visível, foco roxo com anel claro."""
    s = escala(janela)
    raio, anel = round(7 * s), max(2, round(3 * s))
    lado = (round(960 * s), round(80 * s))     # meio grande: ver _ret
    esp = max(1.0, round(s))

    def img(borda, fill="#ffffff", espessura=esp, com_anel=None):
        return _ret(janela, lado, raio, fill, borda=borda, fundo=CORES["cartao"],
                    espessura=espessura, espessura_anel=anel, anel=com_anel)

    repouso = img(CORES["borda_campo"])
    hover = img(CORES["borda_forte"])
    foco = img(CORES["primaria"], espessura=esp * 1.5,
               com_anel=CORES["primaria_borda"])
    inativo = img("#e2e8f0", fill=CORES["inativo_fundo"])
    invalido = img(CORES["erro"], com_anel="#fee2e2")
    borda_9 = raio + anel + 2
    estilo.element_create(
        "Campo.field", "image", repouso,
        ("disabled", inativo), ("invalid", invalido),
        ("focus", foco), ("readonly pressed", foco), ("hover", hover),
        border=borda_9, padding=0, sticky="nsew",
        width=2 * borda_9, height=2 * borda_9)
    estilo.layout("TEntry", [("Campo.field", {"sticky": "nsew", "children": [
        ("Entry.padding", {"sticky": "nsew", "children": [
            ("Entry.textarea", {"sticky": "nsew"})]})]})])
    estilo.layout("TCombobox", [("Campo.field", {"sticky": "nsew", "children": [
        ("Combobox.arrow", {"side": "right", "sticky": "ns"}),
        ("Combobox.padding", {"sticky": "nsew", "children": [
            ("Combobox.textarea", {"sticky": "nsew"})]})]})])
    folga_x, folga_y = anel + px(janela, 10), anel + px(janela, 8)
    for classe in ("TEntry", "TCombobox"):
        estilo.configure(classe, padding=(folga_x, folga_y, folga_x, folga_y),
                         foreground=CORES["texto"], fieldbackground="#ffffff",
                         background=CORES["cartao"], font=(FONTE, 10),
                         selectbackground=CORES["primaria_borda"],
                         selectforeground=CORES["texto"])
        estilo.map(classe, foreground=[("disabled", CORES["inativo_texto"])],
                   selectbackground=[("readonly", "#ffffff")],
                   selectforeground=[("readonly", CORES["texto"])])
    janela.option_add("*TCombobox*Listbox.background", "#ffffff")
    janela.option_add("*TCombobox*Listbox.foreground", CORES["texto"])
    janela.option_add("*TCombobox*Listbox.selectBackground",
                      CORES["primaria_suave"])
    janela.option_add("*TCombobox*Listbox.selectForeground",
                      CORES["primaria_texto"])
    janela.option_add("*TCombobox*Listbox.font", (FONTE, 10))


def _estilos_superficies(janela, estilo, forte):
    s = escala(janela)
    raio, sombra = round(RAIO["g"] * s), max(2, round(3 * s))
    cartao = _ret(janela, (round(1200 * s), round(720 * s)), raio, CORES["cartao"],
                  borda=CORES["borda"], espessura=max(1.0, round(s)),
                  fundo=CORES["fundo"], sombra=sombra, forca_sombra=0.05)
    estilo.element_create("Cartao.fundo", "image", cartao,
                          border=raio + sombra + 3, padding=0, sticky="nsew",
                          width=2 * (raio + sombra + 3),
                          height=2 * (raio + sombra + 3))
    estilo.layout("Cartao.TFrame", [("Cartao.fundo", {"sticky": "nsew"})])
    estilo.configure("Superficie.TFrame", background=CORES["cartao"])
    estilo.configure("Pagina.TFrame", background=CORES["fundo"])
    estilo.configure("TFrame", background=CORES["fundo"])

    # o TLabel do Sun Valley não tem elemento de fundo: o `background` do
    # estilo não pintava nada e o rótulo mostrava o cinza da página dentro
    # do cartão branco (faixa cinza atrás dos textos de ajuda)
    estilo.layout("TLabel", [("Label.border", {"sticky": "nswe", "children": [
        ("Label.padding", {"sticky": "nswe", "children": [
            ("Label.label", {"sticky": "nswe"})]})]})])

    rotulos = {
        # na página (fundo claro)
        "Titulo": dict(font=(forte, 20), foreground=CORES["texto"],
                       background=CORES["fundo"]),
        "Subtitulo": dict(font=(FONTE, 10), foreground=CORES["texto_suave"],
                          background=CORES["fundo"]),
        "Suave": dict(font=(FONTE, 9), foreground=CORES["texto_suave"],
                      background=CORES["fundo"]),
        "Grupo": dict(font=(forte, 12), foreground=CORES["texto"],
                      background=CORES["fundo"]),
        # dentro do cartão (branco)
        "Secao": dict(font=(forte, 12), foreground=CORES["texto"],
                      background=CORES["cartao"]),
        "Rotulo": dict(font=(forte, 10), foreground=CORES["texto"],
                       background=CORES["cartao"]),
        "Texto": dict(font=(FONTE, 10), foreground=CORES["texto"],
                      background=CORES["cartao"]),
        "Ajuda": dict(font=(FONTE, 9), foreground=CORES["texto_suave"],
                      background=CORES["cartao"]),
        "Numero": dict(font=(forte, 12), foreground=CORES["primaria"],
                       background=CORES["cartao"]),
        "Aviso": dict(foreground=CORES["aviso_texto"], background=CORES["cartao"]),
        "Ok": dict(foreground=CORES["sucesso_texto"], background=CORES["cartao"]),
    }
    for nome, opcoes in rotulos.items():
        estilo.configure(f"{nome}.TLabel", **opcoes)


def aplicar_tema(janela):
    """Liga o tema e os estilos do bot. Chamar logo depois de criar a Tk."""
    estilo = ttk.Style(janela)

    def cores_do_bot():
        estilo.configure(".", font=(FONTE, 10), background=CORES["fundo"],
                         foreground=CORES["texto"])

    if sv_ttk is not None:
        sv_ttk.set_theme("light", janela)
        # O sv-ttk liga `configure_colors` ao <<ThemeChanged>>, que o Tk
        # manda a CADA estilo/elemento criado (as páginas criam os delas ao
        # abrir). Cada vez ele volta o estilo "." para #fafafa e chama
        # tk_setPalette, cujo RecolorTree percorre TODOS os widgets e pinta
        # #fafafa/#1c1c1c em toda opção de cor ainda vazia — todo ttk.Label
        # já montado perdia o estilo (faixa cinza e texto preto nos textos
        # de ajuda). Agora a paleta do sv-ttk roda UMA vez, aqui, chamada
        # direto, antes de existir qualquer rótulo; nos eventos seguintes só
        # as cores do bot são reaplicadas. (Esperar o evento com update() não
        # serve: a janela ainda não existe na tela e o evento não chega.)
        nome = janela.register(cores_do_bot)
        janela.tk.eval(
            'if {[info procs _sv_configure_colors] eq ""} {'
            ' rename configure_colors _sv_configure_colors }; '
            'proc configure_colors {} {'
            ' if {![info exists ::mbot_paleta_aplicada]} {'
            ' set ::mbot_paleta_aplicada 1; _sv_configure_colors };'
            f' {nome} }}')
        janela.tk.call("configure_colors")
    janela.configure(bg=CORES["fundo"])
    icone(janela)

    forte = FONTE_FORTE if _fonte_existe(janela, FONTE_FORTE) else FONTE
    global FONTE_ICONES
    if _fonte_existe(janela, "Segoe Fluent Icons"):
        FONTE_ICONES = "Segoe Fluent Icons"
    cores_do_bot()
    try:
        _estilos_superficies(janela, estilo, forte)
        _estilos_campos(janela, estilo)
        _estilos_botoes(janela, estilo, forte)
    except tk.TclError:
        # elemento já criado nesta raiz (aplicar_tema chamado de novo)
        pass
    estilo.configure("Treeview", rowheight=px(janela, 30))
    return estilo


# ----------------------------------------------------- compatibilidade
BOTOES = {
    "destaque": "Primario.TButton", "ok": "Primario.TButton",
    "primario": "Primario.TButton", "perigo": "Perigo.TButton",
    "neutro": "Secundario.TButton", "secundario": "Secundario.TButton",
    "fantasma": "Fantasma.TButton", "fantasma_cartao": "FantasmaCartao.TButton",
}


def botao(pai, texto, comando, cor="neutro", largura=None):
    """Botão do tema. `cor`: primario/destaque/ok, secundario/neutro,
    perigo, fantasma (sobre o fundo) ou fantasma_cartao (sobre cartão)."""
    return ttk.Button(pai, text=texto, command=comando,
                      style=BOTOES.get(cor, "Secundario.TButton"),
                      cursor="hand2")


def quebra_automatica(rotulo, margem=48):
    """O texto quebra pela largura do pai (e não num valor fixo, que ficava
    errado quando a escala do monitor muda o tamanho da fonte)."""
    pai = rotulo.master

    def ajustar(evento):
        rotulo.configure(wraplength=max(160, evento.width - px(pai, margem)))

    pai.bind("<Configure>", ajustar, add="+")
    return rotulo


class _Dica(tk.Label):
    """Faixa informativa que some sozinha quando fica sem texto."""

    def configure(self, cnf=None, **kw):
        if "text" in kw:
            if str(kw["text"]).strip():
                kw.update(bg=CORES["info_fundo"], font=(FONTE, 9),
                          padx=px(self.master, 12), pady=px(self.master, 10))
            else:
                kw.update(bg=CORES["cartao"], font=(FONTE, 1), padx=0, pady=0)
        return super().configure(cnf, **kw)

    config = configure


def dica(pai, texto="", largura=None):
    """Faixa azul-clara de informação dentro de um cartão."""
    rotulo = _Dica(pai, fg="#1e3a8a", justify="left", anchor="w",
                   bg=CORES["cartao"], borderwidth=0)
    rotulo.configure(text=texto)
    return quebra_automatica(rotulo, margem=40)


def texto_suave(pai, texto, **kw):
    """Texto auxiliar (cinza, menor) que quebra linha pela largura do pai."""
    kw.setdefault("justify", "left")
    kw.setdefault("style", "Ajuda.TLabel")
    return quebra_automatica(ttk.Label(pai, text=texto, **kw))


_CACHE_SELOS = {}


def selo(pai, texto, tipo="neutro", fundo=None, ponto=False):
    """Selo em pílula: tipo sucesso, info, aviso, erro, neutro ou primaria.
    Com `ponto`, leva a bolinha colorida antes do texto (status)."""
    cor_fundo, cor_texto = SELOS.get(tipo, SELOS["neutro"])
    fundo = fundo or CORES["cartao"]
    rotulo = ("●  " if ponto else "") + texto
    fonte = tkfont.Font(root=pai, family=FONTE_FORTE, size=8)
    largura = fonte.measure(rotulo) + px(pai, 20)
    altura = fonte.metrics("linespace") + px(pai, 6)
    # pílula com cantos transparentes: o tk.Label mistura com o próprio bg,
    # então o mesmo selo serve em linha normal, com hover ou marcada
    chave = (str(pai.winfo_toplevel()), largura, altura, cor_fundo)
    if chave not in _CACHE_SELOS:
        _CACHE_SELOS[chave] = guardar(pai, ui_imagens.retangulo(
            pai, largura, altura, altura / 2, cor_fundo))
    return tk.Label(pai, image=_CACHE_SELOS[chave], text=rotulo, compound="center",
                    fg=cor_texto, bg=fundo, font=(FONTE_FORTE, 8), borderwidth=0)


def campo_texto(pai, altura=3):
    """Caixa de várias linhas com o mesmo contorno dos campos do tema.

    Devolve o `tk.Text`; quem monta a tela posiciona `texto.moldura`.
    """
    moldura = tk.Frame(pai, bg=CORES["borda_campo"], padx=1, pady=1)
    texto = tk.Text(moldura, height=altura, wrap="word", font=(FONTE, 10),
                    bg="#ffffff", fg=CORES["texto"],
                    insertbackground=CORES["texto"], relief="flat",
                    borderwidth=0, highlightthickness=0,
                    selectbackground=CORES["primaria_borda"],
                    selectforeground=CORES["texto"],
                    padx=px(pai, 12), pady=px(pai, 10), undo=True)
    texto.pack(fill="both", expand=True)
    texto.bind("<FocusIn>", lambda _e: moldura.configure(
        bg=CORES["primaria"], padx=2, pady=2), add="+")
    texto.bind("<FocusOut>", lambda _e: moldura.configure(
        bg=CORES["borda_campo"], padx=1, pady=1), add="+")
    texto.moldura = moldura
    return texto
