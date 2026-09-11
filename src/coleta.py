# bot/coleta.py
import json
import os
import re

import config
from paths import get_visitados_path


def carregar_todos(pagina):
    """Rola a página até os posts pararem de aparecer. Retorna o total."""
    total_anterior = -1
    for _ in range(config.MAX_SCROLLS):
        total = pagina.locator(config.SEL_CARD_POST).count()
        if total == total_anterior:
            break  # não apareceu nada novo -> chegou no fim da lista
        total_anterior = total
        pagina.mouse.wheel(0, 4000)
        pagina.wait_for_timeout(int(config.PAUSA_SCROLL * 1000))
    return pagina.locator(config.SEL_CARD_POST).count()

# ordena pela POSIÇÃO NA TELA (linha, depois coluna), não pela ordem do DOM:
# o Marketplace injeta cards conforme rola e reposiciona a grade, então a
# ordem do DOM não é a que você vê — o bot abria "o primeiro" que havia
# carregado, e não o primeiro da lista já montada.
# O texto do card vem junto para a peneira de "só veículos".
_JS_LINKS_ORDENADOS = r"""
(seletor) => {
  const vistos = new Set();
  const itens = [];
  for (const a of document.querySelectorAll(seletor)) {
    const href = a.getAttribute('href');
    if (!href) continue;
    const url = href.startsWith('/') ? 'https://www.facebook.com' + href : href;
    if (vistos.has(url)) continue;
    vistos.add(url);
    const r = a.getBoundingClientRect();
    const texto = (a.innerText || '').replace(/\s+/g, ' ').trim();
    itens.push({url, texto, topo: r.top + window.scrollY, esq: r.left + window.scrollX});
  }
  itens.sort((a, b) => (Math.round(a.topo / 40) - Math.round(b.topo / 40))
                       || (a.esq - b.esq));
  return itens.map(i => ({url: i.url, texto: i.texto}));
}
"""

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


def coletar_links(pagina, so_veiculos=True):
    """Links únicos dos anúncios, na ordem em que aparecem NA TELA.

    Com `so_veiculos` (o padrão), só entra o que é veículo à venda: a
    busca do Marketplace não tem filtro de categoria por termo, e um termo
    genérico ("repasse", "assumir financiamento") traz casa, apartamento e
    peça junto.
    """
    itens = None
    try:
        itens = pagina.evaluate(_JS_LINKS_ORDENADOS, config.SEL_CARD_POST)
    except Exception as exc:
        print(f"  ! não deu para ordenar por posição ({exc}); usando a ordem do DOM")
    if not itens:
        itens = _itens_na_ordem_do_dom(pagina)

    if not so_veiculos:
        return [item["url"] for item in itens]

    links = [item["url"] for item in itens if eh_card_de_veiculo(item["texto"])]
    fora = len(itens) - len(links)
    if fora:
        print(f"  {fora} anúncio(s) que não são veículo ficaram de fora "
              "(imóvel, peça ou serviço)")
    return links

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
