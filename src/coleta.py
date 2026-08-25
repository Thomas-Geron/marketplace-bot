# bot/coleta.py
import json
import os
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
_JS_LINKS_ORDENADOS = """
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
    itens.push({url, topo: r.top + window.scrollY, esq: r.left + window.scrollX});
  }
  itens.sort((a, b) => (Math.round(a.topo / 40) - Math.round(b.topo / 40))
                       || (a.esq - b.esq));
  return itens.map(i => i.url);
}
"""


def coletar_links(pagina):
    """Links únicos dos anúncios, na ordem em que aparecem NA TELA."""
    try:
        links = pagina.evaluate(_JS_LINKS_ORDENADOS, config.SEL_CARD_POST)
        if links:
            return links
    except Exception as exc:
        print(f"  ! não deu para ordenar por posição ({exc}); usando a ordem do DOM")

    # reserva: mesma coleta de antes, na ordem do DOM
    cards = pagina.locator(config.SEL_CARD_POST)

    links = []
    vistos = set()

    for i in range(cards.count()):
        href = cards.nth(i).get_attribute("href")

        if not href:
            continue

        # Converte links relativos em absolutos
        if href.startswith("/"):
            href = "https://www.facebook.com" + href

        if href in vistos:
            continue

        vistos.add(href)
        links.append(href)

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