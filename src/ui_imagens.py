# src/ui_imagens.py
"""
Imagens do visual, geradas em código: cantos arredondados suaves, borda,
anel de foco, sombra, gradiente, caixa de marcação e interruptor.

O Tk não desenha retângulo arredondado com antisserrilhado nem sombra.
Aqui cada forma é calculada por distância com sinal (SDF) e vira um PNG
com transparência — sem Pillow e sem arquivos em assets/.

Onde a transparência funciona (conferido no Tk 8.6 do Windows):
- `tk.Label` e `tk.Canvas` misturam o alpha do PNG com o fundo real;
- elemento de imagem `ttk` mistura com o cinza do sistema (#f0f0f0), então
  imagem para ttk precisa de `fundo=` (cor opaca de quem está atrás).

Linhas do meio da imagem são iguais entre si: são calculadas uma vez e
repetidas, o que mantém o custo baixo mesmo para cartões grandes.
"""
import base64
import math
import struct
import zlib
import tkinter as tk


def cor(hexa):
    """'#7c3aed' -> (0.49, 0.23, 0.93)."""
    return tuple(int(hexa[i:i + 2], 16) / 255 for i in (1, 3, 5))


def misturar(a, b, t):
    """Cor entre `a` e `b` (hexa) na fração `t`."""
    ca, cb = cor(a), cor(b)
    return "#%02x%02x%02x" % tuple(round((x + (y - x) * t) * 255)
                                   for x, y in zip(ca, cb))


def _png(largura, altura, linhas):
    def bloco(tipo, dados):
        return (struct.pack(">I", len(dados)) + tipo + dados
                + struct.pack(">I", zlib.crc32(tipo + dados) & 0xFFFFFFFF))
    bruto = b"".join(b"\x00" + bytes(linha) for linha in linhas)
    return (b"\x89PNG\r\n\x1a\n"
            + bloco(b"IHDR", struct.pack(">IIBBBBB", largura, altura, 8, 6, 0, 0, 0))
            + bloco(b"IDAT", zlib.compress(bruto, 1))
            + bloco(b"IEND", b""))


def foto(janela, largura, altura, linhas):
    """PhotoImage a partir de linhas RGBA (bytes)."""
    dados = base64.b64encode(_png(largura, altura, linhas))
    return tk.PhotoImage(master=janela, data=dados, format="png")


def _sdf_ret(x, y, x0, y0, x1, y1, raio):
    """Distância com sinal até o retângulo arredondado (negativo = dentro)."""
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    meia_l, meia_a = (x1 - x0) / 2, (y1 - y0) / 2
    raio = max(0.0, min(raio, meia_l, meia_a))
    qx = abs(x - cx) - (meia_l - raio)
    qy = abs(y - cy) - (meia_a - raio)
    fora = math.hypot(max(qx, 0.0), max(qy, 0.0))
    return fora + min(max(qx, qy), 0.0) - raio


def _cobre(d):
    return 0.0 if d >= 0.5 else 1.0 if d <= -0.5 else 0.5 - d


def _sobre(pixel, c, a):
    """Compõe a cor `c` com alpha `a` sobre `pixel` (pré-multiplicado)."""
    if a <= 0:
        return pixel
    r, g, b, pa = pixel
    return (c[0] * a + r * (1 - a), c[1] * a + g * (1 - a),
            c[2] * a + b * (1 - a), a + pa * (1 - a))


def _para_bytes(pixel):
    r, g, b, a = pixel
    if a <= 0:
        return b"\x00\x00\x00\x00"
    return bytes((min(255, round(r / a * 255)), min(255, round(g / a * 255)),
                  min(255, round(b / a * 255)), min(255, round(a * 255))))


