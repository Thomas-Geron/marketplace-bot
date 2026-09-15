# src/tutorial.py
"""
Passo a passo guiado das telas do bot.

Na primeira vez que cada tela abre, o tutorial mostra um passo por vez: o
resto da janela escurece, o que o passo explica fica aceso com um contorno
azul e um cartão ao lado diz para que serve e como preencher. "Concluir"
ou "Pular" gravam em `tutorial.json` (pasta de dados do usuário) e o
tutorial não volta sozinho; o botão "?" do topo de cada tela abre de novo.

O Tk não tem camada semitransparente por cima dos próprios widgets, então
o destaque é feito com janelas sem borda sobre a tela:
- quatro faixas escuras (alpha) em volta do "furo" — o furo é a união dos
  alvos do passo, então o que está aceso continua visível e clicável;
- uma janela com cor-chave transparente (`-transparentcolor`) só com os
  contornos azuis — onde ela é transparente, o clique atravessa;
- o cartão do passo.
As posições são conferidas a cada 150 ms enquanto o tutorial está aberto:
mover, redimensionar ou rolar a janela leva o destaque junto.
"""
import json
import tkinter as tk
from tkinter import ttk

import ui_tema
from paths import get_data_dir

COR_CHAVE = "#ff00fe"      # cor que a janela dos contornos torna invisível
ESCURIDAO = 0.55
INTERVALO_MS = 150


# ------------------------------------------------------------ memória
def _arquivo():
    return get_data_dir() / "tutorial.json"


def _ler():
    try:
        return json.loads(_arquivo().read_text(encoding="utf-8"))
    except Exception:
        return {}


def ja_visto(chave):
    """True se o usuário já concluiu (ou pulou) o tutorial desta tela."""
    return bool(_ler().get(chave))


def marcar_visto(chave):
    dados = _ler()
    dados[chave] = True
    try:
        _arquivo().parent.mkdir(parents=True, exist_ok=True)
        _arquivo().write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    except Exception:
        pass   # sem conseguir gravar, o pior caso é o tutorial reaparecer


# -------------------------------------------------------------- passos
# (o botão "? Ajuda" que reabre o passo a passo fica no cabeçalho de cada
# página: ui_componentes.CabecalhoPagina)
class Passo:
    """Um passo: título, explicação e os widgets que ficam acesos.

    `alvos` é uma função, porque na montagem da tela os widgets podem ainda
    não existir ou estar escondidos. Passo `opcional` some quando nenhum
    alvo está visível (ex.: dados de contato só aparecem com certos sites).
    """

    def __init__(self, titulo, texto, alvos=None, opcional=False):
        self.titulo = titulo
        self.texto = texto
        self.alvos = alvos or (lambda: [])
        self.opcional = opcional


def _visivel(widget):
    try:
        return bool(widget is not None and widget.winfo_exists()
                    and widget.winfo_ismapped())
    except tk.TclError:
        return False


