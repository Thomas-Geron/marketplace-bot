# src/ui_tema.py
"""
Aparência comum das telas do bot — tema Sun Valley (visual do Windows 11).

Antes as telas usavam o tema "clam" do Tk, botões `tk.Button` pintados à
mão e nenhuma consciência de DPI: em monitor com escala o Windows esticava
a janela e a fonte saía borrada — a cara de programa de Windows XP. Agora:

- `preparar_dpi()` roda uma vez, antes de qualquer janela (main.py);
- `aplicar_tema()` liga o Sun Valley (sv-ttk) e os estilos do bot por cima;
- `geometria()` dimensiona a janela pela escala do monitor;
- `secao()`, `botao()`, `dica()`, `selo()`, `campo_texto()` e `caixa_log()`
  são os blocos das telas — cor e fonte ficam só aqui.

Duas pegadinhas do Tk que custaram uma rodada de capturas:
- `place()` conta a posição a partir de DENTRO do padding do frame — por
  isso o título da seção vai com deslocamento negativo;
- o `ttk.Label` do Sun Valley não pinta fundo — faixa de dica e selo são
  `tk.Label`, que pinta.

Sem o sv-ttk instalado a tela continua abrindo, com o ttk padrão.
"""
import ctypes
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

try:
    import sv_ttk
except ImportError:          # sem o tema, as telas abrem com o ttk padrão
    sv_ttk = None

from paths import get_resource_dir

CORES = {
    "fundo": "#fafafa",       # o fundo do Sun Valley claro (e dos cartões)
    "cartao": "#ffffff",
    "titulo": "#1c1c1c",
    "texto": "#1c1c1c",
    "suave": "#616161",
    "destaque": "#005fb8",
    "aviso": "#8a5300",
    "ok": "#0f7b0f",
    "perigo": "#c42b1c",
    "neutro": "#5f6b7a",
    "borda": "#e3e3e3",
    "info_fundo": "#e8f1fb",
    "info_texto": "#0b3d6e",
    "log_fundo": "#1f1f23",
    "log_texto": "#dcdcdc",
}

SELOS = {
    "Pago": ("#fff4ce", "#7a4b00"),
    "Breve": ("#ececec", "#5f5f5f"),
    "Info": ("#e6f0fb", "#0b3d6e"),
}

FONTE = "Segoe UI"
FONTE_FORTE = "Segoe UI Semibold"
FONTE_MONO = "Consolas"


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


def geometria(janela, largura, altura, minimo=None):
    """Tamanho da janela pela escala do monitor, sem passar da tela."""
    f = escala(janela)
    alto_max = janela.winfo_screenheight() - px(janela, 80)
    janela.geometry(f"{int(largura * f)}x{min(int(altura * f), alto_max)}")
    if minimo:
        janela.minsize(int(minimo[0] * f), min(int(minimo[1] * f), alto_max))


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


def aplicar_tema(janela):
    """Liga o tema e os estilos do bot. Chamar logo depois de criar a Tk."""
    if sv_ttk is not None:
        sv_ttk.set_theme("light", janela)
    estilo = ttk.Style(janela)

    janela.configure(bg=CORES["fundo"])
    icone(janela)

    forte = FONTE_FORTE if _fonte_existe(janela, FONTE_FORTE) else FONTE
    estilo.configure(".", font=(FONTE, 10))
    estilo.configure("Titulo.TLabel", font=(forte, 18),
                     foreground=CORES["titulo"])
    estilo.configure("Subtitulo.TLabel", font=(FONTE, 10),
                     foreground=CORES["suave"])
    estilo.configure("Secao.TLabel", font=(forte, 11),
                     foreground=CORES["titulo"])
    estilo.configure("Suave.TLabel", font=(FONTE, 9),
                     foreground=CORES["suave"])
    estilo.configure("Aviso.TLabel", foreground=CORES["aviso"])
    estilo.configure("Ok.TLabel", foreground=CORES["ok"])

    # ação destrutiva: botão comum com texto vermelho (padrão do Windows 11,
    # que reserva a cor de destaque para a ação principal)
    estilo.configure("Perigo.TButton", foreground=CORES["perigo"])

    # a altura de linha da tabela é em pixels: acompanha a escala
    estilo.configure("Treeview", rowheight=px(janela, 30))
    return estilo


