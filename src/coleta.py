# bot/coleta.py
import json
import os
import re

import config
from marcas import cita_modelo, palavra_do_modelo
from paths import get_visitados_path


# Cards montados agora na página, com a posição ABSOLUTA (a janela rola:
# conferido ao vivo, window.scrollY acompanha a lista) e o texto do card,
# que alimenta as peneiras de "só veículos" e do modelo.
_JS_CARDS = r"""
(seletor) => {
  const itens = [];
  for (const a of document.querySelectorAll(seletor)) {
    const href = a.getAttribute('href');
    if (!href) continue;
    const r = a.getBoundingClientRect();
    if (r.width < 20 || r.height < 20) continue;
    itens.push({url: href.startsWith('/') ? 'https://www.facebook.com' + href : href,
                texto: (a.innerText || '').replace(/\s+/g, ' ').trim(),
                topo: r.top + window.scrollY, esq: r.left + window.scrollX});
  }
  return itens;
}
"""
_JS_PASSO = "() => Math.max(300, Math.round(window.innerHeight * 0.8))"


def sem_query(url):
    """O anúncio sem os parâmetros: o Facebook põe um código de rastreio
    ALEATÓRIO em cada link (`tracking=browse_serp:<uuid>`), então o mesmo
    anúncio vinha com URL diferente a cada busca."""
    return str(url or "").split("#")[0].split("?")[0].rstrip("/")


def _cards_rolando(pagina, chega=None):
    """Todos os cards da busca, na ordem da TELA, do topo ao fim.

    O Marketplace DESCARTA do DOM os cards que saem da tela (conferido ao
    vivo, set/2026: depois de rolar até o fim, 0 dos 6 primeiros ainda
    existiam) — coletar só no fim fazia a lista começar no meio e o bot
    mandava mensagem para um anúncio do meio. Por isso a coleta começa no
    topo e anota cada card ENQUANTO rola, em passos menores que a tela
    (um salto grande pula linhas que nunca chegam a ser montadas).
    Para assim que `chega(itens_na_ordem)` disser que já basta — a lista
    inteira pode ter centenas de anúncios e levar minutos para rolar.
    """
    pagina.evaluate("window.scrollTo(0, 0)")
    pagina.wait_for_timeout(1500)
    vistos = {}
    parado = 0
    # passos de ~0,8 tela: o teto de rolagens é maior que o do salto antigo
    for _ in range(config.MAX_SCROLLS * 4):
        antes = len(vistos)
        for item in pagina.evaluate(_JS_CARDS, config.SEL_CARD_POST):
            vistos.setdefault(item["url"], item)
        parado = parado + 1 if len(vistos) == antes else 0
        if parado >= 3:
            break          # três passos sem card novo: fim da lista
        if chega and chega(_na_ordem(vistos)):
            break
        pagina.mouse.wheel(0, pagina.evaluate(_JS_PASSO))
        pagina.wait_for_timeout(int(config.PAUSA_SCROLL * 1000))
    return _na_ordem(vistos)


def _na_ordem(vistos):
    return sorted(vistos.values(), key=lambda i: (round(i["topo"] / 40), i["esq"]))

# --------------------------------------------------------- só veículos
# O Facebook NÃO oferece busca por termo dentro da categoria Veículos:
# verificado ao vivo (set/2026), `category_id` junto com `query` é
# ignorado, e a página /vehicles ignora o `query`. Então a restrição é
# feita aqui, pelo card.
#
# Anúncio criado pelo formulário de veículo sai sempre como
# "<preço> <ano> <marca> <modelo>" ("R$5.000 2016 Hyundai HB20"); imóvel
# sai "2 quartos 1 banheiro · Casa", peça sai "Retrovisor elétrico…".
# Carro anunciado como item comum ("REPASSE - VOYAGE 1.6 2015") não segue
# o formato, mas tem o ano no texto — por isso a segunda regra.
_CARD_VEICULO = re.compile(
    r"^(?:Acabou de ser anunciado\s*)?"
    r"(?:(?:R\$\s?[\d.,]+|Gratuito)\s*){1,2}"
    r"(?:19|20)\d{2}\s+\S",
    re.IGNORECASE)
_ANO = re.compile(r"\b(?:19|20)\d{2}\b")
_NAO_VEICULO = re.compile(
    r"\b(?:quartos?|banheiros?|apartamento|apto|casa|terreno|kitnet|sobrado|"
    r"duplex|cobertura|aluguel|im[oó]vel|"
    r"pe[cç]as?|sucata|desmanche|retrovisor|radiador|farol|lanterna|"
    r"para-?choque|pneus?)\b",
    re.IGNORECASE)