def retangulo(janela, largura, altura, raio, preenchimento, borda=None,
              espessura=1.0, fundo=None, sombra=0, forca_sombra=0.10,
              anel=None, espessura_anel=0, gradiente=None, borda_baixo=None,
              espessura_baixo=None):
    """Retângulo arredondado. A forma ocupa a imagem menos as margens da
    sombra e do anel de foco (que ficam por fora, sem mexer no layout).

    gradiente: (cor_esquerda, cor_direita) no lugar do preenchimento.
    borda_baixo: linha de baixo em outra cor (a "base" dos campos).
    """
    m = max(espessura_anel, sombra)
    x0, y0 = m, m - (sombra // 3 if sombra else 0)
    x1, y1 = largura - m, altura - m - (sombra // 3 if sombra else 0)
    base = cor(fundo) + (1.0,) if fundo else (0.0, 0.0, 0.0, 0.0)
    c_fill, c_borda = cor(preenchimento), cor(borda) if borda else None
    c_anel = cor(anel) if anel else None
    c_baixo = cor(borda_baixo) if borda_baixo else None
    e_baixo = espessura_baixo if espessura_baixo is not None else espessura
    grad = None
    if gradiente:
        ce, cd = cor(gradiente[0]), cor(gradiente[1])
        grad = [tuple(e + (d - e) * (x / max(1, largura - 1))
                      for e, d in zip(ce, cd)) for x in range(largura)]

    def pixel(x, y):
        px_, py_ = x + 0.5, y + 0.5
        p = base
        if sombra:
            d = _sdf_ret(px_, py_ - sombra / 2, x0, y0, x1, y1, raio)
            if d > -1:
                t = max(0.0, 1 - max(d, 0.0) / sombra)
                p = _sobre(p, (0.06, 0.09, 0.16), forca_sombra * t * t)
        if c_anel:
            p = _sobre(p, c_anel, _cobre(_sdf_ret(px_, py_, x0 - espessura_anel,
                                                  y0 - espessura_anel,
                                                  x1 + espessura_anel,
                                                  y1 + espessura_anel,
                                                  raio + espessura_anel)))
        fora = _cobre(_sdf_ret(px_, py_, x0, y0, x1, y1, raio))
        if fora <= 0:
            return p
        preenche = grad[x] if grad else c_fill
        if c_borda or c_baixo:
            e_cima = espessura if c_borda else 0
            e_bx = e_baixo if c_baixo else e_cima
            dentro = _cobre(_sdf_ret(px_, py_, x0 + e_cima, y0 + e_cima,
                                     x1 - e_cima, y1 - e_bx,
                                     max(0.0, raio - e_cima)))
            anel_borda = c_baixo if (c_baixo and py_ > y1 - e_bx - 0.5) else (
                c_borda or preenche)
            p = _sobre(p, anel_borda, fora)
            p = _sobre(p, preenche, dentro)
        else:
            p = _sobre(p, preenche, fora)
        return p

    zona = int(math.ceil(raio + m + sombra + e_baixo + 2))
    lado = min(largura // 2 + 1, zona)

    def linha(y):
        if largura <= 2 * lado:
            return b"".join(_para_bytes(pixel(x, y)) for x in range(largura))
        esquerda = b"".join(_para_bytes(pixel(x, y)) for x in range(lado))
        if grad:
            # gradiente em blocos de 6 px: a diferença entre blocos vizinhos
            # fica abaixo de 1 tom e o cartão grande sai ~20x mais rápido
            partes, x = [], lado
            while x < largura - lado:
                bloco = min(6, largura - lado - x)
                partes.append(_para_bytes(pixel(x + bloco // 2, y)) * bloco)
                x += bloco
            meio = b"".join(partes)
        else:
            meio = _para_bytes(pixel(largura // 2, y)) * (largura - 2 * lado)
        direita = b"".join(_para_bytes(pixel(x, y))
                           for x in range(largura - lado, largura))
        return esquerda + meio + direita

    linhas = []
    meio_calculado = None
    for y in range(altura):
        if zona <= y < altura - zona:
            if meio_calculado is None:
                meio_calculado = linha(altura // 2)
            linhas.append(meio_calculado)
        else:
            linhas.append(linha(y))
    return foto(janela, largura, altura, linhas)


def _sdf_segmento(px_, py_, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px_ - ax) * vx + (py_ - ay) * vy) / (vx * vx + vy * vy)))
    return math.hypot(px_ - (ax + t * vx), py_ - (ay + t * vy))


def marcacao(janela, lado, estado, destaque, borda, fundo=None, escala=1.0):
    """Caixa de marcação: estado 'vazio', 'marcado', 'parcial' ou 'inativo'."""
    raio = 4 * escala
    if estado in ("marcado", "parcial"):
        img_fill, img_borda = destaque, None
    elif estado == "inativo":
        img_fill, img_borda = "#f1f5f9", "#cbd5e1"
    else:
        img_fill, img_borda = "#ffffff", borda
    base = cor(fundo) + (1.0,) if fundo else (0.0, 0.0, 0.0, 0.0)
    c_fill = cor(img_fill)
    c_borda = cor(img_borda) if img_borda else None
    branco = (1.0, 1.0, 1.0)
    grossura = 1.6 * escala
    linhas = []
    for y in range(lado):
        partes = []
        for x in range(lado):
            px_, py_ = x + 0.5, y + 0.5
            p = base
            fora = _cobre(_sdf_ret(px_, py_, 0.5, 0.5, lado - 0.5, lado - 0.5, raio))
            if c_borda:
                p = _sobre(p, c_borda, fora)
                p = _sobre(p, c_fill, _cobre(_sdf_ret(px_, py_, 1.5 * escala,
                                                      1.5 * escala,
                                                      lado - 1.5 * escala,
                                                      lado - 1.5 * escala,
                                                      raio - escala)))
            else:
                p = _sobre(p, c_fill, fora)
            if estado == "marcado":
                d = min(_sdf_segmento(px_, py_, lado * .27, lado * .52,
                                      lado * .43, lado * .68),
                        _sdf_segmento(px_, py_, lado * .43, lado * .68,
                                      lado * .74, lado * .34))
                p = _sobre(p, branco, _cobre(d - grossura / 2) * fora)
            elif estado == "parcial":
                d = _sdf_segmento(px_, py_, lado * .3, lado / 2, lado * .7, lado / 2)
                p = _sobre(p, branco, _cobre(d - grossura / 2) * fora)
            partes.append(_para_bytes(p))
        linhas.append(b"".join(partes))
    return foto(janela, lado, lado, linhas)


def interruptor(janela, largura, altura, ligado, cor_ligado, cor_desligado,
                inativo=False, posicao=None):
    """Interruptor (toggle) com trilho em pílula e botão branco.

    `posicao` (0 a 1) põe o botão no meio do caminho e mistura a cor do
    trilho — é o quadro intermediário da animação de ligar/desligar.
    """
    if posicao is None:
        posicao = 1.0 if ligado else 0.0
    trilho = cor(misturar(cor_desligado, cor_ligado, posicao))
    if inativo:
        trilho = tuple(c + (1 - c) * 0.55 for c in trilho)
    raio = altura / 2
    folga = max(2.0, altura * 0.14)
    r_botao = raio - folga
    cx = raio + (largura - 2 * raio) * posicao
    cy = altura / 2
    linhas = []
    for y in range(altura):
        partes = []
        for x in range(largura):
            px_, py_ = x + 0.5, y + 0.5
            p = _sobre((0.0, 0.0, 0.0, 0.0), trilho,
                       _cobre(_sdf_ret(px_, py_, 0, 0, largura, altura, raio)))
            d_sombra = math.hypot(px_ - cx, py_ - cy - 0.8) - r_botao
            p = _sobre(p, (0.06, 0.09, 0.16),
                       0.18 * max(0.0, 1 - max(d_sombra, 0) / 1.6))
            d = math.hypot(px_ - cx, py_ - cy) - r_botao
            p = _sobre(p, (1.0, 1.0, 1.0), _cobre(d))
            partes.append(_para_bytes(p))
        linhas.append(b"".join(partes))
    return foto(janela, largura, altura, linhas)