class Tutorial:
    def __init__(self, janela, chave, passos, rolavel=None):
        self.janela = janela
        self.chave = chave
        self.passos = passos
        # frame interno da área rolável: o tutorial rola até o alvo do passo
        self.rolavel = rolavel
        self.indice = 0
        self.ativo = False
        self._faixas = []
        self._contornos = None
        self._tela_contornos = None
        self._cartao = None
        self._alvos = []
        self._assinatura = None
        self._vigia = None

    # ---------------------------------------------------------- ciclo
    def iniciar_se_primeira_vez(self, atraso=700):
        if not ja_visto(self.chave):
            self.janela.after(atraso, self.iniciar)

    def iniciar(self):
        if self.ativo or not self.janela.winfo_exists():
            return
        primeiro = self._valido(0, 1)
        if primeiro is None:
            return
        self.ativo = True
        self._montar()
        self.indice = primeiro
        self._mostrar()
        self._vigiar()

    def proximo(self, _evento=None):
        seguinte = self._valido(self.indice + 1, 1)
        if seguinte is None:
            self.encerrar()
        else:
            self.indice = seguinte
            self._mostrar()

    def anterior(self, _evento=None):
        antes = self._valido(self.indice - 1, -1)
        if antes is not None:
            self.indice = antes
            self._mostrar()

    def encerrar_sem_marcar(self):
        """Fecha as camadas sem gravar como visto (o usuário trocou de
        página no meio do passo a passo: ele volta na próxima visita)."""
        self.ativo = True
        self._fechar_camadas()

    def encerrar(self, _evento=None):
        """Concluir ou pular: fecha e não volta sozinho nas próximas vezes."""
        if not self.ativo:
            return
        self._fechar_camadas()
        marcar_visto(self.chave)

    def _fechar_camadas(self):
        if not self.ativo:
            return
        self.ativo = False
        if self._vigia is not None:
            try:
                self.janela.after_cancel(self._vigia)
            except Exception:
                pass
            self._vigia = None
        for janela in (*self._faixas, self._contornos, self._cartao):
            try:
                if janela is not None:
                    janela.destroy()
            except Exception:
                pass
        self._faixas, self._contornos, self._cartao = [], None, None
        try:
            self.janela.focus_force()
        except Exception:
            pass

    # ------------------------------------------------------ montagem
    def _nova_camada(self):
        camada = tk.Toplevel(self.janela)
        camada.withdraw()
        camada.overrideredirect(True)
        camada.transient(self.janela)
        return camada

    def _montar(self):
        px = lambda valor: ui_tema.px(self.janela, valor)  # noqa: E731

        for _ in range(4):
            faixa = self._nova_camada()
            faixa.configure(bg="#000000")
            faixa.attributes("-alpha", ESCURIDAO)
            self._faixas.append(faixa)

        self._contornos = self._nova_camada()
        self._contornos.configure(bg=COR_CHAVE)
        self._contornos.attributes("-transparentcolor", COR_CHAVE)
        self._tela_contornos = tk.Canvas(self._contornos, bg=COR_CHAVE,
                                         highlightthickness=0, borderwidth=0)
        self._tela_contornos.pack(fill="both", expand=True)

        self._cartao = self._nova_camada()
        self._cartao.configure(bg=ui_tema.CORES["borda_campo"])  # a borda
        moldura = tk.Frame(self._cartao, bg=ui_tema.CORES["cartao"])
        moldura.pack(fill="both", expand=True, padx=1, pady=1)
        tk.Frame(moldura, bg=ui_tema.CORES["primaria"], height=px(4)).pack(
            fill="x")
        corpo = ttk.Frame(moldura, style="Superficie.TFrame",
                          padding=(px(20), px(14), px(20), px(16)))
        corpo.pack(fill="both", expand=True)

        self._contador = ttk.Label(corpo, style="Ajuda.TLabel")
        self._contador.pack(anchor="w")
        self._titulo = ttk.Label(corpo, style="Secao.TLabel")
        self._titulo.pack(anchor="w", pady=(px(2), px(6)))
        self._texto = ttk.Label(corpo, wraplength=px(360), justify="left",
                                style="Texto.TLabel")
        self._texto.pack(anchor="w", fill="x")

        botoes = ttk.Frame(corpo, style="Superficie.TFrame")
        botoes.pack(fill="x", pady=(px(16), 0))
        ttk.Button(botoes, text="Pular tutorial", command=self.encerrar,
                   style="FantasmaCartao.TButton", cursor="hand2").pack(
            side="left")
        self._bt_proximo = ttk.Button(botoes, text="Próximo",
                                      style="Primario.TButton", cursor="hand2",
                                      command=self.proximo)
        self._bt_proximo.pack(side="right")
        self._bt_anterior = ttk.Button(botoes, text="Anterior",
                                       style="Secundario.TButton",
                                       cursor="hand2", command=self.anterior)
        self._bt_anterior.pack(side="right", padx=(0, px(8)))

        for tecla, acao in (("<Right>", self.proximo), ("<Return>", self.proximo),
                            ("<Left>", self.anterior), ("<Escape>", self.encerrar)):
            self._cartao.bind(tecla, acao)

    # -------------------------------------------------------- passos
    def _alvos_visiveis(self, passo):
        try:
            return [w for w in passo.alvos() if _visivel(w)]
        except Exception:
            return []

    def _e_valido(self, indice):
        passo = self.passos[indice]
        return not passo.opcional or bool(self._alvos_visiveis(passo))

    def _valido(self, inicio, direcao):
        indice = inicio
        while 0 <= indice < len(self.passos):
            if self._e_valido(indice):
                return indice
            indice += direcao
        return None

    def _mostrar(self):
        passo = self.passos[self.indice]
        self._alvos = self._alvos_visiveis(passo)
        if self._alvos:
            self._rolar_ate(self._alvos)
        self.janela.update_idletasks()

        validos = [i for i in range(len(self.passos)) if self._e_valido(i)]
        posicao = validos.index(self.indice) + 1 if self.indice in validos else 1
        self._contador.configure(text=f"Passo {posicao} de {len(validos)}")
        self._titulo.configure(text=passo.titulo)
        self._texto.configure(text=passo.texto)
        ultimo = self._valido(self.indice + 1, 1) is None
        self._bt_proximo.configure(text="Concluir" if ultimo else "Próximo")
        primeiro = self._valido(self.indice - 1, -1) is None
        self._bt_anterior.state(["disabled"] if primeiro else ["!disabled"])

        self._assinatura = None
        self._redesenhar()
        try:
            self._cartao.focus_force()
        except Exception:
            pass

    def _rolar_ate(self, alvos):
        """Rola a área da tela até o que o passo explica."""
        if self.rolavel is None or not isinstance(self.rolavel.master, tk.Canvas):
            return
        tela = self.rolavel.master
        self.janela.update_idletasks()
        total = max(1, self.rolavel.winfo_height())
        if total <= tela.winfo_height():
            return
        topo = min(w.winfo_rooty() for w in alvos) - self.rolavel.winfo_rooty()
        inicio = max(0, topo - ui_tema.px(self.janela, 90))
        tela.yview_moveto(min(1.0, inicio / total))

    # ------------------------------------------------------ desenho
    def _cliente(self):
        j = self.janela
        return j.winfo_rootx(), j.winfo_rooty(), j.winfo_width(), j.winfo_height()

    def _retangulos(self):
        rx, ry, largura, altura = self._cliente()
        folga = ui_tema.px(self.janela, 6)
        retangulos = []
        for w in self._alvos:
            if not _visivel(w):
                continue
            x0 = max(rx, w.winfo_rootx() - folga)
            y0 = max(ry, w.winfo_rooty() - folga)
            x1 = min(rx + largura, w.winfo_rootx() + w.winfo_width() + folga)
            y1 = min(ry + altura, w.winfo_rooty() + w.winfo_height() + folga)
            if x1 > x0 and y1 > y0:
                retangulos.append((x0, y0, x1, y1))
        return retangulos

    def _vigiar(self):
        """Refaz o destaque quando a janela mexe, muda de tamanho ou rola."""
        if not self.ativo:
            return
        try:
            if self.janela.state() == "iconic":
                # minimizada: as camadas somem e voltam no lugar ao restaurar
                for camada in (*self._faixas, self._contornos, self._cartao):
                    camada.withdraw()
                self._assinatura = None
            else:
                assinatura = (self._cliente(), tuple(self._retangulos()))
                if assinatura != self._assinatura:
                    self._redesenhar()
            self._vigia = self.janela.after(INTERVALO_MS, self._vigiar)
        except tk.TclError:
            # a janela fechou com o tutorial aberto: não conta como visto
            self.ativo = False

    def _redesenhar(self):
        if not self.ativo:
            return
        rx, ry, largura, altura = self._cliente()
        retangulos = self._retangulos()
        self._assinatura = ((rx, ry, largura, altura), tuple(retangulos))

        if retangulos:
            fx0 = min(r[0] for r in retangulos)
            fy0 = min(r[1] for r in retangulos)
            fx1 = max(r[2] for r in retangulos)
            fy1 = max(r[3] for r in retangulos)
            pedacos = [(rx, ry, rx + largura, fy0),
                       (rx, fy1, rx + largura, ry + altura),
                       (rx, fy0, fx0, fy1),
                       (fx1, fy0, rx + largura, fy1)]
            furo = (fx0, fy0, fx1, fy1)
        else:                     # passo sem alvo: escurece a janela inteira
            pedacos = [(rx, ry, rx + largura, ry + altura), None, None, None]
            furo = None

        for faixa, pedaco in zip(self._faixas, pedacos):
            if pedaco and pedaco[2] > pedaco[0] and pedaco[3] > pedaco[1]:
                faixa.geometry(f"{pedaco[2] - pedaco[0]}x{pedaco[3] - pedaco[1]}"
                               f"+{pedaco[0]}+{pedaco[1]}")
                faixa.deiconify()
            else:
                faixa.withdraw()

        tela = self._tela_contornos
        tela.delete("all")
        if furo:
            # um contorno só, em volta do furo: com vários alvos (rótulo +
            # campo), um contorno por widget virava uma pilha de caixas
            espessura = ui_tema.px(self.janela, 3)
            self._contornos.geometry(f"{largura}x{altura}+{rx}+{ry}")
            meio = espessura // 2 + 1
            x0, y0, x1, y1 = furo
            tela.create_rectangle(x0 - rx + meio, y0 - ry + meio,
                                  x1 - rx - meio, y1 - ry - meio,
                                  outline=ui_tema.CORES["destaque"],
                                  width=espessura)
            self._contornos.deiconify()
        else:
            self._contornos.withdraw()

        for faixa in self._faixas:
            faixa.lift()
        self._contornos.lift()
        self._posicionar_cartao(furo)

    def _posicionar_cartao(self, furo):
        cartao = self._cartao
        cartao.update_idletasks()
        cw, ch = cartao.winfo_reqwidth(), cartao.winfo_reqheight()
        rx, ry, largura, altura = self._cliente()
        vao = ui_tema.px(self.janela, 10)

        def encaixar(x, y, limites):
            """Posição (x, y) empurrada para dentro dos limites, ou None se
            o cartão não cabe neles de jeito nenhum."""
            lx0, ly0, lx1, ly1 = limites
            if cw > lx1 - lx0 or ch > ly1 - ly0:
                return None
            return (max(lx0, min(x, lx1 - cw)), max(ly0, min(y, ly1 - ch)))

        janela = (rx, ry, rx + largura, ry + altura)
        tela = (0, 0, self.janela.winfo_screenwidth(),
                self.janela.winfo_screenheight())
        posicao = None
        if furo:
            fx0, fy0, fx1, fy1 = furo
            opcoes = (
                (fx0, fy1 + vao, lambda y: y >= fy1 + vao),          # embaixo
                (fx0, fy0 - vao - ch, lambda y: y + ch <= fy0 - vao),  # em cima
            )
            # primeiro dentro da janela; se não couber (janela pequena, como
            # a do seletor), o cartão pode passar da borda dela
            for limites in (janela, tela):
                for x, y, sem_cobrir in opcoes:
                    lugar = encaixar(x, y, limites)
                    if lugar and sem_cobrir(lugar[1]):
                        posicao = lugar
                        break
                if posicao:
                    break
            if posicao is None:                      # sem espaço: no rodapé
                posicao = encaixar(rx + (largura - cw) // 2,
                                   ry + altura - ch - vao, tela)
        else:
            posicao = encaixar(rx + (largura - cw) // 2,
                               ry + (altura - ch) // 2, tela)
        x, y = posicao or (rx, ry)
        cartao.geometry(f"+{x}+{y}")
        cartao.deiconify()
        cartao.lift()