def secao(pai, titulo):
    """Cartão com título, para agrupar campos do mesmo assunto.

    O título fica na faixa reservada pelo padding de cima e não ocupa
    linha da grade: quem usa continua pondo os campos a partir de row=0.
    """
    lado, topo = px(pai, 16), px(pai, 46)
    cartao = ttk.Frame(pai, style="Card.TFrame",
                       padding=(lado, topo, lado, px(pai, 16)))
    titulo_lbl = ttk.Label(cartao, text=titulo, style="Secao.TLabel")
    # place() conta a partir de DENTRO do padding: volta para a faixa do topo
    titulo_lbl.place(x=0, y=px(pai, 14) - topo)
    return cartao


BOTOES = {
    "destaque": "Accent.TButton",
    "ok": "Accent.TButton",
    "perigo": "Perigo.TButton",
    "neutro": "TButton",
}


def botao(pai, texto, comando, cor="neutro", largura=None):
    """Botão do tema. `cor`: destaque/ok (ação principal), perigo, neutro.

    `largura` fica por compatibilidade: o texto e o padding do tema já dão
    o tamanho certo, e largura fixa em caracteres deixava botões gigantes.
    """
    return ttk.Button(pai, text=texto, command=comando,
                      style=BOTOES.get(cor, "TButton"), cursor="hand2")


def quebra_automatica(rotulo, margem=48):
    """O texto quebra pela largura do pai (e não num valor fixo, que ficava
    errado quando a escala do monitor muda o tamanho da fonte).

    `margem` desconta o padding do cartão e o do próprio rótulo.
    """
    pai = rotulo.master

    def ajustar(evento):
        rotulo.configure(wraplength=max(160, evento.width - px(pai, margem)))

    pai.bind("<Configure>", ajustar, add="+")
    return rotulo


class _Dica(tk.Label):
    """Faixa informativa (o "InfoBar" do Windows 11) que some sozinha
    quando fica sem texto."""

    def configure(self, cnf=None, **kw):
        if "text" in kw:
            if str(kw["text"]).strip():
                kw.update(bg=CORES["info_fundo"], font=(FONTE, 9),
                          padx=px(self.master, 12), pady=px(self.master, 9))
            else:
                kw.update(bg=CORES["fundo"], font=(FONTE, 1), padx=0, pady=0)
        return super().configure(cnf, **kw)

    config = configure


def dica(pai, texto="", largura=None):
    """Faixa azul-clara de informação (o que o site aceita, avisos)."""
    rotulo = _Dica(pai, fg=CORES["info_texto"], justify="left", anchor="w",
                   bg=CORES["fundo"], borderwidth=0)
    rotulo.configure(text=texto)
    return quebra_automatica(rotulo, margem=88)


def texto_suave(pai, texto, **kw):
    """Texto secundário que quebra linha pela largura do pai."""
    kw.setdefault("justify", "left")
    return quebra_automatica(ttk.Label(pai, text=texto, style="Suave.TLabel",
                                       **kw))


def selo(pai, texto, tipo="Info"):
    """Etiqueta pequena colorida: tipo Pago, Breve ou Info."""
    fundo, cor = SELOS.get(tipo, SELOS["Info"])
    return tk.Label(pai, text=texto, bg=fundo, fg=cor, font=(FONTE, 8),
                    padx=px(pai, 8), pady=px(pai, 1), borderwidth=0)


def campo_texto(pai, altura=3):
    """Caixa de texto de várias linhas no mesmo desenho dos campos do tema."""
    return tk.Text(pai, height=altura, wrap="word", font=(FONTE, 10),
                   bg=CORES["cartao"], fg=CORES["texto"],
                   insertbackground=CORES["texto"], relief="flat",
                   borderwidth=0, highlightthickness=1,
                   highlightbackground="#d1d1d1",
                   highlightcolor=CORES["destaque"],
                   padx=px(pai, 10), pady=px(pai, 8))


def caixa_log(pai, altura=10):
    """Console escuro do log, com respiro nas bordas."""
    return tk.Text(pai, height=altura, bg=CORES["log_fundo"],
                   fg=CORES["log_texto"], insertbackground=CORES["log_texto"],
                   relief="flat", borderwidth=0, highlightthickness=0,
                   font=(FONTE_MONO, 9), wrap="word",
                   padx=px(pai, 12), pady=px(pai, 10),
                   selectbackground="#264f78")
