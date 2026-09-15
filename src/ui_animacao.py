# src/ui_animacao.py
"""
Transições curtas do visual (100–240 ms).

O Tk não anima nada sozinho: aqui um relógio (`after` a ~60 quadros por
segundo) chama `passo(p)` com o progresso já suavizado, de 0 a 1, e a
tela se redesenha a cada quadro. O progresso vem do tempo decorrido, não
da contagem de quadros — numa máquina lenta a animação pula quadros, mas
dura o mesmo e sempre termina no estado final. Travada longa (acima de
50 ms, ex.: a página montando na primeira visita) PAUSA o relógio: sem
isso a animação terminava durante a trava e ninguém a via.

Regras de uso:
- cada animação tem uma `chave` por widget; começar outra com a mesma
  chave cancela a anterior e parte de onde ela estava (o hover que entra
  e sai rápido não "pisca");
- imagens intermediárias usam `degrau()` para cair sempre nos mesmos
  poucos valores e aproveitar o cache (gerar PNG por quadro seria caro);
- `MBOT_SEM_ANIMACAO=1` no ambiente desliga tudo (cada animação vai
  direto ao estado final).
"""
import os
import time
import tkinter as tk

import ui_imagens

ATIVO = os.environ.get("MBOT_SEM_ANIMACAO", "") != "1"
QUADRO_MS = 16
DURACAO = {"rapida": 120, "media": 180, "lenta": 240}

_ativas = {}


def suave(t):
    """Desacelera no fim (ease-out cúbico): começa rápido, pousa macio."""
    return 1 - (1 - t) ** 3


def suave_ida_volta(t):
    """Acelera e desacelera (ease-in-out)."""
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def degrau(p, passos=6):
    """Arredonda o progresso para um de `passos` valores (cache de imagem)."""
    return round(max(0.0, min(1.0, p)) * passos) / passos


def cor(a, b, p):
    """Cor intermediária entre dois hexadecimais."""
    if p <= 0:
        return a
    if p >= 1:
        return b
    return ui_imagens.misturar(a, b, p)


def cancelar(widget, chave):
    item = _ativas.pop((str(widget), chave), None)
    if item is not None:
        try:
            widget.after_cancel(item)
        except (tk.TclError, ValueError):
            pass


def animando(widget, chave):
    return (str(widget), chave) in _ativas


def animar(widget, chave, passo, duracao="media", fim=None, curva=suave):
    """Chama `passo(p)` de p=0 a p=1 ao longo de `duracao` (ms ou nome)."""
    cancelar(widget, chave)
    ms = DURACAO.get(duracao, duracao) if isinstance(duracao, str) else duracao
    identificador = (str(widget), chave)
    if not ATIVO or ms <= 0:
        passo(1.0)
        if fim:
            fim()
        return
    relogio = {"inicio": None, "ultimo": None}

    def agendar():
        # cada quadro espera o intervalo E a fila de redesenho esvaziar
        # (after_idle): numa cascata de eventos o Tk dispara os timers mas
        # só pinta a tela no ocioso, e a animação terminava sem ser vista
        def depois_do_intervalo():
            _ativas[identificador] = widget.after_idle(quadro)
        _ativas[identificador] = widget.after(QUADRO_MS, depois_do_intervalo)

    def quadro():
        _ativas.pop(identificador, None)
        agora = time.perf_counter()
        if relogio["inicio"] is None:          # relógio parte no 1º quadro pintado
            relogio["inicio"] = relogio["ultimo"] = agora
        # travada longa entre quadros (rolagem, seção aparecendo): o relógio
        # espera, senão a animação "acaba" escondida atrás da trava
        atraso = agora - relogio["ultimo"] - 2 * QUADRO_MS / 1000
        if atraso > 0.05:
            relogio["inicio"] += atraso
        relogio["ultimo"] = agora
        try:
            if not widget.winfo_exists():
                return
            t = min(1.0, (agora - relogio["inicio"]) * 1000 / ms)
            passo(curva(t))
        except tk.TclError:
            return            # widget destruído no meio da animação
        if t < 1.0:
            agendar()
        elif fim:
            fim()

    try:
        passo(curva(0.0))      # estado inicial já, sem esperar o 1º quadro
    except tk.TclError:
        return
    _ativas[identificador] = widget.after_idle(quadro)


class Transicao:
    """Valor de 0 a 1 que anda até o alvo com animação, partindo de onde
    está — base do hover e da seleção dos cartões.

    `ao_mudar(valor)` é chamado a cada quadro.
    """

    def __init__(self, widget, chave, ao_mudar, valor=0.0, duracao="rapida"):
        self.widget, self.chave = widget, chave
        self.ao_mudar, self.duracao = ao_mudar, duracao
        self.valor = float(valor)
        self.alvo = float(valor)

    def ir(self, alvo, duracao=None):
        alvo = float(alvo)
        if alvo == self.alvo and not animando(self.widget, self.chave):
            if self.valor != alvo:
                self.valor = alvo
                self.ao_mudar(alvo)
            return
        self.alvo = alvo
        origem = self.valor
        distancia = abs(alvo - origem)
        base = duracao or self.duracao
        ms = DURACAO.get(base, base) if isinstance(base, str) else base
        # meia volta dura meio tempo: o hover que sai no meio não se arrasta
        ms = max(40, int(ms * max(distancia, 0.25)))

        def passo(p):
            self.valor = origem + (alvo - origem) * p
            self.ao_mudar(self.valor)

        animar(self.widget, self.chave, passo, ms)

    def fixar(self, valor):
        """Muda sem animar (estado inicial ou redesenho)."""
        cancelar(self.widget, self.chave)
        self.valor = self.alvo = float(valor)