def eh_card_de_veiculo(texto):
    """True quando o card é de um veículo à venda.

    Fica: o card no formato de veículo, e o card com ano no texto que não
    fala em imóvel nem em peça. Sai: imóvel, peça/sucata e oferta de
    serviço ("financiamento facilitado", sem ano). Card sem texto lido
    passa — não conseguir ler não é motivo para descartar.
    """
    texto = (texto or "").strip()
    if not texto:
        return True
    if _CARD_VEICULO.search(texto):
        return True
    return bool(_ANO.search(texto)) and not _NAO_VEICULO.search(texto)


def _itens_na_ordem_do_dom(pagina):
    """Reserva: mesma coleta de antes, na ordem do DOM, com o texto."""
    cards = pagina.locator(config.SEL_CARD_POST)
    itens = []
    vistos = set()
    for i in range(cards.count()):
        card = cards.nth(i)
        href = card.get_attribute("href")
        if not href:
            continue
        # Converte links relativos em absolutos
        if href.startswith("/"):
            href = "https://www.facebook.com" + href
        if href in vistos:
            continue
        vistos.add(href)
        try:
            texto = " ".join((card.inner_text() or "").split())
        except Exception:
            texto = ""
        itens.append({"url": href, "texto": texto})
    return itens


def coletar_links(pagina, so_veiculos=True, produto=None, bastam=None,
                  pular=()):
    """Links únicos dos anúncios, na ordem em que aparecem NA TELA,
    rolando do topo ao fim da lista.

    Com `so_veiculos` (o padrão), só entra o que é veículo à venda: a
    busca do Marketplace não tem filtro de categoria por termo, e um termo
    genérico ("repasse", "assumir financiamento") traz casa, apartamento e
    peça junto. Com `produto`, só entra card que fala no modelo ("gol"
    não deixa passar a BMW perdida no meio dos Gols) — e o card do modelo
    sem ano no texto passa a contar como veículo. Com `bastam`, a rolagem
    para quando há essa quantidade de anúncios aprovados fora de `pular`
    (os já contatados).
    """
    def peneirar(itens):
        links, fora_veiculo, fora_modelo = [], 0, 0
        for item in itens:
            texto = item["texto"]
            if not so_veiculos:
                links.append(item["url"])
            elif produto and texto and not cita_modelo(texto, produto):
                fora_modelo += 1
            elif eh_card_de_veiculo(texto) or (
                    produto and not _NAO_VEICULO.search(texto)):
                links.append(item["url"])
            else:
                fora_veiculo += 1
        return links, fora_veiculo, fora_modelo

    def chega(itens):
        return bool(bastam) and sum(
            1 for url in peneirar(itens)[0] if sem_query(url) not in pular
        ) >= bastam

    print("Garantindo início da lista...")
    itens = None
    try:
        itens = _cards_rolando(pagina, chega)
    except Exception as exc:
        print(f"  ! não deu para ordenar por posição ({exc}); usando a ordem do DOM")
    if not itens:
        itens = _itens_na_ordem_do_dom(pagina)

    links, fora_veiculo, fora_modelo = peneirar(itens)
    if fora_veiculo:
        print(f"  {fora_veiculo} anúncio(s) que não são veículo ficaram de fora "
              "(imóvel, peça ou serviço)")
    if fora_modelo:
        print(f"  {fora_modelo} anúncio(s) de outro modelo (sem "
              f"'{palavra_do_modelo(produto)}' no título) ficaram de fora")
    return links


def titulo_do_anuncio(pagina):
    """Título do anúncio aberto (o único h1 da página do item, conferido ao
    vivo); vazio se não der para ler."""
    try:
        return " ".join((pagina.locator("h1").first.inner_text(timeout=4000)
                         or "").split())
    except Exception:
        return ""

def carregar_visitados():
    """Carrega os anúncios já processados."""

    if not os.path.exists(get_visitados_path()):
        return []

    try:
        with open(get_visitados_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def salvar_visitados(visitados):
    """Salva o histórico de anúncios."""

    with open(get_visitados_path(), "w", encoding="utf-8") as f:
        json.dump(
            visitados,
            f,
            ensure_ascii=False,
            indent=4
        )


def calcular_alvo(total, quantidade):
    if quantidade is None:
        return total

    alvo = min(quantidade, total)

    if config.LIMITE_ENVIOS is None:
        return alvo

    return min(alvo, config.LIMITE_ENVIOS)
